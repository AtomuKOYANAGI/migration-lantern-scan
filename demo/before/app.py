"""Intentionally outdated, synthetic code for Migration Lantern Scan."""

import openai


def legacy_openai(messages: list[dict[str, str]]) -> object:
    return openai.ChatCompletion.create(
        model="gpt-5.2-chat-latest",
        messages=messages,
    )


def deprecated_openai_model(openai_client: object) -> object:
    return openai_client.responses.create(
        model="gpt-5.2-chat-latest",
        input="Summarize this release note.",
    )


def legacy_anthropic_endpoint(anthropic_client: object) -> object:
    return anthropic_client.completions.create(
        model="claude-opus-4-1-20250805",
        max_tokens_to_sample=128,
        prompt="\n\nHuman: Summarize this release note.\n\nAssistant:",
    )
