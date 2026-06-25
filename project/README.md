# Project Core Modules

This folder contains the RAG and Agent core used by the current FastAPI + Vue application.

## Current Entry Points

- Backend API: `backend/main.py`
- Frontend app: `frontend/`
- Evaluation runner: `eval/run_rag_eval.py`

The previous Gradio entry point and UI files were removed. Runtime chat now flows through `backend/services/chat_service.py`.

## Core Layout

| Path | Purpose |
| --- | --- |
| `config.py` | Runtime configuration for models, retrieval, rerank, chunking, paths, and observability. |
| `core/rag_system.py` | Creates the vector store, parent store, tools, LLM, and LangGraph agent. |
| `core/document_manager.py` | Handles document ingestion, PDF/Markdown conversion, chunking, indexing, and metadata. |
| `core/observability.py` | Optional Langfuse callback lifecycle. |
| `db/vector_db_manager.py` | Local Qdrant wrapper with dense + sparse hybrid retrieval setup. |
| `db/parent_store_manager.py` | File-backed parent chunk storage. |
| `db/document_metadata_manager.py` | SQLite metadata for uploaded documents. |
| `db/qa_record_manager.py` | SQLite QA history records. |
| `document_chunker.py` | Parent/child Markdown chunking logic. |
| `rag/retriever_pipeline.py` | Child chunk recall, optional rerank, context assembly, and trace creation. |
| `rag/context_assembler.py` | Similarity thresholding, rerank thresholding, deduplication, and context budget control. |
| `rag/rerankers.py` | Zhipu and local lexical rerank implementations. |
| `rag/retrieval_models.py` | Shared retrieval item and context assembly data models. |
| `rag_agent/graph.py` | LangGraph graph/subgraph construction. |
| `rag_agent/nodes.py` | Query rewrite, orchestration, compression, fallback, and answer aggregation nodes. |
| `rag_agent/edges.py` | Conditional routing for clarification, tool execution, fallback, and answer collection. |
| `rag_agent/tools.py` | LangGraph tools for `search_child_chunks` and `retrieve_parent_chunks`. |
| `rag_agent/prompts.py` | System prompts used by the Agent graph. |
| `utils.py` | PDF conversion helpers, directory cleanup, and token estimation. |

## Run Locally

From the repository root:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

From `frontend/`:

```powershell
npm.cmd install
npm.cmd run dev -- --host 127.0.0.1 --port 5173
```
