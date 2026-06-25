from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CASES_PATH = ROOT_DIR / "eval" / "eval_cases.json"
DEFAULT_REPORTS_DIR = ROOT_DIR / "eval" / "reports"
DEFAULT_BASE_URL = "http://127.0.0.1:8000"
CITATION_PATTERN = re.compile(r"\bS\d+\b", re.IGNORECASE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run batch RAG evaluation cases and generate JSON/Markdown reports."
    )
    parser.add_argument(
        "--cases",
        default=str(DEFAULT_CASES_PATH),
        help="Path to eval cases JSON file.",
    )
    parser.add_argument(
        "--reports-dir",
        default=str(DEFAULT_REPORTS_DIR),
        help="Directory where reports will be written.",
    )
    parser.add_argument(
        "--mode",
        choices=("http", "local"),
        default="http",
        help=(
            "http uses the running FastAPI server and avoids local Qdrant file locks. "
            "local initializes RAGSystem in this process and supports threshold comparison."
        ),
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help="FastAPI base URL for --mode http.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="Run with a single score threshold. Requires --mode local.",
    )
    parser.add_argument(
        "--thresholds",
        default=None,
        help="Comma-separated score thresholds for comparison. Requires --mode local.",
    )
    parser.add_argument(
        "--candidate-top-k",
        type=int,
        default=None,
        help="Override retrieval candidate top_k. Requires --mode local.",
    )
    parser.add_argument(
        "--final-top-k",
        type=int,
        default=None,
        help="Override final selected chunk top_k. Requires --mode local.",
    )
    parser.add_argument(
        "--context-max-chunks",
        type=int,
        default=None,
        help="Override max chunks packed into the final context. Requires --mode local.",
    )
    parser.add_argument(
        "--context-max-tokens",
        type=int,
        default=None,
        help="Override approximate token budget for final context assembly. Requires --mode local.",
    )
    parser.add_argument(
        "--rerank-enabled",
        choices=("true", "false"),
        default=None,
        help="Enable or disable rerank for this run. Requires --mode local.",
    )
    parser.add_argument(
        "--compare-rerank",
        action="store_true",
        help="Run two local variants with rerank disabled and enabled.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only run the first N cases.",
    )
    parser.add_argument(
        "--case-id",
        action="append",
        default=None,
        help="Run only the specified case id. Can be provided multiple times.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=180,
        help="Per-request timeout in seconds.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate cases and generate a report without calling the RAG system.",
    )
    parser.add_argument(
        "--keep-session",
        action="store_true",
        help="Do not reset chat session between cases.",
    )
    return parser.parse_args()


def load_cases(cases_path: Path) -> list[dict[str, Any]]:
    with cases_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("Eval cases JSON must be a list.")

    cases = []
    for index, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Case #{index} must be an object.")
        if not item.get("question"):
            raise ValueError(f"Case #{index} is missing required field: question")

        normalized = {
            "id": item.get("id") or f"case_{index}",
            "question": str(item["question"]),
            "expected_keywords": list(item.get("expected_keywords") or []),
            "expected_sources": list(item.get("expected_sources") or []),
        }
        if "expected_answerable" in item:
            normalized["expected_answerable"] = bool(item["expected_answerable"])
        cases.append(normalized)

    return cases


def resolve_path(value: str, *, base: Path = ROOT_DIR) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return base / path


def parse_thresholds(args: argparse.Namespace) -> list[float | None]:
    if args.thresholds:
        thresholds = []
        for raw in args.thresholds.split(","):
            raw = raw.strip()
            if raw:
                thresholds.append(float(raw))
        if not thresholds:
            raise ValueError("--thresholds did not contain any numeric values.")
        return thresholds

    if args.threshold is not None:
        return [args.threshold]

    return [None]


def parse_optional_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    return value.lower() == "true"


