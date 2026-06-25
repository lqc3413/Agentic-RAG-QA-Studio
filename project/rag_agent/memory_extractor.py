import json
import logging
from langchain_core.messages import SystemMessage, HumanMessage
from db.agent_memory_manager import AgentMemoryManager
from db.user_manager import UserManager
from core.rag_system import create_llm

logger = logging.getLogger(__name__)

# ── 一步到位的记忆提取 + 画像更新 Prompt ───────────────────
UNIFIED_EXTRACTION_PROMPT = """\
你是智能体的记忆与画像管理助手。

你的任务是分析本轮用户问答，同时完成两件事：
1. **用户画像更新**：识别用户明确表达的长期偏好、协作规则或工作风格，生成需要更新的画像键值对。
2. **长期事实提取**：识别对未来交互有价值的项目事实、关键决策或遗留待办，生成新的事实记忆。

同时，你需要审查已有的事实记忆列表，如果新提取的事实与某条已有事实产生逻辑冲突或已被取代，请将其 ID 加入删除列表。

## 画像更新规则
- 只提取用户**明确、反复、长期**的偏好或协作规则。
- 例如："以后都用中文回答" → `{"preferred_language": "zh"}`
- 例如："回答请尽量用表格" → `{"response_style": "table"}`
- 例如："每次代码修改前必须先写测试" → `{"custom_rules": ["每次代码修改前必须先写测试"]}`
- 对于 custom_rules 类型，你应该只输出需要**新增**的规则文本，系统会自动追加。
- 临时性的单次指令（如"这次简短一点"）不要写入画像。

## 事实提取规则
- 只提取对未来多次交互有持续参考价值的客观事实、技术决策、遗留任务。
- 不要提取：闲聊、情绪表达、单次临时操作指令、具体报错日志。
- importance（0.0~1.0）：对未来交互的指导意义。

## 冲突判定规则
- 如果新事实与已有事实在逻辑上矛盾或完全取代（例如：旧事实说"用 gpt-4o"，新事实说"改用 deepseek"），
  将旧事实的 ID 加入 conflicting_fact_ids。
- 如果只是补充或细化，不算冲突。

请严格输出以下 JSON 格式（不要包裹 ```json 标记）：
{
  "profile_updates": {},
  "new_facts": [
    {"content": "事实内容", "importance": 0.8}
  ],
  "conflicting_fact_ids": []
}

如果没有任何需要更新的内容，输出：
{"profile_updates": {}, "new_facts": [], "conflicting_fact_ids": []}
"""


class MemoryExtractor:
    """简化版记忆提取器。

    将原先"提取候选 + 冲突对比"两步 LLM 调用，
    合并为单次 LLM 调用，同时完成画像更新、事实提取和冲突删除。
    """

    def __init__(
        self,
        memory_manager: AgentMemoryManager = None,
        user_manager: UserManager = None,
        llm=None,
    ):
        self.memory_manager = memory_manager or AgentMemoryManager()
        self.user_manager = user_manager or UserManager()
        self.llm = llm or create_llm()

    async def extract_and_update(
        self, question: str, answer: str, session_id: str, user_id: str = None
    ):
        """异步执行一步到位的记忆提取与画像更新。"""
        print(f"[MemoryExtractor] Starting unified extraction for session: {session_id}...", flush=True)

        # 1. 获取当前用户画像
        current_profile = {}
        if user_id:
            try:
                current_profile = self.user_manager.get_profile(int(user_id))
            except Exception as e:
                logger.error(f"Failed to load user profile: {e}")

        # 2. 获取该会话最近的长期事实记忆
        try:
            existing_facts = self.memory_manager.list_memories(
                user_id=user_id,
                session_id=session_id,
                limit=10,
            )
            facts_text = "\n".join(
                [f"- [ID:{m['id']}] {m['content']}" for m in existing_facts]
            ) or "None"
        except Exception as e:
            logger.error(f"Failed to fetch existing facts: {e}")
            facts_text = "None"

        # 3. 组装 LLM 输入
        profile_text = json.dumps(current_profile, ensure_ascii=False) if current_profile else "{}"
        user_content = (
            f"User Question: {question}\n\n"
            f"Final Answer: {answer}\n\n"
            f"Current User Profile: {profile_text}\n\n"
            f"Existing Fact Memories:\n{facts_text}"
        )

        # 4. 单次 LLM 调用
        try:
            print("[MemoryExtractor] Invoking LLM for unified extraction...", flush=True)
            response = await self.llm.ainvoke([
                SystemMessage(content=UNIFIED_EXTRACTION_PROMPT),
                HumanMessage(content=user_content),
            ])

            content = response.content.strip()
            print(f"[MemoryExtractor] LLM raw response: {content}", flush=True)

            # 清理 Markdown 包裹
            if content.startswith("```json"):
                content = content.replace("```json", "", 1)
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            data = json.loads(content)
        except Exception as e:
            print(f"[MemoryExtractor] LLM extraction failed: {e}", flush=True)
            logger.error(f"Unified memory extraction failed: {e}")
            return

        # 5. 执行画像更新（In-place merge）
        profile_updates = data.get("profile_updates", {})
        if profile_updates and user_id:
            try:
                # 对 custom_rules 做追加合并而非覆盖
                if "custom_rules" in profile_updates:
                    new_rules = profile_updates.pop("custom_rules", [])
                    if new_rules:
                        existing_rules = current_profile.get("custom_rules", [])
                        # 去重追加
                        for rule in new_rules:
                            if rule not in existing_rules:
                                existing_rules.append(rule)
                        profile_updates["custom_rules"] = existing_rules

                self.user_manager.update_profile(int(user_id), profile_updates)
                logger.info(f"User profile updated: {profile_updates}")
            except Exception as e:
                logger.error(f"Failed to update user profile: {e}")

        # 6. 执行冲突旧事实的物理删除
        conflict_ids = data.get("conflicting_fact_ids", [])
        if conflict_ids:
            try:
                deleted = self.memory_manager.delete_memories_batch(
                    [int(cid) for cid in conflict_ids],
                    user_id=user_id,
                )
                logger.info(f"Deleted {deleted} conflicting fact memories: {conflict_ids}")
            except Exception as e:
                logger.error(f"Failed to delete conflicting memories: {e}")

        # 7. 写入新事实记忆
        new_facts = data.get("new_facts", [])
        for fact in new_facts:
            fact_content = (fact.get("content") or "").strip()
            if not fact_content:
                continue

            # 简单去重：检查是否已存在完全相同内容的记忆
            try:
                with self.memory_manager._connect() as conn:
                    dup = conn.execute(
                        "SELECT id FROM agent_memories WHERE content = ? AND user_id IS ? LIMIT 1",
                        (fact_content, user_id),
                    ).fetchone()
                if dup:
                    logger.info(f"Skip duplicate fact: {fact_content}")
                    continue
            except Exception as e:
                logger.error(f"Failed to check duplicate: {e}")

            try:
                new_id = self.memory_manager.create_memory(
                    content=fact_content,
                    user_id=user_id,
                    session_id=session_id,
                    source="qa_interaction",
                    importance=float(fact.get("importance", 0.5)),
                )
                logger.info(f"Saved new fact memory id={new_id}: {fact_content}")
            except Exception as e:
                logger.error(f"Failed to save fact memory: {e}")
