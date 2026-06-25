import os
import sys
import json
import re
from pathlib import Path
from langchain_text_splitters import MarkdownHeaderTextSplitter

# 1. 设置 sys.path 确保能正确加载项目配置和模块
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "project"))

import config

def fix_no_proxy():
    no_proxy = os.environ.get("no_proxy")
    if no_proxy:
        os.environ["no_proxy"] = ",".join(
            item.strip()
            for item in no_proxy.split(",")
            if ":" not in item
        )

def get_real_source_mapping():
    """读取 document_metadata.db 建立真实 source 映射名。"""
    import sqlite3
    db_path = ROOT_DIR / "document_metadata.db"
    mapping = {}
    if not db_path.exists():
        return mapping
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT name, original_name FROM document_metadata")
        for row in cursor.fetchall():
            # e.g., mapping['590ce28a6eea4f71afac8567b025da19'] = 'Git'
            doc_id = Path(row["name"]).stem
            # 去除 .md 尾缀得到如 'MySQL'
            original_stem = Path(row["original_name"]).stem
            mapping[doc_id] = original_stem
        conn.close()
    except Exception as e:
        print(f"Warning: Failed to query document_metadata: {e}")
    return mapping


def main():
    fix_no_proxy()
    print("--- Starting Synthetic RAG Evaluation Case Generator ---")
    
    # 获取指定的密钥和模型
    api_key = os.environ.get("ali_api_key") or config.OPENAI_COMPATIBLE_API_KEY
    if not api_key:
        print("Error: No API key found. Please configure 'ali_api_key' environment variable.")
        sys.exit(1)
        
    model_name = "deepseek-v4-pro"
    base_url = config.OPENAI_COMPATIBLE_API_BASE_URL
    print(f"Using Model: {model_name}")
    print(f"Base URL: {base_url}")
    
    # 2. 初始化 LangChain LLM 实例
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import SystemMessage, HumanMessage
    
    llm = ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=base_url,
        temperature=0.3,
        model_kwargs={"response_format": {"type": "json_object"}} # 约束输出为 JSON
    )

    # 3. 读取 markdown_docs/public/ 下的所有技术文档
    docs_dir = ROOT_DIR / "markdown_docs" / "public"
    if not docs_dir.exists():
        print(f"Error: Public docs directory {docs_dir} not found.")
        sys.exit(1)

    md_files = list(docs_dir.glob("*.md"))
    if not md_files:
        print("No markdown files found in the target directory.")
        sys.exit(0)

    # 获取原始源文件名映射字典
    source_mapping = get_real_source_mapping()
    
    # 读取各文件内容，统计权重
    doc_contents = {}
    for path in md_files:
        with open(path, "r", encoding="utf-8") as f:
            doc_contents[path] = f.read()

    # 4. 根据文件内容长度按比例分配总计 20 个问题的指标
    total_len = sum(len(content) for content in doc_contents.values())
    target_total_questions = 20
    
    distribution = {}
    for path, content in doc_contents.items():
        weight = len(content) / total_len
        allocated = max(1, round(weight * target_total_questions))
        distribution[path] = allocated

    print("\nAllocated Question Count per Document:")
    for path, count in distribution.items():
        print(f"  {path.name} (Len: {len(doc_contents[path])}) -> Allocated: {count} questions")

    # 5. 切分文档并生成问题
    splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=config.HEADERS_TO_SPLIT_ON,
        strip_headers=False
    )
    
    synthetic_cases = []
    case_counter = 0

    for path, target_count in distribution.items():
        doc_id = path.stem
        # 得到出处映射名称，如 MySQL.md ➡️ MySQL
        mapped_source_name = source_mapping.get(doc_id, doc_id)
        if mapped_source_name.endswith(".md"):
            mapped_source_name = mapped_source_name[:-3]
            
        print(f"\nProcessing document: {path.name} (mapped as: {mapped_source_name})")
        parent_chunks = splitter.split_text(doc_contents[path])
        
        # 挑选长度足够（大于 150 字符）的段落进行提问抽取
        valid_chunks = [
            chunk for chunk in parent_chunks 
            if len(chunk.page_content.strip()) > 150
        ]
        if not valid_chunks:
            valid_chunks = parent_chunks # 降级

        # 弹性间隔选取段落，确保知识点覆盖均匀
        step = max(1, len(valid_chunks) // target_count)
        selected_chunks = []
        for i in range(target_count):
            idx = (i * step) % len(valid_chunks)
            selected_chunks.append(valid_chunks[idx])

        # 限制只保留唯一的段落，去重
        seen_contents = set()
        unique_selected_chunks = []
        for chunk in selected_chunks:
            text = chunk.page_content.strip()
            if text not in seen_contents:
                seen_contents.add(text)
                unique_selected_chunks.append(chunk)

        # 调配生成
        for idx_c, chunk in enumerate(unique_selected_chunks):
            chunk_content = chunk.page_content.strip()
            case_counter += 1
            case_id = f"synthetic_{mapped_source_name.lower()}_{case_counter}"
            
            print(f"  [{case_id}] Requesting LLM to generate case...")
            
            system_prompt = (
                "You are an expert technical QA case designer. You will read the provided document snippet "
                "and generate exactly one representative question that users might ask based on this context. "
                "You must also extract 3 to 4 specific, exact core technical terminology keywords or phrases from the text "
                "that are essential for a correct answer. These keywords will be used for auto-grading.\n\n"
                "You must return the result strictly in JSON format as follows:\n"
                "{\n"
                "  \"question\": \"The professional technical question...\",\n"
                "  \"expected_keywords\": [\"keyword1\", \"keyword2\", \"keyword3\"]\n"
                "}"
            )
            
            user_content = f"--- DOCUMENT CONTENT START ---\n{chunk_content}\n--- DOCUMENT CONTENT END ---"
            
            try:
                response = llm.invoke([
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_content)
                ])
                res_json = json.loads(response.content.strip())
                
                question = res_json.get("question")
                expected_keywords = res_json.get("expected_keywords") or []
                
                if not question:
                    raise ValueError("Generated question is empty.")
                    
                case_item = {
                    "id": case_id,
                    "question": question,
                    "expected_keywords": [str(kw) for kw in expected_keywords if kw],
                    "expected_sources": [mapped_source_name],
                    "expected_answerable": True
                }
                synthetic_cases.append(case_item)
                print(f"    - Generated Question: {question}")
                print(f"    - Expected Keywords: {expected_keywords}")
                
            except Exception as e:
                print(f"    - Failed to generate case for chunk {idx_c} in {path.name}: {e}")

    # 6. 保存生成的评测文件
    output_path = ROOT_DIR / "eval" / "eval_cases_synthetic.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(synthetic_cases, f, ensure_ascii=False, indent=2)

    print(f"\n[OK] Success! Generated {len(synthetic_cases)} synthetic evaluation cases.")
    print(f"Saved to: {output_path}")

if __name__ == "__main__":
    main()
