import json
from pathlib import Path

from holo_arxiv.feed import Paper
from holo_arxiv.site import build_site
from holo_arxiv.state import StateStore, dedupe_papers


def make_paper(arxiv_id="2608.01234", version=1, title="Title", category="hep-th"):
    p = Paper(arxiv_id, version, title, "Abstract", ["<b>Alice</b>"], [category],
              "2026-08-24T01:00:00Z", "2026-08-24T01:00:00Z", category)
    p.classification = {
        "is_theoretical_holography": True, "confidence": 0.9,
        "primary_topic": "全息凝聚态/超流超导/强关联", "secondary_topics": [],
        "title_zh": "中文标题", "abstract_zh": "中文摘要", "one_liner": "导读",
        "keywords": ["全息"], "importance": "normal", "relevance": "high",
        "relevance_reason": "相关", "focus_tags": ["全息超流超导"],
    }
    return p


def test_dedupe_by_arxiv_id_keeps_latest_and_merges_categories():
    a = make_paper(category="hep-th")
    b = make_paper(category="gr-qc")
    result = dedupe_papers([a, b])
    assert len(result) == 1
    assert result[0].categories == ["hep-th", "gr-qc"]


def test_state_records_revisions_but_only_unsent_v1_is_pushable(tmp_path):
    path = tmp_path / "state.json"
    store = StateStore(path)
    first = make_paper(version=1)
    revision = make_paper(version=2)
    assert [p.versioned_id for p in store.record([first])] == ["2608.01234v1"]
    store.mark_sent([first], short_code="abc")
    assert store.record([first]) == []
    assert store.record([revision]) == []
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["papers"]["2608.01234"]["latest_version"] == 2
    assert saved["papers"]["2608.01234"]["versions"] == [1, 2]
    assert sorted(saved["papers"]["2608.01234"]["version_records"]) == ["1", "2"]
    assert [p.version for p in store.all_papers()] == [1, 2]
    assert saved["papers"]["2608.01234"]["sent_versions"] == [1]
    assert saved["pushes"][-1]["shortCode"] == "abc"


def test_site_escapes_untrusted_model_and_paper_text_and_writes_data(tmp_path):
    paper = make_paper(title="<script>alert(1)</script>")
    paper.classification["abstract_zh"] = "<img src=x onerror=alert(2)>"
    build_site([paper], tmp_path)
    page = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page
    assert "<img src=x" not in page
    assert "按日期浏览" in page and "按主题浏览" in page
    assert 'data-filter-kind="date"' in page and 'data-filter-kind="topic"' in page
    assert 'class="paper" data-date=' in page
    data = json.loads((tmp_path / "data.json").read_text(encoding="utf-8"))
    assert data["papers"][0]["title"] == "<script>alert(1)</script>"
    assert data["papers"][0]["version"] == 1
