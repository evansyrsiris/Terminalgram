from datetime import datetime, timezone
from types import SimpleNamespace

from terstagram_core import body_of, fmt_time, login_error_hint, network_error_hint, reconcile_pending_messages, thread_title


def test_thread_title_prefers_custom_title():
    thread = SimpleNamespace(thread_title="Project chat", users=[])
    assert thread_title(thread) == "Project chat"


def test_thread_title_falls_back_to_usernames():
    thread = SimpleNamespace(
        thread_title=None,
        users=[SimpleNamespace(username="alice"), SimpleNamespace(username="bob")],
    )
    assert thread_title(thread) == "alice, bob"


def test_thread_title_handles_unknown_thread():
    thread = SimpleNamespace(thread_title=None, users=[])
    assert thread_title(thread) == "(unknown)"


def test_body_of_returns_text_when_available():
    assert body_of(SimpleNamespace(text="hello", item_type="text")) == "hello"


def test_body_of_labels_non_text_message():
    assert body_of(SimpleNamespace(text=None, item_type="image")) == "[image]"


def test_body_of_handles_missing_item_type():
    assert body_of(SimpleNamespace(text=None, item_type=None)) == "[message]"


def test_fmt_time_handles_missing_timestamp():
    assert fmt_time(None) == ""


def test_fmt_time_formats_datetime():
    value = datetime(2024, 1, 2, 3, 4, tzinfo=timezone.utc)
    assert fmt_time(value)  # Format depends on the machine's local timezone/date.


def test_reconcile_removes_message_confirmed_by_server():
    pending = [{"text": "hello", "known": set(), "t": 10.0}]
    messages = [SimpleNamespace(
        id="new-id", is_sent_by_viewer=True, user_id="me", text="hello"
    )]
    assert reconcile_pending_messages(messages, pending, me="me", now=11.0) == []


def test_reconcile_keeps_unconfirmed_message_until_timeout():
    pending_item = {"text": "hello", "known": set(), "t": 10.0}
    assert reconcile_pending_messages([], [pending_item], me="me", now=20.0) == [pending_item]


def test_reconcile_drops_unconfirmed_message_after_timeout():
    pending_item = {"text": "hello", "known": set(), "t": 10.0}
    assert reconcile_pending_messages([], [pending_item], me="me", now=71.0) == []


def test_reconcile_does_not_consume_previously_known_message():
    pending_item = {"text": "hello", "known": {"old-id"}, "t": 10.0}
    messages = [SimpleNamespace(
        id="old-id", is_sent_by_viewer=True, user_id="me", text="hello"
    )]
    assert reconcile_pending_messages(messages, [pending_item], me="me", now=20.0) == [pending_item]


def test_login_error_hint_is_actionable():
    error = type("PleaseWaitFewMinutes", (Exception,), {})()
    assert "rate-limiting" in login_error_hint(error)


def test_login_error_hint_has_safe_fallback():
    assert "--debug" in login_error_hint(RuntimeError("sensitive detail"))


def test_network_error_hint_does_not_echo_raw_exception_text():
    error = RuntimeError("private request payload")
    hint = network_error_hint(error)
    assert "private request payload" not in hint
    assert "RuntimeError" in hint


def test_network_error_hint_explains_rate_limit():
    error = type("PleaseWaitFewMinutes", (Exception,), {})()
    assert "rate-limiting" in network_error_hint(error)
