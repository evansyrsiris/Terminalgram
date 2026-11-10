#!/usr/bin/env python3
from __future__ import annotations

import argparse
import getpass
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from rich.text import Text
from terstagram_core import (
    body_of,
    fmt_time,
    login_error_hint,
    network_error_hint,
    reconcile_pending_messages,
    thread_title,
)
from textual import events, on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, Input, OptionList, RichLog, Static
from textual.widgets.option_list import Option

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "terstagram"
SESSION_FILE = CONFIG_DIR / "session.json"
POLL_INBOX_SECONDS = 45  
POLL_CHAT_SECONDS = 8    
REQUEST_DELAY = [0.2, 0.8]  


def _secure_config_dir() -> None:
    """Create the configuration directory and restrict its permissions where possible."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        CONFIG_DIR.chmod(0o700)
    except OSError:
        pass


def _secure_session_file() -> None:
    """Restrict the saved session file because it grants account access."""
    try:
        SESSION_FILE.chmod(0o600)
    except OSError:
        pass


def login(username: str | None):
    from instagrapi import Client
    from instagrapi.exceptions import TwoFactorRequired

    _secure_config_dir()
    cl = Client()
    cl.delay_range = REQUEST_DELAY

    old_uuids = None
    if SESSION_FILE.exists():
        try:
            _secure_session_file()
            cl.load_settings(SESSION_FILE)
            cl.direct_threads(amount=1)  # cheap call to check the session still works
            print("Resumed saved session.")
            return cl
        except Exception as exc:  # noqa: BLE001
            print(f"Could not resume the saved session ({type(exc).__name__}); attempting login.")
            try:
                old_uuids = cl.get_settings().get("uuids")
            except Exception:  # noqa: BLE001
                old_uuids = None

    cl = Client()
    cl.delay_range = REQUEST_DELAY
    if old_uuids:
        cl.set_uuids(old_uuids)

    username = username or input("Instagram username: ").strip()
    password = getpass.getpass("Password (not stored): ")
    try:
        cl.login(username, password)
    except TwoFactorRequired:
        code = input("2FA code: ").strip()
        cl.login(username, password, verification_code=code)

    cl.dump_settings(SESSION_FILE)
    _secure_session_file()  
    return cl


class _DoubleG:
    """`gg` = top. A single `g` just arms it for 0.6s."""
    _g_at = 0.0

    def action_g(self) -> None:
        now = time.monotonic()
        if now - self._g_at < 0.6:
            self._g_at = 0.0
            self.go_top()
        else:
            self._g_at = now


class VimList(_DoubleG, OptionList):
    BINDINGS = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("g", "g", "Top", show=False),
        Binding("G", "last", "Bottom", show=False),
        Binding("ctrl+d", "page_down", show=False),
        Binding("ctrl+u", "page_up", show=False),
        Binding("l", "select", "Open"),
    ]

    def go_top(self) -> None:
        self.action_first()


class VimLog(_DoubleG, RichLog):
    can_focus = True
    BINDINGS = [
        Binding("j", "line_down", "Down", show=False),
        Binding("k", "line_up", "Up", show=False),
        Binding("g", "g", "Top", show=False),
        Binding("G", "scroll_end", "Bottom", show=False),
        Binding("ctrl+d", "half_down", show=False),
        Binding("ctrl+u", "half_up", show=False),
        Binding("i,a,enter", "app.insert_mode", "Insert"),
        Binding("h", "app.focus_threads", "Chats"),
    ]

    def go_top(self) -> None:
        self.scroll_home(animate=False)

    def action_line_down(self) -> None:
        self.scroll_relative(y=1, animate=False)

    def action_line_up(self) -> None:
        self.scroll_relative(y=-1, animate=False)

    def action_half_down(self) -> None:
        self.scroll_relative(y=max(1, self.size.height // 2), animate=False)

    def action_half_up(self) -> None:
        self.scroll_relative(y=-max(1, self.size.height // 2), animate=False)

    def action_scroll_end(self) -> None:
        self.scroll_end(animate=False)


class MessageInput(Input):
    BINDINGS = [Binding("escape", "app.normal_mode", "Normal", show=True)]


# --------------------------------------------------------------------------
# App
# --------------------------------------------------------------------------
class Terstagram(App):
    TITLE = "Terstagram"
    CSS = """
    #threads { width: 34; border-right: solid $primary-darken-2; }
    #chat { width: 1fr; }
    #log { height: 1fr; padding: 0 1; }
    #input { dock: bottom; }
    #mode { dock: bottom; height: 1; padding: 0 1; background: $boost; }
    """
    BINDINGS = [
        Binding("ctrl+r", "refresh", "Refresh"),
        Binding("ctrl+t", "focus_threads", "Chats"),
        Binding("ctrl+q", "quit", "Quit", show=False),
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh", show=False),
    ]

    def __init__(self, client, username: str = ""):
        super().__init__()
        self.cl = client
        self.me = str(getattr(client, "user_id", "") or "")
        self.sub_title = f"@{username}" if username else ""
        self.threads: dict[str, object] = {}
        self.current_id: str | None = None
        self._rendered: dict[str, tuple] = {} 
        self._pending: dict[str, list[dict]] = {}  

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Horizontal():
            yield VimList(id="threads")
            with Vertical(id="chat"):
                yield VimLog(id="log", wrap=True, markup=False, highlight=False)
                yield MessageInput(placeholder="Select a chat on the left first", id="input", disabled=True)
        yield Static("-- NORMAL --", id="mode")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#threads").focus()
        self.load_threads()
        self.set_interval(POLL_INBOX_SECONDS, self.load_threads)
        self.set_interval(POLL_CHAT_SECONDS, self.poll_chat)

    # ---- actions ---------------------------------------------------------
    def action_refresh(self) -> None:
        self.load_threads()
        self.poll_chat()

    def action_focus_threads(self) -> None:
        self.query_one("#threads").focus()

    def action_insert_mode(self) -> None:
        inp = self.query_one("#input", Input)
        if not inp.disabled:
            inp.focus()

    def action_normal_mode(self) -> None:
        self.query_one("#log").focus()

    @on(events.DescendantFocus)
    def _update_mode(self, event: events.DescendantFocus) -> None:
        w = event.widget
        label = "-- INSERT --" if w.id == "input" else "-- NORMAL --"
        self.query_one("#mode", Static).update(label)

    def poll_chat(self) -> None:
        if self.current_id:
            self.load_messages(self.current_id)

    # ---- network (threads, so the UI never blocks) -----------------------
    @work(thread=True, exclusive=True, group="threads")
    def load_threads(self) -> None:
        try:
            threads = self.cl.direct_threads(amount=20)
        except Exception as e:  # noqa: BLE001
            self.call_from_thread(self.notify, f"Could not load chats: {network_error_hint(e)}", severity="error")
            return
        self.call_from_thread(self.show_threads, threads)

    @work(thread=True, exclusive=True, group="messages")
    def load_messages(self, thread_id: str) -> None:
        try:
            msgs = self.cl.direct_messages(int(thread_id), amount=30)
        except Exception as e:  # noqa: BLE001
            self.call_from_thread(self.notify, f"Could not load messages: {network_error_hint(e)}", severity="error")
            return
        self.call_from_thread(self.show_messages, thread_id, msgs)

    @work(thread=True, group="send")
    def send_message(self, thread_id: str, pending: dict) -> None:
        try:
            self.cl.direct_send(pending["text"], thread_ids=[int(thread_id)])
        except Exception as e:  # noqa: BLE001
            self.call_from_thread(self.notify, f"Send failed: {network_error_hint(e)}", severity="error")
            self.call_from_thread(self.drop_pending, thread_id, pending)

    def drop_pending(self, thread_id: str, pending: dict) -> None:
        if pending in self._pending.get(thread_id, []):
            self._pending[thread_id].remove(pending)
        self._rendered.pop(thread_id, None)
        self.load_messages(thread_id)

    # ---- rendering -------------------------------------------------------
    def show_threads(self, threads) -> None:
        self.threads = {str(t.id): t for t in threads}
        ol = self.query_one("#threads", OptionList)
        ol.clear_options()
        options = []
        for t in threads:
            preview = ""
            if t.messages:
                m = t.messages[0]  # newest first
                prefix = "you: " if m.is_sent_by_viewer else ""
                preview = (prefix + body_of(m)).replace("\n", " ")[:30]
            options.append(Option(Text.assemble((thread_title(t), "bold"), "\n", (preview, "dim")), id=str(t.id)))
        ol.add_options(options)
        if self.current_id:
            try:
                ol.highlighted = ol.get_option_index(self.current_id)
            except Exception:  # noqa: BLE001
                pass
        elif options and ol.highlighted is None:
            ol.highlighted = 0

    def show_messages(self, thread_id: str, msgs) -> None:
        if thread_id != self.current_id:
            return 
        still = reconcile_pending_messages(msgs, self._pending.get(thread_id, []), self.me)
        self._pending[thread_id] = still

        sig = (tuple(str(m.id) for m in msgs), tuple(p["text"] for p in still))
        if self._rendered.get(thread_id) == sig:
            return 
        self._rendered[thread_id] = sig
        t = self.threads.get(thread_id)
        names = {str(u.pk): u.username for u in (t.users if t else [])}
        log = self.query_one("#log", RichLog)
        log.clear()
        for m in reversed(msgs):
            mine = m.is_sent_by_viewer or str(m.user_id) == self.me
            who = "me" if mine else names.get(str(m.user_id), "?")
            log.write(Text.assemble(
                (f"{fmt_time(m.timestamp)} ", "dim"),
                (f"{who}: ", "bold green" if mine else "bold cyan"),
                body_of(m),
            ))
        for p in still:
            log.write(Text.assemble((f"{p['when']} ", "dim"), ("me: ", "bold green"), p["text"]))

    # ---- events ----------------------------------------------------------
    @on(OptionList.OptionSelected, "#threads")
    def open_thread(self, event: OptionList.OptionSelected) -> None:
        self.current_id = event.option.id
        t = self.threads.get(self.current_id)
        self.sub_title = thread_title(t) if t else ""
        self.query_one("#log", RichLog).clear()
        self._rendered.pop(self.current_id, None)
        if t and t.messages:
            self.show_messages(self.current_id, t.messages) 
        inp = self.query_one("#input", Input)
        inp.disabled = False
        inp.placeholder = "Message… (Enter to send, Ctrl+T for chats)"
        inp.focus()
        self.load_messages(self.current_id)

    @on(Input.Submitted, "#input")
    def submit(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text or not self.current_id:
            return
        event.input.value = ""
        tid = self.current_id
        known = frozenset(self._rendered.get(tid, ((), ()))[0])
        pending = {"text": text, "known": known, "t": time.monotonic(), "when": fmt_time(datetime.now())}
        self._pending.setdefault(tid, []).append(pending)
        self._rendered.pop(tid, None) 
        self.query_one("#log", RichLog).write(
            Text.assemble((f"{pending['when']} ", "dim"), ("me: ", "bold green"), text)
        )
        self.send_message(tid, pending)


def main() -> None:
    ap = argparse.ArgumentParser(description="Instagram DMs in your terminal.")
    ap.add_argument("-u", "--username", help="Instagram username")
    ap.add_argument("--logout", action="store_true", help="delete the saved session and exit")
    ap.add_argument("--debug", action="store_true", help="show full tracebacks on login errors")
    args = ap.parse_args()

    if args.logout:
        SESSION_FILE.unlink(missing_ok=True)
        print("Saved local session deleted.")
        return

    try:
        client = login(args.username)
    except Exception as e:  # noqa: BLE001
        if args.debug:
            import traceback
            traceback.print_exc()
        name = type(e).__name__
        sys.exit(f"Login failed ({name}).\n{login_error_hint(e)}")
    Terstagram(client, username=args.username or "").run()


if __name__ == "__main__":
    main()