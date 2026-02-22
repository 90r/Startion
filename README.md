# Startion ⭐

[简体中文](README.zh-CN.md) | English

Sync your GitHub stars to a Notion database with AI-generated summaries — then use Notion AI to search and discover related projects.

## How It Works

1. Fetches all your GitHub starred repositories via the GitHub API
2. Reads each project's README and generates a concise summary using an OpenAI-compatible LLM
3. Writes everything into a Notion database (name, URL, language, topics, stars, AI summary)
4. On subsequent runs, only new stars get summarized; unstarred repos are automatically archived
5. Notion's built-in AI can then semantically search across all your starred projects

## Setup

### Prerequisites

- Python 3.13+
- A [GitHub personal access token](https://github.com/settings/tokens) with `read:user` scope
- A [Notion integration](https://www.notion.so/profile/integrations/internal) with access to a page
- An OpenAI API key (or any OpenAI-compatible endpoint, e.g. Ollama, vLLM)

### Install

```bash
uv sync
```

### Configure

```bash
cp .env.example .env
# Edit .env with your tokens
```

Environment variables:

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `GITHUB_TOKEN` | Yes | — | GitHub personal access token (`read:user` scope) |
| `NOTION_TOKEN` | Yes | — | Notion integration token |
| `NOTION_DATA_SOURCE_ID` | Yes | — | Data source ID (created by `startion setup`) |
| `OPENAI_API_KEY` | Yes | — | OpenAI API key (or compatible provider) |
| `OPENAI_BASE_URL` | No | `https://api.openai.com/v1` | API base URL for OpenAI-compatible endpoints |
| `OPENAI_MODEL` | No | `gpt-4o-mini` | Model name to use for summarization |
| `GITHUB_USERNAME` | No | *(authenticated user)* | Set to sync another user's public stars instead |
| `SUMMARY_LANGUAGE` | No | `English` | Language for AI-generated summaries |
| `SYNC_CONCURRENCY` | No | `5` | Max concurrent AI summary requests |

### Create the Notion Database

```bash
uv run startion setup
```

This will ask for a parent page ID and create a pre-configured database. Add the
returned `NOTION_DATA_SOURCE_ID` to your `.env`.

> **Tip:** To find a page ID, open the page in Notion and copy the 32-character hex
> string from the URL (after the workspace name, before the `?`).

### Run

```bash
uv run startion sync
```

Options:

| Flag | Description |
| --- | --- |
| `--force-resummarize` | Re-generate AI summaries for *all* repos, not just new ones |
| `--dry-run` | Preview changes without writing to Notion |
| `--limit N` | Only process the first N starred repos (useful for testing) |
| `--no-archive` | Do not archive repos that are no longer starred |
| `--include-empty-summary` | Include repos with empty AI summaries — re-summarize and update them |
| `--concurrency N` | Max concurrent summary requests (overrides `SYNC_CONCURRENCY`) |

## Periodic Sync

### cron (local)

```bash
# Every day at midnight
0 0 * * * cd /path/to/Startion && uv run startion sync >> sync.log 2>&1
```

### GitHub Actions

A ready-to-use workflow is included at `.github/workflows/sync.yml`. It runs daily at 00:00 UTC and can be triggered manually via `workflow_dispatch`.

Add the following secrets to your repository (**Settings > Secrets and variables > Actions**):

| Secret | Description |
| --- | --- |
| `GH_PAT` | GitHub personal access token |
| `NOTION_TOKEN` | Notion integration token |
| `NOTION_DATA_SOURCE_ID` | Data source ID from `startion setup` |
| `OPENAI_API_KEY` | OpenAI API key |
| `OPENAI_BASE_URL` | *(optional)* Custom API base URL |
| `OPENAI_MODEL` | *(optional)* Model name override |
| `SUMMARY_LANGUAGE` | *(optional)* Summary language override |

## Notion Database Schema

| Property | Type | Description |
| --- | --- | --- |
| Name | Title | `owner/repo` (hyperlinked to the repository) |
| Description | Rich text | Original GitHub description |
| Language | Select | Primary language |
| Topics | Multi-select | Repository topics |
| Stars | Number | Star count |
| AI Summary | Rich text | LLM-generated project summary |
| Owner | Rich text | Repository owner |
| Last Synced | Date | Timestamp of last sync |

## License

MIT
