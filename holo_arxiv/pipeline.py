from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
from typing import Callable, Mapping
from zoneinfo import ZoneInfo

import requests

from .classifier import DeepSeekClassifier
from .feed import Paper, parse_atom
from .pushplus import build_payload, query_send_result, send_push
from .rules import is_candidate
from .site import build_site
from .state import StateStore, dedupe_papers

CATEGORIES = [
    "hep-th", "gr-qc", "hep-ph", "hep-lat", "nucl-th", "math-ph", "quant-ph",
    "cond-mat.str-el", "cond-mat.supr-con", "cond-mat.quant-gas", "cond-mat.stat-mech",
]
SCAN_ZONE = ZoneInfo("Asia/Shanghai")
SCAN_AFTER_HOUR = 14


def scan_push_date(now: datetime | None = None) -> str:
    """Return the China-local date of the arXiv batch this run is allowed to push."""
    current = (now or datetime.now(timezone.utc)).astimezone(SCAN_ZONE)
    batch_date = current.date()
    if current.hour < SCAN_AFTER_HOUR:
        batch_date -= timedelta(days=1)
    return batch_date.isoformat()


def scan_time_gate(now: datetime | None = None) -> bool:
    """Do not scan before arXiv has announced the China-local daily batch."""
    current = (now or datetime.now(timezone.utc)).astimezone(SCAN_ZONE)
    return current.hour >= SCAN_AFTER_HOUR


def _batch_dates(papers: list[Paper]) -> set[str]:
    return {(paper.updated or paper.published or "")[:10] for paper in papers}


def ensure_current_batch(papers: list[Paper], target_date: str) -> None:
    """Fail closed instead of pushing an older announcement batch as today's digest."""
    dates = _batch_dates(papers)
    if not papers:
        raise RuntimeError(f"没有抓取到目标批次 {target_date} 的论文")
    stale = sorted(date for date in dates if date and date < target_date)
    if stale:
        raise RuntimeError(f"arXiv 批次仍是旧日期 {stale[0]}，目标批次为 {target_date}")
    missing = sorted(date for date in dates if date and date > target_date)
    if missing:
        raise RuntimeError(f"arXiv 批次已进入新日期 {missing[0]}，但本次目标批次为 {target_date}")


def filter_announcements(papers: list[Paper], target_date: str | None) -> list[Paper]:
    """Use the feed as the announcement batch unless replaying a date."""
    if not target_date:
        return papers
    return [paper for paper in papers if (paper.updated or "")[:10] == target_date]


