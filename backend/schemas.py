from typing import List, Optional
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=128)


class UserResponse(BaseModel):
    id: int
    username: str
    role: str


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class LogoutResponse(BaseModel):
    success: bool = True


class DocumentItem(BaseModel):
    name: str
    document_id: Optional[str] = None
    user_id: Optional[str] = None
    visibility: Optional[str] = None
    category: Optional[str] = "general"
    original_name: Optional[str] = None
    type: str
    status: str = "indexed"
    original_size_bytes: int = 0
    parent_chunk_count: int = 0
    child_chunk_count: int = 0
    embedding_provider: Optional[str] = None
    dense_model: Optional[str] = None
    sparse_model: Optional[str] = None
    child_chunk_size: Optional[int] = None
    child_chunk_overlap: Optional[int] = None
    min_parent_size: Optional[int] = None
    max_parent_size: Optional[int] = None
    collection_name: Optional[str] = None
    error_message: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class DocumentListResponse(BaseModel):
    documents: List[DocumentItem]


class DocumentUploadResponse(BaseModel):
    added: int
    skipped: int
    documents: List[DocumentItem]


class DocumentClearResponse(BaseModel):
    success: bool
    documents: List[DocumentItem] = Field(default_factory=list)


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ChatResetRequest(BaseModel):
    session_id: Optional[str] = "default_session"



class QueryAnalysis(BaseModel):
    is_clear: bool = Field(
        description="Indicates if the user's question is clear and answerable."
    )
    rewritten_queries: List[str] = Field(
        default_factory=list,
        description="List of rewritten, self-contained questions."
    )
    clarification_needed: str = Field(
        default="",
        description="Explanation or follow-up question if the question is unclear."
    )


class Candidate(BaseModel):
    rank: int
    citation_id: str
    parent_id: str
    source: str
    score: float
    threshold: float
    status: str
    content_preview: str
    rejection_reason: Optional[str] = None
    rerank_score: Optional[float] = None
    rank_before_rerank: Optional[int] = None
    rank_after_rerank: Optional[int] = None
    content_hash: Optional[str] = None
    estimated_tokens: Optional[int] = None


class RetrievalTrace(BaseModel):
    tool: str = "search_child_chunks"
    query: str
    top_k: int
    candidate_top_k: Optional[int] = None
    final_top_k: Optional[int] = None
    threshold: float
    rerank_enabled: bool = False
    rerank_applied: bool = False
    rerank_provider: Optional[str] = None
    rerank_model: Optional[str] = None
    rerank_top_k: Optional[int] = None
    rerank_score_threshold: Optional[float] = None
    rerank_error: Optional[str] = None
    candidate_count: int
    selected_count: int
    rejected_count: int
    failure_reason: Optional[str] = None
    parent_ids: List[str] = Field(default_factory=list)
    error: Optional[str] = None
    candidates: List[Candidate] = Field(default_factory=list)
    selected_results: List[Candidate] = Field(default_factory=list)
    rejected_results: List[Candidate] = Field(default_factory=list)
    context_assembly: dict = Field(default_factory=dict)


class Source(BaseModel):
    source_id: str
    source: str
    parent_id: str
    score: float
    threshold: float
    content_preview: str
    rerank_score: Optional[float] = None


class SystemAlert(BaseModel):
    title: str
    content: str


class ChatResponse(BaseModel):
    answer: str
    query_analysis: QueryAnalysis
    retrieval_traces: List[RetrievalTrace] = Field(default_factory=list)
    sources: List[Source] = Field(default_factory=list)
    system_alerts: List[SystemAlert] = Field(default_factory=list)
    answerable: bool = True
    failure_reason: Optional[str] = None
    meta: dict = Field(default_factory=dict)


class ChatResetResponse(BaseModel):
    success: bool = True


class ChatSessionItem(BaseModel):
    session_id: str
    title: str
    created_at: str
    updated_at: str
    record_count: int = 0
    last_question: Optional[str] = None


class ChatSessionListResponse(BaseModel):
    sessions: List[ChatSessionItem] = Field(default_factory=list)


class ChatSessionRenameRequest(BaseModel):
    title: str = Field(min_length=1, max_length=80)


class ChatSessionDeleteResponse(BaseModel):
    success: bool = True
    session_id: str
    deleted_records: int = 0
    deleted_memories: int = 0


class QARecordItem(BaseModel):
    id: int
    question: str
    answer: str
    answerable: bool
    sources_count: int
    rejected_sources_count: int
    failure_reason: Optional[str] = None
    created_at: str


class QARecordListResponse(BaseModel):
    records: List[QARecordItem] = Field(default_factory=list)


class QARecordDetail(QARecordItem):
    trace_json: str
    meta_json: Optional[str] = None


class EvalReportSummary(BaseModel):
    name: str
    created_at: str
    mode: Optional[str] = None
    dry_run: bool = False
    case_count: int = 0
    pass_rate: Optional[float] = None
    source_hit_rate: Optional[float] = None
    no_answer_rate: Optional[float] = None
    markdown_name: Optional[str] = None


class EvalReportListResponse(BaseModel):
    reports: List[EvalReportSummary] = Field(default_factory=list)


class EvalReportMarkdownResponse(BaseModel):
    content: str


class MemoryItem(BaseModel):
    id: int
    content: str
    source: str = "qa_interaction"
    importance: float = 0.5
    session_id: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""
    last_used_at: Optional[str] = None
    hit_count: int = 0


class MemoryListResponse(BaseModel):
    memories: List[MemoryItem] = Field(default_factory=list)


class MemoryCreateRequest(BaseModel):
    content: str
    importance: float = 0.5
    session_id: Optional[str] = None


class MemoryUpdateRequest(BaseModel):
    content: Optional[str] = None
    importance: Optional[float] = None


class MemorySearchRequest(BaseModel):
    query: str = ""
    session_id: Optional[str] = None
    limit: int = 5


class UserProfileResponse(BaseModel):
    preferred_language: Optional[str] = None
    response_style: Optional[str] = None
    custom_rules: List[str] = Field(default_factory=list)


class UserProfileUpdateRequest(BaseModel):
    preferred_language: Optional[str] = None
    response_style: Optional[str] = None
    custom_rules: Optional[List[str]] = None


