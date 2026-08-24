from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
from html import escape
import json
from pathlib import Path

from .feed import Paper


CSS = """
:root{color-scheme:light;--ink:#172033;--muted:#64748b;--accent:#3157d5;--card:#fff;--bg:#f4f7fb;--border:#dce4f1}
*{box-sizing:border-box}html,body{max-width:100%;overflow-x:hidden}body{margin:0;font-family:system-ui,-apple-system,"Segoe UI","Microsoft YaHei",sans-serif;background:var(--bg);color:var(--ink);overflow-wrap:anywhere;word-break:break-word}
header,main{max-width:1100px;margin:auto;padding:1.2rem}header h1{margin-bottom:.3rem}.muted{color:var(--muted)}
nav{display:flex;gap:1rem;flex-wrap:wrap;margin:1rem 0}nav a,a{color:var(--accent)}.grid{display:grid;gap:1rem}
.paper,.archive-card{min-width:0;max-width:100%;background:var(--card);border:1px solid var(--border);border-radius:14px;padding:1.1rem;box-shadow:0 3px 15px #1831530a}
.archive-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:1rem}.archive-card h3{margin-top:0}
.badge{display:inline-block;background:#e8eeff;color:#2948aa;border-radius:999px;padding:.2rem .55rem;margin:.1rem;font-size:.82rem}
.filter{border:1px solid #b9c7e8;background:#fff;color:var(--accent);border-radius:999px;padding:.4rem .7rem;margin:.2rem;cursor:pointer}.paper[hidden]{display:none}
h2{margin-top:2rem}.abstract{line-height:1.65}.meta{font-size:.9rem;color:var(--muted)}
.notice{background:#eef3ff;border:1px solid #cad7ff;border-radius:12px;padding:.8rem 1rem;line-height:1.6}
@media(max-width:650px){header,main{padding:.8rem}.paper{padding:.85rem}h1{font-size:1.55rem}}
"""


def _classification(paper: Paper, key: str, default=""):
    return paper.classification.get(key, default)


def _paper_day(paper: Paper) -> str:
    return (paper.updated or paper.published or "未知日期")[:10]


def _paper_month(paper: Paper) -> str:
    return _paper_day(paper)[:7]


def _parse_day(paper: Paper) -> date | None:
    try:
        return date.fromisoformat(_paper_day(paper))
    except ValueError:
        return None


def _json_payload(papers: list[Paper]) -> dict:
    ordered = sorted(
        papers,
        key=lambda p: (p.updated or p.published, p.arxiv_id, p.version),
        reverse=True,
    )
    return {"papers": [asdict(paper) for paper in ordered]}


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _paper_cards(papers: list[Paper]) -> str:
    cards: list[str] = []
    for paper in sorted(
        papers,
        key=lambda p: (p.updated or p.published, p.arxiv_id, p.version),
        reverse=True,
    ):
        classification = paper.classification
        tags = "".join(
            f'<span class="badge">{escape(str(tag))}</span>'
            for tag in classification.get("focus_tags", [])
        )
        categories = ", ".join(escape(item) for item in paper.categories)
        authors = ", ".join(escape(item) for item in paper.authors)
        day = _paper_day(paper)
        topic = classification.get("primary_topic", "未分类")
        cards.append(
            f"""<article class="paper" data-date="{escape(day, quote=True)}" data-topic="{escape(topic, quote=True)}">
<h3>{escape(classification.get('title_zh', paper.title))}</h3><p><strong>{escape(paper.title)}</strong></p>
<p class="meta">{authors} · {categories} · v{paper.version} · 更新 {escape(day)}</p>
<p class="abstract"><strong>中文摘要：</strong>{escape(classification.get('abstract_zh', '待分类'))}</p>
<p class="abstract"><strong>English:</strong> {escape(paper.abstract)}</p>
<p><strong>一句话导读：</strong>{escape(classification.get('one_liner', '待分类'))}</p>
<p><strong>相关度：</strong>{escape(classification.get('relevance', 'unknown'))} — {escape(classification.get('relevance_reason', ''))}</p>
<p>{tags}</p><p><a href="{escape(paper.abs_url, quote=True)}">arXiv 摘要</a> · <a href="{escape(paper.pdf_url, quote=True)}">PDF</a></p>
</article>"""
        )
    return "".join(cards) or "<p>暂无记录。</p>"


def _filter_controls(papers: list[Paper]) -> tuple[str, str]:
    topic_counts = Counter(_classification(paper, "primary_topic", "未分类") for paper in papers)
    date_counts = Counter(_paper_day(paper) for paper in papers)
    date_list = "".join(
        f'<button class="filter" data-filter-kind="date" data-filter-value="{escape(day, quote=True)}">{escape(day)}：{count} 篇</button>'
        for day, count in sorted(date_counts.items(), reverse=True)
    )
    topic_list = "".join(
        f'<button class="filter" data-filter-kind="topic" data-filter-value="{escape(topic, quote=True)}">{escape(topic)}：{count} 篇</button>'
        for topic, count in topic_counts.most_common()
    )
    return date_list, topic_list


