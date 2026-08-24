from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from html import escape
import json
from pathlib import Path

from .feed import Paper


CSS = """
:root{color-scheme:light;--ink:#172033;--muted:#64748b;--accent:#3157d5;--card:#fff;--bg:#f4f7fb}
*{box-sizing:border-box}body{margin:0;font-family:system-ui,-apple-system,"Segoe UI","Microsoft YaHei",sans-serif;background:var(--bg);color:var(--ink)}
header,main{max-width:1100px;margin:auto;padding:1.2rem}header h1{margin-bottom:.3rem}.muted{color:var(--muted)}
nav{display:flex;gap:1rem;flex-wrap:wrap;margin:1rem 0}nav a{color:var(--accent)}.grid{display:grid;gap:1rem}
.paper{background:var(--card);border:1px solid #dce4f1;border-radius:14px;padding:1.1rem;box-shadow:0 3px 15px #1831530a}
.badge{display:inline-block;background:#e8eeff;color:#2948aa;border-radius:999px;padding:.2rem .55rem;margin:.1rem;font-size:.82rem}
.filter{border:1px solid #b9c7e8;background:#fff;color:var(--accent);border-radius:999px;padding:.4rem .7rem;margin:.2rem;cursor:pointer}.paper[hidden]{display:none}
a{color:var(--accent)}h2{margin-top:2rem}.abstract{line-height:1.65}.meta{font-size:.9rem;color:var(--muted)}
@media(max-width:650px){header,main{padding:.8rem}.paper{padding:.85rem}h1{font-size:1.55rem}}
"""


def _classification(paper: Paper, key: str, default=""):
    return paper.classification.get(key, default)


def build_site(papers: list[Paper], docs_dir: Path) -> None:
    docs_dir = Path(docs_dir)
    docs_dir.mkdir(parents=True, exist_ok=True)
    ordered = sorted(papers, key=lambda p: (p.updated, p.arxiv_id), reverse=True)
    data = {"papers": [asdict(paper) for paper in ordered]}
    (docs_dir / "data.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    topic_counts = Counter(_classification(p, "primary_topic", "未分类") for p in ordered)
    date_counts = Counter((p.updated or p.published or "未知日期")[:10] for p in ordered)
    cards = []
    for p in ordered:
        c = p.classification
        tags = "".join(f'<span class="badge">{escape(str(tag))}</span>' for tag in c.get("focus_tags", []))
        categories = ", ".join(escape(x) for x in p.categories)
        authors = ", ".join(escape(x) for x in p.authors)
        cards.append(f"""<article class="paper" data-date="{escape((p.updated or p.published or '未知日期')[:10], quote=True)}" data-topic="{escape(c.get('primary_topic', '未分类'), quote=True)}">
<h3>{escape(c.get('title_zh', p.title))}</h3><p><strong>{escape(p.title)}</strong></p>
<p class="meta">{authors} · {categories} · v{p.version} · 更新 {escape((p.updated or '')[:10])}</p>
<p class="abstract"><strong>中文摘要：</strong>{escape(c.get('abstract_zh', '待分类'))}</p>
<p class="abstract"><strong>English:</strong> {escape(p.abstract)}</p>
<p><strong>一句话导读：</strong>{escape(c.get('one_liner', '待分类'))}</p>
<p><strong>相关度：</strong>{escape(c.get('relevance', 'unknown'))} — {escape(c.get('relevance_reason', ''))}</p>
<p>{tags}</p><p><a href="{escape(p.abs_url, quote=True)}">arXiv 摘要</a> · <a href="{escape(p.pdf_url, quote=True)}">PDF</a></p>
</article>""")
    date_list = "".join(f'<button class="filter" data-filter-kind="date" data-filter-value="{escape(day, quote=True)}">{escape(day)}：{count} 篇</button>' for day, count in sorted(date_counts.items(), reverse=True))
    topic_list = "".join(f'<button class="filter" data-filter-kind="topic" data-filter-value="{escape(topic, quote=True)}">{escape(topic)}：{count} 篇</button>' for topic, count in topic_counts.most_common())
    page = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>全息 arXiv 每日推送</title><style>{CSS}</style></head><body><header><h1>全息 arXiv 每日推送</h1><p class="muted">理论物理全息论文中文索引</p>
<nav><a href="#dates">按日期浏览</a><a href="#topics">按主题浏览</a><a href="#papers">每日完整论文</a></nav></header><main>
<section id="dates"><h2>按日期浏览</h2><div><button class="filter" data-filter-kind="all" data-filter-value="">显示全部</button>{date_list}</div></section><section id="topics"><h2>按主题浏览</h2><div>{topic_list}</div></section>
<section id="papers"><h2>每日完整论文</h2><div class="grid">{''.join(cards) or '<p>暂无记录。</p>'}</div></section></main>
<script>document.querySelectorAll('.filter').forEach(function(button){{button.addEventListener('click',function(){{var kind=button.dataset.filterKind,value=button.dataset.filterValue;document.querySelectorAll('.paper').forEach(function(card){{card.hidden=kind!=='all'&&card.dataset[kind]!==value;}});document.getElementById('papers').scrollIntoView({{behavior:'smooth'}});}});}});</script></body></html>"""
    (docs_dir / "index.html").write_text(page, encoding="utf-8")
