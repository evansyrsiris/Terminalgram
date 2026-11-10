
from __future__ import annotations

import time
from datetime import datetime


def thread_title(thread) -> str:
    return thread.thread_title or ", ".join(user.username for user in thread.users) or "(unknown)"


def body_of(message) -> str:
    if message.text:
        return message.text
    return f"[{message.item_type or 'message'}]"


def fmt_time(timestamp: datetime | None) -> str:
    if timestamp is None:
        return ""
    if timestamp.tzinfo is not None:
        timestamp = timestamp.astimezone()
    now = datetime.now(timestamp.tzinfo)
    return timestamp.strftime("%H:%M") if timestamp.date() == now.date() else timestamp.strftime("%d %b %H:%M")


def reconcile_pending_messages(messages, pending: list[dict], me: str,
                               now: float | None = None, timeout: float = 60) -> list[dict]:
    now = time.monotonic() if now is None else now
    consumed: set[str] = set()
    still: list[dict] = []

    for item in pending:
        match = next((message for message in messages
                      if (message.is_sent_by_viewer or str(message.user_id) == me)
                      and message.text == item["text"]
                      and str(message.id) not in item["known"]
                      and str(message.id) not in consumed), None)
        if match is not None:
            consumed.add(str(match.id))
        elif now - item["t"] < timeout:
            still.append(item)
    return still


def login_error_hint(error: Exception) -> str:
    hints = {
        "BadPassword": "Instagram rejected the password.",
        "ChallengeRequired": "Instagram wants a security check. Approve the login in the Instagram app, then retry.",
        "TwoFactorRequired": "A two-factor authentication code is required or was rejected.",
        "PleaseWaitFewMinutes": "Instagram is rate-limiting requests. Stop retrying and wait before trying again.",
        "RateLimitError": "Instagram is rate-limiting requests. Stop retrying and wait before trying again.",
    }
    return hints.get(type(error).__name__, "Unexpected login error. Re-run with --debug for a traceback.")


def network_error_hint(error: Exception) -> str:
    hints = {
        "PleaseWaitFewMinutes": "Instagram is rate-limiting requests. Wait before retrying.",
        "RateLimitError": "Instagram is rate-limiting requests. Wait before retrying.",
        "ChallengeRequired": "Instagram requested a security check. Complete it in the official app before retrying.",
        "LoginRequired": "The saved session may have expired. Run with --logout, then sign in again.",
    }
    return hints.get(
        type(error).__name__,
        f"Request failed ({type(error).__name__}). Check your connection and try again later.",
    )
