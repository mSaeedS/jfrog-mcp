# JFrog MCP

Read-only Model Context Protocol server for JFrog Artifactory repository intelligence.

This server is intentionally narrow. It lists repositories, lists explicit repository paths, fetches item metadata, fetches properties and stats, and performs bounded file searches. It does not deploy, delete, move, copy, mutate properties, run raw AQL, or download file content.

## Tools

- `jfrog_ping` checks URL and token access without returning secrets.
- `jfrog_capabilities` describes server limits, security settings, compatibility behavior, and optional live feature probes for a repo/path.
- `jfrog_list_repositories` lists repositories with optional `type`, `package_type`, and `project` filters.
- `jfrog_list_path` lists one repository path with bounded depth and cursor pagination. If Artifactory rejects the Pro-only storage list mode, it falls back to basic metadata children.
- `jfrog_get_item_info` returns metadata for one file or folder.
- `jfrog_get_item_properties` returns item properties as a separate storage query mode.
- `jfrog_get_item_stats` returns download statistics as a separate storage query mode.
- `jfrog_get_tree` returns a bounded file/folder tree using metadata traversal.
- `jfrog_find_files` searches files with generic filters and response shaping.
- `jfrog_latest_files` searches files and sorts the bounded result set by `modified` client-side.

The safe search tools intentionally avoid non-portable AQL fields and default server-side sorting, because some Artifactory OSS/CE installations reject those features. Use `name_pattern` for artifact-specific needs, such as `*.jar`, `*.war`, or `*.zip`, instead of adding artifact-specific tools.

## Resources

- `jfrog://repositories` lists repositories.
- `jfrog://repo/{repoKey}` lists the root path of one repository.
- `jfrog://repo/{repoKey}/path/{path}` returns metadata for one repository path. Encode slashes in `path` as `%2F`, for example `jfrog://repo/libs-release-local/path/com%2Facme`.

## Configuration

Set credentials through a local `.env` file, environment variables, or a mounted token file. Do not pass the token as a tool argument.

For local use, copy the template and edit the values:

```powershell
Copy-Item .env.example .env
notepad .env
```

Minimal `.env` with a direct token:

```bash
JFROG_URL=https://example.jfrog.io
JFROG_ACCESS_TOKEN=REPLACE_ME
```

Or use a token file:

```powershell
New-Item -ItemType Directory -Force .secrets
Set-Content -NoNewline .secrets/jfrog-token "REPLACE_ME"
```

```bash
JFROG_URL=https://example.jfrog.io
JFROG_ACCESS_TOKEN_FILE=.secrets/jfrog-token
```

`JFROG_ACCESS_TOKEN` takes priority when both settings are present. Direct tokens are convenient for local agents and private runtime configuration. Token files are still useful for mounted secrets in containers, CI, Kubernetes, and OpenShift.

```bash
export JFROG_URL="https://example.jfrog.io"
export JFROG_ACCESS_TOKEN="REPLACE_ME"
```

Optional settings:

```bash
export JFROG_MCP_TRANSPORT="stdio"
export JFROG_REQUEST_TIMEOUT_SECONDS="20"
export JFROG_DEFAULT_PAGE_SIZE="50"
export JFROG_MAX_PAGE_SIZE="200"
export JFROG_MAX_DEPTH="5"
export JFROG_MAX_AQL_LIMIT="500"
export JFROG_CACHE_TTL_SECONDS="60"
export JFROG_VERIFY_SSL="true"
export JFROG_CA_BUNDLE="/etc/ssl/certs/company-ca.pem"
export JFROG_TRUST_ENV="false"
export JFROG_LOG_LEVEL="INFO"
```

`JFROG_URL` may be either the JFrog base URL, such as `https://example.jfrog.io`, or the Artifactory base URL, such as `https://example.jfrog.io/artifactory`.

Keep `JFROG_VERIFY_SSL=true` in production. If your Artifactory endpoint uses a private CA, set `JFROG_CA_BUNDLE` to the mounted PEM bundle instead of disabling verification.

`JFROG_TRUST_ENV=false` makes the HTTP client ignore proxy-related environment variables. Keep this default for internal Artifactory routes unless your deployment intentionally needs `HTTP_PROXY` or `HTTPS_PROXY`.

## Run Locally

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
jfrog-mcp
```

For Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
jfrog-mcp
```

The default transport is `stdio`. For Streamable HTTP:

```bash
JFROG_MCP_TRANSPORT=streamable-http jfrog-mcp
```

## Client Example

For a stdio MCP client configuration:

```json
{
  "mcpServers": {
    "jfrog": {
      "command": "jfrog-mcp",
      "env": {
        "JFROG_URL": "https://example.jfrog.io",
        "JFROG_ACCESS_TOKEN": "REPLACE_ME"
      }
    }
  }
}
```

For agents that expect an `npx`-style MCP command, use the Node wrapper.

Local development:

