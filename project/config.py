import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=True)

# --- 目录配置 ---
_BASE_DIR = os.path.dirname(os.path.dirname(__file__))

MARKDOWN_DIR = os.path.join(_BASE_DIR, "markdown_docs")
PARENT_STORE_PATH = os.path.join(_BASE_DIR, "parent_store")
QDRANT_DB_PATH = os.path.join(_BASE_DIR, "qdrant_db")
QA_RECORD_DB_PATH = os.path.join(_BASE_DIR, "qa_records.db")
DOCUMENT_METADATA_DB_PATH = os.path.join(_BASE_DIR, "document_metadata.db")
CHECKPOINT_PROVIDER = os.environ.get("CHECKPOINT_PROVIDER", "postgres")
CHECKPOINT_DB_PATH = os.path.join(_BASE_DIR, "agent_checkpoints.db")
AGENT_MEMORY_DB_PATH = os.path.join(_BASE_DIR, "agent_memory.db")
USER_DB_PATH = os.path.join(_BASE_DIR, "users.db")

# --- PostgreSQL 连接配置 ---
PG_HOST = os.environ.get("PG_HOST", "127.0.0.1")
PG_PORT = os.environ.get("PG_PORT", "5432")
PG_USER = os.environ.get("PG_USER", "postgres")
PG_PASSWORD = os.environ.get("PG_PASSWORD", "postgres")
PG_DB = os.environ.get("PG_DB", "rag_studio")
POSTGRES_DSN = os.environ.get(
    "POSTGRES_DSN",
    f"host={PG_HOST} port={PG_PORT} user={PG_USER} password={PG_PASSWORD} dbname={PG_DB}",
)

# --- Qdrant 配置 ---
CHILD_COLLECTION = "document_child_chunks"
SPARSE_VECTOR_NAME = "sparse"
SEARCH_SCORE_THRESHOLD = float(os.environ.get("SEARCH_SCORE_THRESHOLD", "0.4"))

# --- 模型配置 ---
EMBEDDING_PROVIDER = os.environ.get("EMBEDDING_PROVIDER", "openai_compatible")
EMBEDDING_API_BASE_URL = os.environ.get(
    "EMBEDDING_API_BASE_URL",
    "https://open.bigmodel.cn/api/paas/v4/",
)
EMBEDDING_API_KEY = (
    os.environ.get("EMBEDDING_API_KEY")
    or os.environ.get("ali_api_key")
    or os.environ.get("DASHSCOPE_API_KEY")
)
DENSE_MODEL = os.environ.get("DENSE_MODEL", "embedding-2")
EMBEDDING_BATCH_SIZE = 10
SPARSE_MODEL = "Qdrant/bm25"
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "openai_compatible")
LLM_MODEL = os.environ.get("LLM_MODEL", "deepseek-v4-flash")
LLM_TEMPERATURE = 0
OPENAI_COMPATIBLE_API_BASE_URL = os.environ.get(
    "OPENAI_COMPATIBLE_API_BASE_URL",
    "https://dashscope.aliyuncs.com/compatible-mode/v1",
)
DASHSCOPE_LLM_API_KEY = (
    os.environ.get("DASHSCOPE_API_KEY")
    or os.environ.get("ali_api_key")
    or os.environ.get("EMBEDDING_API_KEY")
)
OPENAI_COMPATIBLE_API_KEY = (
    os.environ.get("OPENAI_COMPATIBLE_API_KEY")
    or (
        DASHSCOPE_LLM_API_KEY
        if "dashscope.aliyuncs.com" in OPENAI_COMPATIBLE_API_BASE_URL
        else None
    )
    or os.environ.get("DATE_NOW_API_KEY")
    or os.environ.get("OPENAI_API_KEY")
)
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:4b-instruct-2507-q4_K_M")

# --- 智能体配置 ---
MAX_TOOL_CALLS = 8
MAX_ITERATIONS = 10
GRAPH_RECURSION_LIMIT = 50
BASE_TOKEN_THRESHOLD = 2000
TOKEN_GROWTH_FACTOR = 0.9

# --- 检索流水线配置 ---
RETRIEVAL_CANDIDATE_TOP_K = int(os.environ.get("RETRIEVAL_CANDIDATE_TOP_K", "12"))
RETRIEVAL_FINAL_TOP_K = int(os.environ.get("RETRIEVAL_FINAL_TOP_K", "5"))
RETRIEVAL_MAX_TOOL_LIMIT = int(os.environ.get("RETRIEVAL_MAX_TOOL_LIMIT", "10"))
TRACE_MAX_CANDIDATES = int(os.environ.get("TRACE_MAX_CANDIDATES", "12"))

RERANK_ENABLED = os.environ.get("RERANK_ENABLED", "true").lower() == "true"
RERANK_PROVIDER = os.environ.get("RERANK_PROVIDER", "zhipu")
RERANK_MODEL = os.environ.get("RERANK_MODEL", "rerank")
RERANK_API_BASE_URL = os.environ.get(
    "RERANK_API_BASE_URL",
    "https://open.bigmodel.cn/api/paas/v4/rerank",
)
RERANK_API_KEY = (
    os.environ.get("ZP_api_key")
    or os.environ.get("ZHIPU_API_KEY")
    or os.environ.get("RERANK_API_KEY")
)
RERANK_TOP_K = int(os.environ.get("RERANK_TOP_K", "8"))
RERANK_SCORE_THRESHOLD = float(os.environ.get("RERANK_SCORE_THRESHOLD", "0"))
RERANK_TIMEOUT_SECONDS = int(os.environ.get("RERANK_TIMEOUT_SECONDS", "30"))
RERANK_MAX_DOCUMENT_CHARS = int(os.environ.get("RERANK_MAX_DOCUMENT_CHARS", "4000"))

CONTEXT_MAX_CHUNKS = int(os.environ.get("CONTEXT_MAX_CHUNKS", str(RETRIEVAL_FINAL_TOP_K)))
CONTEXT_MAX_TOKENS = int(os.environ.get("CONTEXT_MAX_TOKENS", "3000"))
CONTEXT_DEDUP_BY_PARENT = os.environ.get("CONTEXT_DEDUP_BY_PARENT", "true").lower() == "true"
CONTEXT_DEDUP_BY_CONTENT = os.environ.get("CONTEXT_DEDUP_BY_CONTENT", "true").lower() == "true"

# --- 文本切分器配置 ---
CHILD_CHUNK_SIZE = 500
CHILD_CHUNK_OVERLAP = 100
MIN_PARENT_SIZE = 2000
MAX_PARENT_SIZE = 4000
HEADERS_TO_SPLIT_ON = [
    ("#", "H1"),
    ("##", "H2"),
    ("###", "H3")
]

# --- Langfuse 可观测性配置 ---
LANGFUSE_ENABLED = os.environ.get("LANGFUSE_ENABLED", "false").lower() == "true"
LANGFUSE_PUBLIC_KEY = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_SECRET_KEY = os.environ.get("LANGFUSE_SECRET_KEY", "")
LANGFUSE_BASE_URL = os.environ.get("LANGFUSE_BASE_URL", "http://localhost:3000")
