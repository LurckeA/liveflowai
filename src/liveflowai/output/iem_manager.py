# src/liveflowai/output/iem_manager.py

from typing import Iterable, Optional


class IEMManager:
    """
    Announce upcoming song information to the performer, typically
    routed to an in-ear monitor (IEM) mix.

    Prints a formatted announcement to the console and, if a
    text-to-speech engine is available, speaks it aloud as well.
    """

    def __init__(
        self,
        enable_speech: bool = True,
        rate: int = 175,
        volume: float = 1.0,
    ):
        self.enable_speech = enable_speech
        self.engine = None

        if self.enable_speech:
            self.engine = self._init_engine(rate, volume)

    # ============================================================
    # ENGINE SETUP
    # ============================================================

    @staticmethod
    def _init_engine(rate: int, volume: float):
        """
        Try to initialize the pyttsx3 TTS engine.

        Returns None (and disables speech) if it fails, e.g. because
        no audio output device is available.
        """

        try:
            import pyttsx3

            engine = pyttsx3.init()
            engine.setProperty("rate", rate)
            engine.setProperty("volume", volume)

            return engine

        except Exception as e:
            print(
                f"[IEMManager] Speech engine unavailable, "
                f"falling back to text-only announcements: {e}"
            )

            return None

    # ============================================================
    # FORMATTING HELPERS
    # ============================================================

    @staticmethod
    def _format_duration(duration_seconds: float) -> str:
        """Format seconds as M:SS, e.g. 187.4 -> '3:07'."""

        total_seconds = int(round(duration_seconds))
        minutes, seconds = divmod(total_seconds, 60)

        return f"{minutes}:{seconds:02d}"

    @staticmethod
    def _describe_chords(
        chords: Optional[Iterable],
        limit: int = 5,
    ) -> Optional[str]:
        """
        Build a short, spoken-friendly summary of the opening chords.

        Accepts chord objects (via str()) or plain strings. Returns
        None if there are no chords to describe.
        """

        if not chords:
            return None

        chord_names = [str(chord) for chord in chords][:limit]

        if not chord_names:
            return None

        return ", ".join(chord_names)

    # ============================================================
    # ANNOUNCEMENT
    # ============================================================

    def announce_next_song(
        self,
        title: str,
        duration_seconds: float,
        bpm: float,
        chords: Optional[Iterable] = None,
        speak: bool = True,
    ) -> str:
        """
        Announce the next song's title, duration, and BPM.

        Args:
            title: Song title (e.g. file stem).
            duration_seconds: Song duration in seconds.
            bpm: Tempo in beats per minute.
            chords: Optional iterable of detected chords; only the
                opening few are mentioned.
            speak: Whether to speak the announcement aloud, in
                addition to printing it. Ignored if speech is
                disabled or unavailable.

        Returns:
            The announcement text that was printed/spoken.
        """

        duration_display = self._format_duration(duration_seconds)
        duration_minutes = duration_seconds / 60

        message_lines = [
            "\n=== NEXT SONG ===",
            f"Title:    {title}",
            f"Duration: {duration_display} "
            f"({duration_minutes:.1f} min)",
            f"Tempo:    {bpm:.0f} BPM",
        ]

        chord_summary = self._describe_chords(chords)

        if chord_summary:
            message_lines.append(f"Opening chords: {chord_summary}")

        message_lines.append("=================\n")

        printed_message = "\n".join(message_lines)
        print(printed_message)

        spoken_message = (
            f"Next up: {title}. "
            f"Duration {duration_display}, at {bpm:.0f} beats per minute."
        )

        if speak and self.enable_speech and self.engine is not None:
            self._speak(spoken_message)

        return spoken_message

    # ============================================================
    # LOW-LEVEL SPEECH
    # ============================================================

    def _speak(self, text: str) -> None:
        """Speak the given text, swallowing any runtime engine errors."""

        try:
            self.engine.say(text)
            self.engine.runAndWait()

        except Exception as e:
            print(f"[IEMManager] Speech playback failed: {e}")

    # ============================================================
    # SHUTDOWN
    # ============================================================

    def shutdown(self) -> None:
        """Release the TTS engine, if one was initialized."""

        if self.engine is not None:
            try:
                self.engine.stop()
            except Exception:
                pass

            self.engine = None