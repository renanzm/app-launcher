# App Launcher

**English** · [Português (Brasil)](README.pt-BR.md)

A Windows launcher that **installs, updates and runs applications** distributed over FTP/FTPS. Everything environment-specific — server, applications, options, login, standalone downloads — lives in a single `launcher_config.json`, so the same executable works for any set of applications.

Built with Python + PyQt6: dark interface, configurable accent colour, and all network work kept off the UI thread. The interface is available in **English** and **Brazilian Portuguese**.

<p align="center">
  <img src="docs/screenshots/main.png" width="360" alt="Main window">
  <img src="docs/screenshots/custom-build.png" width="360" alt="Custom build">
</p>

## Features

- **Multiple applications** in a selector, each with its own folder, package and executable.
- **Install and update** from the server, comparing the date (`MDTM`) and size (`SIZE`) of the published package with the installed version; an "Installed / Available" panel with a status indicator.
- **Safe downloads**: written to a `.part` file, checked for size and — if a `<package>.sha256` file sits next to it on the server — for its SHA-256 hash before installing. Extraction blocks *Zip Slip* (entries outside the destination folder).
- **FTP or FTPS** (explicit TLS), with credentials in the configuration, encrypted (`password_enc`) or fetched from a remote URL with a local cache.
- **Automatic updates** of the selected application and of the launcher itself (the `.exe` is swapped by a script and verified on the next start).
- **Per-application options** declared in the configuration (toggle, text or password) that become environment variables of the launched process.
- **Extra actions**: buttons for other executables in the same package.
- **Per-ticket custom builds**: support publishes a specific version for a ticket; the user types the code and it is installed in an isolated folder, leaving the official installation untouched. User files (e.g. settings) can be copied over from the official installation.
- **Standalone downloads** in tabs (tools, installers…), with multi-select.
- **Optional HTTP login**, with "remember me" and automatic sign-in.
- **Verify integrity**, **open install folder** and **uninstall**.
- **English and Portuguese (Brazil)** interface, following the system language or chosen in Settings.

<p align="center">
  <img src="docs/screenshots/downloads.png" width="440" alt="Downloads">
  <img src="docs/screenshots/settings.png" width="330" alt="Settings">
</p>

## Getting started

Requires Windows and Python 3.11+.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
```

To see everything working without a real server, start the demo server in one terminal:

```bash
python -m tools.demo_server
```

And open the launcher in another:

```bash
python -m launcher
```

Without a `launcher_config.json`, the launcher uses [`launcher_config.example.json`](launcher_config.example.json), which points at the demo server. To simulate a newly published version, restart the server with `python -m tools.demo_server --bump`. The code `12345` installs the sample custom build.

## Language

The interface language is picked in this order:

1. the `--lang` command-line flag (`en` or `pt-BR`);
2. the **Language** option in *Settings* (takes effect on the next start);
3. the `language` key in `launcher_config.json`;
4. the operating system language, falling back to English.

Adding another language means adding a catalogue in [`launcher/locales/`](launcher/locales) that maps each English text to its translation (see [`pt_br.py`](launcher/locales/pt_br.py)) and registering it in `LANGUAGES` in [`launcher/i18n.py`](launcher/i18n.py). A test fails if a string in the code has no translation, or if a catalogue entry is no longer used.

## Configuration

Copy `launcher_config.example.json` to `launcher_config.json` (next to `Launcher.exe`, or in the project root when running from Python) and adjust it. You can also point to another file with `--config path.json`.

| Key | Description |
|---|---|
| `app_name`, `app_id` | Display name and the identifier used for the state folder (`%LOCALAPPDATA%\<app_id>`). |
| `accent_color` | Interface accent colour (`#RRGGBB`). |
| `language` | `auto` (default), `en` or `pt-BR`. |
| `support_url` | Page opened by *Help → Report a problem*. |
| `server` | `protocol` (`ftp`/`ftps`), `host`, `port`, `user`, `password` **or** `password_enc` + `secret`, `credentials_url`, `encoding`, `timeout`. |
| `auth` | `type: "none"` or `"http"` (`url`, `title`, `user_label`, `success_contains`, `session_env`). |
| `self_update` | `remote_dir` and `file_name` of the published `Launcher.exe`. |
| `apps[]` | See below. |
| `downloads[]` | Download tabs: `label`, `remote_dir`, `destination`, `extra_files[]` (`name`, `remote_dir`, `badge`). |

Each item of `apps`:

