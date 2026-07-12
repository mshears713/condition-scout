"""Tavily client behavior: request construction, async polling, completion,
and failure handling. Uses a mocked `requests` layer, not the network."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from valuation_research_scout.tavily import (
    RealTavilyClient,
    TavilyError,
    TavilyTaskFailed,
    TavilyTimeout,
)


def make_response(status_code: int, json_body: dict, text: str = ""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_body
    resp.text = text or str(json_body)
    return resp


def test_client_requires_api_key(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    with pytest.raises(TavilyError, match="TAVILY_API_KEY"):
        RealTavilyClient(api_key=None)


def test_create_task_sends_expected_request_and_returns_request_id():
    client = RealTavilyClient(api_key="tvly-test-key")
    with patch("requests.post") as mock_post:
        mock_post.return_value = make_response(
            201, {"request_id": "req-123", "status": "pending"}
        )
        request_id = client.create_task(
            input="research this cohort", model="mini", output_schema={"type": "object", "properties": {}}
        )
    assert request_id == "req-123"
    call = mock_post.call_args
    assert call.args[0] == "https://api.tavily.com/research"
    assert call.kwargs["headers"]["Authorization"] == "Bearer tvly-test-key"
    assert call.kwargs["json"]["input"] == "research this cohort"
    assert call.kwargs["json"]["model"] == "mini"
    assert call.kwargs["json"]["output_schema"] == {"type": "object", "properties": {}}


def test_create_task_accepts_live_observed_200_status():
    # Tavily's docs say 201; the live API actually returns 200 with a
    # {"status": "pending", ...} body (confirmed 2026-07-12).
    client = RealTavilyClient(api_key="tvly-test-key")
    with patch("requests.post") as mock_post:
        mock_post.return_value = make_response(200, {"request_id": "req-123", "status": "pending"})
        request_id = client.create_task(input="x", model="mini", output_schema={})
    assert request_id == "req-123"


def test_create_task_raises_on_error_status():
    client = RealTavilyClient(api_key="tvly-test-key")
    with patch("requests.post") as mock_post:
        mock_post.return_value = make_response(401, {}, text="unauthorized")
        with pytest.raises(TavilyError, match="401"):
            client.create_task(input="x", model="mini", output_schema={})


def test_get_status_polls_expected_url():
    client = RealTavilyClient(api_key="tvly-test-key")
    with patch("requests.get") as mock_get:
        mock_get.return_value = make_response(202, {"status": "pending"})
        data = client.get_status("req-123")
    assert data == {"status": "pending"}
    assert mock_get.call_args.args[0] == "https://api.tavily.com/research/req-123"


def test_run_polls_until_completed():
    client = RealTavilyClient(api_key="tvly-test-key")
    sleeps: list[float] = []
    with patch("requests.post") as mock_post, patch("requests.get") as mock_get:
        mock_post.return_value = make_response(201, {"request_id": "req-123", "status": "pending"})
        mock_get.side_effect = [
            make_response(202, {"status": "pending"}),
            make_response(202, {"status": "in_progress"}),
            make_response(
                200,
                {
                    "status": "completed",
                    "content": {"cohort_summary": "x"},
                    "sources": [{"title": "A", "url": "https://a.example"}],
                },
            ),
        ]
        result = client.run(
            input="x", model="mini", output_schema={}, poll_interval_s=0,
            sleep=lambda s: sleeps.append(s),
        )
    assert result.request_id == "req-123"
    assert result.content == {"cohort_summary": "x"}
    assert result.sources == [{"title": "A", "url": "https://a.example"}]
    assert len(sleeps) == 2  # slept between the two non-terminal polls


def test_run_raises_on_failed_status():
    client = RealTavilyClient(api_key="tvly-test-key")
    with patch("requests.post") as mock_post, patch("requests.get") as mock_get:
        mock_post.return_value = make_response(201, {"request_id": "req-123", "status": "pending"})
        mock_get.return_value = make_response(200, {"status": "failed"})
        with pytest.raises(TavilyTaskFailed, match="req-123"):
            client.run(input="x", model="mini", output_schema={}, poll_interval_s=0, sleep=lambda s: None)


def test_run_raises_timeout_when_never_completes():
    client = RealTavilyClient(api_key="tvly-test-key")
    clock_values = iter([0.0, 0.0, 10.0, 20.0])  # deadline computed from first value (0 + timeout)
    with patch("requests.post") as mock_post, patch("requests.get") as mock_get:
        mock_post.return_value = make_response(201, {"request_id": "req-123", "status": "pending"})
        mock_get.return_value = make_response(202, {"status": "pending"})
        with pytest.raises(TavilyTimeout, match="req-123"):
            client.run(
                input="x", model="mini", output_schema={},
                poll_interval_s=0, timeout_s=5.0,
                sleep=lambda s: None, clock=lambda: next(clock_values),
            )
