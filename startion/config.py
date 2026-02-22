from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass
class Config:
    github_token: str
    notion_token: str
    notion_data_source_id: str
    openai_api_key: str
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    github_username: str = ""
    summary_language: str = "English"
    sync_concurrency: int = 5

    @classmethod
    def from_env(cls) -> Config:
        load_dotenv()

        return cls(
            github_token=os.environ["GITHUB_TOKEN"],
            notion_token=os.environ["NOTION_TOKEN"],
            notion_data_source_id=os.environ.get("NOTION_DATA_SOURCE_ID", ""),
            openai_api_key=os.environ["OPENAI_API_KEY"],
            openai_base_url=os.environ.get(
                "OPENAI_BASE_URL", "https://api.openai.com/v1"
            ),
            openai_model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            github_username=os.environ.get("GITHUB_USERNAME", ""),
            summary_language=os.environ.get("SUMMARY_LANGUAGE", "English"),
            sync_concurrency=int(os.environ.get("SYNC_CONCURRENCY", "5")),
        )