def has_local_overrides(args: argparse.Namespace) -> bool:
    return any(
        value is not None
        for value in (
            args.threshold,
            args.thresholds,
            args.candidate_top_k,
            args.final_top_k,
            args.context_max_chunks,
            args.context_max_tokens,
            args.rerank_enabled,
        )
    ) or bool(args.compare_rerank)


def build_run_configs(args: argparse.Namespace) -> list[dict[str, Any]]:
    thresholds = parse_thresholds(args)
    rerank_value = parse_optional_bool(args.rerank_enabled)
    rerank_values = [rerank_value]

    if args.compare_rerank:
        rerank_values = [False, True]
    elif rerank_value is None:
        rerank_values = [None]

    run_configs = []
    for threshold in thresholds:
        for rerank_enabled in rerank_values:
            overrides: dict[str, Any] = {}
            if threshold is not None:
                overrides["SEARCH_SCORE_THRESHOLD"] = threshold
            if args.candidate_top_k is not None:
                overrides["RETRIEVAL_CANDIDATE_TOP_K"] = args.candidate_top_k
            if args.final_top_k is not None:
                overrides["RETRIEVAL_FINAL_TOP_K"] = args.final_top_k
                overrides.setdefault("CONTEXT_MAX_CHUNKS", args.final_top_k)
            if args.context_max_chunks is not None:
                overrides["CONTEXT_MAX_CHUNKS"] = args.context_max_chunks
            if args.context_max_tokens is not None:
                overrides["CONTEXT_MAX_TOKENS"] = args.context_max_tokens
            if rerank_enabled is not None:
                overrides["RERANK_ENABLED"] = rerank_enabled

            label_parts = []
            label_parts.append(
                f"threshold={threshold}"
                if threshold is not None
                else "threshold=server_current"
            )
            if args.candidate_top_k is not None:
                label_parts.append(f"candidate_top_k={args.candidate_top_k}")
            if args.final_top_k is not None:
                label_parts.append(f"final_top_k={args.final_top_k}")
            if args.context_max_chunks is not None:
                label_parts.append(f"context_chunks={args.context_max_chunks}")
            if args.context_max_tokens is not None:
                label_parts.append(f"context_tokens={args.context_max_tokens}")
            if rerank_enabled is not None:
                label_parts.append(f"rerank={'on' if rerank_enabled else 'off'}")

            run_configs.append(
                {
                    "threshold": threshold,
                    "label": ", ".join(label_parts),
                    "overrides": overrides,
                }
            )

    return run_configs


