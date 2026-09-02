from datetime import datetime, timezone
import json
from pathlib import Path
import pytest

from holo_arxiv.feed import parse_atom
from holo_arxiv.pipeline import (
    CATEGORIES,
    ensure_current_batch,
    filter_announcements,
    pushplus_is_enabled,
    run_pipeline,
    scan_push_date,
    scan_time_gate,
)
from holo_arxiv.state import StateStore

FIXTURE = Path(__file__).parent / "fixtures" / "sample_atom.xml"


def test_categories_cover_hep_th_and_all_requested_cross_lists():
    assert CATEGORIES == [
        "hep-th", "gr-qc", "hep-ph", "hep-lat", "nucl-th", "math-ph", "quant-ph",
        "cond-mat.str-el", "cond-mat.supr-con", "cond-mat.quant-gas", "cond-mat.stat-mech",
    ]


def test_default_feed_processing_keeps_all_announced_items_but_manual_date_filters():
    papers = parse_atom(FIXTURE.read_bytes(), "hep-th")
    assert filter_announcements(papers, None) == papers
    assert [paper.versioned_id for paper in filter_announcements(papers, "2026-08-24")] == [
        "2608.01234v1", "hep-th/9901001v3"
    ]
    assert filter_announcements(papers, "2026-08-23") == []


def test_scan_push_date_uses_beijing_14_hour_batch_boundary():
    before_update = datetime(2026, 9, 2, 5, 0, tzinfo=timezone.utc)   # 13:00 北京
    after_update = datetime(2026, 9, 2, 6, 0, tzinfo=timezone.utc)    # 14:00 北京
    assert scan_push_date(before_update) == "2026-09-01"
    assert scan_push_date(after_update) == "2026-09-02"
    assert scan_time_gate(before_update) is False
    assert scan_time_gate(after_update) is True


def test_current_batch_guard_rejects_empty_stale_or_newer_batches():
    papers = parse_atom(FIXTURE.read_bytes(), "hep-th")
    with pytest.raises(RuntimeError, match="旧日期"):
        ensure_current_batch(papers, "2026-08-25")
    with pytest.raises(RuntimeError, match="新日期"):
        ensure_current_batch(papers, "2026-08-23")
    with pytest.raises(RuntimeError, match="没有抓取"):
        ensure_current_batch([], "2026-08-24")
    ensure_current_batch(papers, "2026-08-24")


def test_pushplus_requires_explicit_true_switch():
    assert pushplus_is_enabled({}) is False
    assert pushplus_is_enabled({"PUSHPLUS_ENABLED": "false"}) is False
    assert pushplus_is_enabled({"PUSHPLUS_ENABLED": "TRUE"}) is True


def test_pushed_on_guards_repeat_push_same_day(tmp_path):
    store = StateStore(tmp_path / "state.json")
    assert store.pushed_on("2026-09-02") is False
    store.mark_sent([], push_date="2026-09-02")
    assert store.pushed_on("2026-09-02") is True
    assert store.pushed_on("2026-09-03") is False


def test_dry_run_skips_already_recorded_versions_before_model_calls(tmp_path):
    def forbidden_network(*args, **kwargs):
        raise AssertionError("dry-run 不得访问网络")

    first = run_pipeline(
        dry_run=True,
        fixture=FIXTURE,
        state_path=tmp_path / "data" / "state.json",
        docs_dir=tmp_path / "docs",
        preview_path=tmp_path / "first-preview.json",
        network_get=forbidden_network,
        network_post=forbidden_network,
    )
    second = run_pipeline(
        dry_run=True,
        fixture=FIXTURE,
        state_path=tmp_path / "data" / "state.json",
        docs_dir=tmp_path / "docs",
        preview_path=tmp_path / "second-preview.json",
        network_get=forbidden_network,
        network_post=forbidden_network,
    )
    assert first["candidates"] == 2
    assert second["candidates"] == 0
    assert second["in_scope"] == 0
    assert second["pushable_v1"] == 1


def test_dry_run_is_offline_end_to_end_and_writes_preview_site_state(tmp_path):
    def forbidden_network(*args, **kwargs):
        raise AssertionError("dry-run 不得访问网络")

    result = run_pipeline(
        dry_run=True,
        fixture=FIXTURE,
        state_path=tmp_path / "data" / "state.json",
        docs_dir=tmp_path / "docs",
        preview_path=tmp_path / "pushplus-preview.json",
        network_get=forbidden_network,
        network_post=forbidden_network,
    )
    assert result == {"fetched": 2, "candidates": 2, "in_scope": 2, "pushable_v1": 1, "sent": False}
    assert (tmp_path / "docs" / "index.html").exists()
    assert (tmp_path / "docs" / "data.json").exists()
    state = json.loads((tmp_path / "data" / "state.json").read_text(encoding="utf-8"))
    assert state["papers"]["hep-th/9901001"]["versions"] == [3]
    preview = json.loads((tmp_path / "pushplus-preview.json").read_text(encoding="utf-8"))
    assert preview["dry_run"] is True
    assert "token" not in preview["payload"]
    assert "今日候选共 1 篇" in preview["payload"]["content"]
