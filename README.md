# Terminalgram

**Instagram Direct Messages in your terminal. Nothing else.**

Terminalgram is a keyboard-driven terminal application for browsing Instagram Direct conversations and sending text messages. It is built with Python, [Textual](https://textual.textualize.io/) and [Rich](https://rich.readthedocs.io/), with [`instagrapi`](https://github.com/subzeroid/instagrapi) providing the Instagram connection.

> [!WARNING]
> Terminalgram relies on an **unofficial private Instagram API** through `instagrapi`. Its use may violate Instagram's Terms of Use. The API can change or stop working without notice, and Instagram may require additional verification, rate-limit requests, or restrict accounts. Use this project only if you understand these risks. Do not use an account whose loss of access would cause you harm. This project is not affiliated with or endorsed by Instagram or Meta.

## Features

- Browse recent Direct Message conversations and message previews.
- Open a conversation and view its latest messages.
- Send text messages from the terminal.
- Automatically refresh the inbox and currently open conversation.
- Run network operations in background workers so they do not block the interface.
- Show outgoing messages immediately while waiting for server confirmation (optimistic rendering).
- Resume a saved login session and handle two-factor authentication during login.
- Navigate with Vim-inspired keyboard shortcuts.
- Manually refresh data or delete the locally saved session.
- Keep UI-independent message and formatting helpers in a separately testable module.

## Requirements

- Python 3.10 or newer
- An Instagram account
- A terminal that supports Textual's interactive interface

## Installation

Clone the repository and enter its directory:

```bash
git clone https://github.com/YOUR_USERNAME/Terminalgram.git
cd Terminalgram
```

Create and activate a virtual environment (recommended):

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Windows Command Prompt:

```bat
.venv\Scripts\activate.bat
```

macOS / Linux:

```bash
source .venv/bin/activate
```

Install runtime dependencies:

```bash
python -m pip install -r requirements.txt
```

## Usage

Run the application from the project directory:

```bash
python Terminalgram.py
```

You can provide the account username as an argument:

```bash
python Terminalgram.py --username YOUR_USERNAME
```

The password is requested interactively using a password prompt and is not written to the session file. If Instagram requests a two-factor authentication code, Terminalgram prompts for it.

### Command-line options

| Option | Description |
|---|---|
| `-u`, `--username` | Provide the Instagram username. |
| `--logout` | Delete the locally saved session and exit. |
| `--debug` | Print a traceback when login fails. |

Examples:

```bash
python Terminalgram.py --debug
python Terminalgram.py --logout
```

## Keyboard shortcuts

### Conversation list

| Key | Action |
|---|---|
| `j` / `k` | Move down / up |
| `gg` | Jump to the top |
| `G` | Jump to the bottom |
| `Ctrl+D` / `Ctrl+U` | Move down / up by a page |
| `l` or `Enter` | Open the selected conversation |
| `Ctrl+T` | Focus the conversation list |

### Open conversation

| Key | Action |
|---|---|
| `j` / `k` | Scroll down / up |
| `gg` | Jump to the top |
| `G` | Jump to the bottom |
| `Ctrl+D` / `Ctrl+U` | Scroll down / up by half a page |
| `i`, `a`, or `Enter` | Focus the message input |
| `h` | Focus the conversation list |

### Message input

| Key | Action |
|---|---|
| `Enter` | Send the message |
| `Esc` | Return to NORMAL mode |

### Global shortcuts

| Key | Action |
|---|---|
| `Ctrl+R` or `r` | Refresh the inbox and open conversation |
| `q` or `Ctrl+Q` | Quit |

## Session storage and security

The saved session is stored at:

```text
~/.config/Terminalgram/session.json
```

If `XDG_CONFIG_HOME` is set, Terminalgram uses that directory instead of `~/.config`.

The session file contains authentication-related data and should be treated like a password. Terminalgram attempts to restrict the configuration directory to owner-only access (`0700`) and the session file to owner read/write access (`0600`) on platforms that support POSIX permissions. Permission handling is best-effort on Windows and filesystems that do not implement these permission bits.

**Never commit or share `session.json`.** Use `python Terminalgram.py --logout` to delete the saved local session. This does not log out other devices or delete your Instagram account.

## How it works

1. Terminalgram attempts to load and validate a previously saved session.
2. If the saved session cannot be resumed, it requests login credentials and handles a two-factor prompt when required.
3. Textual starts the terminal interface.
4. Background workers retrieve the inbox and messages without blocking the UI.
5. The inbox refreshes every 45 seconds; the currently open conversation refreshes every 8 seconds.
6. When a message is submitted, it is rendered immediately and sent in a background worker. Pending messages are reconciled with messages returned by Instagram and expire from the pending display after 60 seconds if they are not confirmed.

These intervals are implementation defaults, not guarantees of real-time delivery. Avoid reducing them: frequent requests can increase the likelihood of rate limits or account challenges.

## Tests

The project includes unit tests for the UI-independent helper functions and pending-message reconciliation.

Install the test dependency and run the suite:

```bash
python -m pip install pytest
python -m pytest -q
```

The tests do not log in to Instagram or make network requests.

## Project structure

```text
Terminalgram/
├── Terminalgram.py          # Textual application and Instagram integration
├── Terminalgram_core.py       # UI-independent helpers and message reconciliation
├── requirements.txt         # Runtime dependencies
├── tests/
│   └── test_terminalgram.py # Offline unit tests
├── .gitignore
└── README.md
```

## Limitations

- This is an unofficial client and depends on private Instagram API behavior.
- Instagram may change its API, require additional verification, rate-limit requests, or restrict access.
- The current implementation focuses on text-based Direct Messages.
- Non-text message items are shown as a placeholder such as `[image]`; media is not rendered.
- The application is a personal project, not an officially supported Instagram product.

## Dependencies

- [Textual](https://github.com/Textualize/textual) — terminal user interface framework.
- [Rich](https://github.com/Textualize/rich) — styled terminal text.
- [instagrapi](https://github.com/subzeroid/instagrapi) — unofficial Instagram API client.

---

Made as a Python terminal application project.
