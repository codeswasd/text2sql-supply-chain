import t2s.pipeline as pipeline
from t2s.pipeline import Assistant


def _fake(responses, calls):
    def fake(question, blocks, instructions="", error=None):
        calls.append(error)
        return responses[min(len(calls) - 1, len(responses) - 1)]

    return fake


def test_retry_feeds_error_back_and_recovers(monkeypatch):
    calls = []
    monkeypatch.setattr(
        pipeline,
        "generate_sql",
        _fake([("SELECT * FROM no_such_table", 10, 5), ("SELECT COUNT(*) FROM mfg_plant", 12, 6)], calls),
    )
    ans = Assistant().ask("How many plants?")
    assert ans.attempts == 2
    assert calls[0] is None and calls[1]  # second call got the error text
    assert ans.error is None and ans.rows
    assert (ans.input_tokens, ans.output_tokens) == (22, 11)


def test_no_retries_leaves_error(monkeypatch):
    calls = []
    monkeypatch.setattr(pipeline, "generate_sql", _fake([("SELECT * FROM no_such_table", 1, 1)], calls))
    ans = Assistant().ask("anything", retries=0)
    assert ans.attempts == 1 and ans.error
