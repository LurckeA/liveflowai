# src/liveflowai/output/iem_manager.py

from dataclasses import dataclass
from typing import Iterable, Optional

import pyttsx3


@dataclass
class SongInfo:
    """
    Information that will be announced to the user.
    """

    title: str
    duration_seconds: float
    bpm: float
    chords: list[str]


class IEMManager:
    """
    Handles voice announcements for LiveFlowAI.

    The manager announces:
        - Next song
        - Song duration
        - BPM
        - Chord progression

    This class does not analyze the audio itself.

    Analysis should be done by:
        - TempoAnalyzer
        - ChordAnalyzer

    Then the results are passed into this manager.
    """

    def __init__(
        self,
        rate: int = 160,
        volume: float = 1.0,
        voice_id: Optional[int] = None,
    ):
        self.engine = pyttsx3.init()

        self.engine.setProperty("rate", rate)
        self.engine.setProperty(
            "volume",
            max(0.0, min(1.0, volume)),
        )

        if voice_id is not None:
            voices = self.engine.getProperty("voices")

            if 0 <= voice_id < len(voices):
                self.engine.setProperty(
                    "voice",
                    voices[voice_id].id,
                )

        self.current_song: Optional[SongInfo] = None

    # ============================================================
    # SPEAK TEXT
    # ============================================================

    def speak(
        self,
        text: str,
        wait: bool = True,
    ):
        """
        Speak text using pyttsx3.

        Parameters
        ----------
        text:
            Text to announce.

        wait:
            If True, wait until speech finishes.
        """

        if not text:
            return

        self.engine.say(text)

        if wait:
            self.engine.runAndWait()

    # ============================================================
    # FORMAT SONG DURATION
    # ============================================================

    @staticmethod
    def format_duration(
        duration_seconds: float,
    ) -> str:
        """
        Convert seconds into a natural speech format.

        Examples:
            45       -> "45 seconds"
            60       -> "1 minute"
            75       -> "1 minute and 15 seconds"
            125.5    -> "2 minutes and 5 seconds"
        """

        duration_seconds = max(
            0,
            float(duration_seconds),
        )

        minutes = int(duration_seconds // 60)

        seconds = int(
            round(duration_seconds % 60)
        )

        if seconds == 60:
            minutes += 1
            seconds = 0

        if minutes == 0:
            return f"{seconds} seconds"

        if minutes == 1:
            if seconds == 0:
                return "1 minute"

            return (
                f"1 minute and "
                f"{seconds} seconds"
            )

        if seconds == 0:
            return f"{minutes} minutes"

        return (
            f"{minutes} minutes and "
            f"{seconds} seconds"
        )

    # ============================================================
    # CLEAN CHORDS
    # ============================================================

    @staticmethod
    def clean_chords(
        chords: Iterable,
    ) -> list[str]:
        """
        Convert chord objects or strings into a clean chord list.

        Consecutive duplicate chords are removed.

        Example:
            C, C, C, G, G, Am

        Becomes:
            C, G, Am
        """

        clean = []

        for chord in chords:

            chord_name = str(chord).strip()

            if not chord_name:
                continue

            # Remove consecutive duplicates.
            if (
                not clean
                or clean[-1] != chord_name
            ):
                clean.append(chord_name)

        return clean

    # ============================================================
    # FORMAT CHORDS FOR SPEECH
    # ============================================================

    @staticmethod
    def format_chords(
        chords: list[str],
        max_chords: int = 16,
    ) -> str:
        """
        Create a natural chord progression announcement.

        The first max_chords are announced to avoid an extremely
        long voice announcement.
        """

        if not chords:
            return (
                "No chord progression was detected"
            )

        selected_chords = chords[:max_chords]

        progression = ", then ".join(
            selected_chords
        )

        if len(chords) > max_chords:
            progression += (
                ", and more chords later in the song"
            )

        return progression

    # ============================================================
    # CREATE SONG INFO
    # ============================================================

    def create_song_info(
        self,
        title: str,
        duration_seconds: float,
        bpm: float,
        chords: Iterable,
    ) -> SongInfo:
        """
        Create a SongInfo object from analysis results.
        """

        clean_chord_list = self.clean_chords(
            chords
        )

        return SongInfo(
            title=title,
            duration_seconds=float(
                duration_seconds
            ),
            bpm=float(bpm),
            chords=clean_chord_list,
        )

    # ============================================================
    # BUILD ANNOUNCEMENT
    # ============================================================

    def build_announcement(
        self,
        song_info: SongInfo,
        max_chords: int = 16,
    ) -> str:
        """
        Build the complete announcement.

        Example:

        "Next song is Mary Had a Little Lamb.
        Duration is 1 minute and 23 seconds.
        Tempo is 120 beats per minute.
        The chord progression is C, then G, then A minor."
        """

        duration_text = self.format_duration(
            song_info.duration_seconds
        )

        bpm_text = (
            f"{round(song_info.bpm)} "
            f"beats per minute"
        )

        chords_text = self.format_chords(
            song_info.chords,
            max_chords=max_chords,
        )

        announcement = (
            f"Next song is {song_info.title}. "
            f"The duration is {duration_text}. "
            f"The tempo is {bpm_text}. "
            f"The chord progression is "
            f"{chords_text}."
        )

        return announcement

    # ============================================================
    # ANNOUNCE NEXT SONG
    # ============================================================

    def announce_next_song(
        self,
        title: str,
        duration_seconds: float,
        bpm: float,
        chords: Iterable,
        max_chords: int = 16,
    ) -> SongInfo:
        """
        Announce the next song and its analysis information.

        Parameters
        ----------
        title:
            Name of the next song.

        duration_seconds:
            Song duration in seconds.

        bpm:
            Song tempo.

        chords:
            List of Chord objects or chord strings.

        max_chords:
            Maximum number of chord changes to announce.

        Returns
        -------
        SongInfo
        """

        song_info = self.create_song_info(
            title=title,
            duration_seconds=duration_seconds,
            bpm=bpm,
            chords=chords,
        )

        self.current_song = song_info

        announcement = self.build_announcement(
            song_info,
            max_chords=max_chords,
        )

        print("\n" + "=" * 60)
        print("IEM ANNOUNCEMENT")
        print("=" * 60)
        print(announcement)
        print("=" * 60 + "\n")

        self.speak(
            announcement,
            wait=True,
        )

        return song_info

    # ============================================================
    # ANNOUNCE ONLY CHORDS
    # ============================================================

    def announce_chords(
        self,
        chords: Iterable,
        max_chords: int = 16,
    ):
        """
        Announce only the chord progression.
        """

        clean_chord_list = self.clean_chords(
            chords
        )

        chord_text = self.format_chords(
            clean_chord_list,
            max_chords=max_chords,
        )

        self.speak(
            f"The chord progression is {chord_text}.",
            wait=True,
        )

    # ============================================================
    # LIST AVAILABLE VOICES
    # ============================================================

    def list_voices(self):
        """
        Return the voices available to pyttsx3.
        """

        voices = self.engine.getProperty("voices")

        voice_list = []

        for index, voice in enumerate(voices):
            voice_list.append(
                {
                    "id": index,
                    "name": voice.name,
                    "voice_id": voice.id,
                }
            )

        return voice_list

    # ============================================================
    # STOP / CLEANUP
    # ============================================================

    def stop(self):
        """
        Stop the current speech.
        """

        self.engine.stop()