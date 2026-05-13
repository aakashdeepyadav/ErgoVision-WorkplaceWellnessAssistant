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


def test_head_tilt_alert_fires():
    state = SessionState()
    voice = DummyVoice()
    database = DummyDatabase()
    engine = AlertEngine(state, voice, database, session_id=20)
    engine.cooldown_seconds = 0

    state.update(
        is_monitoring=True,
        head_tilt_alert=True,
        head_tilt_reason='Head tilted right at 18°',
        head_tilt_angle=18.0,
    )

    fired = engine.check()
    assert 'HEAD_TILT' in fired
    assert len(database.events) == 1


def test_prolonged_stare_alert_fires():
    state = SessionState()
    voice = DummyVoice()
    database = DummyDatabase()
    engine = AlertEngine(state, voice, database, session_id=21)
    engine.cooldown_seconds = 0

    state.update(
        is_monitoring=True,
        stare_alert=True,
        stare_duration=45.0,
    )

    fired = engine.check()
    assert 'PROLONGED_STARE' in fired


def test_break_overdue_alert_fires():
    state = SessionState()
    voice = DummyVoice()
    database = DummyDatabase()
    engine = AlertEngine(state, voice, database, session_id=22)
    engine.cooldown_seconds = 0

    state.update(
        is_monitoring=True,
        break_overdue=True,
        time_since_break=1800,
    )

    fired = engine.check()
    assert 'TAKE_BREAK' in fired


def test_no_alerts_when_not_monitoring():
    state = SessionState()
    voice = DummyVoice()
    database = DummyDatabase()
    engine = AlertEngine(state, voice, database, session_id=30)
    engine.cooldown_seconds = 0

    state.update(
        is_monitoring=False,
        eye_alert=True,
        head_tilt_alert=True,
    )

    fired = engine.check()
    assert fired == []
