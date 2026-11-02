# src/liveflowai/audio/audio_file_selector.py

from pathlib import Path

from liveflowai.ui import ConsoleUI


class AudioFileSelector:
    """
    Interactive selector for audio files in a user-selected directory.
    """

    SUPPORTED_EXTENSIONS = {
        ".mp3",
        ".wav",
        ".flac",
        ".m4a",
        ".aac",
        ".ogg",
        ".wma",
    }

    def __init__(self, base_dir=None, audio_dir=None, ui=None):
        """
        Args:
            base_dir: Project root directory. If None, automatically
                      determines the project root.
            audio_dir: Directory containing audio files. If provided,
                       it may be absolute or relative to base_dir.
        """

        if base_dir is None:
            self.project_root = Path(__file__).resolve().parents[3]
        else:
            self.project_root = Path(base_dir).resolve()

        if audio_dir is None:
            self.audio_dir = self.project_root / "data" / "songs"
        else:
            selected_dir = Path(audio_dir).expanduser()
            if not selected_dir.is_absolute():
                selected_dir = self.project_root / selected_dir
            self.audio_dir = selected_dir.resolve()

        self.ui = ui or ConsoleUI()

    def choose_directory(self):
        """Ask the user which directory contains the song files."""

        current_directory = Path.cwd()
        choice = self.ui.prompt(
            "Folder containing your songs "
            f"[default: {current_directory}]:"
        )

        selected_dir = Path(choice or current_directory).expanduser()
        if not selected_dir.is_absolute():
            selected_dir = current_directory / selected_dir

        self.audio_dir = selected_dir.resolve()
        self.ui.status(f"Using audio folder: {self.audio_dir}")

    def get_audio_files(self):
        """
        Return all supported audio files in the selected directory.
        """

        if not self.audio_dir.exists():
            self.ui.status(f"Audio directory does not exist: {self.audio_dir}", "error")
            return []

        audio_files = [
            file
            for file in self.audio_dir.iterdir()
            if file.is_file()
            and file.suffix.lower() in self.SUPPORTED_EXTENSIONS
        ]

        return sorted(audio_files, key=lambda path: path.name.lower())

    def display_audio_files(self, audio_files):
        """
        Display all available audio files with numbers.
        """

        self.ui.header("Song picker", "Available audio files", "Choose one file at a time to build an analysis queue.")
        self.ui.table(
            ("#", "FILE", "FORMAT"),
            ((str(index), file_path.name, file_path.suffix.upper().lstrip("."))
             for index, file_path in enumerate(audio_files, start=1)),
        )

    def select_file(self):
        """
        Show all available audio files and let the user select one.

        Returns:
            Path or None
        """

        audio_files = self.get_audio_files()

        if not audio_files:
            self.ui.status(f"No supported audio files found in: {self.audio_dir}", "warning")
            return None

        self.display_audio_files(audio_files)

        while True:
            choice = self.ui.prompt(
                f"Select a file [1–{len(audio_files)}] or q to return:"
            )

            if choice.lower() == "q":
                return None

            try:
                index = int(choice) - 1
            except ValueError:
                self.ui.status("Enter a file number or q to return.", "warning")
                continue

            if 0 <= index < len(audio_files):
                selected_file = audio_files[index]

                self.ui.status(f"Added to queue: {selected_file.name}", "success")

                return selected_file

            self.ui.status(f"Choose a number between 1 and {len(audio_files)}.", "warning")

    def ask_continue(self):
        """
        Ask whether the user wants to select another audio file.

        Returns:
            True  -> select another file
            False -> return to startup menu
        """

        while True:
            choice = self.ui.prompt("Add another file? [y/n]:").lower()

            if choice in {"y", "yes"}:
                return True

            if choice in {"n", "no"}:
                return False

            self.ui.status("Please enter y or n.", "warning")

    def select_multiple(self):
        """
        Allow the user to repeatedly select audio files.

        Returns:
            list[Path]: Selected audio files.
        """

        selected_files = []

        self.choose_directory()

        while True:
            selected_file = self.select_file()

            if selected_file is None:
                break

            selected_files.append(selected_file)

            if not self.ask_continue():
                break

        return selected_files
