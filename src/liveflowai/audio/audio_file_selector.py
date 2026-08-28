# src/liveflowai/audio/audio_file_selector.py

from pathlib import Path


class AudioFileSelector:
    """
    Interactive selector for audio files stored in data/songs/.
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

    def __init__(self, base_dir=None):
        """
        Args:
            base_dir: Project root directory. If None, automatically
                      determines the project root.
        """

        if base_dir is None:
            self.project_root = Path(__file__).resolve().parents[3]
        else:
            self.project_root = Path(base_dir).resolve()

        self.audio_dir = self.project_root / "data" / "songs"

    def get_audio_files(self):
        """
        Return all supported audio files in data/songs/.
        """

        if not self.audio_dir.exists():
            print(f"\nAudio directory does not exist:")
            print(f"  {self.audio_dir}")
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

        print("\n=== Available Audio Files ===")

        for index, file_path in enumerate(audio_files, start=1):
            print(f"{index}. {file_path.name}")

        print("=============================")

    def select_file(self):
        """
        Show all available audio files and let the user select one.

        Returns:
            Path or None
        """

        audio_files = self.get_audio_files()

        if not audio_files:
            print("\nNo supported audio files found in:")
            print(f"  {self.audio_dir}")
            return None

        self.display_audio_files(audio_files)

        while True:
            choice = input(
                f"\nSelect an audio file (1-{len(audio_files)}) "
                "or 'q' to cancel: "
            ).strip()

            if choice.lower() == "q":
                return None

            try:
                index = int(choice) - 1
            except ValueError:
                print("Invalid input. Please enter a number.")
                continue

            if 0 <= index < len(audio_files):
                selected_file = audio_files[index]

                print(f"\nSelected: {selected_file.name}")

                return selected_file

            print(
                f"Invalid selection. "
                f"Please enter a number between 1 and {len(audio_files)}."
            )

    def ask_continue(self):
        """
        Ask whether the user wants to select another audio file.

        Returns:
            True  -> select another file
            False -> return to startup menu
        """

        while True:
            choice = input(
                "\nDo you want to select another audio file? (y/n): "
            ).strip().lower()

            if choice in {"y", "yes"}:
                return True

            if choice in {"n", "no"}:
                return False

            print("Please enter 'y' or 'n'.")

    def select_multiple(self):
        """
        Allow the user to repeatedly select audio files.

        Returns:
            list[Path]: Selected audio files.
        """

        selected_files = []

        while True:
            selected_file = self.select_file()

            if selected_file is None:
                break

            selected_files.append(selected_file)

            if not self.ask_continue():
                break

        return selected_files
