from app.call_log import CallLog


def _fresh_log(tmp_path):
    return CallLog(str(tmp_path / "calls.db"))


def test_start_call_returns_incrementing_ids(tmp_path):
    log = _fresh_log(tmp_path)
    first = log.start_call("+237600000001")
    second = log.start_call("+237600000002")
    assert second > first


def test_get_call_includes_turns_in_order(tmp_path):
    log = _fresh_log(tmp_path)
    call_id = log.start_call("+237600000001")
    log.log_turn(call_id, "caller", "Do you have red bags?")
    log.log_turn(call_id, "assistant", "Yes, we have one in stock.")

    call = log.get_call(call_id)
    assert call["caller_number"] == "+237600000001"
    assert [t["role"] for t in call["turns"]] == ["caller", "assistant"]
    assert call["turns"][0]["text"] == "Do you have red bags?"


def test_get_call_returns_none_for_unknown_id(tmp_path):
    log = _fresh_log(tmp_path)
    assert log.get_call(9999) is None


def test_end_call_sets_ended_at(tmp_path):
    log = _fresh_log(tmp_path)
    call_id = log.start_call(None)
    assert log.get_call(call_id)["ended_at"] is None
    log.end_call(call_id)
    assert log.get_call(call_id)["ended_at"] is not None


def test_first_audio_latency_is_recorded_only_once(tmp_path):
    log = _fresh_log(tmp_path)
    call_id = log.start_call(None)
    log.log_first_audio_latency(call_id, 450.0)
    log.log_first_audio_latency(call_id, 900.0)  # should be ignored — already set
    assert log.get_call(call_id)["first_audio_latency_ms"] == 450.0


def test_latency_stats_computes_percentiles(tmp_path):
    log = _fresh_log(tmp_path)
    for latency in [100, 200, 300, 400, 500]:
        call_id = log.start_call(None)
        log.log_first_audio_latency(call_id, latency)

    stats = log.latency_stats()
    assert stats["count"] == 5
    assert stats["p50_ms"] == 300
    assert stats["p95_ms"] == 500


def test_latency_stats_empty_when_no_calls(tmp_path):
    log = _fresh_log(tmp_path)
    assert log.latency_stats() == {"count": 0, "p50_ms": None, "p95_ms": None}


def test_list_calls_orders_most_recent_first(tmp_path):
    log = _fresh_log(tmp_path)
    first = log.start_call("+237600000001")
    second = log.start_call("+237600000002")
    calls = log.list_calls()
    assert [c["id"] for c in calls] == [second, first]
