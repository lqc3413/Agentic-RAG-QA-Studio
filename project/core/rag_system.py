import uuid
import config
from collections import defaultdict
from db.vector_db_manager import VectorDbManager
from db.parent_store_manager import ParentStoreManager
from db.qa_record_manager import QARecordManager
from document_chunker import DocumentChuncker
from rag_agent.tools import ToolFactory
from rag_agent.graph import create_agent_graph
from core.observability import Observability


def create_llm():
    """创建 RAG 回答和 Agent 决策使用的 LLM。"""
    if config.LLM_PROVIDER == "openai_compatible":
        from langchain_openai import ChatOpenAI

        if not config.OPENAI_COMPATIBLE_API_KEY:
            raise ValueError("DATE_NOW_API_KEY or OPENAI_API_KEY is required for openai_compatible provider.")

        model_kwargs = {}
        if "qwen3.7" in config.LLM_MODEL or ("qwen" in config.LLM_MODEL.lower() and "max" in config.LLM_MODEL.lower()):
            model_kwargs["extra_body"] = {"enable_thinking": False}

        return ChatOpenAI(
            model=config.LLM_MODEL,
            temperature=config.LLM_TEMPERATURE,
            api_key=config.OPENAI_COMPATIBLE_API_KEY,
            base_url=config.OPENAI_COMPATIBLE_API_BASE_URL,
            **model_kwargs
        )

    if config.LLM_PROVIDER == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(model=config.OLLAMA_MODEL, temperature=config.LLM_TEMPERATURE)

    raise ValueError(f"Unsupported LLM_PROVIDER: {config.LLM_PROVIDER}")


