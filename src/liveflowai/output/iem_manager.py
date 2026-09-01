# src/liveflowai/output/iem_manager.py

from typing import Iterable, Optional
import base64
import platform
import shutil
import subprocess
import threading
import time


class IEMManager:
    """
    IEM announcement and metronome manager.

    Features:
        - Announces next song information
        - Announces duration, BPM, and opening chords
        - Text-to-speech
        - Continuous background metronome
        - WSL-compatible Windows audio output
    """

    def __init__(
        self,
        enable_speech: bool = True,
        rate: int = 175,
        volume: float = 1.0,
    ):
        self.enable_speech = enable_speech
        self.rate = rate
        self.volume = volume

        # --------------------------------------------------------
        # Speech
        # --------------------------------------------------------

        self.engine = None
        self.speech_backend = None

        if self.enable_speech:
            self._init_speech()

        # --------------------------------------------------------
        # Metronome
        # --------------------------------------------------------

        self.metronome_running = False
        self.metronome_bpm = 120.0
        self.metronome_thread = None
        self.metronome_stop_event = threading.Event()

    # ============================================================
    # PLATFORM DETECTION
    # ============================================================

    @staticmethod
    def _is_wsl() -> bool:
        """Return True when running inside WSL."""

        try:
            with open(
                "/proc/version",
                "r",
                encoding="utf-8",
            ) as f:
                version = f.read().lower()

            return (
                "microsoft" in version
                or "wsl" in version
            )

        except Exception:
            return False

    # ============================================================
    # SPEECH SETUP
    # ============================================================

    def _init_speech(self):
        """
        Select speech backend.

        WSL:
            Windows SpeechSynthesizer.

        Native Windows/Linux:
            pyttsx3.
        """

        # --------------------------------------------------------
        # WSL
        # --------------------------------------------------------

        if self._is_wsl():

            if shutil.which("powershell.exe"):

                self.speech_backend = "windows"

                print(
                    "[IEMManager] "
                    "Using Windows SpeechSynthesizer."
                )

                return

            print(
                "[IEMManager] Windows PowerShell unavailable. "
                "Speech disabled."
            )

            self.enable_speech = False
            return

        # --------------------------------------------------------
        # Native pyttsx3
        # --------------------------------------------------------

        try:

            import pyttsx3

            self.engine = pyttsx3.init()

            self.engine.setProperty(
                "rate",
                self.rate,
            )

            self.engine.setProperty(
                "volume",
                self.volume,
            )

            self.speech_backend = "pyttsx3"

            print(
                "[IEMManager] "
                "Using pyttsx3 speech engine."
            )

        except Exception as e:

            print(
                "[IEMManager] "
                f"Speech unavailable: {e}"
            )

            self.enable_speech = False

    # ============================================================
    # FORMATTING
    # ============================================================

    @staticmethod
    def _format_duration(
        duration_seconds: float,
    ) -> str:
        """Format seconds as M:SS."""

        total_seconds = int(
            round(duration_seconds)
        )

        minutes, seconds = divmod(
            total_seconds,
            60,
        )

        return f"{minutes}:{seconds:02d}"

    @staticmethod
    def _describe_chords(
        chords: Optional[Iterable],
        limit: int = 5,
    ) -> Optional[str]:
        """Create a spoken-friendly chord summary."""

        if not chords:
            return None

        chord_names = [
            str(chord)
            for chord in chords
        ][:limit]

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
        Announce the next song.

        Prints:
            title
            duration
            BPM
            opening chords

        Also speaks the announcement when enabled.
        """

        duration_display = self._format_duration(
            duration_seconds
        )

        duration_minutes = (
            duration_seconds / 60
        )

        message_lines = [
            "\n=== NEXT SONG ===",
            f"Title:    {title}",
            f"Duration: {duration_display} "
            f"({duration_minutes:.1f} min)",
            f"Tempo:    {bpm:.0f} BPM",
        ]

        chord_summary = self._describe_chords(
            chords
        )

        if chord_summary:
            message_lines.append(
                f"Opening chords: {chord_summary}"
            )

        message_lines.append(
            "=================\n"
        )

        printed_message = "\n".join(
            message_lines
        )

        print(printed_message)

        spoken_message = (
            f"Next up: {title}. "
            f"Duration {duration_display}, "
            f"at {bpm:.0f} beats per minute."
        )

        if (
            speak
            and self.enable_speech
            and self.speech_backend
        ):
            self._speak(spoken_message)

        return spoken_message

    # ============================================================
    # SPEECH
    # ============================================================

    def _speak(self, text: str) -> None:
        """Speak using the selected backend."""

        if self.speech_backend == "windows":
            self._speak_windows(text)

        elif self.speech_backend == "pyttsx3":
            self._speak_pyttsx3(text)

    # ============================================================
    # WINDOWS SPEECH
    # ============================================================

    def _speak_windows(self, text: str) -> None:
        """Use Windows SpeechSynthesizer."""

        try:

            windows_rate = int(
                max(
                    -10,
                    min(
                        10,
                        (self.rate - 150) // 20,
                    ),
                )
            )

            windows_volume = int(
                max(
                    0,
                    min(
                        100,
                        self.volume * 100,
                    ),
                )
            )

            safe_text = text.replace(
                "'",
                "''",
            )

            script = f"""
