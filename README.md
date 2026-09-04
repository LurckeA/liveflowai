# LiveFlowAI

A Python-based audio analysis toolkit for real-time tempo and chord detection from music files and live microphone input. Designed for music production, live performance analysis, and audio research.

## Features

- **Tempo Detection**: Accurately detect BPM and beat tracking for audio files
- **Chord Analysis**: Automatic chord recognition and harmonic content analysis
- **Real-time Live Detection**: Process live microphone input for immediate chord detection
- **Database Storage**: Persist analysis results in SQLite with easy querying
- **Visualization**: Visual representations of tempo and beat patterns
- **IEM Integration**: Announce song information for in-ear monitor systems
- **Multi-file Processing**: Batch analyze multiple audio files
- **Confidence Metrics**: Get confidence scores for all detections

## Quick Start

### Prerequisites

- Python 3.10 or higher
- `uv` package manager (or pip as alternative)
- FFmpeg (for audio format support)

### Installation

1. **Install from PyPI**
  ```bash
  python -m pip install liveflowai
  ```

2. **Install system audio support**

  FFmpeg is required for common compressed audio formats. Live microphone
  input also requires a working PortAudio installation and microphone.

3. **Start LiveFlowAI**
  ```bash
  liveflowai
  # Or:
  python -m liveflowai
  ```

  When you choose **Analyze Audio Files**, enter the full path to the folder
  containing your songs. The application scans that folder for supported
  audio files; songs do not need to be copied into the installation directory.

### Development Installation

For contributors, clone the repository and set up a development environment:
   ```bash
  git clone https://github.com/yourusername/liveflowai.git
  cd liveflowai

   # Using uv (recommended)
   uv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   uv sync
   
   # Or using pip
   python -m venv venv
   source venv/bin/activate
   pip install -e .
   ```

The tool presents an interactive menu with options to:
- Analyze audio files from your system
- View all analyzed songs and their data
- Store results in the local database
- Visualize tempo patterns

### Example Workflow

```python
from liveflowai.audio.tempo_analyzer import TempoAnalyzer
from liveflowai.audio.chord_analyzer import ChordAnalyzer
from liveflowai.database.database import DatabaseLogic

# Initialize analyzers
tempo_analyzer = TempoAnalyzer()
chord_analyzer = ChordAnalyzer()
db = DatabaseLogic()

# Analyze an audio file
audio_file = "path/to/song.mp3"

# Detect tempo and beats
tempo_data = tempo_analyzer.detect_tempo(audio_file)
print(f"BPM: {tempo_data['tempo_bpm']}")

# Analyze chords
chords = chord_analyzer.analyze_chords(audio_file)
for chord in chords:
    print(f"{chord.timestamp:.2f}s: {chord}")

# Store results. The database location is configurable with
# LIVEFLOWAI_DATA_DIR and defaults to a per-user data directory.
db.MakeDB()
db.PushDB(
  song="song.mp3",
    duration=tempo_data['duration'],
    bpm=tempo_data['tempo_bpm'],
    chords=", ".join(str(c) for c in chords)
)
```

## Project Structure

```
liveflowai/
├── src/liveflowai/
│   ├── audio/              # Audio processing modules
│   │   ├── tempo_analyzer.py       # BPM and beat detection
│   │   ├── chord_analyzer.py       # Chord recognition
│   │   └── audio_file_selector.py  # File selection UI
│   ├── detection/          # Real-time detection modules
│   │   ├── chord_detector.py       # Live chord detection
│   │   └── song_predictor.py       # Song/music prediction
│   ├── database/           # Data persistence
│   │   └── database.py     # SQLite database operations
│   ├── output/             # Output handling
│   │   └── iem_manager.py  # IEM announcements
│   ├── transition/         # Audio transition analysis
│   └── main.py             # CLI entry point
├── config/                 # Optional configuration files
├── data/                   # Local development data only
├── tests/                  # Unit tests
└── pyproject.toml          # Project metadata and dependencies
```

## Core Modules

### Audio Analysis
- **TempoAnalyzer**: Detects BPM, beat tracking, and generates tempo visualizations using librosa
- **ChordAnalyzer**: Identifies chord progressions and harmonic content with confidence metrics

### Real-time Detection
- **LiveChordDetector**: Process microphone input for real-time chord detection with temporal smoothing
- **SongPredictor**: Identify or predict songs based on audio characteristics

### Data Management
- **DatabaseLogic**: SQLite database for storing analysis results with query methods
- **AudioFileSelector**: Interactive file selection interface for batch processing

## Dependencies

Core dependencies include:
- `librosa` - Audio analysis and processing
- `numpy`, `scipy` - Numerical computations
- `scikit-learn` - Machine learning utilities
- `basic-pitch` - Pitch detection
- `sounddevice` - Real-time audio I/O
- `mido` - MIDI file support
- `matplotlib` - Visualization

See [pyproject.toml](pyproject.toml) for the complete list and versions.

## Configuration

Configuration can be customized in `config/config.yaml`. Currently minimal configuration is required, but this can be expanded for:
- Sample rate settings
- Analysis window sizes
- Confidence thresholds
- Output paths

## Development

### Running Tests

```bash
pytest tests/
```

### Project Structure Notes

- When analyzing files, enter any folder on your system that contains your songs.
- Analysis data is stored in the per-user data directory by default. Set
  `LIVEFLOWAI_DATA_DIR` to choose a different location for the database.
- Visualizations are generated in the output directory
- The project uses `uv_build` as the build backend

## Troubleshooting

### Audio File Not Found
Ensure the audio file path is correct and the file format is supported (MP3, WAV, FLAC, etc.)

### No Chords Detected
- Verify the audio has clear harmonic content
- Try different chord detection confidence thresholds
- Check that audio sample rate is appropriate (22050 Hz default)

### Real-time Detection Issues
- Ensure microphone is properly connected and enabled
- Check system audio input settings
- Verify PyAudio/PortAudio installation

## Support & Documentation

- **Issues & Bugs**: Report via GitHub Issues
- **Discussions**: Ask questions in GitHub Discussions

## Authors & Maintainers

- **Hioe Gregorius Owen** - [bloggerzz231@gmail.com](mailto:bloggerzz231@gmail.com)
- **Petrus Aria Prakoso Widarto** - [ariaprakoso@proton.me](mailto:ariaprakoso@proton.me)

## License

This project is licensed under the MIT License. See [LICENSE.txt](LICENSE.txt) for details.

Copyright © 2026 bloggerzz231-jpg & Arialize

## Acknowledgments

Built with:
- [Librosa](https://librosa.org/) - Audio analysis
- [Basic Pitch](https://github.com/spotify/basic-pitch) - Pitch detection
- [HarmonyScope](https://github.com/harmonic-analysis/harmonioscope) - Harmonic analysis
- [Sonic Visualizer](https://www.sonicvisualiser.org/) - Visualization reference

## Citation

If you use LiveFlowAI in your research, please cite:

```bibtex
@software{liveflowai2025,
  title={LiveFlowAI: Real-time Audio Analysis Toolkit},
  author={Hioe Gregorius Owen and Petrus Aria Prakoso Widarto},
  year={2026},
  url={https://github.com/LurckeA/liveflowai}
}
```

---

**Status**: Research Project - Active Development

For questions or issues, please open a GitHub issue or contact the maintainers.
