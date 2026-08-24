import json
from pathlib import Path

from holo_arxiv.feed import parse_atom
from holo_arxiv.pipeline import CATEGORIES, filter_announcements, pushplus_is_enabled, run_pipeline

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


def test_pushplus_requires_explicit_true_switch():
    assert pushplus_is_enabled({}) is False
    assert pushplus_is_enabled({"PUSHPLUS_ENABLED": "false"}) is False
    assert pushplus_is_enabled({"PUSHPLUS_ENABLED": "TRUE"}) is True


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
    assert result == {"fetched": 2, "candidates": 2, "holography": 2, "pushable_v1": 1, "sent": False}
    assert (tmp_path / "docs" / "index.html").exists()
    assert (tmp_path / "docs" / "data.json").exists()
    state = json.loads((tmp_path / "data" / "state.json").read_text(encoding="utf-8"))
    assert state["papers"]["hep-th/9901001"]["versions"] == [3]
    preview = json.loads((tmp_path / "pushplus-preview.json").read_text(encoding="utf-8"))
    assert preview["dry_run"] is True
    assert "token" not in preview["payload"]
    assert "今日候选共 1 篇" in preview["payload"]["content"]
