import json
import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException, Path as FastapiPath
from backend.schemas import (
    EvalReportSummary,
    EvalReportListResponse,
    EvalReportMarkdownResponse,
)

logger = logging.getLogger("eval_reports")

router = APIRouter(prefix="/api/eval/reports", tags=["eval_reports"])

# 计算当前项目根目录下的 eval/reports 文件夹路径
# backend/routers/eval_reports.py 深度为 2
REPORTS_DIR = Path(__file__).resolve().parents[2] / "eval" / "reports"


@router.get("", response_model=EvalReportListResponse)
async def list_reports():
    if not REPORTS_DIR.exists():
        return EvalReportListResponse(reports=[])

    reports_summary = []
    
    # 查找所有的 .json 报告并按最后修改时间倒序排列
    json_paths = sorted(
        REPORTS_DIR.glob("*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )

    for path in json_paths:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # 读取 run 元数据
            run_data = data.get("run", {})
            started_at = run_data.get("started_at", "")
            mode = run_data.get("mode", "unknown")
            dry_run = run_data.get("dry_run", False)
            
            # 如果没有 started_at，使用文件的修改时间作为兜底
            if not started_at:
                import datetime
                mtime = path.stat().st_mtime
                started_at = datetime.datetime.fromtimestamp(mtime).isoformat()
            
            # 读取 threshold_reports 首项摘要数据
            threshold_reports = data.get("threshold_reports", [])
            if threshold_reports and isinstance(threshold_reports, list):
                first_tr = threshold_reports[0]
            else:
                first_tr = {}
                
            summary_data = first_tr.get("summary", {})
            
            case_count = summary_data.get("case_count", 0)
            pass_rate = summary_data.get("pass_rate", None)
            source_hit_rate = summary_data.get("source_hit_rate", None)
            no_answer_rate = summary_data.get("no_answer_rate", None)
            
            # 判断对应的 Markdown 文件是否存在
            md_name = path.name.replace(".json", ".md")
            md_path = REPORTS_DIR / md_name
            markdown_name = md_name if md_path.exists() else None
            
            reports_summary.append(
                EvalReportSummary(
                    name=path.name,
                    created_at=started_at,
                    mode=mode,
                    dry_run=dry_run,
                    case_count=case_count,
                    pass_rate=pass_rate,
                    source_hit_rate=source_hit_rate,
                    no_answer_rate=no_answer_rate,
                    markdown_name=markdown_name,
                )
            )
        except Exception as e:
            # 容错：当某个报告 JSON 解析出错时，打印警告日志并跳过，防止整体接口挂掉
            logger.warning(f"Failed to read eval report file: {path}, error: {e}")
            continue

    return EvalReportListResponse(reports=reports_summary)


@router.get("/{report_name}", response_model=dict)
async def get_report_detail(
    report_name: str = FastapiPath(..., description="JSON report file name")
):
    # 安全性防范：禁止路径穿越
    safe_name = Path(report_name).name
    if safe_name != report_name or not safe_name.endswith(".json"):
        raise HTTPException(status_code=400, detail="Invalid report name format")

    file_path = REPORTS_DIR / safe_name
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Eval report not found")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            report_data = json.load(f)
        return report_data
    except Exception as e:
        logger.error(f"Failed to load report {safe_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to read report file: {e}")


@router.get("/{report_name}/markdown", response_model=EvalReportMarkdownResponse)
async def get_report_markdown(
    report_name: str = FastapiPath(..., description="Corresponding JSON report file name")
):
    # 安全性防范：禁止路径穿越，只允许从符合规范的 JSON 文件名推导 MD
    safe_name = Path(report_name).name
    if safe_name != report_name or not safe_name.endswith(".json"):
        raise HTTPException(status_code=400, detail="Invalid report name format")

    md_name = safe_name.replace(".json", ".md")
    file_path = REPORTS_DIR / md_name
    
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Markdown report not found")

    try:
        content = file_path.read_text(encoding="utf-8")
        return EvalReportMarkdownResponse(name=md_name, content=content)
    except Exception as e:
        logger.error(f"Failed to read markdown report {md_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to read markdown file: {e}")
