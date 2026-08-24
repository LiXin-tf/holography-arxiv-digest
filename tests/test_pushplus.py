import pytest

from holo_arxiv.pushplus import build_payload, send_push
from tests.test_state_site import make_paper


def test_payload_contains_counts_recommendations_site_and_optional_topic_callback():
    papers = [make_paper(), make_paper(arxiv_id="2608.00002")]
    papers[0].classification["importance"] = "high"
    payload = build_payload(papers, "token", "group", "https://example.github.io/site", "https://callback.example/push")
    assert payload["token"] == "token"
    assert payload["topic"] == "group"
    assert payload["template"] == "html"
    assert payload["callbackUrl"] == "https://callback.example/push"
    assert "共 2 篇" in payload["content"]
    assert "重点推荐" in payload["content"]
    assert "https://example.github.io/site" in payload["content"]
    assert len(payload["content"]) < 12000


def test_code_200_is_accepted_pending_verification_and_short_code_saved():
    def post(url, **kwargs):
        assert url == "https://www.pushplus.plus/send"
        return {"code": 200, "msg": "请求成功", "data": "short-123"}
    result = send_push({"token": "secret"}, post=post)
    assert result == {"status": "accepted_pending_verification", "shortCode": "short-123"}


def test_failed_push_raises_so_caller_cannot_mark_sent():
    with pytest.raises(RuntimeError, match="PushPlus"):
        send_push({"token": "secret"}, post=lambda *a, **k: {"code": 500, "msg": "failed"})
