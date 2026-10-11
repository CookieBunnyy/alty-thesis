"""Email through Resend's HTTPS API (no network: httpx.post is replaced)."""

import logging

import httpx

from app.core.config import settings
from app.services import email_service


def _resend(monkeypatch, reply: httpx.Response | Exception):
    calls = []

    def fake_post(url, **kwargs):
        calls.append({"url": url, **kwargs})
        if isinstance(reply, Exception):
            raise reply
        return reply

    monkeypatch.setattr(email_service, "outbox", None)
    monkeypatch.setattr(settings, "EMAIL_PROVIDER", "resend")
    monkeypatch.setattr(settings, "RESEND_API_KEY", "re_test_key")
    monkeypatch.setattr(settings, "EMAIL_FROM", "no-reply@abellar.example")
    monkeypatch.setattr(settings, "EMAIL_FROM_NAME", "Abellar Realty")
    monkeypatch.setattr(email_service.httpx, "post", fake_post)
    return calls


def test_resend_request(monkeypatch):
    request = httpx.Request("POST", "https://api.resend.com/emails")
    calls = _resend(monkeypatch, httpx.Response(200, json={"id": "abc"}, request=request))
    assert email_service.send_email("staff@example.com", "Reset your Alty MSA password", "plain", "<p>html</p>")
    call = calls[0]
    assert call["url"] == "https://api.resend.com/emails"
    assert call["headers"] == {"Authorization": "Bearer re_test_key"}
    assert call["json"] == {"from": "Abellar Realty <no-reply@abellar.example>", "to": ["staff@example.com"],
                            "subject": "Reset your Alty MSA password", "text": "plain", "html": "<p>html</p>"}


def test_resend_refusal_is_reported_without_the_message(monkeypatch, caplog):
    request = httpx.Request("POST", "https://api.resend.com/emails")
    _resend(monkeypatch, httpx.Response(403, json={"message": "domain not verified"}, request=request))
    with caplog.at_level(logging.WARNING, logger="alty.email"):
        assert email_service.send_email("staff@example.com", "Subject", "secret link https://x/#token=abc") is False
    assert "token=abc" not in caplog.text and "HTTPStatusError" in caplog.text


def test_plain_text_message_gets_an_html_part(monkeypatch):
    request = httpx.Request("POST", "https://api.resend.com/emails")
    calls = _resend(monkeypatch, httpx.Response(200, json={"id": "abc"}, request=request))
    assert email_service.send_email("staff@example.com", "Changed", "Hello <Ana>,\n\nLine one\nLine two\n")
    assert calls[0]["json"]["html"] == "<p>Hello &lt;Ana&gt;,</p><p>Line one<br>Line two</p>"


def test_resend_unreachable(monkeypatch):
    _resend(monkeypatch, httpx.ConnectError("offline"))
    assert email_service.send_email("staff@example.com", "Subject", "text") is False


def test_missing_sender_sends_nothing(monkeypatch):
    calls = _resend(monkeypatch, httpx.Response(200))
    monkeypatch.setattr(settings, "EMAIL_FROM", "")
    assert email_service.send_email("staff@example.com", "Subject", "text") is False
    assert calls == []
