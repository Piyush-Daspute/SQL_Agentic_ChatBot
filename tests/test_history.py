import json

from workflow import serialize_recent_chat_history


def test_serialize_recent_chat_history_keeps_last_five_exchanges():
    messages = []
    for turn in range(6):
        messages.extend([
            {"role": "user", "content": f"Question {turn}"},
            {"role": "assistant", "content": f"Answer {turn}", "sql": "SELECT 1"},
        ])

    history = json.loads(serialize_recent_chat_history(messages))

    assert len(history) == 10
    assert history[0] == {"role": "user", "content": "Question 1"}
    assert history[-1] == {"role": "assistant", "content": "Answer 5"}
    assert "sql" not in history[-1]


def test_serialize_recent_chat_history_preserves_unicode():
    history = json.loads(serialize_recent_chat_history([
        {"role": "user", "content": "Show employees in Zürich"},
    ]))

    assert history == [{"role": "user", "content": "Show employees in Zürich"}]
