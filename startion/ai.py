from __future__ import annotations

import time

from loguru import logger
from openai import APIStatusError, OpenAI

_MAX_RETRIES = 4
_BASE_DELAY = 1.0
_RETRYABLE_STATUS = (429, 500, 502, 503, 504)

SYSTEM_PROMPT = """\
You are a technical project analyst. \
Given a GitHub repository's information, write a concise summary in {language}. \
Output the summary directly without any preamble or labels."""

USER_PROMPT = """\
Summarize this repository covering:
1. 核心功能和用途
2. 主要技术栈
3. 适用场景和目标用户
4. 独特优势或亮点

Keep the summary within 200–300 characters. Be precise and informative.

---
Repository: {full_name}
Description: {description}
Language: {language_tech}
Topics: {topics}

README (excerpt):
{readme}
"""


class AISummarizer:
    def __init__(self, api_key: str, base_url: str, model: str, language: str):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.language = language

    def summarize(
        self,
        full_name: str,
        description: str,
        language_tech: str,
        topics: list[str],
        readme: str,
    ) -> str:
        system = SYSTEM_PROMPT.format(language=self.language)
        user = USER_PROMPT.format(
            full_name=full_name,
            description=description or "N/A",
            language_tech=language_tech or "N/A",
            topics=", ".join(topics) if topics else "N/A",
            readme=readme[:20_000] if readme else "N/A",
        )

        for attempt in range(_MAX_RETRIES + 1):
            try:
                resp = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    max_tokens=8192,
                    temperature=0.3,
                )
                usage = resp.usage
                logger.info(
                    "Token usage for {}: {} prompt + {} completion = {} total",
                    full_name,
                    usage.prompt_tokens if usage else "?",
                    usage.completion_tokens if usage else "?",
                    usage.total_tokens if usage else "?",
                )
                msg = resp.choices[0].message
                summary = (msg.content or "").strip()
                if not summary:
                    logger.warning("Empty content for {}, fields: {}", full_name, vars(msg))
                else:
                    logger.info("AI summary for {}: {}", full_name, summary[:100])
                return summary
            except APIStatusError as e:
                if e.status_code in _RETRYABLE_STATUS and attempt < _MAX_RETRIES:
                    delay = _BASE_DELAY * (2 ** attempt)
                    logger.warning(
                        "LLM request failed for {} (HTTP {}), retrying in {:.1f}s…",
                        full_name, e.status_code, delay,
                    )
                    time.sleep(delay)
                    continue
                logger.error("AI summary failed for {}: {}", full_name, e)
                return ""
            except Exception as e:
                logger.error("AI summary failed for {}: {}", full_name, e)
                return ""
