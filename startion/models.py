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

    @classmethod
    def from_github(cls, raw: dict) -> RepoInfo:
        return cls(
            full_name=raw["full_name"],
            name=raw["name"],
            owner=raw["owner"]["login"],
            url=raw["html_url"],
            description=raw.get("description") or "",
            language=raw.get("language") or "",
            topics=raw.get("topics") or [],
            stars=raw.get("stargazers_count", 0),
        )
