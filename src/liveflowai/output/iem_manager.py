# src/liveflowai/output/iem_manager.py

from typing import Iterable, Optional
import base64
import math
import os
import platform
import shutil
import subprocess
import tempfile
import threading
import wave
import struct


class IEMManager:
    """
    LIVEFLOWAI IEM manager.

    Features:
        - Announces the predicted song
        - Announces duration, BPM, and opening chords
        - Windows/WSL text-to-speech
        - Accurate continuous metronome
        - Automatic metronome BPM from predicted song
        - Metronome can be stopped/restarted safely
    """

    # ============================================================
    # INITIALIZATION
    # ============================================================

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
        self.metronome_process = None

        self.metronome_stop_event = threading.Event()

        self.metronome_click_file = None

        # Used to prevent an old metronome process from
        # continuing after a new BPM is selected.
        self._metronome_lock = threading.Lock()

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
                "[IEMManager] "
                "Windows PowerShell unavailable. "
                "Speech disabled."
            )

            self.enable_speech = False

            return

        # --------------------------------------------------------
        # Native Windows/Linux
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

    def _speak(
        self,
        text: str,
    ) -> None:
        """Speak using the selected backend."""

        if self.speech_backend == "windows":

            self._speak_windows(text)

        elif self.speech_backend == "pyttsx3":

            self._speak_pyttsx3(text)

    # ============================================================
    # WINDOWS SPEECH
    # ============================================================

    def _speak_windows(
        self,
        text: str,
    ) -> None:
        """Use Windows SpeechSynthesizer through WSL."""

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
    # METRONOME CLICK TRACK GENERATION
    # ============================================================

    def _create_metronome_track(
        self,
        bpm: float,
        duration_seconds: float = 300.0,
    ) -> str:
        """
        Generate a long WAV click track.

        The important difference from the previous implementation
        is that PowerShell is NOT started for every beat.

        Instead, all beats are placed into one WAV file with exact
        sample positions.

        300 seconds = 5 minutes.

        At 44.1 kHz this gives very accurate beat spacing.
        """

        sample_rate = 44100

        # --------------------------------------------------------
        # Click properties
        # --------------------------------------------------------

        click_duration = 0.075

        normal_frequency = 1200.0
        accent_frequency = 1700.0

        normal_volume = 0.75
        accent_volume = 0.90

        click_samples = int(
            sample_rate * click_duration
        )

        total_samples = int(
            sample_rate * duration_seconds
        )

        # --------------------------------------------------------
        # Calculate exact beat interval.
        #
        # We calculate beat positions directly from BPM instead
        # of repeatedly sleeping 60/BPM.
        # --------------------------------------------------------

        beat_interval = (
            60.0 / bpm
        )

        # --------------------------------------------------------
        # Output file
        # --------------------------------------------------------

        path = os.path.join(
            tempfile.gettempdir(),
            "liveflow_metronome.wav",
        )

        # --------------------------------------------------------
        # Build click samples once.
        # --------------------------------------------------------

        normal_click = []

        accent_click = []

        for i in range(click_samples):

            t = i / sample_rate

            # Exponential-ish decay.

            envelope = (
                1.0
                - (i / click_samples)
            )

            envelope = envelope ** 2

            normal_value = int(
                32767
                * normal_volume
                * envelope
                * math.sin(
                    2
                    * math.pi
                    * normal_frequency
                    * t
                )
            )

            accent_value = int(
                32767
                * accent_volume
                * envelope
                * math.sin(
                    2
                    * math.pi
                    * accent_frequency
                    * t
                )
            )

            normal_click.append(
                struct.pack(
                    "<h",
                    normal_value,
                )
            )

            accent_click.append(
                struct.pack(
                    "<h",
                    accent_value,
                )
            )

        # --------------------------------------------------------
        # Generate WAV
        # --------------------------------------------------------

        with wave.open(
            path,
            "wb",
        ) as wav:

            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)

            # ----------------------------------------------------
            # Write silence/beat positions.
            # ----------------------------------------------------

            current_sample = 0
            beat_number = 0

            # A zero sample.

            silence_sample = struct.pack(
                "<h",
                0,
            )

            while current_sample < total_samples:

                # Exact beat position.

                beat_time = (
                    beat_number
                    * beat_interval
                )

                beat_sample = int(
                    round(
                        beat_time
                        * sample_rate
                    )
                )

                # Silence between previous beat and
                # current beat.

                silence_samples = (
                    beat_sample
                    - current_sample
                )

                if silence_samples > 0:

                    # Write silence in chunks so we don't
                    # create an enormous Python object.

                    chunk_size = 44100

                    while silence_samples > 0:

                        chunk = min(
                            silence_samples,
                            chunk_size,
                        )

                        wav.writeframes(
                            silence_sample
                            * chunk
                        )

                        current_sample += chunk
                        silence_samples -= chunk

                # ------------------------------------------------
                # Click
                # ------------------------------------------------

                if current_sample >= total_samples:
                    break

                click_data = (
                    accent_click
                    if beat_number % 4 == 0
                    else normal_click
                )

                remaining = (
                    total_samples
                    - current_sample
                )

                click_count = min(
                    len(click_data),
                    remaining,
                )

                wav.writeframes(
                    b"".join(
                        click_data[:click_count]
                    )
                )

                current_sample += click_count

                beat_number += 1

        return path

    # ============================================================
    # START METRONOME
    # ============================================================

    def start_metronome(
        self,
        bpm: float,
    ) -> None:
        """
        Start the metronome at the specified BPM.

        The previous metronome is stopped first.

        Example:

            iem_manager.start_metronome(99)
        """

        # --------------------------------------------------------
        # Validate BPM
        # --------------------------------------------------------

        try:

            bpm = float(bpm)

        except (
            TypeError,
            ValueError,
        ):

            print(
                "[IEMManager] "
                "Invalid metronome BPM."
            )

            return

        if bpm <= 0:

            print(
                "[IEMManager] "
                "BPM must be greater than 0."
            )

            return

        if bpm > 300:

            print(
                "[IEMManager] "
                "BPM cannot exceed 300."
            )

            return

        # --------------------------------------------------------
        # Stop previous metronome.
        # --------------------------------------------------------

        self.stop_metronome()

        # --------------------------------------------------------
        # Store BPM
        # --------------------------------------------------------

        self.metronome_bpm = bpm

        self.metronome_stop_event.clear()

        self.metronome_running = True

        # --------------------------------------------------------
        # Start background thread.
        # --------------------------------------------------------

        self.metronome_thread = threading.Thread(
            target=self._metronome_loop,
            daemon=True,
            name="LIVEFLOWAI-Metronome",
        )

        self.metronome_thread.start()

        print(
            "[IEMManager] "
            f"Metronome started at {bpm:.2f} BPM"
        )

    # ============================================================
    # METRONOME LOOP
    # ============================================================

    def _metronome_loop(self):
        """
        Generate and play the click track.

        The entire click track is sent to Windows as one audio
        playback operation instead of spawning PowerShell for
        every click.
        """

        try:

            while not self.metronome_stop_event.is_set():

                bpm = self.metronome_bpm

                # ------------------------------------------------
                # Generate a 5-minute click track.
                # ------------------------------------------------

                click_file = (
                    self._create_metronome_track(
                        bpm=bpm,
                        duration_seconds=300.0,
                    )
                )

                self.metronome_click_file = click_file

                # ------------------------------------------------
                # Play it.
                # ------------------------------------------------

                if self._is_wsl():

                    self._play_wsl_wav(
                        click_file
                    )

                elif platform.system() == "Windows":

                    self._play_windows_wav(
                        click_file
                    )

                else:

                    self._play_linux_wav(
                        click_file
                    )

                # ------------------------------------------------
                # If playback ended normally, loop again.
                #
                # This normally happens after 5 minutes.
                # ------------------------------------------------

        except Exception as e:

            print(
                "[IEMManager] "
                f"Metronome error: {e}"
            )

        finally:

            self.metronome_running = False

    # ============================================================
    # PLAY WAV THROUGH WSL → WINDOWS
    # ============================================================

    def _play_wsl_wav(
        self,
        click_file: str,
    ) -> None:
        """
        Play a WAV file using Windows SoundPlayer.

        A PowerShell process is started ONCE for the whole
        click track, not once per click.
        """

        try:

            # ----------------------------------------------------
            # PowerShell needs a Windows-accessible path.
            #
            # WSL paths can be converted using wslpath.
            # ----------------------------------------------------

            windows_path = None

            try:

                result = subprocess.run(
                    [
                        "wslpath",
                        "-w",
                        click_file,
                    ],
                    capture_output=True,
                    text=True,
                    check=True,
                )

                windows_path = result.stdout.strip()

            except Exception:

                windows_path = click_file

            # ----------------------------------------------------
            # Escape single quotes for PowerShell.
            # ----------------------------------------------------

            safe_path = windows_path.replace(
                "'",
                "''",
            )

            command = (
                "Add-Type -AssemblyName System.Windows.Forms; "
                "Add-Type -AssemblyName System.Media; "
                "$player = New-Object "
                "System.Media.SoundPlayer; "
                f"$player.SoundLocation = '{safe_path}'; "
                "$player.Load(); "
                "$player.PlaySync(); "
                "$player.Dispose();"
            )

            # ----------------------------------------------------
            # Start ONE PowerShell process for the entire track.
            # ----------------------------------------------------

            process = subprocess.Popen(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    command,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            with self._metronome_lock:

                self.metronome_process = process

            # ----------------------------------------------------
            # Wait until:
            #
            # 1. Track finishes
            # OR
            # 2. stop_metronome() asks us to stop.
            # ----------------------------------------------------

            while process.poll() is None:

                if self.metronome_stop_event.wait(
                    timeout=0.05
                ):

                    # Stop requested.

                    try:

                        process.terminate()

                    except Exception:
                        pass

                    break

            # ----------------------------------------------------
            # Make sure process is dead.
            # ----------------------------------------------------

            if process.poll() is None:

                try:

                    process.kill()

                except Exception:
                    pass

            with self._metronome_lock:

                if self.metronome_process is process:

                    self.metronome_process = None

        except Exception as e:

            print(
                "[IEMManager] "
                f"WSL metronome playback failed: {e}"
            )

    # ============================================================
    # PLAY WAV ON NATIVE WINDOWS
    # ============================================================

    def _play_windows_wav(
        self,
        click_file: str,
    ) -> None:

        try:

            import winsound

            # winsound plays the whole WAV continuously.

            winsound.PlaySound(
                click_file,
                winsound.SND_FILENAME,
            )

        except Exception as e:

            print(
                "[IEMManager] "
                f"Windows metronome playback failed: {e}"
            )

    # ============================================================
    # LINUX FALLBACK
    # ============================================================

    def _play_linux_wav(
        self,
        click_file: str,
    ) -> None:

        # --------------------------------------------------------
        # Try aplay first.
        # --------------------------------------------------------

        if shutil.which("aplay"):

            try:

                process = subprocess.Popen(
                    [
                        "aplay",
                        "-q",
                        click_file,
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )

                with self._metronome_lock:

                    self.metronome_process = process

                while process.poll() is None:

                    if self.metronome_stop_event.wait(
                        timeout=0.05
                    ):

                        try:
                            process.terminate()
                        except Exception:
                            pass

                        break

                with self._metronome_lock:

                    if self.metronome_process is process:

                        self.metronome_process = None

                return

            except Exception:
                pass

        # --------------------------------------------------------
        # Try paplay.
        # --------------------------------------------------------

        if shutil.which("paplay"):

            try:

                process = subprocess.Popen(
                    [
                        "paplay",
                        click_file,
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )

                with self._metronome_lock:

                    self.metronome_process = process

                while process.poll() is None:

                    if self.metronome_stop_event.wait(
                        timeout=0.05
                    ):

                        try:
                            process.terminate()
                        except Exception:
                            pass

                        break

                with self._metronome_lock:

                    if self.metronome_process is process:

                        self.metronome_process = None

                return

            except Exception:
                pass

        print(
            "[IEMManager] "
            "No Linux WAV playback device found."
        )

    # ============================================================
    # CHANGE BPM
    # ============================================================

    def set_metronome_bpm(
        self,
        bpm: float,
    ) -> None:
        """
        Change the metronome BPM.

        The current click track is stopped and a new one is
        generated at the new BPM.
        """

        try:

            bpm = float(bpm)

        except (
            TypeError,
            ValueError,
        ):

            print(
                "[IEMManager] "
                "Invalid metronome BPM."
            )

            return

        if bpm <= 0 or bpm > 300:

            print(
                "[IEMManager] "
                "Metronome BPM must be between "
                "1 and 300."
            )

            return

        was_running = (
            self.metronome_running
        )

        self.metronome_bpm = bpm

        if was_running:

            self.stop_metronome()

            self.start_metronome(
                bpm
            )

        print(
            "[IEMManager] "
            f"Metronome BPM set to {bpm:.2f}"
        )

    # ============================================================
    # STOP METRONOME
    # ============================================================

    def stop_metronome(self) -> None:
        """
        Stop the metronome immediately.
        """

        # --------------------------------------------------------
        # Signal thread.
        # --------------------------------------------------------

        self.metronome_stop_event.set()

        # --------------------------------------------------------
        # Kill active PowerShell/audio process.
        # --------------------------------------------------------

        with self._metronome_lock:

            process = (
                self.metronome_process
            )

            self.metronome_process = None

        if process is not None:

            try:

                if process.poll() is None:

                    process.terminate()

            except Exception:
                pass

            try:

                process.wait(
                    timeout=0.5
                )

            except Exception:

                try:

                    process.kill()

                except Exception:
                    pass

        # --------------------------------------------------------
        # Stop native Windows playback.
        # --------------------------------------------------------

        if (
            platform.system() == "Windows"
            and not self._is_wsl()
        ):

            try:

                import winsound

                winsound.PlaySound(
                    None,
                    winsound.SND_PURGE,
                )

            except Exception:
                pass

        # --------------------------------------------------------
        # Wait for metronome thread.
        # --------------------------------------------------------

        thread = (
            self.metronome_thread
        )

        if (
            thread is not None
            and thread.is_alive()
            and threading.current_thread()
            is not thread
        ):

            thread.join(
                timeout=1.0
            )

        self.metronome_thread = None

        self.metronome_running = False

        # --------------------------------------------------------
        # Reset event so the next start works.
        # --------------------------------------------------------

        self.metronome_stop_event.clear()

        print(
            "[IEMManager] "
            "Metronome stopped."
        )

    # ============================================================
    # SHUTDOWN
    # ============================================================

    def shutdown(self) -> None:
        """
        Completely shut down IEMManager.
        """

        print(
            "[IEMManager] "
            "Shutting down..."
        )

        self.stop_metronome()

        # --------------------------------------------------------
        # Stop TTS
        # --------------------------------------------------------

        if self.engine is not None:

            try:

                self.engine.stop()

            except Exception:
                pass

        # --------------------------------------------------------
        # Delete generated metronome file.
        # --------------------------------------------------------

        if self.metronome_click_file:

            try:

                if os.path.exists(
                    self.metronome_click_file
                ):

                    os.remove(
                        self.metronome_click_file
                    )

            except Exception:
                pass

        self.metronome_click_file = None

        print(
            "[IEMManager] "
            "Shutdown complete."
        )