def pushplus_is_enabled(environ: Mapping[str, str] | None = None) -> bool:
    """Require an explicit opt-in so tests and first deployments cannot send."""
    env = os.environ if environ is None else environ
    return env.get("PUSHPLUS_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}


def _fake_classification(paper: Paper) -> dict:
    text = f"{paper.title} {paper.abstract}".lower()
    superfluid = any(word in text for word in ("superfluid", "superconductor"))
    nonuniform = any(word in text for word in ("vortex", "soliton", "domain wall", "inhomogeneous"))
    focus = []
    if superfluid:
        focus.append("全息超流超导")
    if nonuniform:
        focus.append("畴壁/孤子/涡旋/非均匀")
    return {
        "is_theoretical_holography": True,
        "is_classical_gravity": False,
        "confidence": 0.90,
        "primary_topic": "全息凝聚态/超流超导/强关联" if superfluid else "AdS/CFT 基础与字典",
        "secondary_topics": ["非均匀态/孤子/涡旋/畴壁"] if nonuniform else [],
        "title_zh": f"[演示翻译] {paper.title}",
        "abstract_zh": f"[演示摘要，非模型输出] {paper.abstract}",
        "one_liner": "dry-run 假分类器：仅用于验证完整流程。",
        "keywords": ["全息"],
        "importance": "high" if focus else "normal",
        "relevance": "high" if focus else "medium",
        "relevance_reason": "由 fixture 关键词触发，仅供 dry-run 测试。",
        "focus_tags": focus,
    }


def _response_bytes(response) -> bytes:
    if isinstance(response, bytes):
        return response
    response.raise_for_status()
    return response.content


def run_pipeline(*, dry_run: bool = False, fixture: Path | None = None,
                 state_path: Path = Path("data/state.json"), docs_dir: Path = Path("docs"),
                 preview_path: Path = Path("pushplus-preview.json"),
                 network_get: Callable = requests.get, network_post: Callable | None = None,
                 target_date: str | None = None) -> dict:
    if not dry_run and not scan_time_gate():
        raise RuntimeError("arXiv 尚未到达北京时间 14:00 的更新时段，拒绝扫描和推送")
    target_date = target_date or scan_push_date()
    papers: list[Paper] = []
    if dry_run:
        if fixture is None:
            raise ValueError("dry-run 必须指定 fixture")
        content = Path(fixture).read_bytes()
        papers = parse_atom(content, "hep-th")
    else:
        for category in CATEGORIES:
            response = network_get(f"https://rss.arxiv.org/atom/{category}", timeout=30)
            fetched = parse_atom(_response_bytes(response), category)
            papers.extend(filter_announcements(fetched, target_date))
    papers = dedupe_papers(papers)
    if not dry_run:
        ensure_current_batch(papers, target_date)
    store = StateStore(Path(state_path))
    candidates = [paper for paper in papers if is_candidate(paper) and not store.is_known(paper)]
    if dry_run:
        for paper in candidates:
            paper.classification = _fake_classification(paper)
    else:
        classifier = DeepSeekClassifier(
            os.environ.get("DEEPSEEK_API_KEY", ""),
            os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash"),
            os.environ.get("DEEPSEEK_REVIEW_MODEL", "deepseek-v4-pro"),
            post=network_post,
        )
        for paper in candidates:
            paper.classification = classifier.classify(paper)
    in_scope = [
        p for p in candidates
        if p.classification.get("is_theoretical_holography")
        or p.classification.get("is_classical_gravity")
    ]
    store.record(in_scope)
    pushable = store.pending_v1()
    build_site(store.all_papers(), Path(docs_dir))
    site_url = os.environ.get("SITE_BASE_URL", "")
    sent = False
    if dry_run:
        payload = build_payload(pushable, "", site_base_url=site_url or "https://example.invalid/holo-arxiv")
        payload.pop("token", None)
        Path(preview_path).parent.mkdir(parents=True, exist_ok=True)
        Path(preview_path).write_text(json.dumps({"dry_run": True, "payload": payload}, ensure_ascii=False, indent=2), encoding="utf-8")
    elif pushable and pushplus_is_enabled():
        token = os.environ.get("PUSHPLUS_TOKEN", "")
        if not token:
            raise ValueError("有待推送论文，但缺少 PUSHPLUS_TOKEN")
        payload = build_payload(
            pushable, token, os.environ.get("PUSHPLUS_TOPIC", ""), site_url,
            os.environ.get("PUSHPLUS_CALLBACK_URL", ""),
        )
        result = send_push(payload, post=network_post)
        short_code = result["shortCode"]
        access_key = os.environ.get("PUSHPLUS_ACCESS_KEY", "")
        if access_key:
            delivery = query_send_result(short_code, access_key)
            print(f"PushPlus 最终投递状态: {json.dumps(delivery, ensure_ascii=False)}")
            if delivery["status"] == 3:
                raise RuntimeError(f"PushPlus 最终投递失败: {delivery.get('errorMessage', '')}")
            if delivery["status"] != 2:
                raise RuntimeError(f"PushPlus 最终投递尚未完成: status={delivery['status']}")
            result["status"] = "sent"
        else:
            print(f"PushPlus 已接单但未验证最终投递，shortCode={short_code}")
        store.mark_sent(pushable, short_code, result["status"])
        sent = True
    return {
        "fetched": len(papers), "candidates": len(candidates), "in_scope": len(in_scope),
        "pushable_v1": len(pushable), "sent": sent,
    }
