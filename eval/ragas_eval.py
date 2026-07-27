from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Callable


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CASES_PATH = ROOT_DIR / "eval" / "ragas_cases.json"
DEFAULT_REPORTS_DIR = ROOT_DIR / "eval" / "ragas_reports"
DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_RAGAS_LLM_MODEL = "qwen3.6-flash"
DEFAULT_METRICS = [
    "faithfulness",
    "answer_relevancy",
    "context_precision",
    "context_recall",
    "factual_correctness",
]


def load_project_env() -> None:
    project_dir = ROOT_DIR / "project"
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    try:
        import config  # type: ignore
    except Exception:
        return

    defaults = {
        "OPENAI_COMPATIBLE_API_KEY": getattr(config, "OPENAI_COMPATIBLE_API_KEY", None),
        "OPENAI_COMPATIBLE_API_BASE_URL": getattr(config, "OPENAI_COMPATIBLE_API_BASE_URL", None),
        "EMBEDDING_API_KEY": getattr(config, "EMBEDDING_API_KEY", None),
        "EMBEDDING_API_BASE_URL": getattr(config, "EMBEDDING_API_BASE_URL", None),
        "DENSE_MODEL": getattr(config, "DENSE_MODEL", None),
    }
    for key, value in defaults.items():
        if value and not os.environ.get(key):
            os.environ[key] = str(value)


@dataclass
class EvalCase:
    id: str
    question: str
    reference: str = ""
    reference_contexts: list[str] = field(default_factory=list)
    expected_sources: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    answerable: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Ragas-based RAG evaluation and write JSON/Markdown/CSV reports."
    )
    parser.add_argument("--cases", default=str(DEFAULT_CASES_PATH), help="Path to Ragas eval cases JSON.")
    parser.add_argument("--reports-dir", default=str(DEFAULT_REPORTS_DIR), help="Directory for reports.")
    parser.add_argument(
        "--runner",
        choices=("http", "local", "mock"),
        default="http",
        help="How to collect RAG answers before scoring.",
    )
    parser.add_argument(
        "--evaluator",
        choices=("ragas", "mock"),
        default="ragas",
        help="Use real Ragas scoring or deterministic mock scoring for dry validation.",
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="FastAPI base URL for --runner http.")
    parser.add_argument(
        "--metrics",
        default=",".join(DEFAULT_METRICS),
        help="Comma-separated metric names. Unknown names fail fast.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Only run the first N cases.")
    parser.add_argument("--case-id", action="append", default=None, help="Run a specific case id.")
    parser.add_argument("--timeout", type=int, default=180, help="Per-request timeout in seconds.")
    parser.add_argument("--keep-session", action="store_true", help="Do not reset chat session between cases.")
    parser.add_argument(
        "--require-reference",
        action="store_true",
        help="Require every case to define reference before running.",
    )
    parser.add_argument(
        "--no-register",
        action="store_true",
        help="Do not create a temporary eval user for HTTP mode.",
    )
    parser.add_argument("--username", default=None, help="Existing username for HTTP auth.")
    parser.add_argument("--password", default=None, help="Existing password for HTTP auth.")
    parser.add_argument(
        "--include-raw-events",
        action="store_true",
        help="Store raw SSE events in JSON report. Useful for debugging, noisy for normal reports.",
    )
    return parser.parse_args(argv)


def resolve_path(value: str, *, base: Path = ROOT_DIR) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return base / path


def parse_metrics(value: str) -> list[str]:
    metrics = [item.strip() for item in value.split(",") if item.strip()]
    if not metrics:
        raise ValueError("At least one metric must be selected.")

    allowed = set(DEFAULT_METRICS)
    unknown = sorted(set(metrics) - allowed)
    if unknown:
        raise ValueError(f"Unknown metric(s): {', '.join(unknown)}")
    return metrics


