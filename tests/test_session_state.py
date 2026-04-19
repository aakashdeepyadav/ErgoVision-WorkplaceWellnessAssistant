from src.session_state import SessionState


def test_update_ignores_unknown_keys_and_preserves_known_values():
    state = SessionState()

    state.update(ear=0.218, blink_rate=9, non_existing_key='ignored')

    assert state.get('ear') == 0.218
    assert state.get('blink_rate') == 9
    assert state.get('non_existing_key') is None


def test_get_all_returns_copy_not_internal_reference():
    state = SessionState()
    snapshot = state.get_all()

    snapshot['ear'] = 99

    assert state.get('ear') != 99