Add-Type -AssemblyName System.Speech

$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer

$synth.Rate = {windows_rate}
$synth.Volume = {windows_volume}

$synth.SetOutputToDefaultAudioDevice()

$synth.Speak('{safe_text}')

$synth.Dispose()
"""

            encoded = base64.b64encode(
                script.encode("utf-16le")
            ).decode("ascii")

            subprocess.run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-NonInteractive",
                    "-EncodedCommand",
                    encoded,
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
            )

        except Exception as e:

            print(
                "[IEMManager] "
                f"Windows speech failed: {e}"
            )

    # ============================================================
    # PYTTSX3 SPEECH
    # ============================================================

    def _speak_pyttsx3(
        self,
        text: str,
    ) -> None:

        try:

            self.engine.say(text)
            self.engine.runAndWait()

        except Exception as e:

            print(
                "[IEMManager] "
                f"Speech playback failed: {e}"
            )

    # ============================================================
    # METRONOME
    # ============================================================

    def start_metronome(
        self,
        bpm: float,
    ) -> None:
        """
        Start the metronome in a background thread.

        The metronome continues until stop_metronome()
        is called.

        Example:

            iem.start_metronome(99)
        """

        try:
            bpm = float(bpm)

        except (TypeError, ValueError):
            print(
                "[IEMManager] Invalid metronome BPM."
            )
            return

        if bpm <= 0:
            print(
                "[IEMManager] BPM must be greater than 0."
            )
            return

        if bpm > 300:
            print(
                "[IEMManager] BPM cannot exceed 300."
            )
            return

        # Stop an existing metronome first.
        self.stop_metronome()

        self.metronome_bpm = bpm
        self.metronome_running = True
        self.metronome_stop_event.clear()

        self.metronome_thread = threading.Thread(
            target=self._metronome_loop,
            daemon=True,
        )

        self.metronome_thread.start()

        print(
            f"[IEMManager] "
            f"Metronome started: {bpm:.0f} BPM"
        )

    # ============================================================
    # METRONOME LOOP
    # ============================================================

    def _metronome_loop(self):
        """Continuously generate metronome beats."""

        next_beat = time.perf_counter()

        while not self.metronome_stop_event.is_set():

            # Read current BPM each beat so it can be changed
            # while the metronome is running.
            bpm = self.metronome_bpm

            interval = 60.0 / bpm

            # Make the click.
            self._metronome_click()

            # Schedule next beat.
            next_beat += interval

            sleep_time = (
                next_beat
                - time.perf_counter()
            )

            if sleep_time > 0:

                self.metronome_stop_event.wait(
                    sleep_time
                )

            else:

                # We fell behind. Reset timing rather than
                # rapidly firing several catch-up clicks.
                next_beat = time.perf_counter()

        self.metronome_running = False

    # ============================================================
    # METRONOME CLICK
    # ============================================================

    def _metronome_click(self):
        """
        Play one audible metronome click through Windows.

        Works from WSL by calling powershell.exe.
        """

        if self._is_wsl():

            if not shutil.which("powershell.exe"):
                return

            try:
                subprocess.run(
                    [
                        "powershell.exe",
                        "-NoProfile",
                        "-NonInteractive",
                        "-Command",
                        "[console]::beep(1000,45)",
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )

            except Exception:
                pass

            return

        if platform.system() == "Windows":

            try:
                import winsound

                winsound.Beep(
                    1000,
                    45,
                )

            except Exception:
                pass

            return

        # Linux fallback
    try:
        print("\a", end="", flush=True)
    except Exception:
        pass

    # ============================================================
    # CHANGE METRONOME BPM
    # ============================================================

    def set_metronome_bpm(
        self,
        bpm: float,
    ) -> None:
        """
        Change the BPM of a running metronome.

        Example:

            iem.set_metronome_bpm(99)
        """

        try:
            bpm = float(bpm)

        except (TypeError, ValueError):

            print(
                "[IEMManager] Invalid metronome BPM."
            )
            return

        if bpm <= 0 or bpm > 300:

            print(
                "[IEMManager] "
                "Metronome BPM must be between "
                "1 and 300."
            )
            return

        self.metronome_bpm = bpm

        print(
            f"[IEMManager] "
            f"Metronome BPM changed to {bpm:.0f}"
        )

    # ============================================================
    # STOP METRONOME
    # ============================================================

    def stop_metronome(self) -> None:
        """Stop the background metronome."""

        if not self.metronome_running:
            return

        self.metronome_stop_event.set()

        if (
            self.metronome_thread is not None
            and self.metronome_thread.is_alive()
            and threading.current_thread()
            is not self.metronome_thread
        ):

            self.metronome_thread.join(
                timeout=1.0
            )

        self.metronome_running = False
        self.metronome_thread = None

        print(
            "[IEMManager] Metronome stopped."
        )

    # ============================================================
    # SHUTDOWN
    # ============================================================

    def shutdown(self) -> None:
        """Stop metronome and release speech engine."""

        self.stop_metronome()

        if self.engine is not None:

            try:
                self.engine.stop()

            except Exception:
                pass
if __name__ == "__main__":

    iem = IEMManager(
        enable_speech=False
    )

    iem.start_metronome(60)

    try:
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        iem.stop_metronome()    