def load_cases(
    cases_path: Path,
    *,
    require_reference: bool = False,
    limit: int | None = None,
    case_ids: list[str] | None = None,
) -> list[EvalCase]:
    with cases_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("Ragas eval cases JSON must be a list.")

    cases: list[EvalCase] = []
    for index, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Case #{index} must be an object.")
        if not item.get("question"):
            raise ValueError(f"Case #{index} is missing required field: question")

        case = EvalCase(
            id=str(item.get("id") or f"case_{index}"),
            question=str(item["question"]).strip(),
            reference=str(item.get("reference") or item.get("reference_answer") or "").strip(),
            reference_contexts=[str(ctx) for ctx in item.get("reference_contexts") or [] if str(ctx).strip()],
            expected_sources=[str(source) for source in item.get("expected_sources") or [] if str(source).strip()],
            tags=[str(tag) for tag in item.get("tags") or [] if str(tag).strip()],
            answerable=bool(item.get("answerable", item.get("expected_answerable", True))),
            metadata=dict(item.get("metadata") or {}),
        )
        if require_reference and not case.reference:
            raise ValueError(f"Case {case.id} is missing required field: reference")
        cases.append(case)

    if case_ids:
        wanted = set(case_ids)
        cases = [case for case in cases if case.id in wanted]
        missing = sorted(wanted - {case.id for case in cases})
        if missing:
            raise ValueError(f"Unknown case id(s): {', '.join(missing)}")

    if limit is not None:
        cases = cases[: max(0, limit)]

    if not cases:
        raise ValueError("No eval cases selected.")

    return cases


def normalize_text(value: Any) -> str:
    return " ".join(str(value or "").lower().split())


def post_json(url: str, payload: dict[str, Any], timeout: int, *, token: str | None = None) -> bytes:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def login_http_user(base_url: str, username: str, password: str, timeout: int) -> str:
    url = f"{base_url.rstrip('/')}/api/auth/login"
    body = post_json(url, {"username": username, "password": password}, timeout)
    data = json.loads(body.decode("utf-8"))
    token = data.get("access_token")
    if not token:
        raise RuntimeError("Login response did not include access_token.")
    return str(token)


def register_http_user(base_url: str, timeout: int) -> str | None:
    import random
    import string

    rnd = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    username = f"ragas_eval_{rnd}"
    password = "ragas_eval_password_123"
    url = f"{base_url.rstrip('/')}/api/auth/register"
    try:
        body = post_json(url, {"username": username, "password": password}, timeout)
        data = json.loads(body.decode("utf-8"))
        return data.get("access_token")
    except Exception as exc:
        print(f"Warning: failed to register temporary eval user: {exc}")
        return None


def parse_sse_events(raw_lines: Any) -> list[dict[str, Any]]:
    events = []
    for raw_line in raw_lines:
        line = raw_line.decode("utf-8", errors="replace").strip()
        if not line or not line.startswith("data: "):
            continue
        events.append(json.loads(line[6:]))
    return events


