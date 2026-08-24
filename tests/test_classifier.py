import json
import pytest

from holo_arxiv.classifier import (
    ClassificationError,
    DeepSeekClassifier,
    build_chat_url,
    parse_classification,
)
from holo_arxiv.feed import Paper


def valid_result(**overrides):
    result = {
        "is_theoretical_holography": True,
        "confidence": 0.92,
        "primary_topic": "全息凝聚态/超流超导/强关联",
        "secondary_topics": ["非均匀态/孤子/涡旋/畴壁"],
        "title_zh": "全息超流中的涡旋",
        "abstract_zh": "本文研究全息超流中的涡旋动力学。",
        "one_liner": "关注涡旋的非线性演化。",
        "keywords": ["全息超流", "涡旋"],
        "importance": "high",
        "relevance": "high",
        "relevance_reason": "直接涉及用户重点标签：涡旋与非线性演化。",
        "focus_tags": ["畴壁/孤子/涡旋/非均匀", "QNM与非线性演化"],
    }
    result.update(overrides)
    return result


def sample_paper():
    return Paper("2608.01234", 1, "Vortices", "We study vortices only.", ["A"], ["hep-th"], "", "", "hep-th")


def test_chat_url_normalization_never_duplicates_v1():
    assert build_chat_url("https://api.deepseek.com") == "https://api.deepseek.com/v1/chat/completions"
    assert build_chat_url("https://api.deepseek.com/v1/") == "https://api.deepseek.com/v1/chat/completions"
    assert build_chat_url("https://proxy.example/openai/v1/chat/completions") == "https://proxy.example/openai/v1/chat/completions"


def test_model_json_is_parsed_and_schema_validated():
    parsed = parse_classification("```json\n" + json.dumps(valid_result(), ensure_ascii=False) + "\n```")
    assert parsed["primary_topic"] == "全息凝聚态/超流超导/强关联"
    assert parsed["focus_tags"] == ["畴壁/孤子/涡旋/非均匀", "QNM与非线性演化"]


def test_invalid_or_hallucinated_schema_is_rejected():
    with pytest.raises(ClassificationError):
        parse_classification(json.dumps(valid_result(confidence=1.2)))
    with pytest.raises(ClassificationError):
        parse_classification(json.dumps(valid_result(primary_topic="不存在的主题"), ensure_ascii=False))
    with pytest.raises(ClassificationError):
        parse_classification(json.dumps(valid_result(unexpected="不能接受额外字段"), ensure_ascii=False))
    with pytest.raises(ClassificationError):
        parse_classification(json.dumps(valid_result(keywords=[1, 2]), ensure_ascii=False))


def test_only_low_confidence_invalid_json_or_important_results_are_reviewed():
    calls = []
    responses = [valid_result(confidence=0.60), valid_result(confidence=0.96)]

    def post(url, **kwargs):
        calls.append((url, kwargs["json"]["model"]))
        value = responses.pop(0)
        return {"choices": [{"message": {"content": json.dumps(value, ensure_ascii=False)}}]}

    classifier = DeepSeekClassifier("secret", "https://api.deepseek.com/v1", "deepseek-v4-flash", "deepseek-v4-pro", post=post)
    result = classifier.classify(sample_paper())
    assert result["confidence"] == 0.96
    assert [model for _, model in calls] == ["deepseek-v4-flash", "deepseek-v4-pro"]
    assert all(url == "https://api.deepseek.com/v1/chat/completions" for url, _ in calls)


def test_high_confidence_normal_result_skips_review():
    calls = []
    def post(url, **kwargs):
        calls.append(kwargs["json"]["model"])
        return {"choices": [{"message": {"content": json.dumps(valid_result(importance="normal"), ensure_ascii=False)}}]}
    classifier = DeepSeekClassifier("secret", "https://api.deepseek.com", "main", "review", post=post)
    classifier.classify(sample_paper())
    assert calls == ["main"]
