from __future__ import annotations

from collections import Counter
from html import escape
from typing import Callable

import requests

from .feed import Paper

PUSH_URL = "https://www.pushplus.plus/send"


def build_payload(papers: list[Paper], token: str, topic: str = "", site_base_url: str = "",
                  callback_url: str = "") -> dict:
    counts = Counter(p.classification.get("primary_topic", "未分类") for p in papers)
    lines = [f"<p>今日候选共 {len(papers)} 篇。</p>", "<h3>主题目录</h3><ul>"]
    lines.extend(f"<li>{escape(name)}：{count} 篇</li>" for name, count in counts.most_common())
    lines.append("</ul>")
    featured = [p for p in papers if p.classification.get("importance") == "high" or p.classification.get("relevance") == "high"]
    if featured:
        lines.append("<h3>重点推荐</h3>")
        display = featured[:12]
    else:
        lines.append("<h3>今日收录</h3>")
        display = papers[:8]
    for paper in display:
        c = paper.classification
        lines.append(
            f'<p><strong>{escape(c.get("title_zh", paper.title))}</strong><br>'
            f'{escape(c.get("one_liner", ""))}<br>'
            f'<a href="{escape(paper.abs_url, quote=True)}">arXiv {escape(paper.versioned_id)}</a></p>'
        )
    if site_base_url:
        lines.append(f'<p><a href="{escape(site_base_url, quote=True)}">查看完整网站与历史记录</a></p>')
    content = "".join(lines)
    if len(content) > 11900:
        content = content[:11800] + "<p>内容已截断，请访问网站查看完整目录。</p>"
    payload = {
        "token": token,
        "title": f"全息与经典引力 arXiv 每日推送（{len(papers)} 篇）",
        "content": content,
        "template": "html",
        "channel": "wechat",
    }
    if topic:
        payload["topic"] = topic
    if callback_url:
        payload["callbackUrl"] = callback_url
    return payload


def send_push(payload: dict, post: Callable | None = None, timeout: int = 30) -> dict:
    if post is None:
        def post(url, **kwargs):
            response = requests.post(url, timeout=timeout, **kwargs)
            response.raise_for_status()
            return response.json()
    data = post(PUSH_URL, json=payload, headers={"Content-Type": "application/json"})
    if data.get("code") != 200:
        raise RuntimeError(f"PushPlus 拒绝请求: {data.get('msg', 'unknown error')}")
    return {"status": "accepted_pending_verification", "shortCode": data.get("data")}


def query_send_result(short_code: str, access_key: str, get: Callable | None = None,
                     timeout: int = 30) -> dict:
    """Query PushPlus asynchronous delivery status using a short-lived AccessKey."""
    if not short_code:
        raise ValueError("缺少 PushPlus shortCode")
    if not access_key:
        raise ValueError("查询最终状态需要 PUSHPLUS_ACCESS_KEY")
    if get is None:
        get = requests.get
    url = f"https://www.pushplus.plus/api/open/message/sendMessageResult?shortCode={short_code}"
    response = get(url, headers={"access-key": access_key}, timeout=timeout)
    if hasattr(response, "raise_for_status"):
        response.raise_for_status()
        data = response.json()
    else:
        data = response
    if data.get("code") != 200:
        raise RuntimeError(f"PushPlus 状态查询失败: {data.get('msg', 'unknown error')}")
    result = data.get("data") or {}
    return {
        "status": result.get("status"),
        "errorMessage": result.get("errorMessage", ""),
    }
