from __future__ import annotations

import argparse
import logging
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from loguru import logger

from startion.ai import AISummarizer
from startion.config import Config
from startion.github import GitHubClient
from startion.models import RepoInfo
from startion.notion import NotionSync


def _extract_notion_id(raw: str) -> str:
    """Extract a 32-char hex Notion ID from a raw string (URL, slug, or bare ID)."""
    raw = raw.split("?")[0].strip("/").split("/")[-1]
    cleaned = raw.replace("-", "")
    match = re.search(r"[0-9a-f]{32}$", cleaned)
    if match:
        return match.group()
    raise ValueError(f"Could not extract a valid 32-char hex page ID from: {raw}")


def cmd_setup(config: Config) -> None:
    """Interactively create the Notion database."""
    notion = NotionSync(config.notion_token, "")

    with GitHubClient(config.github_token) as github:
        username = config.github_username or github.get_username()

    print(
        "Enter the Notion parent page ID or URL.\n"
        "  You can paste the full page URL or just the 32-char hex ID.\n"
        "  Hint: database URLs contain '?v=', page URLs do not.\n"
    )
    raw_input = input("Parent page ID or URL: ").strip()

    try:
        parent_page_id = _extract_notion_id(raw_input)
    except ValueError:
        logger.error("Could not extract a valid page ID from: {}", raw_input)
        sys.exit(1)

    try:
        ds_id = notion.create_database(parent_page_id, username=username)
    except Exception as exc:
        if "parented by a database" in str(exc):
            logger.error(
                "The ID you provided belongs to a database, not a page. "
                "Please create a new page in Notion and use that page's ID instead."
            )
            sys.exit(1)
        raise

    print(
        f"\nDatabase created successfully!\n"
        f"Add this to your .env file:\n  NOTION_DATA_SOURCE_ID={ds_id}"
    )


def cmd_sync(
    config: Config,
    *,
    force_resummarize: bool = False,
    dry_run: bool = False,
    limit: int | None = None,
    no_archive: bool = False,
    include_empty_summary: bool = False,
    concurrency: int | None = None,
) -> None:
    """Sync GitHub stars to Notion, generating AI summaries for new repos."""
    if not config.notion_data_source_id:
        logger.error("NOTION_DATA_SOURCE_ID is not set. Run `startion setup` first.")
        sys.exit(1)

    notion = NotionSync(config.notion_token, config.notion_data_source_id)
    workers = concurrency or config.sync_concurrency

    with GitHubClient(config.github_token) as github:
        logger.info("Fetching starred repos from GitHub…")
        raw_repos = github.get_starred_repos(config.github_username)
        logger.info("Found {} starred repos", len(raw_repos))

        if limit is not None:
            raw_repos = raw_repos[:limit]
            logger.info("Limited to first {} repos", limit)

        logger.info("Loading existing Notion entries…")
        existing, empty_summary_names = notion.get_existing_repos()
        logger.info("Found {} existing entries in Notion", len(existing))

        repos = [RepoInfo.from_github(raw) for raw in raw_repos]
        starred_names = {r.full_name for r in repos}

        new_repos = [r for r in repos if r.full_name not in existing]
        unstarred = set(existing) - starred_names

        resummarize_repos: list[RepoInfo] = []
        skip_repos: list[RepoInfo] = []
        if force_resummarize:
            resummarize_repos = [r for r in repos if r.full_name in existing]
        elif include_empty_summary:
            for r in repos:
                if r.full_name in existing and r.full_name in empty_summary_names:
                    resummarize_repos.append(r)
                elif r.full_name in existing:
                    skip_repos.append(r)
        else:
            skip_repos = [r for r in repos if r.full_name in existing]

        print(f"\n{'=' * 60}")
        print(f" Sync Preview")
        print(f"{'=' * 60}")
        print(f"  Starred on GitHub : {len(repos)}")
        print(f"  Already in Notion : {len(skip_repos)}  (skip)")
        if resummarize_repos:
            label = "force re-summarize" if force_resummarize else "will re-summarize"
            print(f"  Re-summarize      : {len(resummarize_repos)}  ({label})")
        print(f"  New to add        : {len(new_repos)}")
        print(f"  Unstarred         : {len(unstarred)}  {'(will archive)' if not no_archive else '(skip archive)'}")
        print(f"{'=' * 60}\n")

        if skip_repos:
            print("  [SKIP] Existing repos (no changes):")
            for r in skip_repos:
                print(f"    ✓ {r.full_name}  ★{r.stars}")
            print()

        if resummarize_repos:
            label = "all" if force_resummarize else "empty AI summary"
            print(f"  [RESUMMARIZE] Existing repos ({label}):")
            for r in resummarize_repos:
                print(f"    ↻ {r.full_name}  ★{r.stars}")
            print()

        if new_repos:
            print("  [NEW] Repos to be added:")
            for r in new_repos:
                print(f"    + {r.full_name}  ★{r.stars}")
            print()

        if unstarred:
            label = "archive" if not no_archive else "skip"
            print(f"  [UNSTARRED] Repos no longer starred ({label}):")
            for name in sorted(unstarred):
                print(f"    - {name}")
            print()

        if dry_run:
            print("  Dry-run mode — no changes made.")
            return

        all_to_process = [(r, None) for r in new_repos] + [
            (r, existing[r.full_name]) for r in resummarize_repos
        ]

        if not all_to_process and (no_archive or not unstarred):
            print("  Nothing to do — Notion is already up to date!")
            return

        ai = AISummarizer(
            config.openai_api_key,
            config.openai_base_url,
            config.openai_model,
            config.summary_language,
        )

        total = len(all_to_process)
        counters = {"added": 0, "resummarized": 0, "empty": 0}
        lock = threading.Lock()

        def _process_repo(repo: RepoInfo, page_id: str | None) -> RepoInfo:
            readme = github.get_readme(repo.full_name)
            repo.ai_summary = ai.summarize(
                repo.full_name,
                repo.description,
                repo.language,
                repo.topics,
                readme,
            )
            if not repo.ai_summary and not (include_empty_summary or force_resummarize):
                with lock:
                    counters["empty"] += 1
                    logger.warning("Skipped {} (empty AI summary)", repo.full_name)
                return repo
            notion.upsert(repo, page_id=page_id)
            with lock:
                if page_id:
                    counters["resummarized"] += 1
                else:
                    counters["added"] += 1
                done = counters["added"] + counters["resummarized"]
                print(f"  [{done}/{total}] {repo.full_name} done")
            return repo

        logger.info("Processing {} repos (concurrency={})", total, workers)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(_process_repo, repo, page_id): repo
                for repo, page_id in all_to_process
            }
            for future in as_completed(futures):
                repo = futures[future]
                try:
                    future.result()
                except Exception:
                    logger.opt(exception=True).error("Failed to process {}", repo.full_name)

        archived_count = 0
        if not no_archive:
            for name in unstarred:
                notion.archive_page(existing[name])
                logger.info("Archived: {}", name)
                archived_count += 1

        print(f"\n{'=' * 60}")
        parts = [f"{counters['added']} added", f"{len(skip_repos)} skipped"]
        if counters["resummarized"]:
            parts.append(f"{counters['resummarized']} re-summarized")
        if counters["empty"]:
            parts.append(f"{counters['empty']} empty-summary")
        parts.append(f"{archived_count} archived")
        print(f"  Sync complete — {', '.join(parts)}")
        print(f"{'=' * 60}\n")


