from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RepoInfo:
    """Normalized representation of a GitHub repository."""

    full_name: str
    name: str
    owner: str
    url: str
    description: str
    language: str
    topics: list[str] = field(default_factory=list)
    stars: int = 0
    ai_summary: str = ""
    starred_at: str = ""

    @classmethod
    def from_github(cls, raw: dict) -> RepoInfo:
        """Build from the star+json wrapper ``{"starred_at": ..., "repo": ...}``."""
        repo = raw.get("repo", raw)
        return cls(
            full_name=repo["full_name"],
            name=repo["name"],
            owner=repo["owner"]["login"],
            url=repo["html_url"],
            description=repo.get("description") or "",
            language=repo.get("language") or "",
            topics=repo.get("topics") or [],
            stars=repo.get("stargazers_count", 0),
            starred_at=raw.get("starred_at", ""),
        )