```json
{
  "mcpServers": {
    "jfrog": {
      "command": "npx",
      "args": [
        "-y",
        "D:\\OneDrive - Systems Limited\\Desktop\\jfrog-mcp"
      ],
      "env": {
        "JFROG_MCP_PROJECT_DIR": "D:\\OneDrive - Systems Limited\\Desktop\\jfrog-mcp"
      }
    }
  }
}
```

Uploaded GitHub repo:

```json
{
  "mcpServers": {
    "jfrog": {
      "command": "npx",
      "args": [
        "-y",
        "github:mSaeedS/jfrog-mcp"
      ],
      "env": {
        "JFROG_URL": "https://example.jfrog.io",
        "JFROG_ACCESS_TOKEN": "REPLACE_ME",
        "JFROG_TRUST_ENV": "false"
      }
    }
  }
}
```

Published npm package:

```json
{
  "mcpServers": {
    "jfrog": {
      "command": "npx",
      "args": [
        "-y",
        "@YOUR_SCOPE/jfrog-mcp@0.1.0"
      ],
      "env": {
        "JFROG_URL": "https://example.jfrog.io",
        "JFROG_ACCESS_TOKEN": "REPLACE_ME",
        "JFROG_TRUST_ENV": "false"
      }
    }
  }
}
```

The wrapper starts the Python MCP server, sets `JFROG_ENV_FILE` to the project `.env` when present, and preserves stdio for MCP protocol traffic. For uploaded `npx` usage, it bootstraps a small Python venv in the user cache on first run and installs the bundled Python package there. If your environment uses an internal Python package index, pass `PIP_INDEX_URL` / `PIP_EXTRA_INDEX_URL` through the MCP env.

If Windows or OneDrive blocks the default npm cache, set a cache outside synced folders before running `npx`:

```powershell
$env:npm_config_cache = "$env:TEMP\npm-cache"
npx -y "D:\OneDrive - Systems Limited\Desktop\jfrog-mcp" --version
```

## Publishing

Do not publish `.env`, `.secrets/`, `.venv/`, caches, or generated reports. The npm package uses a `files` allow-list so only the wrapper, Python source, `pyproject.toml`, and README are packed.

For a shareable source zip, use the clean allow-list export instead of manually zipping the project folder:

```bash
python bin/build-clean-zip.py
```

The zip is written to `dist/jfrog-mcp-clean.zip` by default and includes only the documented source, test, wrapper, and metadata files.

Option 1: private GitHub repository, no npm registry:

```bash
git init
git add .
git commit -m "Initial JFrog MCP"
git remote add origin https://github.com/mSaeedS/jfrog-mcp.git
git push -u origin main
```

Then use `npx -y github:mSaeedS/jfrog-mcp` in your agent.

Option 2: npm or private npm-compatible registry:

1. Change `package.json` `name` from `jfrog-mcp` to your scoped package, for example `@YOUR_SCOPE/jfrog-mcp`.
2. Change `private` to `false`.
3. Run `npm pack --dry-run` and confirm no secrets are included.
4. Publish:

```bash
npm publish --access restricted
```

For Artifactory npm registry, use your registry URL:

```bash
npm publish --registry https://YOUR_ARTIFACTORY/artifactory/api/npm/YOUR_NPM_REPO/
```

## Docker

```bash
docker build -t jfrog-mcp:latest .
docker run --rm -i \
  -e JFROG_URL="https://example.jfrog.io" \
  -e JFROG_ACCESS_TOKEN="REPLACE_ME" \
  jfrog-mcp:latest
```

For HTTP transport:

```bash
docker run --rm -p 8000:8000 \
  -e JFROG_URL="https://example.jfrog.io" \
  -e JFROG_ACCESS_TOKEN="REPLACE_ME" \
  -e JFROG_MCP_TRANSPORT="streamable-http" \
  jfrog-mcp:latest
```

## Production Notes

- Use a least-privilege read-only JFrog access token. Rotate it regularly and immediately after any accidental exposure.
- Use `JFROG_ACCESS_TOKEN` when your agent/runtime can inject secrets securely as environment variables. Use `JFROG_ACCESS_TOKEN_FILE` when your platform mounts secrets as files.
- Set page, depth, and AQL limits for your environment with `JFROG_MAX_PAGE_SIZE`, `JFROG_MAX_DEPTH`, and `JFROG_MAX_AQL_LIMIT`.
- Run `jfrog_capabilities(live_probe=true, repo_key="...", path="...")` against a representative repo to discover whether that Artifactory instance supports Pro storage listing or server-side AQL sort.
- Restart the MCP client or server process after changing environment variables or code. Existing stdio MCP sessions keep their original process environment.
- Treat `JFROG_VERIFY_SSL=false` as local troubleshooting only. Use `JFROG_CA_BUNDLE` for private CA deployments.

## Tests

```bash
pytest
```

The tests use mocked HTTP transports and do not call a real JFrog instance.

Optional live tests run only when all of these are set:

```bash
export JFROG_TEST_URL="https://example.jfrog.io"
export JFROG_TEST_TOKEN="REPLACE_ME"
export JFROG_TEST_REPO="libs-release-local"
pytest tests/test_live_integration.py
```
