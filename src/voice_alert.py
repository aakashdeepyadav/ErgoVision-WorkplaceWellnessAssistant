"""
ErgoVision — Voice Alert System
Offline text-to-speech wrapper using pyttsx3.
"""

import threading
import pyttsx3

import config


class VoiceAlert:
    """
    Non-blocking offline TTS alert system.
    Runs speech in a separate thread to avoid blocking the main loop.
    """

    def __init__(self):
        self.enabled = True
        self._engine = None
        self._lock = threading.Lock()
        self._speaking = False

    def _init_engine(self):
        """Initialize TTS engine (must be done in the thread that uses it)."""
        engine = pyttsx3.init()
        engine.setProperty("rate", 160)   # Moderate speed
        engine.setProperty("volume", 0.8)
        
        # Try to set a natural-sounding voice
        voices = engine.getProperty("voices")
        for voice in voices:
            if "female" in voice.name.lower() or "zira" in voice.name.lower():
                engine.setProperty("voice", voice.id)
                break
        
        return engine

    def speak(self, message):
        """
        Speak a message in a background thread.
        
        Args:
            message: text to speak
        """
        if not self.enabled:
            return
        if self._speaking:
            return  # Don't queue — skip if already speaking

        thread = threading.Thread(target=self._speak_thread, args=(message,), daemon=True)
        thread.start()

    def _speak_thread(self, message):
        """Background thread for TTS."""
        with self._lock:
            self._speaking = True
            try:
                engine = self._init_engine()
                engine.say(message)
                engine.runAndWait()
                engine.stop()
            except Exception as e:
                print(f"[VoiceAlert] TTS error: {e}")
            finally:
                self._speaking = False

    def speak_alert(self, alert_type):
        """
        Speak a predefined alert message by type.
        
        Args:
            alert_type: one of EYE_STRAIN, POOR_POSTURE, TOO_CLOSE, FATIGUE
        """
        message = config.ALERT_MESSAGES.get(alert_type, "Please take a break.")
        self.speak(message)

    def toggle(self):
        """Toggle voice alerts on/off."""
        self.enabled = not self.enabled
        return self.enabled
