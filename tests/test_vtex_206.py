"""VTEX search must accept HTTP 206 Partial Content (common catalog response)."""

from __future__ import annotations

from market_connectors.vtex import _vtex_json_list


class _FakeResp:
    def __init__(self, status_code: int, content_type: str, payload):
        self.status_code = status_code
        self.headers = {"content-type": content_type}
        self._payload = payload

    def json(self):
        return self._payload


def test_vtex_json_list_accepts_206():
    resp = _FakeResp(206, "application/json; charset=utf-8", [{"productId": "1"}])
    assert _vtex_json_list(resp) == [{"productId": "1"}]


def test_vtex_json_list_rejects_html():
    resp = _FakeResp(200, "text/html", "<html></html>")
    assert _vtex_json_list(resp) is None


def test_vtex_json_list_accepts_200():
    resp = _FakeResp(200, "application/json", [])
    assert _vtex_json_list(resp) == []