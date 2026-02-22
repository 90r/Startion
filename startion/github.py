from __future__ import annotations

import base64
import time
from types import TracebackType

import httpx
from loguru import logger

_MAX_RETRIES = 4
_BASE_DELAY = 1.0


class GitHubClient:
    def __init__(self, token: str) -> None:
        self._client = httpx.Client(
            base_url="https://api.github.com",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30,
        )

    # -- context manager ---------------------------------------------------

    def __enter__(self) -> GitHubClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()

    # -- public API ---------------------------------------------------------

    def get_username(self) -> str:
        """Return the login name of the authenticated user."""
        resp = self._client.get("/user")
        resp.raise_for_status()
        return resp.json()["login"]

    def get_starred_repos(self, username: str = "") -> list[dict]:
        """Fetch all starred repos with pagination.

        Uses the star+json media type so each item includes ``starred_at``.
        Returned dicts have the shape ``{"starred_at": str, "repo": dict}``.
        """
        repos: list[dict] = []
        page = 1

        while True:
            url = f"/users/{username}/starred" if username else "/user/starred"
            resp = self._client.get(
                url,
                params={"page": page, "per_page": 100},
                headers={"Accept": "application/vnd.github.star+json"},
            )
            resp.raise_for_status()

            data = resp.json()
            if not data:
                break

            repos.extend(data)
            logger.info("Fetched page {} — {} repos", page, len(data))
            page += 1

        return repos

    def get_readme(self, full_name: str, max_length: int = 30_000) -> str:
        """Fetch and decode the README for a repo. Returns empty string on failure."""
        for attempt in range(_MAX_RETRIES + 1):
            try:
                resp = self._client.get(f"/repos/{full_name}/readme")
                if resp.status_code == 404:
                    return ""
                if resp.status_code in (429, 403) and attempt < _MAX_RETRIES:
                    delay = _BASE_DELAY * (2 ** attempt)
                    logger.warning(
                        "GitHub rate-limited ({}), retrying in {:.1f}s…",
                        resp.status_code, delay,
                    )
                    time.sleep(delay)
                    continue
                resp.raise_for_status()

                content = base64.b64decode(resp.json()["content"]).decode(
                    "utf-8", errors="replace"
                )
                if len(content) > max_length:
                    content = content[:max_length] + "\n…(truncated)"
                return content
            except httpx.HTTPStatusError:
                raise
            except Exception:
                logger.opt(exception=True).warning(
                    "Failed to fetch README for {}", full_name
                )
                return ""
        return ""

    def close(self) -> None:
        self._client.close()
