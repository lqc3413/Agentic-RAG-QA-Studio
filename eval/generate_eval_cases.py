from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = ROOT_DIR / "project"
DEFAULT_PARENT_STORE_DIR = ROOT_DIR / "parent_store" / "public"
DEFAULT_OUTPUT_PATH = ROOT_DIR / "eval" / "ragas_cases.generated.json"
DEFAULT_MODEL = "qwen3.6-flash"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate Ragas eval cases from indexed parent documents."
    )
    parser.add_argument(
        "--parent-store-dir",
        default=str(DEFAULT_PARENT_STORE_DIR),
        help="Directory containing parent chunk JSON files.",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT_PATH),
        help="Output JSON path for generated Ragas cases.",
    )
    parser.add_argument(
        "--cases-per-doc",
        type=int,
        default=1,
        help="Number of eval cases to generate per document.",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("RAGAS_CASE_GENERATOR_MODEL") or DEFAULT_MODEL,
        help="OpenAI-compatible LLM model used to generate questions and references.",
    )
    parser.add_argument(
        "--max-context-chars",
        type=int,
        default=6000,
        help="Maximum source context characters sent to the generator per case.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build deterministic cases without calling an LLM.",
    )
    return parser.parse_args(argv)


def load_project_config() -> Any:
    if str(PROJECT_DIR) not in sys.path:
        sys.path.insert(0, str(PROJECT_DIR))
    import config  # type: ignore

    return config


