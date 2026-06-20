import os

import anthropic

DEFAULT_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")


def _api_key():
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        try:
            import streamlit as st

            key = st.secrets.get("ANTHROPIC_API_KEY")
        except Exception:
            key = None
    if not key:
        raise ValueError(
            "No Anthropic API key found. Set ANTHROPIC_API_KEY "
            "(env var or .streamlit/secrets.toml)."
        )
    return key


def get_client():
    return anthropic.Anthropic(api_key=_api_key())


def chat(messages, system=None, tools=None, model=None, max_tokens=1024, temperature=0.2):
    client = get_client()
    kwargs = {
        "model": model or DEFAULT_MODEL,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": messages,
    }
    if system:
        kwargs["system"] = system
    if tools:
        kwargs["tools"] = tools
    return client.messages.create(**kwargs)