def _html_shell(title: str, subtitle: str, body: str, *, root_prefix: str = "") -> str:
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)}</title><style>{CSS}</style></head><body><header><h1>{escape(title)}</h1><p class="muted">{escape(subtitle)}</p>
<nav><a href="{root_prefix}index.html">最近 30 天</a><a href="{root_prefix}archive/index.html">历史归档</a></nav></header><main>{body}</main></body></html>"""


def _listing_page(title: str, subtitle: str, papers: list[Paper], *, root_prefix: str) -> str:
    date_list, topic_list = _filter_controls(papers)
    body = f"""<section id="dates"><h2>按日期浏览</h2><div><button class="filter" data-filter-kind="all" data-filter-value="">显示全部</button>{date_list}</div></section>
<section id="topics"><h2>按主题浏览</h2><div>{topic_list}</div></section>
<section id="papers"><h2>论文列表</h2><div class="grid">{_paper_cards(papers)}</div></section>
<script>document.querySelectorAll('.filter').forEach(function(button){{button.addEventListener('click',function(){{var kind=button.dataset.filterKind,value=button.dataset.filterValue;document.querySelectorAll('.paper').forEach(function(card){{card.hidden=kind!=='all'&&card.dataset[kind]!==value;}});document.getElementById('papers').scrollIntoView({{behavior:'smooth'}});}});}});</script>"""
    return _html_shell(title, subtitle, body, root_prefix=root_prefix)


def build_site(
    papers: list[Paper],
    docs_dir: Path,
    *,
    today: date | None = None,
    recent_days: int = 30,
) -> None:
    docs_dir = Path(docs_dir)
    docs_dir.mkdir(parents=True, exist_ok=True)
    today = today or datetime.now(timezone.utc).date()
    cutoff = today - timedelta(days=max(recent_days, 1) - 1)
    ordered = sorted(
        papers,
        key=lambda p: (p.updated or p.published, p.arxiv_id, p.version),
        reverse=True,
    )
    recent = [
        paper
        for paper in ordered
        if (parsed := _parse_day(paper)) is not None and cutoff <= parsed <= today
    ]

    latest_payload = _json_payload(recent)
    _write_json(docs_dir / "data.json", latest_payload)
    _write_json(docs_dir / "data" / "latest.json", latest_payload)

    by_month: dict[str, list[Paper]] = defaultdict(list)
    for paper in ordered:
        by_month[_paper_month(paper)].append(paper)
    for month, month_papers in by_month.items():
        _write_json(docs_dir / "data" / f"{month}.json", _json_payload(month_papers))

    date_list, topic_list = _filter_controls(recent)
    home_body = f"""<p class="notice">首页只加载最近 {recent_days} 天，共 {len(recent)} 条版本记录。更早论文请进入<a href="archive/index.html">历史归档</a>按年份和月份查看。</p>
<section id="dates"><h2>按日期浏览</h2><div><button class="filter" data-filter-kind="all" data-filter-value="">显示全部</button>{date_list}</div></section>
<section id="topics"><h2>按主题浏览</h2><div>{topic_list}</div></section>
<section id="papers"><h2>最近 {recent_days} 天论文</h2><div class="grid">{_paper_cards(recent)}</div></section>
<script>document.querySelectorAll('.filter').forEach(function(button){{button.addEventListener('click',function(){{var kind=button.dataset.filterKind,value=button.dataset.filterValue;document.querySelectorAll('.paper').forEach(function(card){{card.hidden=kind!=='all'&&card.dataset[kind]!==value;}});document.getElementById('papers').scrollIntoView({{behavior:'smooth'}});}});}});</script>"""
    (docs_dir / "index.html").write_text(
        _html_shell("全息 arXiv 每日推送", "理论物理全息论文中文索引", home_body),
        encoding="utf-8",
    )

    archive_dir = docs_dir / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    years: dict[str, list[str]] = defaultdict(list)
    for month, month_papers in sorted(by_month.items(), reverse=True):
        year = month[:4]
        years[year].append(month)
        page = _listing_page(
            f"{month} 全息 arXiv 归档",
            f"本月共 {len(month_papers)} 条版本记录",
            month_papers,
            root_prefix="../",
        )
        (archive_dir / f"{month}.html").write_text(page, encoding="utf-8")

    year_cards: list[str] = []
    for year, months in sorted(years.items(), reverse=True):
        links = "".join(
            f'<li><a href="{escape(month, quote=True)}.html">{escape(month)}</a>：{len(by_month[month])} 条</li>'
            for month in sorted(months, reverse=True)
        )
        year_body = f'<section><h2>{escape(year)} 年</h2><ul>{links}</ul></section>'
        (archive_dir / f"{year}.html").write_text(
            _html_shell(f"{year} 年全息 arXiv 归档", "按月份查看", year_body, root_prefix="../"),
            encoding="utf-8",
        )
        year_cards.append(
            f'<article class="archive-card"><h3><a href="{escape(year, quote=True)}.html">{escape(year)} 年</a></h3><ul>{links}</ul></article>'
        )

    archive_body = f'<p class="notice">历史论文按月拆分保存，避免单个 JSON 和 HTML 文件无限增长。</p><div class="archive-grid">{"".join(year_cards) or "<p>暂无归档。</p>"}</div>'
    (archive_dir / "index.html").write_text(
        _html_shell("历史归档", "按年份和月份查看全息论文", archive_body, root_prefix="../"),
        encoding="utf-8",
    )
