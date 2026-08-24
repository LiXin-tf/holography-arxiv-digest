from __future__ import annotations

import json
import re
from typing import Callable

import requests

from .feed import Paper

TOPICS = (
    "AdS/CFT 基础与字典",
    "黑洞/量子引力/信息",
    "纠缠/复杂度/量子信息",
    "全息凝聚态/超流超导/强关联",
    "全息 QCD/核物理",
    "非平衡/热化/输运/混沌/QNM",
    "相变/气泡成核/引力热力学",
    "非均匀态/孤子/涡旋/畴壁",
    "dS/天球/平直时空/BMS-Carroll",
    "JT/SYK/AdS2/矩阵模型",
    "高自旋/非相对论/hyperscaling",
    "宇宙学/膜世界/其他",
)
FOCUS_TAGS = (
    "全息超流超导",
    "p波与多分量序参量",
    "畴壁/孤子/涡旋/非均匀",
    "multi-trace",
    "相变与气泡成核",
    "QNM与非线性演化",
    "冷原子/双组分BEC/凝聚态实验启发",
)
REQUIRED = {
    "is_theoretical_holography", "confidence", "primary_topic", "secondary_topics",
    "title_zh", "abstract_zh", "one_liner", "keywords", "importance",
    "relevance", "relevance_reason", "focus_tags",
}


class ClassificationError(ValueError):
    pass


def build_chat_url(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    if base.endswith("/v1"):
        return f"{base}/chat/completions"
    return f"{base}/v1/chat/completions"


def parse_classification(content: str) -> dict:
    cleaned = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", content, flags=re.I)
    try:
        result = json.loads(cleaned)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ClassificationError("模型未返回有效 JSON") from exc
    if not isinstance(result, dict) or set(result) != REQUIRED:
        raise ClassificationError("模型 JSON 字段必须与模式完全一致")
    if not isinstance(result["is_theoretical_holography"], bool):
        raise ClassificationError("is_theoretical_holography 必须是布尔值")
    confidence = result["confidence"]
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
        raise ClassificationError("confidence 必须在 0 到 1 之间")
    if result["primary_topic"] not in TOPICS:
        raise ClassificationError("primary_topic 不在分类体系内")
    if not isinstance(result["secondary_topics"], list) or any(x not in TOPICS for x in result["secondary_topics"]):
        raise ClassificationError("secondary_topics 不在分类体系内")
    if result["importance"] not in {"low", "normal", "high"}:
        raise ClassificationError("importance 无效")
    if result["relevance"] not in {"low", "medium", "high"}:
        raise ClassificationError("relevance 无效")
    for key in ("keywords", "focus_tags"):
        if not isinstance(result[key], list) or any(not isinstance(item, str) or not item.strip() for item in result[key]):
            raise ClassificationError(f"{key} 必须是非空文本数组")
    if any(x not in FOCUS_TAGS for x in result["focus_tags"]):
        raise ClassificationError("focus_tags 不在用户重点标签内")
    for key in ("title_zh", "abstract_zh", "one_liner", "relevance_reason"):
        if not isinstance(result[key], str) or not result[key].strip():
            raise ClassificationError(f"{key} 必须是非空文本")
    return result


SYSTEM_PROMPT = f"""你是理论物理 arXiv 摘要分类器。只可依据提供的题目和摘要，不得杜撰摘要之外的方法、结论或重要性。
输出单个 JSON 对象，不要 markdown。字段严格为：is_theoretical_holography(bool), confidence(0..1),
primary_topic(下列之一), secondary_topics(数组), title_zh, abstract_zh, one_liner, keywords(数组),
importance(low|normal|high), relevance(low|medium|high), relevance_reason, focus_tags(数组)。
主题：{json.dumps(TOPICS, ensure_ascii=False)}
用户重点标签（不同研究支线必须分开，不要合并自造标签）：{json.dumps(FOCUS_TAGS, ensure_ascii=False)}
若摘要没有足够信息，应明确保守表述并降低置信度。"""


class DeepSeekClassifier:
    def __init__(self, api_key: str, base_url: str, model: str, review_model: str,
                 post: Callable | None = None, timeout: int = 60):
        if not api_key:
            raise ValueError("缺少 DEEPSEEK_API_KEY")
        self.api_key = api_key
        self.url = build_chat_url(base_url)
        self.model = model
        self.review_model = review_model
        self.timeout = timeout
        self.post = post or self._requests_post

    def _requests_post(self, url: str, **kwargs) -> dict:
        response = requests.post(url, timeout=self.timeout, **kwargs)
        response.raise_for_status()
        return response.json()

    def _call(self, paper: Paper, model: str, review_context: str = "") -> dict:
        user = f"arXiv: {paper.versioned_id}\n题目: {paper.title}\n摘要: {paper.abstract}"
        if review_context:
            user += f"\n请独立复核。上一结果或错误仅供定位：{review_context}"
        payload = {
            "model": model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}],
        }
        data = self.post(self.url, headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}, json=payload)
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ClassificationError("API 响应格式无效") from exc
        return parse_classification(content)

    def classify(self, paper: Paper) -> dict:
        try:
            result = self._call(paper, self.model)
        except ClassificationError as exc:
            return self._call(paper, self.review_model, str(exc))
        if result["confidence"] < 0.75 or result["importance"] == "high":
            return self._call(paper, self.review_model, json.dumps(result, ensure_ascii=False))
        return result