def run_http_case(
    case: EvalCase,
    *,
    base_url: str,
    timeout: int,
    reset_session: bool,
    token: str | None = None,
    include_raw_events: bool = False,
) -> dict[str, Any]:
    base_url = base_url.rstrip("/")
    session_id = f"ragas_eval_{case.id}"
    if reset_session:
        post_json(
            f"{base_url}/api/chat/reset",
            {"session_id": session_id},
            timeout,
            token=token,
        )

    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(
        f"{base_url}/api/chat",
        data=json.dumps(
            {"message": case.question, "session_id": session_id},
            ensure_ascii=False,
        ).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    started_at = time.perf_counter()
    response_data: dict[str, Any] = {
        "answer": "",
        "query_analysis": {},
        "retrieval_traces": [],
        "sources": [],
        "meta": {},
        "answerable": True,
        "failure_reason": None,
    }
    answer_chunks = []

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            events = parse_sse_events(response)

        for event in events:
            event_type = event.get("type")
            data = event.get("data")
            if event_type == "text":
                answer_chunks.append(str(data or ""))
            elif event_type == "final_answer":
                response_data["answer"] = str(data or "")
            elif event_type == "query_analysis":
                response_data["query_analysis"] = data or {}
            elif event_type == "traces":
                response_data["retrieval_traces"] = data or []
            elif event_type == "sources":
                response_data["sources"] = data or []
            elif event_type == "meta":
                response_data["meta"] = data or {}

        if not response_data["answer"]:
            response_data["answer"] = "".join(answer_chunks)
        if include_raw_events:
            response_data["raw_events"] = events
        response_data["elapsed_seconds"] = round(time.perf_counter() - started_at, 3)
        return response_data
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {
            **response_data,
            "answer": "",
            "answerable": False,
            "failure_reason": f"RAGAS_HTTP_ERROR: {exc}",
            "error": str(exc),
            "elapsed_seconds": round(time.perf_counter() - started_at, 3),
        }


def prepare_local_imports() -> None:
    project_dir = ROOT_DIR / "project"
    if str(ROOT_DIR) not in sys.path:
        sys.path.insert(0, str(ROOT_DIR))
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    no_proxy = os.environ.get("no_proxy")
    if no_proxy:
        os.environ["no_proxy"] = ",".join(item.strip() for item in no_proxy.split(",") if ":" not in item)

    try:
        from dotenv import load_dotenv
    except Exception:
        return
    load_dotenv(project_dir / ".env")


def model_to_dict(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    return dict(value)


async def run_local_cases(cases: list[EvalCase], *, reset_session: bool) -> list[dict[str, Any]]:
    prepare_local_imports()

    from backend.services.chat_service import ChatService
    from core.rag_system import RAGSystem

    rag_system = RAGSystem(enable_qa_records=False)
    rag_system.initialize()
    chat_service = ChatService(rag_system, enable_memory=False)

    responses = []
    for case in cases:
        session_id = f"ragas_eval_{case.id}"
        if reset_session:
            await chat_service.reset(session_id=session_id)
        started_at = time.perf_counter()
        response = await chat_service.ask(case.question, session_id=session_id)
        data = model_to_dict(response)
        data["elapsed_seconds"] = round(time.perf_counter() - started_at, 3)
        responses.append(data)

    rag_system.observability.flush()
    return responses


def run_mock_case(case: EvalCase) -> dict[str, Any]:
    context = case.reference_contexts[0] if case.reference_contexts else case.reference or case.question
    return {
        "answer": case.reference or f"Mock answer for {case.question}",
        "answerable": case.answerable,
        "failure_reason": None,
        "sources": [
            {
                "source_id": "S1",
                "source": case.expected_sources[0] if case.expected_sources else "mock_source",
                "content_preview": context[:180],
            }
        ],
        "retrieval_traces": [
            {
                "query": case.question,
                "selected_results": [
                    {
                        "rank": 1,
                        "citation_id": "S1",
                        "source": case.expected_sources[0] if case.expected_sources else "mock_source",
                        "content": context,
                        "content_preview": context[:180],
                        "score": 1.0,
                    }
                ],
            }
        ],
        "elapsed_seconds": 0.0,
    }


def collect_retrieved_contexts(response: dict[str, Any]) -> list[str]:
    contexts = []
    seen = set()

    def add(value: Any) -> None:
        text = str(value or "").strip()
        key = normalize_text(text)
        if text and key not in seen:
            contexts.append(text)
            seen.add(key)

    for trace in response.get("retrieval_traces") or []:
        for item in trace.get("selected_results") or []:
            add(item.get("content") or item.get("content_preview"))
        for item in trace.get("candidates") or []:
            if item.get("status") == "selected":
                add(item.get("content") or item.get("content_preview"))

    if not contexts:
        for source in response.get("sources") or []:
            add(source.get("content") or source.get("content_preview"))

    return contexts


def collect_source_names(response: dict[str, Any]) -> list[str]:
    names = []
    seen = set()
    for source in response.get("sources") or []:
        value = str(source.get("source") or "").strip()
        key = normalize_text(value)
        if value and key not in seen:
            names.append(value)
            seen.add(key)
    for trace in response.get("retrieval_traces") or []:
        for item in trace.get("selected_results") or []:
            value = str(item.get("source") or "").strip()
            key = normalize_text(value)
            if value and key not in seen:
                names.append(value)
                seen.add(key)
    return names


def build_ragas_row(case: EvalCase, response: dict[str, Any]) -> dict[str, Any]:
    row = {
        "user_input": case.question,
        "response": response.get("answer") or "",
        "retrieved_contexts": collect_retrieved_contexts(response),
        "reference": case.reference,
        "reference_contexts": case.reference_contexts,
    }
    row["metadata"] = {
        "case_id": case.id,
        "expected_sources": case.expected_sources,
        "actual_sources": collect_source_names(response),
        "tags": case.tags,
        "answerable": case.answerable,
        "elapsed_seconds": response.get("elapsed_seconds", 0.0),
        **case.metadata,
    }
    return row


def build_ragas_rows(cases: list[EvalCase], responses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [build_ragas_row(case, response) for case, response in zip(cases, responses)]


def token_set(value: str) -> set[str]:
    tokens = re.findall(r"[\w\u4e00-\u9fff]+", normalize_text(value), flags=re.UNICODE)
    return set(tokens)


def overlap_score(a: str, b: str) -> float:
    left = token_set(a)
    right = token_set(b)
    if not left or not right:
        return 0.0
    return round(len(left & right) / len(left), 4)


def mock_score_rows(rows: list[dict[str, Any]], metrics: list[str]) -> list[dict[str, float]]:
    scores = []
    for row in rows:
        response = row.get("response") or ""
        question = row.get("user_input") or ""
        reference = row.get("reference") or ""
        contexts = row.get("retrieved_contexts") or []
        reference_contexts = row.get("reference_contexts") or []
        joined_contexts = "\n".join(contexts)
        joined_reference_contexts = "\n".join(reference_contexts)

        metric_scores = {}
        for metric in metrics:
            if metric == "faithfulness":
                metric_scores[metric] = overlap_score(response, joined_contexts)
            elif metric == "answer_relevancy":
                metric_scores[metric] = max(overlap_score(question, response), overlap_score(response, question))
            elif metric == "context_precision":
                metric_scores[metric] = overlap_score(question, joined_contexts)
            elif metric == "context_recall":
                metric_scores[metric] = overlap_score(joined_reference_contexts or reference, joined_contexts)
            elif metric == "factual_correctness":
                metric_scores[metric] = overlap_score(reference, response) if reference else 0.0
        scores.append(metric_scores)
    return scores


def create_ragas_components() -> tuple[Any, Any]:
    load_project_env()
    try:
        from openai import AsyncOpenAI
        from ragas.embeddings.base import embedding_factory
        from ragas.llms.base import llm_factory
    except ImportError as exc:
        raise RuntimeError(
            "Ragas scoring requires `ragas`, `openai`, and their dependencies. "
            "Install them with `pip install -r requirements.txt`, or run with `--evaluator mock`."
        ) from exc

    api_key = (
        os.environ.get("RAGAS_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or os.environ.get("OPENAI_COMPATIBLE_API_KEY")
        or os.environ.get("EMBEDDING_API_KEY")
        or os.environ.get("ali_api_key")
        or os.environ.get("DASHSCOPE_API_KEY")
    )
    base_url = (
        os.environ.get("RAGAS_API_BASE_URL")
        or os.environ.get("OPENAI_BASE_URL")
        or os.environ.get("OPENAI_COMPATIBLE_API_BASE_URL")
    )
    if not api_key:
        raise RuntimeError(
            "Missing Ragas judge API key. Set RAGAS_API_KEY, OPENAI_API_KEY, "
            "or OPENAI_COMPATIBLE_API_KEY. Use `--evaluator mock` to validate the local pipeline."
        )

    llm_provider = os.environ.get("RAGAS_LLM_PROVIDER", "openai")
    llm_model = os.environ.get("RAGAS_LLM_MODEL") or DEFAULT_RAGAS_LLM_MODEL
    embedding_provider = os.environ.get("RAGAS_EMBEDDING_PROVIDER", "openai")
    embedding_model = (
        os.environ.get("RAGAS_EMBEDDING_MODEL")
        or os.environ.get("DENSE_MODEL")
        or "text-embedding-3-small"
    )
    embedding_api_key = (
        os.environ.get("RAGAS_EMBEDDING_API_KEY")
        or os.environ.get("EMBEDDING_API_KEY")
        or api_key
    )
    embedding_base_url = (
        os.environ.get("RAGAS_EMBEDDING_API_BASE_URL")
        or os.environ.get("EMBEDDING_API_BASE_URL")
        or base_url
    )

    client_kwargs = {"api_key": api_key}
    if base_url:
        client_kwargs["base_url"] = base_url
    client = AsyncOpenAI(**client_kwargs)

    embedding_client_kwargs = {"api_key": embedding_api_key}
    if embedding_base_url:
        embedding_client_kwargs["base_url"] = embedding_base_url
    embedding_client = AsyncOpenAI(**embedding_client_kwargs)

    llm_kwargs: dict[str, Any] = {
        "temperature": 0.01,
        "max_tokens": int(os.environ.get("RAGAS_LLM_MAX_TOKENS", "4096")),
    }
    if "qwen" in llm_model.lower():
        llm_kwargs["extra_body"] = {"enable_thinking": False}

    llm = llm_factory(llm_model, provider=llm_provider, client=client, **llm_kwargs)
    embeddings = embedding_factory(
        embedding_provider,
        model=embedding_model,
        client=embedding_client,
    )
    return llm, embeddings


def create_ragas_metrics(metric_names: list[str], *, llm: Any, embeddings: Any) -> dict[str, Any]:
    try:
        from ragas.metrics.collections import (
            AnswerRelevancy,
            ContextPrecisionWithReference,
            ContextPrecisionWithoutReference,
            ContextRecall,
            FactualCorrectness,
            Faithfulness,
        )
    except ImportError as exc:
        raise RuntimeError(
            "Ragas scoring requires `ragas`. Install dependencies with "
            "`pip install -r requirements.txt`, or run with `--evaluator mock`."
        ) from exc

    created: dict[str, Any] = {}
    for metric_name in metric_names:
        if metric_name == "faithfulness":
            created[metric_name] = Faithfulness(llm=llm)
        elif metric_name == "answer_relevancy":
            created[metric_name] = AnswerRelevancy(llm=llm, embeddings=embeddings)
        elif metric_name == "context_precision":
            created[metric_name] = {
                "with_reference": ContextPrecisionWithReference(llm=llm),
                "without_reference": ContextPrecisionWithoutReference(llm=llm),
            }
        elif metric_name == "context_recall":
            created[metric_name] = ContextRecall(llm=llm)
        elif metric_name == "factual_correctness":
            created[metric_name] = FactualCorrectness(llm=llm)
        else:
            raise ValueError(f"Unsupported metric: {metric_name}")
    return created


async def score_row_with_ragas(row: dict[str, Any], metric_name: str, metric: Any) -> float | None:
    try:
        if metric_name == "faithfulness":
            if not row["retrieved_contexts"] or not row["response"]:
                return None
            result = await metric.ascore(
                user_input=row["user_input"],
                response=row["response"],
                retrieved_contexts=row["retrieved_contexts"],
            )
        elif metric_name == "answer_relevancy":
            if not row["response"]:
                return None
            result = await metric.ascore(
                user_input=row["user_input"],
                response=row["response"],
            )
        elif metric_name == "context_precision":
            if not row["retrieved_contexts"]:
                return None
            if row.get("reference"):
                result = await metric["with_reference"].ascore(
                    user_input=row["user_input"],
                    reference=row["reference"],
                    retrieved_contexts=row["retrieved_contexts"],
                )
            elif row.get("response"):
                result = await metric["without_reference"].ascore(
                    user_input=row["user_input"],
                    response=row["response"],
                    retrieved_contexts=row["retrieved_contexts"],
                )
            else:
                return None
        elif metric_name == "context_recall":
            if not row["retrieved_contexts"] or not row.get("reference"):
                return None
            result = await metric.ascore(
                user_input=row["user_input"],
                retrieved_contexts=row["retrieved_contexts"],
                reference=row["reference"],
            )
        elif metric_name == "factual_correctness":
            if not row["response"] or not row.get("reference"):
                return None
            result = await metric.ascore(
                response=row["response"],
                reference=row["reference"],
            )
        else:
            raise ValueError(f"Unsupported metric: {metric_name}")
    except Exception as exc:
        raise RuntimeError(
            f"Ragas metric `{metric_name}` failed for case "
            f"`{row.get('metadata', {}).get('case_id', 'unknown')}`: {exc}"
        ) from exc

    value = getattr(result, "value", result)
    if value is None:
        return None
    return round(float(value), 4)


async def score_with_ragas_async(rows: list[dict[str, Any]], metrics: list[str]) -> list[dict[str, float | None]]:
    llm, embeddings = create_ragas_components()
    metric_objects = create_ragas_metrics(metrics, llm=llm, embeddings=embeddings)
    scored = []
    for row in rows:
        row_scores = {}
        for metric_name in metrics:
            row_scores[metric_name] = await score_row_with_ragas(
                row,
                metric_name,
                metric_objects[metric_name],
            )
        scored.append(row_scores)
    return scored


def score_with_ragas(rows: list[dict[str, Any]], metrics: list[str]) -> list[dict[str, float | None]]:
    return asyncio.run(score_with_ragas_async(rows, metrics))


def source_hit(case: EvalCase, actual_sources: list[str]) -> bool | None:
    if not case.expected_sources:
        return None
    haystacks = [normalize_text(item) for item in actual_sources]
    for expected_source in case.expected_sources:
        needle = normalize_text(expected_source)
        if not any(needle in haystack for haystack in haystacks):
            return False
    return True


def summarize_case_scores(case_results: list[dict[str, Any]], metrics: list[str]) -> dict[str, Any]:
    metric_averages = {}
    for metric in metrics:
        values = [
            result["metrics"][metric]
            for result in case_results
            if isinstance(result.get("metrics", {}).get(metric), (int, float))
        ]
        metric_averages[metric] = round(mean(values), 4) if values else None

    source_values = [
        result["source_hit"]
        for result in case_results
        if result.get("source_hit") is not None
    ]
    latencies = [
        result["elapsed_seconds"]
        for result in case_results
        if isinstance(result.get("elapsed_seconds"), (int, float))
    ]
    return {
        "case_count": len(case_results),
        "metric_averages": metric_averages,
        "source_hit_rate": (
            round(sum(1 for value in source_values if value) / len(source_values), 4)
            if source_values
            else None
        ),
        "average_latency_seconds": round(mean(latencies), 4) if latencies else None,
        "low_score_cases": find_low_score_cases(case_results, metrics),
    }


def find_low_score_cases(
    case_results: list[dict[str, Any]],
    metrics: list[str],
    *,
    threshold: float = 0.5,
) -> list[dict[str, Any]]:
    low_cases = []
    for result in case_results:
        low_metrics = {
            metric: result["metrics"][metric]
            for metric in metrics
            if isinstance(result.get("metrics", {}).get(metric), (int, float))
            and result["metrics"][metric] < threshold
        }
        if low_metrics:
            low_cases.append(
                {
                    "case_id": result["case_id"],
                    "question": result["question"],
                    "low_metrics": low_metrics,
                }
            )
    return low_cases


def build_report(
    *,
    cases: list[EvalCase],
    responses: list[dict[str, Any]],
    ragas_rows: list[dict[str, Any]],
    metric_scores: list[dict[str, float]],
    metrics: list[str],
    args: argparse.Namespace,
    started_at: datetime,
) -> dict[str, Any]:
    case_results = []
    for case, response, row, scores in zip(cases, responses, ragas_rows, metric_scores):
        actual_sources = row["metadata"]["actual_sources"]
        case_results.append(
            {
                "case_id": case.id,
                "question": case.question,
                "answer": response.get("answer") or "",
                "reference": case.reference,
                "tags": case.tags,
                "metrics": scores,
                "source_hit": source_hit(case, actual_sources),
                "expected_sources": case.expected_sources,
                "actual_sources": actual_sources,
                "retrieved_context_count": len(row["retrieved_contexts"]),
                "elapsed_seconds": response.get("elapsed_seconds", 0.0),
                "answerable": response.get("answerable", True),
                "failure_reason": response.get("failure_reason"),
                "retrieved_contexts": row["retrieved_contexts"],
            }
        )

    return {
        "run": {
            "started_at": started_at.isoformat(),
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "runner": args.runner,
            "evaluator": args.evaluator,
            "metrics": metrics,
            "cases_path": str(resolve_path(args.cases)),
            "base_url": args.base_url if args.runner == "http" else None,
            "reset_between_cases": not args.keep_session,
        },
        "summary": summarize_case_scores(case_results, metrics),
        "cases": case_results,
    }


def write_reports(report: dict[str, Any], reports_dir: Path) -> tuple[Path, Path, Path]:
    reports_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"ragas_eval_{timestamp}_{report['run']['runner']}_{report['run']['evaluator']}"
    json_path = reports_dir / f"{base_name}.json"
    markdown_path = reports_dir / f"{base_name}.md"
    csv_path = reports_dir / f"{base_name}.csv"

    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(render_markdown_report(report), encoding="utf-8")
    write_csv_report(report, csv_path)
    return json_path, markdown_path, csv_path


def fmt(value: Any) -> str:
    if value is None:
        return "-"
    return str(value)


def render_markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# Ragas Evaluation Report",
        "",
        f"- Started at: `{report['run']['started_at']}`",
        f"- Runner: `{report['run']['runner']}`",
        f"- Evaluator: `{report['run']['evaluator']}`",
        f"- Metrics: `{', '.join(report['run']['metrics'])}`",
        f"- Cases: `{report['summary']['case_count']}`",
        "",
        "## Summary",
        "",
        "| Metric | Average |",
        "| --- | --- |",
    ]
    for metric, value in report["summary"]["metric_averages"].items():
        lines.append(f"| {metric} | {fmt(value)} |")
    lines.extend(
        [
            f"| source_hit_rate | {fmt(report['summary']['source_hit_rate'])} |",
            f"| average_latency_seconds | {fmt(report['summary']['average_latency_seconds'])} |",
            "",
            "## Case Scores",
            "",
            "| Case | Source Hit | Retrieved Contexts | Latency | Metrics |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for case in report["cases"]:
        metrics_text = ", ".join(f"{key}={value}" for key, value in case["metrics"].items())
        lines.append(
            "| "
            f"{case['case_id']} | "
            f"{fmt(case['source_hit'])} | "
            f"{case['retrieved_context_count']} | "
            f"{fmt(case['elapsed_seconds'])} | "
            f"{metrics_text} |"
        )

    low_score_cases = report["summary"].get("low_score_cases") or []
    if low_score_cases:
        lines.extend(["", "## Low Score Cases", ""])
        for item in low_score_cases:
            lines.append(f"- `{item['case_id']}`: {json.dumps(item['low_metrics'], ensure_ascii=False)}")
    return "\n".join(lines) + "\n"


def write_csv_report(report: dict[str, Any], csv_path: Path) -> None:
    metrics = report["run"]["metrics"]
    fieldnames = [
        "case_id",
        "question",
        "source_hit",
        "retrieved_context_count",
        "elapsed_seconds",
        *metrics,
    ]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for case in report["cases"]:
            row = {
                "case_id": case["case_id"],
                "question": case["question"],
                "source_hit": case["source_hit"],
                "retrieved_context_count": case["retrieved_context_count"],
                "elapsed_seconds": case["elapsed_seconds"],
            }
            row.update(case["metrics"])
            writer.writerow(row)


def collect_responses(args: argparse.Namespace, cases: list[EvalCase]) -> list[dict[str, Any]]:
    if args.runner == "mock":
        return [run_mock_case(case) for case in cases]

    if args.runner == "local":
        return asyncio.run(run_local_cases(cases, reset_session=not args.keep_session))

    token = None
    if args.username and args.password:
        token = login_http_user(args.base_url, args.username, args.password, args.timeout)
    elif not args.no_register:
        token = register_http_user(args.base_url, args.timeout)

    return [
        run_http_case(
            case,
            base_url=args.base_url,
            timeout=args.timeout,
            reset_session=not args.keep_session,
            token=token,
            include_raw_events=args.include_raw_events,
        )
        for case in cases
    ]


def score_rows(rows: list[dict[str, Any]], metrics: list[str], evaluator: str) -> list[dict[str, float]]:
    if evaluator == "mock":
        return mock_score_rows(rows, metrics)
    return score_with_ragas(rows, metrics)


def run_eval(args: argparse.Namespace) -> dict[str, Any]:
    metrics = parse_metrics(args.metrics)
    cases_path = resolve_path(args.cases)
    reports_dir = resolve_path(args.reports_dir)
    started_at = datetime.now(timezone.utc)

    cases = load_cases(
        cases_path,
        require_reference=args.require_reference,
        limit=args.limit,
        case_ids=args.case_id,
    )
    responses = collect_responses(args, cases)
    rows = build_ragas_rows(cases, responses)
    metric_scores = score_rows(rows, metrics, args.evaluator)
    report = build_report(
        cases=cases,
        responses=responses,
        ragas_rows=rows,
        metric_scores=metric_scores,
        metrics=metrics,
        args=args,
        started_at=started_at,
    )
    json_path, markdown_path, csv_path = write_reports(report, reports_dir)
    report["run"]["json_report_path"] = str(json_path)
    report["run"]["markdown_report_path"] = str(markdown_path)
    report["run"]["csv_report_path"] = str(csv_path)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def print_summary(report: dict[str, Any]) -> None:
    print(f"JSON report: {report['run']['json_report_path']}")
    print(f"Markdown report: {report['run']['markdown_report_path']}")
    print(f"CSV report: {report['run']['csv_report_path']}")
    for metric, value in report["summary"]["metric_averages"].items():
        print(f"{metric}: {value}")
    print(f"source_hit_rate: {report['summary']['source_hit_rate']}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = run_eval(args)
    except Exception as exc:
        print(f"Ragas evaluation failed: {exc}", file=sys.stderr)
        return 2
    print_summary(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