class _InterceptHandler(logging.Handler):
    """Route stdlib logging (httpx, openai, etc.) into loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1
        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def _setup_logging() -> None:
    logger.remove()
    logger.add(
        sys.stderr,
        level="DEBUG",
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> — "
            "<level>{message}</level>"
        ),
    )

    logging.basicConfig(handlers=[_InterceptHandler()], level=0, force=True)
    for name in ("httpx", "openai", "httpcore", "notion_client"):
        logging.getLogger(name).setLevel(logging.WARNING)


def main() -> None:
    _setup_logging()

    parser = argparse.ArgumentParser(
        prog="startion",
        description="Sync GitHub stars to Notion with AI-generated summaries",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("setup", help="Create the Notion database interactively")

    sync_p = sub.add_parser("sync", help="Sync GitHub stars to Notion")
    sync_p.add_argument(
        "--force-resummarize",
        action="store_true",
        help="Re-generate AI summaries for all repos (not just new ones)",
    )
    sync_p.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing to Notion",
    )
    sync_p.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only process the first N starred repos (useful for testing)",
    )
    sync_p.add_argument(
        "--no-archive",
        action="store_true",
        help="Do not archive repos that are no longer starred",
    )
    sync_p.add_argument(
        "--include-empty-summary",
        action="store_true",
        help="Include repos with empty AI summaries — re-summarize and update them",
    )
    sync_p.add_argument(
        "--concurrency",
        type=int,
        default=None,
        help="Max concurrent summary requests (default: env SYNC_CONCURRENCY or 5)",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    config = Config.from_env()

    if args.command == "setup":
        cmd_setup(config)
    elif args.command == "sync":
        cmd_sync(
            config,
            force_resummarize=args.force_resummarize,
            dry_run=args.dry_run,
            limit=args.limit,
            no_archive=args.no_archive,
            include_empty_summary=args.include_empty_summary,
            concurrency=args.concurrency,
        )
