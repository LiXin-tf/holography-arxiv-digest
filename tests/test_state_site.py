import json
from datetime import date
from pathlib import Path

import pytest

from holo_arxiv.feed import Paper
from holo_arxiv.site import build_site
from holo_arxiv.size_guard import FileSizeLimitError, check_file_sizes
from holo_arxiv.state import StateStore, dedupe_papers, paper_to_dict


def make_paper(
    arxiv_id="2608.01234",
    version=1,
    title="Title",
    category="hep-th",
    day="2026-08-24",
):
    p = Paper(
        arxiv_id,
        version,
        title,
        "Abstract",
        ["<b>Alice</b>"],
        [category],
        f"{day}T01:00:00Z",
        f"{day}T01:00:00Z",
        category,
    )
    p.abs_url = f"https://arxiv.org/abs/{arxiv_id}v{version}"
    p.pdf_url = f"https://arxiv.org/pdf/{arxiv_id}v{version}"
    p.classification = {
        "is_theoretical_holography": True,
        "confidence": 0.9,
        "primary_topic": "全息凝聚态/超流超导/强关联",
        "secondary_topics": [],
        "title_zh": "中文标题",
        "abstract_zh": "中文摘要",
        "one_liner": "导读",
        "keywords": ["全息"],
        "importance": "normal",
        "relevance": "high",
        "relevance_reason": "相关",
        "focus_tags": ["全息超流超导"],
    }
    return p


def test_dedupe_by_arxiv_id_keeps_latest_and_merges_categories():
    a = make_paper(category="hep-th")
    b = make_paper(category="gr-qc")
    result = dedupe_papers([a, b])
    assert len(result) == 1
    assert result[0].categories == ["hep-th", "gr-qc"]


def test_state_is_lightweight_and_records_versions_in_monthly_archives(tmp_path):
    path = tmp_path / "data" / "state.json"
    store = StateStore(path)
    first = make_paper(version=1, day="2026-08-24")
    revision = make_paper(version=2, day="2026-09-02")

    assert [p.versioned_id for p in store.record([first])] == ["2608.01234v1"]
    store.mark_sent([first], short_code="abc")
    assert store.record([first]) == []
    assert store.record([revision]) == []

    saved = json.loads(path.read_text(encoding="utf-8"))
    record = saved["papers"]["2608.01234"]
    assert saved["schema_version"] == 2
    assert record == {
        "latest_version": 2,
        "versions": [1, 2],
        "sent_versions": [1],
        "version_months": {"1": "2026-08", "2": "2026-09"},
    }
    assert set(record) == {"latest_version", "versions", "sent_versions", "version_months"}
    assert (tmp_path / "data" / "archive" / "2026-08.json").exists()
    assert (tmp_path / "data" / "archive" / "2026-09.json").exists()
    august = json.loads((tmp_path / "data" / "archive" / "2026-08.json").read_text(encoding="utf-8"))
    september = json.loads((tmp_path / "data" / "archive" / "2026-09.json").read_text(encoding="utf-8"))
    assert august["papers"]["2608.01234v1"]["version"] == 1
    assert september["papers"]["2608.01234v2"]["version"] == 2
    assert [p.version for p in store.all_papers()] == [1, 2]
    assert saved["pushes"][-1]["shortCode"] == "abc"


def test_legacy_monolithic_state_migrates_without_losing_papers(tmp_path):
    path = tmp_path / "data" / "state.json"
    path.parent.mkdir(parents=True)
    paper = make_paper()
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "papers": {
                    paper.arxiv_id: {
                        "latest_version": 1,
                        "versions": [1],
                        "sent_versions": [1],
                        "version_records": {"1": paper_to_dict(paper)},
                        "paper": paper_to_dict(paper),
                    }
                },
                "pushes": [{"status": "accepted_pending_verification", "paper_ids": [paper.versioned_id]}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    store = StateStore(path)
    migrated = json.loads(path.read_text(encoding="utf-8"))
    assert migrated["schema_version"] == 2
    assert migrated["papers"][paper.arxiv_id]["version_months"] == {"1": "2026-08"}
    assert "paper" not in migrated["papers"][paper.arxiv_id]
    assert [p.versioned_id for p in store.all_papers()] == [paper.versioned_id]
    assert (path.parent / "archive" / "2026-08.json").exists()


def test_site_keeps_only_recent_30_days_on_home_and_builds_month_archives(tmp_path):
    recent = make_paper(arxiv_id="2608.00001", title="Recent", day="2026-08-24")
    old = make_paper(arxiv_id="2606.00001", title="Old archive paper", day="2026-06-01")
    old.classification["title_zh"] = "旧论文"
    build_site([old, recent], tmp_path, today=date(2026, 8, 24), recent_days=30)

    home = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert "Recent" in home
    assert "Old archive paper" not in home
    assert "历史归档" in home
    assert 'href="archive/index.html"' in home

    latest = json.loads((tmp_path / "data.json").read_text(encoding="utf-8"))
    latest_alias = json.loads((tmp_path / "data" / "latest.json").read_text(encoding="utf-8"))
    assert [p["arxiv_id"] for p in latest["papers"]] == ["2608.00001"]
    assert latest == latest_alias

    june = json.loads((tmp_path / "data" / "2026-06.json").read_text(encoding="utf-8"))
    august = json.loads((tmp_path / "data" / "2026-08.json").read_text(encoding="utf-8"))
    assert [p["arxiv_id"] for p in june["papers"]] == ["2606.00001"]
    assert [p["arxiv_id"] for p in august["papers"]] == ["2608.00001"]
    assert "Old archive paper" in (tmp_path / "archive" / "2026-06.html").read_text(encoding="utf-8")
    archive_index = (tmp_path / "archive" / "index.html").read_text(encoding="utf-8")
    assert "2026 年" in archive_index
    assert "2026-06.html" in archive_index and "2026-08.html" in archive_index


def test_site_escapes_untrusted_model_and_paper_text(tmp_path):
    paper = make_paper(title="<script>alert(1)</script>")
    paper.classification["abstract_zh"] = "<img src=x onerror=alert(2)>"
    build_site([paper], tmp_path, today=date(2026, 8, 24))
    page = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page
    assert "<img src=x" not in page
    assert "按日期浏览" in page and "按主题浏览" in page
    assert 'data-filter-kind="date"' in page and 'data-filter-kind="topic"' in page
    assert "overflow-wrap:anywhere" in page and "min-width:0" in page


def test_size_guard_warns_and_blocks_before_github_file_limit(tmp_path):
    small = tmp_path / "small.json"
    warning = tmp_path / "warning.json"
    hard = tmp_path / "hard.json"
    small.write_bytes(b"x" * 5)
    warning.write_bytes(b"x" * 11)
    hard.write_bytes(b"x" * 21)

    result = check_file_sizes([tmp_path], warn_bytes=10, hard_bytes=20)
    assert result["largest_file"] == str(hard)
    assert any(item["path"] == str(warning) for item in result["warnings"])
    with pytest.raises(FileSizeLimitError, match="hard.json"):
        check_file_sizes([tmp_path], warn_bytes=10, hard_bytes=20, fail_on_hard=True)
