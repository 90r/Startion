# Startion ⭐

简体中文 | [English](README.md)

将你的 GitHub Star 同步到 Notion 数据库，并利用 AI 自动生成每个项目的摘要 —— 然后就可以用 Notion 内置 AI 语义搜索来发现和关联项目了。

## 工作原理

1. 通过 GitHub API 获取你所有 Star 过的仓库
2. 读取每个项目的 README，使用 OpenAI 兼容的 LLM 生成简明摘要
3. 将所有信息写入 Notion 数据库（名称、链接、语言、标签、Star 数、AI 摘要）
4. 后续运行时只为新 Star 生成摘要；取消 Star 的项目会自动归档
5. 之后就可以用 Notion AI 在所有 Star 项目中进行语义搜索

> **提示：** 通过设置 `GITHUB_USERNAME` 环境变量，你还可以同步其他用户的公开 Star —— 方便你发掘和整理他人收藏的优质项目。

## 快速开始

### 前置条件

- Python 3.13+
- [GitHub Personal Access Token](https://github.com/settings/tokens)（需要 `read:user` 权限）
- [Notion Integration](https://www.notion.so/profile/integrations/internal)（需授权访问目标页面）
- OpenAI API Key（或任何 OpenAI 兼容的接口，如 Ollama、vLLM 等）

### 安装

```bash
uv sync
```

### 配置

```bash
cp .env.example .env
# 编辑 .env，填入各项 Token
```

环境变量说明：

| 变量 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `GITHUB_TOKEN` | 是 | — | GitHub 个人访问令牌（需 `read:user` 权限） |
| `NOTION_TOKEN` | 是 | — | Notion Integration Token |
| `NOTION_DATA_SOURCE_ID` | 是 | — | 数据源 ID（通过 `startion setup` 创建） |
| `OPENAI_API_KEY` | 是 | — | OpenAI API Key（或兼容接口的密钥） |
| `OPENAI_BASE_URL` | 否 | `https://api.openai.com/v1` | OpenAI 兼容接口的 Base URL |
| `OPENAI_MODEL` | 否 | `gpt-4o-mini` | 用于生成摘要的模型名称 |
| `GITHUB_USERNAME` | 否 | *（当前认证用户）* | 设置后同步指定用户的公开 Star |
| `SUMMARY_LANGUAGE` | 否 | `English` | AI 摘要的生成语言 |
| `SYNC_CONCURRENCY` | 否 | `5` | AI 摘要请求的最大并发数 |

### 创建 Notion 数据库

```bash
uv run startion setup
```

程序会要求输入一个 Notion 父页面 ID，然后自动创建预配置好的数据库。将返回的 `NOTION_DATA_SOURCE_ID` 填入 `.env` 即可。

> **提示：** 如何找到页面 ID？在 Notion 中打开目标页面，复制 URL 中工作区名称之后、`?` 之前的那段 32 位十六进制字符串。

### 运行同步

```bash
uv run startion sync
```

可选参数：

| 参数 | 说明 |
| --- | --- |
| `--force-resummarize` | 强制为所有项目重新生成 AI 摘要（而非仅新增项目） |
| `--dry-run` | 预览变更，不写入 Notion |
| `--limit N` | 只处理前 N 个 Star 仓库（适用于测试） |
| `--no-archive` | 不归档已取消 Star 的仓库 |
| `--include-empty-summary` | 包含 AI 摘要为空的仓库，重新生成摘要并更新 |
| `--concurrency N` | AI 摘要请求的最大并发数（覆盖 `SYNC_CONCURRENCY`） |

## 定时同步

### cron（本地）

```bash
# 每天午夜执行一次
0 0 * * * cd /path/to/Startion && uv run startion sync >> sync.log 2>&1
```

### GitHub Actions

项目已包含可直接使用的 workflow 文件 `.github/workflows/sync.yml`，默认每天 UTC 00:00（北京时间 08:00）运行一次，也支持手动触发。

在仓库中添加以下 Secrets（**Settings > Secrets and variables > Actions**）：

| Secret | 说明 |
| --- | --- |
| `GH_PAT` | GitHub 个人访问令牌 |
| `NOTION_TOKEN` | Notion Integration Token |
| `NOTION_DATA_SOURCE_ID` | `startion setup` 生成的数据源 ID |
| `OPENAI_API_KEY` | OpenAI API Key |
| `OPENAI_BASE_URL` | *（可选）* 自定义 API Base URL |
| `OPENAI_MODEL` | *（可选）* 模型名称覆盖 |
| `SUMMARY_LANGUAGE` | *（可选）* 摘要语言覆盖 |

## Notion 数据库字段

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| Name | Title | `owner/repo` 格式的仓库全名（超链接指向仓库地址） |
| Description | Rich text | GitHub 原始描述 |
| Language | Select | 主要编程语言 |
| Topics | Multi-select | 仓库标签 |
| Stars | Number | Star 数量 |
| AI Summary | Rich text | LLM 生成的项目摘要 |
| Owner | Rich text | 仓库所有者 |
| Last Synced | Date | 上次同步时间 |

## 许可证

MIT
