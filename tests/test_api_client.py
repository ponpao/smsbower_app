"""Non-GUI tests for APIClient behaviour (run: python -m pytest tests/ -q)."""

from __future__ import annotations

import json
from unittest import mock

import pytest
import requests

from grok_studio.api_client import (
    APIClient,
    ApiError,
    _normalize_video_status,
    _retry_after_seconds,
)
from grok_studio.constants import IMAGE_ASPECT_RATIOS, VIDEO_ASPECT_RATIOS


def make_response(status=200, body=None, headers=None):
    resp = requests.Response()
    resp.status_code = status
    resp._content = json.dumps(body or {}).encode()
    resp.headers.update(headers or {"Content-Type": "application/json"})
    return resp


def client():
    return APIClient(lambda: "test-key-value-123")


def test_video_ratio_list_is_strict_subset_of_image_list():
    assert set(VIDEO_ASPECT_RATIOS) < set(IMAGE_ASPECT_RATIOS)
    for bad in set(IMAGE_ASPECT_RATIOS) - set(VIDEO_ASPECT_RATIOS):
        with pytest.raises(ApiError, match="Invalid video aspect ratio"):
            client().create_video_job("x", model="grok-imagine-video",
                                      aspect_ratio=bad)


def test_invalid_image_ratio_rejected_locally():
    with pytest.raises(ApiError, match="Invalid image aspect ratio"):
        client().generate_images("x", model="grok-imagine-image",
                                 aspect_ratio="21:9")


def test_missing_key_raises():
    c = APIClient(lambda: None)
    with pytest.raises(ApiError, match="No API key"):
        c.chat([{"role": "user", "content": "hi"}])


def test_429_auto_retry_once():
    c = client()
    waits: list[int] = []
    responses = [
        make_response(429, {}, {"Retry-After": "1"}),
        make_response(200, {"choices": [{"message": {"content": "pong"}}]}),
    ]
    with mock.patch.object(c._session, "request", side_effect=responses) as m:
        out = c.chat([{"role": "user", "content": "ping"}],
                     on_retry_wait=waits.append)
    assert out == "pong"
    assert m.call_count == 2
    assert waits == [1]


def test_moderation_flag_surfaces_as_moderation_error():
    c = client()
    body = {"data": [{"b64_json": "aGk=", "respect_moderation": True}]}
    with mock.patch.object(c._session, "request",
                           return_value=make_response(200, body)):
        with pytest.raises(ApiError) as exc_info:
            c.generate_images("x", model="grok-imagine-image")
    assert exc_info.value.moderation


def test_video_status_normalization():
    assert _normalize_video_status("PENDING") == "queued"
    assert _normalize_video_status("in_progress") == "rendering"
    assert _normalize_video_status("completed") == "done"
    assert _normalize_video_status("expired") == "expired"
    assert _normalize_video_status("error") == "failed"


def test_done_without_media_is_failure():
    c = client()
    with mock.patch.object(c._session, "request",
                           return_value=make_response(200, {"status": "done"})):
        job = c.get_video_job("job1")
    assert job.status == "failed"


def test_retry_after_parsing():
    assert _retry_after_seconds(make_response(429, headers={"Retry-After": "7"})) == 7
    assert _retry_after_seconds(make_response(429, headers={"Retry-After": "bogus"})) == 5
    assert _retry_after_seconds(make_response(429, headers={"Retry-After": "9999"})) == 120


def test_error_message_extraction():
    c = client()
    body = {"error": {"message": "invalid aspect ratio"}}
    with mock.patch.object(c._session, "request",
                           return_value=make_response(400, body)):
        with pytest.raises(ApiError, match="HTTP 400: invalid aspect ratio"):
            c.chat([{"role": "user", "content": "hi"}])
