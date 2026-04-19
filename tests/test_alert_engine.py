from src.alert_engine import AlertEngine
from src.session_state import SessionState


class DummyVoice:
    def __init__(self):
        self.calls = []

    def speak_alert(self, alert_type):
        self.calls.append(alert_type)


class DummyDatabase:
    def __init__(self):
        self.events = []

    def log_event(self, session_id, event_type, value, details):
        self.events.append((session_id, event_type, value, details))


def test_alert_engine_respects_cooldown_per_alert_type():
    state = SessionState()
    voice = DummyVoice()
    database = DummyDatabase()
    engine = AlertEngine(state, voice, database, session_id=7)
    engine.cooldown_seconds = 60

    state.update(is_monitoring=True, eye_alert=True, eye_reason='low blink rate', blink_rate=2)

    first_pass = engine.check()
    second_pass = engine.check()

    assert first_pass == ['EYE_STRAIN']
    assert second_pass == []
    assert voice.calls == ['EYE_STRAIN']
    assert len(database.events) == 1


def test_alert_engine_can_fire_multiple_alert_types():
    state = SessionState()
    voice = DummyVoice()
    database = DummyDatabase()
    engine = AlertEngine(state, voice, database, session_id=11)
    engine.cooldown_seconds = 0

    state.update(
        is_monitoring=True,
        eye_alert=True,
        eye_reason='low blink rate',
        blink_rate=1,
        posture_alert=True,
        posture_reason='slouch detected',
        posture_deviation=42,
    )

    fired = engine.check()

    assert 'EYE_STRAIN' in fired
    assert 'POOR_POSTURE' in fired
    assert len(database.events) == 2
