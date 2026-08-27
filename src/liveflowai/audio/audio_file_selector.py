# src/liveflowai/audio/audio_file_selector.py

from pathlib import Path
import os
import sys

class AudioFileSelector:
    """
    A class to handle interactive audio file selection from a specified directory.
    Allows users to select multiple audio files one at a time.
    """
    
    SUPPORTED_EXTENSIONS = {'.mp3', '.wav', '.flac', '.m4a', '.aac', '.ogg', '.wma'}
    
    def __init__(self, base_dir=None):
        """
        Initialize the AudioFileSelector.
        
        Args:
            base_dir (str or Path, optional): Base directory containing audio files.
                If None, uses the project root directory.
        """
        if base_dir is None:
            # Get project root (3 levels up from this file's location)
            self.project_root = Path(__file__).resolve().parents[3]
        else:
            self.project_root = Path(base_dir).resolve()
        
        self.audio_dir = self.project_root / "data" / "songs"
        self.selected_files = []
        
    def get_audio_files(self):
        """
        Get all audio files from the audio directory.
        
        Returns:
            list: List of Path objects for audio files found.
        """
        if not self.audio_dir.exists():
            print(f"Warning: Audio directory not found: {self.audio_dir}")
            return []
        
        audio_files = []
        for ext in self.SUPPORTED_EXTENSIONS:
            audio_files.extend(self.audio_dir.glob(f"*{ext}"))
            audio_files.extend(self.audio_dir.glob(f"*{ext.upper()}"))
        
        # Remove duplicates and sort
        return sorted(set(audio_files))
    
    def display_audio_files(self, audio_files):
        """
        Display available audio files with numbered options.
        
        Args:
            audio_files (list): List of Path objects.
        """
        if not audio_files:
            print("\nNo audio files found in the directory.")
            return
        
        print("\n" + "="*50)
        print("AVAILABLE AUDIO FILES:")
        print("="*50)
        for idx, file_path in enumerate(audio_files, 1):
            print(f"{idx:3}. {file_path.name}")
        print("="*50)
    
    def select_file(self, audio_files):
        """
        Prompt user to select a file from the list.
        
        Args:
            audio_files (list): List of Path objects.
            
        Returns:
            Path or None: Selected file path, or None if selection fails.
        """
        if not audio_files:
            return None
        
        while True:
            try:
                choice = input(f"\nSelect a file (1-{len(audio_files)}): ").strip()
                if not choice:
                    continue
                
                idx = int(choice) - 1
                if 0 <= idx < len(audio_files):
                    selected_file = audio_files[idx]
                    print(f"\nSelected: {selected_file.name}")
                    return selected_file
                else:
                    print(f"Invalid selection. Please enter a number between 1 and {len(audio_files)}.")
            except ValueError:
                print("Invalid input. Please enter a valid number.")
    
    def ask_continue(self):
        """
        Ask user if they want to select another file.
        
        Returns:
            bool: True if user wants to continue, False otherwise.
        """
        while True:
            response = input("\nDo you want to select another file? (y/n): ").strip().lower()
            if response in ['y', 'yes']:
                return True
            elif response in ['n', 'no']:
                return False
            else:
                print("Please enter 'y' or 'n'.")
    
    def run_selection_process(self):
        """
        Run the interactive file selection process.
        
        Returns:
            list: List of selected file paths.
        """
        self.selected_files = []
        
        print("\n" + "="*50)
        print("AUDIO FILE SELECTOR")
        print("="*50)
        print(f"Searching for audio files in: {self.audio_dir}")
        
        # Get all audio files
        audio_files = self.get_audio_files()
        
        if not audio_files:
            print("\nNo audio files found. Please check the directory.")
            return []
        
        # Display available files
        self.display_audio_files(audio_files)
        
        # Selection loop
        while True:
            # Select a file
            selected = self.select_file(audio_files)
            if selected:
                self.selected_files.append(selected)
                print(f"Added to selection: {selected.name}")
            
            # Ask if user wants to continue
            if not self.ask_continue():
                break
        
        # Summary
        print("\n" + "="*50)
        print("SELECTION SUMMARY")
        print("="*50)
        if self.selected_files:
            print(f"Selected {len(self.selected_files)} file(s):")
            for idx, file_path in enumerate(self.selected_files, 1):
                print(f"  {idx}. {file_path.name}")
        else:
            print("No files selected.")
        print("="*50)
        
        return self.selected_files
    
    def get_first_selected(self):
        """
        Get the first selected file (for backward compatibility).
        
        Returns:
            Path or None: First selected file path, or None if none selected.
        """
        return self.selected_files[0] if self.selected_files else None
    
    @staticmethod
    def quick_select(base_dir=None):
        """
        Static method for quick file selection without creating an instance.
        
        Args:
            base_dir (str or Path, optional): Base directory.
            
        Returns:
            list: Selected file paths.
        """
        selector = AudioFileSelector(base_dir)
        return selector.run_selection_process()


# Example usage as a module
if __name__ == "__main__":
    # Run the selector
    selector = AudioFileSelector()
    selected_files = selector.run_selection_process()
    
    if selected_files:
        print("\nProcessing selected files:")
        for file_path in selected_files:
            print(f"  - {file_path}")
