# Codex deployment guide

This repository installs a local, read-only Canvas LMS MCP server. Installation, MCP registration, and Canvas account authorization are separate steps. Never report a live Canvas connection based only on a successful installation or tool listing.

## 1. Install the repository

Use Python 3.11 or newer. Clone the repository into a directory chosen by the user, inspect `AGENTS.md`, then run:

```bash
python3 install.py --register-codex
```

On Windows, use `py -3 install.py --register-codex`. The script finds the checkout using its own location, creates `.venv`, installs the pinned runtime dependencies and this package, runs an offline MCP self-test, and registers a server named `canvas` if the Codex CLI is available. It works when invoked from a different working directory.

Do not overwrite an existing MCP entry. If `canvas` is already used for another server, select a new name with `--name canvas-lms`. Repeating registration with the same command and configuration is safe.

If the Codex CLI is unavailable, the script returns `registered: false` and a portable manual MCP configuration. Apply that configuration in the user's MCP settings using the available client interface; do not claim registration succeeded until it has been read back.

## 2. Configure account access locally

Read [AUTHENTICATION.md](AUTHENTICATION.md). This developer preview consumes an existing institution-approved access credential; it does not include an OAuth login or refresh service. Do not solicit raw access tokens in a chat or commit them to the repository. Ask only for the Canvas HTTPS domain, preferred IANA timezone, and the path to a credential file already provisioned through the approved process. If this information is missing, finish installation and the offline self-test first, then clearly report that account configuration is pending.

With the virtual environment activated, configure an existing UTF-8 credential file or a DOCX containing one credential:

```bash
canvas-bridge configure \
  --base-url https://canvas.example.edu \
  --token-file /absolute/private/path/credentials.token \
  --timezone Asia/Hong_Kong
canvas-bridge register-codex
canvas-bridge doctor
```

These are examples: use the user's real domain, local file path, and timezone. Never put the token value in arguments. The credential is referenced locally and is not copied into the MCP settings.

The default private configuration is `%APPDATA%/canvas-agent-bridge/config.toml` on Windows and `$XDG_CONFIG_HOME/canvas-agent-bridge/config.toml` (normally `~/.config/canvas-agent-bridge/config.toml`) elsewhere. Configuration creation uses restrictive file permissions where supported and refuses to overwrite a different existing file without `--force`.

Use `--config-path` on `configure` and `register-codex` to isolate multiple accounts. The generated MCP entry pins this file with `CANVAS_CONFIG` so it works from any chat or working directory.

## 3. Verify the result

```bash
canvas-bridge self-test
canvas-bridge doctor
canvas-bridge call list_courses
canvas-bridge call get_upcoming_work --args '{"days":14}'
```

`self-test` must return `ok: true` and `tool_count: 14`. It does not connect to Canvas. `doctor` must independently return `ok: true` after a successful authenticated request. Handle 401/403/404, unknown submission state, `partial`, and `truncated` explicitly.

Reconnect the MCP client to refresh tools. A running chat may retain its original tool inventory. The same installation can also be used through `python -m canvas_bridge` or the `canvas-bridge` command.

## Configuration precedence

1. Explicit `CANVAS_CONFIG` or a command's `--config-path`.
2. An existing private `canvas.toml` in a source checkout, for compatibility with early personal installations.
3. The per-user configuration path above.

`CANVAS_BASE_URL`, `CANVAS_TOKEN_FILE`, `CANVAS_TOKEN`, and `CANVAS_TIMEZONE` override their corresponding settings. Environment-only configuration is supported without a TOML file when `CANVAS_CONFIG` is not explicitly set. Do not print environment values. `CANVAS_TOKEN` must be provisioned locally through an approved process.

## Updates and troubleshooting

- Pull an approved update and rerun `install.py`. Existing credential files, different private configurations, and conflicting MCP entries are preserved.
- Python cannot create the virtual environment: install the operating system's `venv` support or select a supported Python interpreter.
- Missing configuration: complete step 2; do not change Canvas interface feature switches.
- Fake-IP proxy: by default private download addresses are blocked. If required by the local proxy, explicitly allow only verified Canvas content domains using `proxy_fake_ip_domains`; see `canvas.example.toml` and the [official domain list](https://community.instructure.com/en/kb/articles/485223-canvas-domain-email-and-server-management).
- OAuth token expired: refresh it through the institution's approved authorization system; automatic refresh is not implemented by this preview.

Codex's supported registration command and configuration are described in the [official OpenAI MCP documentation](https://developers.openai.com/codex/mcp).