```json
{
  "id": "notes",
  "name": "Notes Studio",
  "description": "Short text shown below the selector.",
  "remote_dir": "/apps/notes",
  "package": "notes.zip",
  "install_dir": "Notes Studio",
  "executable": "notes.exe",
  "env": { "NOTES_LAUNCHED_BY": "app-launcher" },
  "extra_actions": [{ "label": "Open diagnostics", "executable": "diagnostics.exe" }],
  "options": [
    { "key": "verbose", "label": "Verbose mode", "type": "bool", "env": "NOTES_VERBOSE" },
    { "key": "token", "label": "API token", "type": "password", "env": "NOTES_TOKEN" }
  ],
  "custom_builds": {
    "remote_subdir": "custom-builds",
    "code_label": "Ticket",
    "code_pattern": "^\\d{5}$",
    "package_names": ["build.zip", "dist.zip"],
    "carry_over_files": ["settings.ini"]
  }
}
```

A `bool` option that is on becomes `"1"`, and one that is off removes the variable; an empty text option also removes the variable, so the application never inherits a stale value from the environment. `password` options are stored encrypted.

Texts that come from the configuration (application names, option labels, `auth.title`, `custom_builds.code_hint`…) are shown exactly as written, in the language you wrote them. When `auth.title`, `auth.user_label` or `custom_builds.code_hint` are omitted, the launcher uses translated defaults.

### HTTP login

With `auth.type = "http"`, the launcher sends `POST {"username": ..., "password": ...}` to `auth.url`. The response is accepted when it is 2xx and (if `success_contains` is set) contains that text; 401/403 count as invalid credentials. `session_env` passes the user and password on to the launched application:

```json
"auth": {
  "type": "http",
  "url": "https://auth.example.com/login",
  "session_env": { "user": "APP_USER", "password": "APP_PASSWORD" }
}
```

### Encrypted password and remote credentials

To avoid leaving the server password in plain text:

```bash
python -m tools.encrypt_password --new-secret
```

The command prints the `secret` (goes in `server.secret`) and the `password_enc`. The scheme (PBKDF2-HMAC-SHA256 + SHA-256 keystream + HMAC, stdlib only) is described in [`launcher/crypto.py`](launcher/crypto.py). It is obfuscation with integrity: it protects a JSON reachable by link, but anyone holding the `secret` can decrypt it.

With `server.credentials_url`, the credentials (`host`, `port`, `user`, `password`/`password_enc`) come from a remote JSON on every connection; changing the server password does not require redistributing the launcher. The last valid response is cached, encrypted with Windows DPAPI, so the launcher keeps working if the URL goes down.

## Server layout

```
/apps/notes/
    notes.zip                 ← official package (package)
    notes.zip.sha256          ← optional: hash checked on download
    custom-builds/
        12345/                ← ticket code
            build.zip         ← first name from package_names that is found
            info.json         ← optional: id, description, base_version, date
/launcher/
    Launcher.exe              ← published for self-update
```

To generate the `.sha256`: `certutil -hashfile notes.zip SHA256` or `sha256sum notes.zip > notes.zip.sha256`.

## Where data lives

- **Installed applications**: in the launcher folder (`<install_dir>`); custom builds in `<install_dir> - build <code>`.
- **State** (preferences, installed versions, options): `%LOCALAPPDATA%\<app_id>\state.json`. The remembered password, password-type options and cached credentials are encrypted with DPAPI — only the same Windows user can read them.

## Architecture

```
launcher/
  config.py        reads and validates launcher_config.json
  remote.py        FTP/FTPS, credentials, listing, verified download
  installer.py     safe extraction, isolated builds, launch environment
  auth.py          optional login and remembered credentials
  self_update.py   swaps the launcher's own .exe
  state.py         JSON state + DPAPI
  crypto.py        password_enc cipher
  i18n.py          translation lookup (English source text)
  locales/         translation catalogues (pt_br.py)
  ui/              windows (PyQt6): theme, icons drawn in code, dialogs
tools/             demo server, icon and encrypted-password generators
tests/             unit and integration tests (real FTP server in a thread)
```

Modules outside `ui/` do not depend on Qt and are covered by the tests. In the interface, every network operation runs in a `QThread` (`ui/widgets.py: Task`), so the window never freezes during downloads.

## Tests

```bash
python -m unittest discover -s tests -v
```

The suite runs on GitHub Actions (`windows-latest`) on every push and pull request.

## Building the executable

```bash
build.bat
```

Produces `dist\Launcher.exe` with PyInstaller (`Launcher.spec`). Distribute the `.exe` together with your `launcher_config.json`. The icon (`assets/app.ico`) is generated from the mark drawn in code: `python -m tools.make_icon --accent "#7C5CFF"`.

For self-update to work, publish the new `Launcher.exe` in `self_update.remote_dir` using **binary** transfer mode — ASCII mode changes the file size and machines never recognise the version as installed.

## License

[MIT](LICENSE)
