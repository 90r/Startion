from __future__ import annotations

import time
from datetime import datetime, timezone

from loguru import logger
from notion_client import APIResponseError, Client

from startion.models import RepoInfo

_MAX_RETRIES = 4
_BASE_DELAY = 1.0

DATABASE_PROPERTIES = {
    "Name": {"title": {}},
    "Description": {"rich_text": {}},
    "Language": {"select": {}},
    "Topics": {"multi_select": {}},
    "Stars": {"number": {}},
    "AI Summary": {"rich_text": {}},
    "Owner": {"rich_text": {}},
    "Last Synced": {"date": {}},
}


class NotionSync:
    def __init__(self, token: str, data_source_id: str) -> None:
        self.client = Client(auth=token)
        self.data_source_id = data_source_id

    def create_database(
        self, parent_page_id: str, username: str = ""
    ) -> str:
        """Create the Startion database and return its data_source_id."""
        title = f"⭐ {username}'s GitHub Stars" if username else "⭐ GitHub Stars"
        resp = self.client.databases.create(
            parent={"type": "page_id", "page_id": parent_page_id},
            title=[{"type": "text", "text": {"content": title}}],
            initial_data_source={"properties": DATABASE_PROPERTIES},
        )
        ds_id = resp["data_sources"][0]["id"]
        self.data_source_id = ds_id
        logger.info("Created database {} (data_source {})", resp["id"], ds_id)
        return ds_id

    def get_existing_repos(self) -> tuple[dict[str, str], set[str]]:
        """Return ({full_name: page_id}, {full_names with empty AI summary})."""
        existing: dict[str, str] = {}
        empty_summary: set[str] = set()
        cursor = None

        while True:
            kwargs: dict = {
                "data_source_id": self.data_source_id,
                "page_size": 100,
            }
            if cursor:
                kwargs["start_cursor"] = cursor

            resp = self.client.data_sources.query(**kwargs)

            for page in resp["results"]:
                title_items = page["properties"].get("Name", {}).get("title", [])
                if title_items:
                    full_name = title_items[0]["plain_text"]
                    existing[full_name] = page["id"]
                    ai_prop = page["properties"].get("AI Summary", {})
                    summary_items = ai_prop.get("rich_text", [])
                    has_text = (
                        summary_items
                        and summary_items[0].get("plain_text", "").strip()
                    )
                    if not has_text:
                        empty_summary.add(full_name)

            if not resp.get("has_more"):
                break
            cursor = resp.get("next_cursor")

        return existing, empty_summary

    def upsert(self, repo: RepoInfo, page_id: str | None = None) -> None:
        """Create or update a page in the data source."""
        props = self._build_properties(repo)
        if page_id:
            self._call_with_retry(
                lambda: self.client.pages.update(page_id=page_id, properties=props)
            )
            logger.info("Updated: {}", repo.full_name)
        else:
            self._call_with_retry(
                lambda: self.client.pages.create(
                    parent={
                        "type": "data_source_id",
                        "data_source_id": self.data_source_id,
                    },
                    properties=props,
                )
            )
            logger.info("Created: {}", repo.full_name)

    def archive_page(self, page_id: str) -> None:
        self._call_with_retry(
            lambda: self.client.pages.update(page_id=page_id, archived=True)
        )

    @staticmethod
    def _call_with_retry(fn, retries: int = _MAX_RETRIES) -> object:
        for attempt in range(retries + 1):
            try:
                return fn()
            except APIResponseError as e:
                if e.status == 429 and attempt < retries:
                    delay = _BASE_DELAY * (2 ** attempt)
                    logger.warning("Notion rate-limited, retrying in {:.1f}s…", delay)
                    time.sleep(delay)
                    continue
                raise

    # ------------------------------------------------------------------

    @staticmethod
    def _build_properties(repo: RepoInfo) -> dict:
        now = datetime.now(timezone.utc).isoformat()

        props: dict = {
            "Name": {
                "title": [
                    {
                        "text": {
                            "content": repo.full_name,
                            "link": {"url": repo.url},
                        },
                    }
                ]
            },
            "Stars": {"number": repo.stars},
            "Last Synced": {"date": {"start": now}},
        }

        if repo.description:
            props["Description"] = {
                "rich_text": [{"text": {"content": repo.description[:2000]}}]
            }

        if repo.language:
            props["Language"] = {"select": {"name": repo.language}}

        if repo.topics:
            props["Topics"] = {
                "multi_select": [{"name": t} for t in repo.topics[:10]]
            }

        if repo.owner:
            props["Owner"] = {
                "rich_text": [{"text": {"content": repo.owner}}]
            }

        if repo.ai_summary:
            props["AI Summary"] = {
                "rich_text": [{"text": {"content": repo.ai_summary[:2000]}}]
            }

        return props