def load_source_mapping() -> dict[str, dict[str, str]]:
    db_path = ROOT_DIR / "document_metadata.db"
    if not db_path.exists():
        return {}

    mapping: dict[str, dict[str, str]] = {}
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT document_id, original_name, category, visibility, user_id, status
            FROM document_metadata
            """
        ).fetchall()
    for row in rows:
        document_id = row["document_id"] or Path(row["name"]).stem
        mapping[str(document_id)] = {
            "original_name": str(row["original_name"] or document_id),
            "category": str(row["category"] or "general"),
            "visibility": str(row["visibility"] or "public"),
            "user_id": str(row["user_id"] or "public"),
            "status": str(row["status"] or ""),
        }
    return mapping


def normalize_case_id(value: str) -> str:
    normalized = re.sub(r"[^0-9A-Za-z_\-\u4e00-\u9fff]+", "_", value).strip("_")
    return normalized[:80] or "case"


def compact_context(text: str, max_chars: int) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= max_chars:
        return text
    head = text[: max_chars // 2].rstrip()
    tail = text[-max_chars // 2 :].lstrip()
    return f"{head}\n...\n{tail}"


def load_parent_documents(parent_store_dir: Path) -> list[dict[str, Any]]:
    source_mapping = load_source_mapping()
    grouped: dict[str, dict[str, Any]] = {}

    for path in sorted(parent_store_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        content = str(data.get("page_content") or "").strip()
        metadata = dict(data.get("metadata") or {})
        document_id = str(metadata.get("document_id") or path.name.split("_parent_")[0])
        source_info = source_mapping.get(document_id, {})

        doc = grouped.setdefault(
            document_id,
            {
                "document_id": document_id,
                "source_name": source_info.get("original_name")
                or metadata.get("source_name")
                or metadata.get("source")
                or f"{document_id}.md",
                "category": source_info.get("category") or "general",
                "visibility": source_info.get("visibility") or metadata.get("visibility") or "public",
                "chunks": [],
            },
        )
        if content:
            doc["chunks"].append(
                {
                    "path": str(path),
                    "parent_id": metadata.get("parent_id") or path.stem,
                    "content": content,
                    "metadata": metadata,
                }
            )

    documents = [doc for doc in grouped.values() if doc["chunks"]]
    documents.sort(key=lambda item: str(item["source_name"]).lower())
    return documents


def create_llm(model: str) -> Any:
    config = load_project_config()
    api_key = (
        os.environ.get("RAGAS_CASE_GENERATOR_API_KEY")
        or os.environ.get("RAGAS_API_KEY")
        or getattr(config, "OPENAI_COMPATIBLE_API_KEY", None)
        or getattr(config, "EMBEDDING_API_KEY", None)
    )
    base_url = (
        os.environ.get("RAGAS_CASE_GENERATOR_BASE_URL")
        or os.environ.get("RAGAS_API_BASE_URL")
        or getattr(config, "OPENAI_COMPATIBLE_API_BASE_URL", None)
    )
    if not api_key:
        raise RuntimeError(
            "Missing Alibaba/OpenAI-compatible API key. Configure project/.env or RAGAS_API_KEY."
        )

    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=0.1,
        model_kwargs={"response_format": {"type": "json_object"}},
    )


def generate_case_with_llm(
    llm: Any,
    *,
    document: dict[str, Any],
    context: str,
    case_index: int,
) -> dict[str, Any]:
    from langchain_core.messages import HumanMessage, SystemMessage

    system_prompt = (
        "你是 RAG 自动评测集设计专家。请只基于给定文档片段生成 1 条中文评测样本。"
        "问题要像真实用户会问的技术/业务问题，标准答案必须能被文档片段直接支持。"
        "不要引入文档片段之外的事实。严格输出 JSON，字段为 question、reference、tags。"
    )
    user_prompt = (
        f"文档名：{document['source_name']}\n"
        f"分类：{document['category']}\n"
        f"片段：\n{context}\n\n"
        "输出格式："
        "{\"question\":\"...\",\"reference\":\"...\",\"tags\":[\"...\"]}"
    )
    response = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)])
    raw = str(response.content).strip()
    data = json.loads(raw)
    question = str(data.get("question") or "").strip()
    reference = str(data.get("reference") or "").strip()
    tags = [str(tag).strip() for tag in data.get("tags") or [] if str(tag).strip()]
    if not question or not reference:
        raise ValueError(f"Generator returned incomplete case: {raw[:300]}")

    source_stem = Path(str(document["source_name"])).stem
    return {
        "id": normalize_case_id(f"{source_stem}_{case_index:02d}"),
        "question": question,
        "reference": reference,
        "reference_contexts": [context],
        "expected_sources": [str(document["source_name"])],
        "tags": sorted(set([str(document["category"]), source_stem, *tags])),
        "answerable": True,
        "metadata": {
            "document_id": document["document_id"],
            "source_name": document["source_name"],
            "generated_by": "eval/generate_eval_cases.py",
            "generator_model": DEFAULT_MODEL,
        },
    }


def build_dry_case(*, document: dict[str, Any], context: str, case_index: int) -> dict[str, Any]:
    source_stem = Path(str(document["source_name"])).stem
    question = f"请概括 {source_stem} 文档中这一段的核心内容是什么？"
    reference = compact_context(context, 900)
    return {
        "id": normalize_case_id(f"{source_stem}_{case_index:02d}"),
        "question": question,
        "reference": reference,
        "reference_contexts": [context],
        "expected_sources": [str(document["source_name"])],
        "tags": sorted(set([str(document["category"]), source_stem, "dry_run"])),
        "answerable": True,
        "metadata": {
            "document_id": document["document_id"],
            "source_name": document["source_name"],
            "generated_by": "eval/generate_eval_cases.py",
            "generator_model": "dry-run",
        },
    }


def select_contexts(document: dict[str, Any], cases_per_doc: int, max_chars: int) -> list[str]:
    chunks = list(document["chunks"])
    if cases_per_doc <= 1:
        best = max(chunks, key=lambda item: len(item["content"]))
        return [compact_context(best["content"], max_chars)]

    step = max(1, len(chunks) // cases_per_doc)
    selected = []
    for index in range(cases_per_doc):
        chunk = chunks[min(index * step, len(chunks) - 1)]
        selected.append(compact_context(chunk["content"], max_chars))
    return selected


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    parent_store_dir = Path(args.parent_store_dir)
    output_path = Path(args.output)
    documents = load_parent_documents(parent_store_dir)
    if not documents:
        raise RuntimeError(f"No parent documents found under {parent_store_dir}")

    llm = None if args.dry_run else create_llm(args.model)
    cases: list[dict[str, Any]] = []
    for document in documents:
        contexts = select_contexts(document, args.cases_per_doc, args.max_context_chars)
        for local_index, context in enumerate(contexts, start=1):
            if llm is None:
                case = build_dry_case(document=document, context=context, case_index=local_index)
            else:
                case = generate_case_with_llm(
                    llm,
                    document=document,
                    context=context,
                    case_index=local_index,
                )
                case["metadata"]["generator_model"] = args.model
            cases.append(case)
            print(f"[OK] {case['id']}: {case['question']}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nGenerated {len(cases)} Ragas cases from {len(documents)} documents.")
    print(f"Saved to: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