def filter_cases(
    cases: list[dict[str, Any]],
    *,
    limit: int | None = None,
    case_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    selected = cases
    if case_ids:
        wanted = set(case_ids)
        selected = [case for case in selected if case["id"] in wanted]
        missing = sorted(wanted - {case["id"] for case in selected})
        if missing:
            raise ValueError(f"Unknown case id(s): {', '.join(missing)}")

    if limit is not None:
        selected = selected[: max(0, limit)]

    return selected


def normalize_text(value: Any) -> str:
    return " ".join(str(value or "").lower().split())


def keyword_results(answer: str, expected_keywords: list[str]) -> list[dict[str, Any]]:
    normalized_answer = normalize_text(answer)
    return [
        {
            "keyword": keyword,
            "matched": normalize_text(keyword) in normalized_answer,
        }
        for keyword in expected_keywords
    ]


def collect_source_haystacks(response: dict[str, Any]) -> list[str]:
    haystacks = []
    for source in response.get("sources") or []:
        haystacks.extend(
            [
                source.get("source", ""),
                source.get("parent_id", ""),
                source.get("content_preview", ""),
            ]
        )

    for trace in response.get("retrieval_traces") or []:
        for candidate in trace.get("candidates") or []:
            haystacks.extend(
                [
                    candidate.get("source", ""),
                    candidate.get("parent_id", ""),
                    candidate.get("content_preview", ""),
                ]
            )

    return [normalize_text(item) for item in haystacks if item]


def source_results(
    response: dict[str, Any],
    expected_sources: list[str],
) -> list[dict[str, Any]]:
    haystacks = collect_source_haystacks(response)
    results = []
    for expected_source in expected_sources:
        needle = normalize_text(expected_source)
        results.append(
            {
                "source": expected_source,
                "matched": any(needle in haystack for haystack in haystacks),
            }
        )
    return results


def collect_scores(response: dict[str, Any]) -> tuple[list[float], list[float], list[float]]:
    selected_scores = []
    candidate_scores = []
    rerank_scores = []

    for source in response.get("sources") or []:
        score = source.get("score")
        if isinstance(score, (int, float)):
            selected_scores.append(float(score))
        rerank_score = source.get("rerank_score")
        if isinstance(rerank_score, (int, float)):
            rerank_scores.append(float(rerank_score))

    for trace in response.get("retrieval_traces") or []:
        for candidate in trace.get("candidates") or []:
            score = candidate.get("score")
            if isinstance(score, (int, float)):
                candidate_scores.append(float(score))
            rerank_score = candidate.get("rerank_score")
            if isinstance(rerank_score, (int, float)):
                rerank_scores.append(float(rerank_score))

    return selected_scores, candidate_scores, rerank_scores


def collect_trace_metrics(response: dict[str, Any]) -> dict[str, Any]:
    traces = response.get("retrieval_traces") or []
    candidate_counts = []
    selected_counts = []
    rejected_counts = []
    rerank_changed_top1 = []

    for trace in traces:
        candidate_counts.append(int(trace.get("candidate_count") or 0))
        selected_counts.append(int(trace.get("selected_count") or 0))
        rejected_counts.append(int(trace.get("rejected_count") or 0))

        if trace.get("rerank_enabled"):
            candidates = trace.get("candidates") or []
            selected = [
                item
                for item in candidates
                if item.get("status") == "selected"
            ]
            if selected:
                first = selected[0]
                before = first.get("rank_before_rerank")
                after = first.get("rank_after_rerank")
                rerank_changed_top1.append(
                    bool(before and after and int(before) != int(after))
                )

    return {
        "candidate_count": sum(candidate_counts),
        "selected_count": sum(selected_counts),
        "rejected_count": sum(rejected_counts),
        "rerank_changed_top1": (
            any(rerank_changed_top1)
            if rerank_changed_top1
            else None
        ),
    }


def first_failure_reason(response: dict[str, Any]) -> str | None:
    if response.get("failure_reason"):
        return response["failure_reason"]

    for trace in response.get("retrieval_traces") or []:
        if trace.get("failure_reason"):
            return trace["failure_reason"]

    if response.get("retrieval_traces") and not response.get("sources"):
        return "LOW_SCORE_FILTERED"

    return None


def evaluate_case_result(
    case: dict[str, Any],
    response: dict[str, Any],
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    if dry_run:
        return {
            "case_id": case["id"],
            "question": case["question"],
            "status": "dry_run",
            "passed": None,
            "checks": {},
            "answer": "",
            "answerable": None,
            "failure_reason": None,
            "average_selected_score": None,
            "average_candidate_score": None,
            "average_rerank_score": None,
            "candidate_count": 0,
            "selected_count": 0,
            "rejected_count": 0,
            "rerank_changed_top1": None,
            "sources": [],
            "retrieval_traces": [],
            "meta": {},
            "elapsed_seconds": 0.0,
        }

    answer = response.get("answer") or ""
    keywords = keyword_results(answer, case.get("expected_keywords") or [])
    sources = source_results(response, case.get("expected_sources") or [])
    selected_scores, candidate_scores, rerank_scores = collect_scores(response)
    trace_metrics = collect_trace_metrics(response)

    keyword_pass = all(item["matched"] for item in keywords) if keywords else None
    source_pass = all(item["matched"] for item in sources) if sources else None

    expected_answerable = case.get("expected_answerable")
    actual_answerable = bool(response.get("answerable"))
    answerable_pass = (
        actual_answerable == expected_answerable
        if expected_answerable is not None
        else None
    )

    has_sources = bool(response.get("sources"))
    has_inline_citation = bool(CITATION_PATTERN.search(answer))
    failure_reason = first_failure_reason(response)

    required_checks = [
        check
        for check in (keyword_pass, source_pass, answerable_pass)
        if check is not None
    ]
    passed = all(required_checks) if required_checks else None

    return {
        "case_id": case["id"],
        "question": case["question"],
        "status": "completed",
        "passed": passed,
        "checks": {
            "keyword_pass": keyword_pass,
            "source_pass": source_pass,
            "answerable_pass": answerable_pass,
            "has_sources": has_sources,
            "has_inline_citation": has_inline_citation,
        },
        "expected_keywords": case.get("expected_keywords") or [],
        "keyword_results": keywords,
        "expected_sources": case.get("expected_sources") or [],
        "source_results": sources,
        "expected_answerable": expected_answerable,
        "answerable": actual_answerable,
        "failure_reason": failure_reason,
        "average_selected_score": round(mean(selected_scores), 4) if selected_scores else None,
        "average_candidate_score": round(mean(candidate_scores), 4) if candidate_scores else None,
        "average_rerank_score": round(mean(rerank_scores), 4) if rerank_scores else None,
        "candidate_count": trace_metrics["candidate_count"],
        "selected_count": trace_metrics["selected_count"],
        "rejected_count": trace_metrics["rejected_count"],
        "rerank_changed_top1": trace_metrics["rerank_changed_top1"],
        "sources": response.get("sources") or [],
        "retrieval_traces": response.get("retrieval_traces") or [],
        "meta": response.get("meta") or {},
        "answer": answer,
        "elapsed_seconds": response.get("elapsed_seconds", 0.0),
        "error": response.get("error"),
    }


def summarize_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    completed = [result for result in results if result["status"] == "completed"]
    if not completed:
        return {
            "case_count": len(results),
            "completed_count": 0,
            "passed_count": 0,
            "pass_rate": None,
            "keyword_pass_rate": None,
            "source_hit_rate": None,
            "answerable_accuracy": None,
            "citation_coverage": None,
            "no_answer_rate": None,
            "average_selected_score": None,
            "average_candidate_score": None,
            "average_rerank_score": None,
            "average_candidate_count": None,
            "average_selected_count": None,
            "average_rejected_count": None,
            "rerank_changed_top1_rate": None,
            "failure_reason_distribution": {},
        }

    def rate(values: list[bool]) -> float | None:
        if not values:
            return None
        return round(sum(1 for value in values if value) / len(values), 4)

    passed_values = [result["passed"] for result in completed if result["passed"] is not None]
    keyword_values = [
        result["checks"]["keyword_pass"]
        for result in completed
        if result["checks"]["keyword_pass"] is not None
    ]
    source_values = [
        result["checks"]["source_pass"]
        for result in completed
        if result["checks"]["source_pass"] is not None
    ]
    answerable_values = [
        result["checks"]["answerable_pass"]
        for result in completed
        if result["checks"]["answerable_pass"] is not None
    ]
    selected_scores = [
        result["average_selected_score"]
        for result in completed
        if result["average_selected_score"] is not None
    ]
    candidate_scores = [
        result["average_candidate_score"]
        for result in completed
        if result["average_candidate_score"] is not None
    ]
    rerank_scores = [
        result["average_rerank_score"]
        for result in completed
        if result.get("average_rerank_score") is not None
    ]
    candidate_counts = [result.get("candidate_count", 0) for result in completed]
    selected_counts = [result.get("selected_count", 0) for result in completed]
    rejected_counts = [result.get("rejected_count", 0) for result in completed]
    rerank_changed_values = [
        result["rerank_changed_top1"]
        for result in completed
        if result.get("rerank_changed_top1") is not None
    ]

    failure_reasons = Counter(
        result["failure_reason"] or "NONE"
        for result in completed
    )

    return {
        "case_count": len(results),
        "completed_count": len(completed),
        "passed_count": sum(1 for value in passed_values if value),
        "pass_rate": rate(passed_values),
        "keyword_pass_rate": rate(keyword_values),
        "source_hit_rate": rate(source_values),
        "answerable_accuracy": rate(answerable_values),
        "citation_coverage": rate([result["checks"]["has_sources"] for result in completed]),
        "inline_citation_rate": rate([result["checks"]["has_inline_citation"] for result in completed]),
        "no_answer_rate": rate([not result["answerable"] for result in completed]),
        "average_selected_score": round(mean(selected_scores), 4) if selected_scores else None,
        "average_candidate_score": round(mean(candidate_scores), 4) if candidate_scores else None,
        "average_rerank_score": round(mean(rerank_scores), 4) if rerank_scores else None,
        "average_candidate_count": round(mean(candidate_counts), 4) if candidate_counts else None,
        "average_selected_count": round(mean(selected_counts), 4) if selected_counts else None,
        "average_rejected_count": round(mean(rejected_counts), 4) if rejected_counts else None,
        "rerank_changed_top1_rate": rate(rerank_changed_values),
        "failure_reason_distribution": dict(failure_reasons),
    }


def post_json(url: str, payload: dict[str, Any], timeout: int, token: str | None = None) -> bytes:
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


def run_http_case(
    case: dict[str, Any],
    *,
    base_url: str,
    timeout: int,
    reset_session: bool,
    token: str | None = None,
) -> dict[str, Any]:
    base_url = base_url.rstrip("/")
    if reset_session:
        post_json(f"{base_url}/api/chat/reset", {}, timeout, token=token)

    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(
        f"{base_url}/api/chat",
        data=json.dumps({"message": case["question"]}, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    started_at = time.perf_counter()
    events = []
    answer_chunks = []
    response_data: dict[str, Any] = {
        "answer": "",
        "query_analysis": {},
        "retrieval_traces": [],
        "sources": [],
        "meta": {},
        "answerable": True,
        "failure_reason": None,
    }

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            for raw_line in response:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line or not line.startswith("data: "):
                    continue

                event = json.loads(line[6:])
                events.append(event)
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

        failure_reason = first_failure_reason(response_data)
        if failure_reason:
            response_data["answerable"] = False
            response_data["failure_reason"] = failure_reason

        if response_data.get("query_analysis", {}).get("is_clear") is False:
            response_data["answerable"] = False
            response_data["failure_reason"] = (
                response_data.get("query_analysis", {}).get("clarification_needed")
                or "Query clarification needed"
            )

        response_data["events_count"] = len(events)
        response_data["elapsed_seconds"] = round(time.perf_counter() - started_at, 3)
        return response_data

    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {
            **response_data,
            "answer": "",
            "answerable": False,
            "failure_reason": f"EVAL_HTTP_ERROR: {exc}",
            "error": str(exc),
            "elapsed_seconds": round(time.perf_counter() - started_at, 3),
        }


def prepare_local_imports():
    project_dir = ROOT_DIR / "project"
    if str(ROOT_DIR) not in sys.path:
        sys.path.insert(0, str(ROOT_DIR))
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    no_proxy = os.environ.get("no_proxy")
    if no_proxy:
        os.environ["no_proxy"] = ",".join(
            item.strip()
            for item in no_proxy.split(",")
            if ":" not in item
        )

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


async def run_local_cases(
    cases: list[dict[str, Any]],
    *,
    config_overrides: dict[str, Any],
    reset_session: bool,
) -> list[dict[str, Any]]:
    prepare_local_imports()

    import config
    from backend.services.chat_service import ChatService
    from core.rag_system import RAGSystem

    for key, value in config_overrides.items():
        setattr(config, key, value)

    rag_system = RAGSystem()
    rag_system.initialize()
    chat_service = ChatService(rag_system)

    responses = []
    for case in cases:
        if reset_session:
            await chat_service.reset()

        started_at = time.perf_counter()
        response = await chat_service.ask(case["question"])
        data = model_to_dict(response)
        data["elapsed_seconds"] = round(time.perf_counter() - started_at, 3)
        responses.append(data)

    rag_system.observability.flush()
    return responses


async def run_eval(args: argparse.Namespace) -> dict[str, Any]:
    cases_path = resolve_path(args.cases)
    reports_dir = resolve_path(args.reports_dir)
    run_configs = build_run_configs(args)

    if args.mode == "http" and has_local_overrides(args):
        raise ValueError(
            "Retrieval config overrides require --mode local because HTTP mode uses the running server config."
        )

    cases = filter_cases(
        load_cases(cases_path),
        limit=args.limit,
        case_ids=args.case_id,
    )
    if not cases:
        raise ValueError("No eval cases selected.")

    run_started_at = datetime.now(timezone.utc)
    threshold_reports = []

    token = None
    if args.mode == "http" and not args.dry_run:
        # 动态注册临时 eval 评测用户
        import random
        import string
        rnd = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
        username = f"eval_runner_{rnd}"
        password = "eval_password_123"
        try:
            reg_url = f"{args.base_url.rstrip('/')}/api/auth/register"
            reg_res = post_json(reg_url, {"username": username, "password": password}, timeout=args.timeout)
            reg_data = json.loads(reg_res.decode("utf-8"))
            token = reg_data.get("access_token")
            print(f"Successfully registered temporary eval user: {username}")
        except Exception as e:
            print(f"Warning: Failed to register temporary user for evaluation: {e}. Attempting unauthenticated requests.")

    for run_config in run_configs:
        label = run_config["label"]
        overrides = run_config["overrides"]

        if args.dry_run:
            raw_responses = [{} for _ in cases]
        elif args.mode == "http":
            raw_responses = [
                run_http_case(
                    case,
                    base_url=args.base_url,
                    timeout=args.timeout,
                    reset_session=not args.keep_session,
                    token=token,
                )
                for case in cases
            ]
        else:
            raw_responses = await run_local_cases(
                cases,
                config_overrides=overrides,
                reset_session=not args.keep_session,
            )

        case_results = [
            evaluate_case_result(case, response, dry_run=args.dry_run)
            for case, response in zip(cases, raw_responses)
        ]

        threshold_reports.append(
            {
                "threshold": run_config["threshold"],
                "label": label,
                "config_overrides": overrides,
                "summary": summarize_results(case_results),
                "cases": case_results,
            }
        )

    report = {
        "run": {
            "started_at": run_started_at.isoformat(),
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "mode": args.mode,
            "dry_run": args.dry_run,
            "cases_path": str(cases_path),
            "base_url": args.base_url if args.mode == "http" else None,
            "reset_between_cases": not args.keep_session,
        },
        "threshold_reports": threshold_reports,
    }

    json_path, markdown_path = write_reports(report, reports_dir)
    report["run"]["json_report_path"] = str(json_path)
    report["run"]["markdown_report_path"] = str(markdown_path)

    with json_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    markdown_path.write_text(render_markdown_report(report), encoding="utf-8")
    return report


def write_reports(report: dict[str, Any], reports_dir: Path) -> tuple[Path, Path]:
    reports_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    mode = report["run"]["mode"]
    suffix = "_dry_run" if report["run"]["dry_run"] else ""
    base_name = f"rag_eval_{timestamp}_{mode}{suffix}"
    return reports_dir / f"{base_name}.json", reports_dir / f"{base_name}.md"


def md(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def truncate(value: str, limit: int = 180) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


def render_markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# RAG 批量评估报告",
        "",
        f"- 运行时间：`{report['run']['started_at']}`",
        f"- 模式：`{report['run']['mode']}`",
        f"- Dry Run：`{report['run']['dry_run']}`",
        f"- 测试集：`{report['run']['cases_path']}`",
        f"- 重置会话：`{report['run']['reset_between_cases']}`",
        "",
    ]

    if report["run"].get("base_url"):
        lines.append(f"- API：`{report['run']['base_url']}`")
        lines.append("")

    for threshold_report in report["threshold_reports"]:
        summary = threshold_report["summary"]
        lines.extend(
            [
                f"## Config: `{threshold_report['label']}`",
                "",
                "| 指标 | 值 |",
                "| --- | --- |",
                f"| 用例数 | {summary['case_count']} |",
                f"| 完成数 | {summary['completed_count']} |",
                f"| 通过数 | {summary['passed_count']} |",
                f"| 通过率 | {summary['pass_rate']} |",
                f"| 关键词命中率 | {summary['keyword_pass_rate']} |",
                f"| Source 命中率 | {summary['source_hit_rate']} |",
                f"| Answerable 准确率 | {summary['answerable_accuracy']} |",
                f"| Source 引用覆盖率 | {summary['citation_coverage']} |",
                f"| 答案内联引用率 | {summary.get('inline_citation_rate')} |",
                f"| 无答案率 | {summary['no_answer_rate']} |",
                f"| 平均 selected score | {summary['average_selected_score']} |",
                f"| 平均 candidate score | {summary['average_candidate_score']} |",
                f"| 平均 rerank score | {summary.get('average_rerank_score')} |",
                f"| 平均候选数 | {summary.get('average_candidate_count')} |",
                f"| 平均入选数 | {summary.get('average_selected_count')} |",
                f"| 平均拒绝数 | {summary.get('average_rejected_count')} |",
                f"| Rerank 改变 Top1 率 | {summary.get('rerank_changed_top1_rate')} |",
                f"| Failure reason 分布 | `{json.dumps(summary['failure_reason_distribution'], ensure_ascii=False)}` |",
                "",
                f"- 配置覆盖：`{json.dumps(threshold_report.get('config_overrides') or {}, ensure_ascii=False)}`",
                "",
                "### 用例明细",
                "",
                "| Case | 通过 | Keyword | Source | Answerable | Avg Score | 候选/入选/拒绝 | Rerank 改排 | Failure | 耗时 |",
                "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
            ]
        )

        for result in threshold_report["cases"]:
            checks = result.get("checks") or {}
            lines.append(
                "| "
                + " | ".join(
                    [
                        md(result["case_id"]),
                        md(result["passed"]),
                        md(checks.get("keyword_pass")),
                        md(checks.get("source_pass")),
                        md(checks.get("answerable_pass")),
                        md(result.get("average_selected_score")),
                        md(
                            f"{result.get('candidate_count', 0)}/"
                            f"{result.get('selected_count', 0)}/"
                            f"{result.get('rejected_count', 0)}"
                        ),
                        md(result.get("rerank_changed_top1")),
                        md(result.get("failure_reason") or "NONE"),
                        md(result.get("elapsed_seconds")),
                    ]
                )
                + " |"
            )

        lines.append("")
        lines.append("### 回答摘录")
        lines.append("")
        for result in threshold_report["cases"]:
            lines.extend(
                [
                    f"#### {result['case_id']}",
                    "",
                    f"- 问题：{result['question']}",
                    f"- 回答：{truncate(result.get('answer', ''))}",
                    "",
                ]
            )

    return "\n".join(lines).rstrip() + "\n"


def print_summary(report: dict[str, Any]) -> None:
    print("RAG eval completed.")
    print(f"JSON report: {report['run']['json_report_path']}")
    print(f"Markdown report: {report['run']['markdown_report_path']}")

    for threshold_report in report["threshold_reports"]:
        summary = threshold_report["summary"]
        print(
            "Config "
            f"{threshold_report['label']}: "
            f"pass_rate={summary['pass_rate']}, "
            f"keyword_pass_rate={summary['keyword_pass_rate']}, "
            f"source_hit_rate={summary['source_hit_rate']}, "
            f"no_answer_rate={summary['no_answer_rate']}"
        )


def main() -> None:
    args = parse_args()
    report = asyncio.run(run_eval(args))
    print_summary(report)


if __name__ == "__main__":
    main()