class RAGSystem:
    """RAG 系统装配器，负责组装向量库、工具、LLM 和 LangGraph。"""

    def __init__(self, collection_name=config.CHILD_COLLECTION):
        """初始化 RAGSystem 依赖的基础组件。"""
        self.collection_name = collection_name
        self.vector_db = VectorDbManager()
        self.parent_store = ParentStoreManager()
        self.qa_record_manager = QARecordManager()
        self.chunker = DocumentChuncker()
        self.observability = Observability()
        self.agent_graph = None
        self.recursion_limit = config.GRAPH_RECURSION_LIMIT
        self.trace_buffers = defaultdict(list)
        self.checkpointer = None

    def _get_checkpointer(self):
        """根据配置动态加载 checkpointer，失败回退内存版。"""
        provider = getattr(config, "CHECKPOINT_PROVIDER", "memory")
        if provider == "sqlite":
            db_path = getattr(config, "CHECKPOINT_DB_PATH", "agent_checkpoints.db")
            try:
                import sqlite3
                from langgraph.checkpoint.sqlite import SqliteSaver
                conn = sqlite3.connect(db_path, check_same_thread=False)
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute("PRAGMA busy_timeout=5000;")
                return SqliteSaver(conn)
            except Exception as e:
                print(f"Warning: Failed to load sqlite checkpointer: {e}. Falling back to InMemorySaver.")
                from langgraph.checkpoint.memory import InMemorySaver
                return InMemorySaver()
        else:
            from langgraph.checkpoint.memory import InMemorySaver
            return InMemorySaver()

    def initialize(self):
        """创建 collection、LLM、tools，并编译 Agent 图（同步回退版）。"""
        self.vector_db.create_collection(self.collection_name)
        collection = self.vector_db.get_collection(self.collection_name)

        llm = create_llm()
        tools = ToolFactory(
            collection,
            trace_callback=self.record_retrieval_trace,
        ).create_tools()

        # 同步模式默认回退至内存 checkpointer，确保基础单元测试与 Notebook 兼容
        from langgraph.checkpoint.memory import InMemorySaver
        self.checkpointer = InMemorySaver()
        self.agent_graph = create_agent_graph(llm, tools, checkpointer=self.checkpointer)

    async def initialize_async(self):
        """异步创建 collection、LLM、tools 并编译绑定 AsyncSqliteSaver 实例的 Agent 图。"""
        self.vector_db.create_collection(self.collection_name)
        collection = self.vector_db.get_collection(self.collection_name)

        llm = create_llm()
        tools = ToolFactory(
            collection,
            trace_callback=self.record_retrieval_trace,
        ).create_tools()

        provider = getattr(config, "CHECKPOINT_PROVIDER", "memory")
        if provider == "postgres":
            try:
                from psycopg_pool import AsyncConnectionPool
                from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

                self._pg_pool = AsyncConnectionPool(
                    conninfo=config.POSTGRES_DSN,
                    max_size=10,
                    open=False,
                )
                await self._pg_pool.open()
                self.checkpointer = AsyncPostgresSaver(self._pg_pool)
                await self.checkpointer.setup()
                print(f"AsyncPostgresSaver successfully initialized on PostgreSQL: {config.PG_HOST}:{config.PG_PORT}/{config.PG_DB}")
            except Exception as e:
                print(f"Warning: Failed to load AsyncPostgresSaver: {e}. Falling back to InMemorySaver.")
                from langgraph.checkpoint.memory import InMemorySaver
                self.checkpointer = InMemorySaver()
                self._pg_pool = None
        elif provider == "sqlite":
            db_path = getattr(config, "CHECKPOINT_DB_PATH", "agent_checkpoints.db")
            try:
                from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
                self.checkpointer_ctx = AsyncSqliteSaver.from_conn_string(db_path)
                self.checkpointer = await self.checkpointer_ctx.__aenter__()
                print(f"AsyncSqliteSaver successfully initialized on database: {db_path}")
            except Exception as e:
                print(f"Warning: Failed to load AsyncSqliteSaver: {e}. Falling back to InMemorySaver.")
                from langgraph.checkpoint.memory import InMemorySaver
                self.checkpointer = InMemorySaver()
                self.checkpointer_ctx = None
        else:
            from langgraph.checkpoint.memory import InMemorySaver
            self.checkpointer = InMemorySaver()
            self.checkpointer_ctx = None

        self.agent_graph = create_agent_graph(llm, tools, checkpointer=self.checkpointer)

    async def close_async(self):
        """异步释放外部持久连接池资源。"""
        # 释放 PostgreSQL 异步连接池
        if getattr(self, "_pg_pool", None):
            try:
                await self._pg_pool.close()
                print("AsyncPostgresSaver connection pool closed successfully.")
            except Exception as e:
                print(f"Error releasing PostgreSQL pool: {e}")

        # 释放旧版 SQLite 连接上下文（向后兼容）
        if getattr(self, "checkpointer_ctx", None):
            try:
                await self.checkpointer_ctx.__aexit__(None, None, None)
                print("AsyncSqliteSaver connection context closed successfully.")
            except Exception as e:
                print(f"Error releasing AsyncSqliteSaver: {e}")

    def get_config(self, session_id: str, request_id: str, user_id: str = None):
        """返回 LangGraph 当前会话的执行配置，绑定 thread_id 和 request_id。"""
        # 直接使用 session_id 作为 thread_id，支持服务重启后恢复
        cfg = {
            "configurable": {
                "thread_id": session_id,
                "request_id": request_id,
                "user_id": user_id,
            },
            "recursion_limit": self.recursion_limit
        }
        handler = self.observability.get_handler()
        if handler:
            cfg["callbacks"] = [handler]
        return cfg

    def record_retrieval_trace(self, trace, thread_id: str = None, request_id: str = None):
        """将当前并发上下文的 trace 记录在二元组隔离缓存中。"""
        if thread_id and request_id:
            self.trace_buffers[(thread_id, request_id)].append(trace)

    def pop_retrieval_trace(self, thread_id: str, request_id: str):
        """根据当前并发会话与请求，安全弹出第一条 trace。"""
        key = (thread_id, request_id)
        if not self.trace_buffers.get(key):
            return None
        return self.trace_buffers[key].pop(0)

    def clear_retrieval_traces(self, thread_id: str, request_id: str):
        """清空当前并发请求遗留的检索 trace。"""
        self.trace_buffers.pop((thread_id, request_id), None)

    async def reset_thread(self, session_id: str = "default_session"):
        """重置指定 session_id 下的 thread checkpointer 并清空 trace。"""
        thread_id = session_id
        try:
            if self.agent_graph and self.agent_graph.checkpointer:
                cp = self.agent_graph.checkpointer
                if hasattr(cp, "adelete_thread"):
                    await cp.adelete_thread(thread_id)
                elif hasattr(cp, "delete_thread"):
                    cp.delete_thread(thread_id)
        except Exception as e:
            print(f"Warning: Could not delete thread {thread_id}: {e}")

        # 清理与该 thread 相关的所有 request trace 缓存
        for k in list(self.trace_buffers.keys()):
            if k[0] == thread_id:
                self.trace_buffers.pop(k, None)
