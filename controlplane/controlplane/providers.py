"""
Model provider adapter.

ControlPlane sits in front of a foundation model it does not own. This module
is the only place that knows how to call one, so everything else in the system
stays provider-agnostic and testable without a network.

Configuration is by environment:

    CONTROLPLANE_API_KEY   or OPENAI_API_KEY    the key
    CONTROLPLANE_BASE_URL                       optional, for any
                                                OpenAI-compatible endpoint
    CONTROLPLANE_MODEL                          model id, defaults below

With no key configured, `get_generator()` returns None and callers fall back to
recorded responses. That fallback is always labelled in the payload. A demo
that quietly replays a recording while implying a live call is the kind of
thing that destroys credibility when someone asks to type their own prompt, so
the source of every generation is reported explicitly.
"""

from __future__ import annotations

import os
import threading
from typing import Any, Callable

DEFAULT_MODEL = os.environ.get("CONTROLPLANE_MODEL", "gpt-4o-mini")
DEFAULT_TIMEOUT_S = float(os.environ.get("CONTROLPLANE_TIMEOUT_S", "30"))

_lock = threading.Lock()
_client: Any = None
_client_attempted = False
_client_error: str | None = None
# Last generation failure, so a misconfigured provider reports why instead of
# surfacing as a bare 503. A key that constructs a client fine but is rejected
# at call time is the common case: pointing a provider-specific key at the
# default OpenAI endpoint returns 401 on the first request, not at setup.
_last_call_error: str | None = None


def _api_key() -> str | None:
    return (
        os.environ.get("CONTROLPLANE_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or None
    )


def provider_status() -> dict[str, Any]:
    """What the demo endpoints report so nobody has to guess what just ran."""
    return {
        "configured": _api_key() is not None,
        "model": DEFAULT_MODEL,
        "base_url": os.environ.get("CONTROLPLANE_BASE_URL"),
        "client_error": _client_error,
        # Never the key itself, only the class and message of the failure.
        "last_call_error": _last_call_error,
    }


def _get_client() -> Any:
    global _client, _client_attempted, _client_error

    if _client_attempted:
        return _client
    with _lock:
        if _client_attempted:
            return _client
        _client_attempted = True

        key = _api_key()
        if key is None:
            _client_error = "no API key configured"
            return None
        try:
            from openai import OpenAI

            kwargs: dict[str, Any] = {"api_key": key, "timeout": DEFAULT_TIMEOUT_S}
            base_url = os.environ.get("CONTROLPLANE_BASE_URL")
            if base_url:
                kwargs["base_url"] = base_url
            _client = OpenAI(**kwargs)
        except Exception as exc:  # noqa: BLE001
            _client = None
            _client_error = f"{type(exc).__name__}: {exc}"
        return _client


def get_generator() -> Callable[[str], str] | None:
    """
    Return a `prompt -> completion` callable, or None when unconfigured.

    Deliberately narrow. The counterfactual bias detector and the live demo
    both need exactly this and nothing more, and keeping the surface small
    means a different provider is a change in one function.
    """
    client = _get_client()
    if client is None:
        return None

    def generate(prompt: str, system: str | None = None) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        result = client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=messages,
            temperature=float(os.environ.get("CONTROLPLANE_TEMPERATURE", "0.7")),
        )
        return (result.choices[0].message.content or "").strip()

    return generate


def generate_or_none(prompt: str, system: str | None = None) -> str | None:
    """
    Generate if a provider is configured, else None. Never raises.

    A failure is recorded rather than discarded. Swallowing it entirely meant a
    provider-specific key pointed at the wrong endpoint produced an
    indistinguishable "no provider" result, and the only way to find out was to
    read the source.
    """
    global _last_call_error

    generator = get_generator()
    if generator is None:
        return None
    try:
        result = generator(prompt, system) if system else generator(prompt)
        _last_call_error = None
        return result
    except Exception as exc:  # noqa: BLE001
        message = str(exc)
        key = _api_key()
        if key:
            message = message.replace(key, "<redacted>")
        _last_call_error = f"{type(exc).__name__}: {message[:300]}"
        return None
