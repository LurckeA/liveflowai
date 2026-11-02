"""Desktop interface for LiveFlowAI.

The GUI intentionally uses Tkinter so the installed application has no web
server, browser, or additional UI dependency to configure.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from tkinter import END, StringVar, Tk, filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from liveflowai.audio.chord_analyzer import ChordAnalyzer
from liveflowai.audio.tempo_analyzer import TempoAnalyzer
from liveflowai.database.database import DatabaseLogic
from liveflowai.detection.chord_detector import LiveChordDetector
from liveflowai.detection.song_predictor import SongPredictor
from liveflowai.output.iem_manager import IEMManager
from liveflowai.ui import ConsoleUI


class LiveFlowApp:
    """Coordinate the desktop UI and the existing audio-analysis services."""

    def __init__(self, root: Tk):
        self.root = root
        self.root.title("LiveFlowAI — Live Music Intelligence")
        self.root.minsize(960, 640)
        self.root.geometry("1120x720")
        self.root.protocol("WM_DELETE_WINDOW", self._close)

        self.tempo_analyzer = TempoAnalyzer(sample_rate=22050)
        self.chord_analyzer = ChordAnalyzer(sample_rate=22050)
        self.chord_detector = LiveChordDetector(
            sample_rate=22050,
            model_path=os.environ.get("LIVEFLOWAI_CHORD_MODEL"),
        )
        self.database = DatabaseLogic()
        self.database.MakeDB()
        self.iem_manager = IEMManager()
        self.song_predictor = SongPredictor(
            chord_detector=self.chord_detector,
            db=self.database,
            recording_duration=15.0,
            segment_duration=1.0,
            iem_manager=self.iem_manager,
        )
        self.selected_folder: Path | None = None
        self.performance_running = False
        self.status = StringVar(value="Ready. Choose a folder to analyze songs.")

        self._configure_style()
        self._build_layout()
        self.refresh_library()

    def _configure_style(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        background, panel, text, accent = "#101827", "#182235", "#E5EDF8", "#4FD1C5"
        self.root.configure(background=background)
        style.configure("TFrame", background=background)
        style.configure("Panel.TFrame", background=panel)
        style.configure("TLabel", background=background, foreground=text, font=("TkDefaultFont", 10))
        style.configure("Title.TLabel", background=background, foreground=text, font=("TkDefaultFont", 22, "bold"))
        style.configure("Subtitle.TLabel", background=background, foreground="#9FB0C8")
        style.configure("TButton", padding=(12, 8), font=("TkDefaultFont", 10, "bold"))
        style.configure("Accent.TButton", background=accent, foreground="#10202A")
        style.map("Accent.TButton", background=[("active", "#73E3D9")])
        style.configure("Treeview", background=panel, fieldbackground=panel, foreground=text, rowheight=30)
        style.configure("Treeview.Heading", background="#223049", foreground=text, font=("TkDefaultFont", 10, "bold"))
        style.map("Treeview", background=[("selected", "#265C6E")])

    def _build_layout(self) -> None:
        shell = ttk.Frame(self.root, padding=(30, 24))
        shell.pack(fill="both", expand=True)
        ttk.Label(shell, text="LIVEFLOWAI", style="Subtitle.TLabel").pack(anchor="w")
        ttk.Label(shell, text="Live music intelligence", style="Title.TLabel").pack(anchor="w", pady=(2, 2))
        ttk.Label(shell, text="Build a performance-ready song library and identify songs from live audio.", style="Subtitle.TLabel").pack(anchor="w", pady=(0, 18))

        self.tabs = ttk.Notebook(shell)
        self.tabs.pack(fill="both", expand=True)
        self.analyze_tab = ttk.Frame(self.tabs, padding=22)
        self.library_tab = ttk.Frame(self.tabs, padding=22)
        self.performance_tab = ttk.Frame(self.tabs, padding=22)
        self.tabs.add(self.analyze_tab, text="  Analyze songs  ")
        self.tabs.add(self.library_tab, text="  Song library  ")
        self.tabs.add(self.performance_tab, text="  Performance  ")
        self._build_analyze_tab()
        self._build_library_tab()
        self._build_performance_tab()

        ttk.Label(shell, textvariable=self.status, style="Subtitle.TLabel").pack(anchor="w", pady=(14, 0))

    def _build_analyze_tab(self) -> None:
        ttk.Label(self.analyze_tab, text="Analyze songs", style="Title.TLabel").pack(anchor="w")
        ttk.Label(self.analyze_tab, text="Select a folder, choose tracks, then analyze tempo and harmonic progression.", style="Subtitle.TLabel").pack(anchor="w", pady=(2, 16))
        actions = ttk.Frame(self.analyze_tab)
        actions.pack(fill="x", pady=(0, 14))
        ttk.Button(actions, text="Choose music folder", style="Accent.TButton", command=self.choose_folder).pack(side="left")
        self.folder_label = ttk.Label(actions, text="No folder selected", style="Subtitle.TLabel")
        self.folder_label.pack(side="left", padx=14)

        columns = ("name", "format")
        self.file_tree = ttk.Treeview(self.analyze_tab, columns=columns, show="headings", selectmode="extended")
        self.file_tree.heading("name", text="TRACK")
        self.file_tree.heading("format", text="FORMAT")
        self.file_tree.column("name", width=640, anchor="w")
        self.file_tree.column("format", width=120, anchor="center")
        self.file_tree.pack(fill="both", expand=True)
        footer = ttk.Frame(self.analyze_tab)
        footer.pack(fill="x", pady=(14, 0))
        ttk.Button(footer, text="Analyze selected tracks", style="Accent.TButton", command=self.analyze_selected).pack(side="left")
        ttk.Button(footer, text="Select all", command=lambda: self.file_tree.selection_set(self.file_tree.get_children())).pack(side="left", padx=8)
        self.analysis_progress = ttk.Progressbar(footer, mode="determinate")
        self.analysis_progress.pack(side="right", fill="x", expand=True, padx=(20, 0))

    def _build_library_tab(self) -> None:
        header = ttk.Frame(self.library_tab)
        header.pack(fill="x")
        ttk.Label(header, text="Song library", style="Title.TLabel").pack(side="left")
        ttk.Button(header, text="Refresh", command=self.refresh_library).pack(side="right")
        ttk.Label(self.library_tab, text="Songs that can be matched during performance mode.", style="Subtitle.TLabel").pack(anchor="w", pady=(2, 16))
        columns = ("song", "bpm", "length", "chords")
        self.library_tree = ttk.Treeview(self.library_tab, columns=columns, show="headings")
        for key, title, width in (("song", "SONG", 360), ("bpm", "BPM", 90), ("length", "LENGTH", 100), ("chords", "OPENING CHORDS", 420)):
            self.library_tree.heading(key, text=title)
            self.library_tree.column(key, width=width, anchor="w" if key in {"song", "chords"} else "center")
        self.library_tree.pack(fill="both", expand=True)

    def _build_performance_tab(self) -> None:
        ttk.Label(self.performance_tab, text="Performance mode", style="Title.TLabel").pack(anchor="w")
        ttk.Label(self.performance_tab, text="LiveFlowAI listens in 15-second windows, matches your library, and starts the saved metronome tempo.", style="Subtitle.TLabel", wraplength=740).pack(anchor="w", pady=(2, 22))
        controls = ttk.Frame(self.performance_tab)
        controls.pack(anchor="w")
        self.start_button = ttk.Button(controls, text="Start listening", style="Accent.TButton", command=self.start_performance)
        self.start_button.pack(side="left")
        self.stop_button = ttk.Button(controls, text="Stop after current window", command=self.stop_performance, state="disabled")
        self.stop_button.pack(side="left", padx=8)
        ttk.Label(self.performance_tab, text="Activity", style="Subtitle.TLabel").pack(anchor="w", pady=(26, 6))
        self.performance_log = ScrolledText(self.performance_tab, height=15, background="#182235", foreground="#E5EDF8", insertbackground="#E5EDF8", relief="flat", padx=12, pady=12)
        self.performance_log.pack(fill="both", expand=True)
        self.performance_log.insert(END, "Performance is idle. Analyze songs with at least five chords before starting.\n")
        self.performance_log.configure(state="disabled")

    def choose_folder(self) -> None:
        folder = filedialog.askdirectory(parent=self.root, title="Choose your music folder")
        if not folder:
            return
        self.selected_folder = Path(folder)
        self.folder_label.configure(text=str(self.selected_folder))
        self._load_folder_files()

    def _load_folder_files(self) -> None:
        supported = {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".wma"}
        for item in self.file_tree.get_children():
            self.file_tree.delete(item)
        files = sorted((path for path in self.selected_folder.iterdir() if path.is_file() and path.suffix.lower() in supported), key=lambda path: path.name.lower())
        for path in files:
            self.file_tree.insert("", END, iid=str(path), values=(path.name, path.suffix[1:].upper()))
        self.status.set(f"Found {len(files)} supported audio file(s). Select tracks to analyze.")

    def analyze_selected(self) -> None:
        selected = [Path(item) for item in self.file_tree.selection()]
        if not selected:
            messagebox.showinfo("No tracks selected", "Select one or more tracks to analyze.", parent=self.root)
            return
        self.analysis_progress.configure(maximum=len(selected), value=0)
        self.status.set(f"Analyzing {len(selected)} track(s)…")
        threading.Thread(target=self._analyze_queue, args=(selected,), daemon=True).start()

    def _analyze_queue(self, files: list[Path]) -> None:
        for index, path in enumerate(files, start=1):
            try:
                tempo = self.tempo_analyzer.detect_tempo(path)
                confidence = self.tempo_analyzer.get_beat_confidence(path)
                chords = self.chord_analyzer.analyze_chords(path)
                chord_text = ", ".join(str(chord) for chord in chords)
                self.database.PushDB(path.name, tempo["duration"], tempo["tempo_bpm"], chord_text)
                summary = f"{path.name}: {tempo['tempo_bpm']:.0f} BPM · {ConsoleUI.format_duration(tempo['duration'])} · confidence {confidence['confidence_score']:.0%}"
                self.root.after(0, self._analysis_finished_file, index, len(files), summary)
            except Exception as error:
                self.root.after(0, self._analysis_finished_file, index, len(files), f"Could not analyze {path.name}: {error}")
        self.root.after(0, self._analysis_complete)

    def _analysis_finished_file(self, index: int, total: int, summary: str) -> None:
        self.analysis_progress.configure(value=index)
        self.status.set(summary)

    def _analysis_complete(self) -> None:
        self.refresh_library()
        self.status.set("Analysis complete. Your song library is up to date.")
        self.tabs.select(self.library_tab)

    def refresh_library(self) -> None:
        for item in self.library_tree.get_children():
            self.library_tree.delete(item)
        for song, duration, bpm, _chords, _created_at in self.database.FetchAllDB():
            opening = ", ".join(self.database.FetchFirstFiveChords(song)) or "—"
            self.library_tree.insert("", END, values=(song, f"{bpm:.0f}", ConsoleUI.format_duration(duration), opening))

    def start_performance(self) -> None:
        if self.performance_running:
            return
        if not self.database.FetchAllFirstFiveChords():
            messagebox.showwarning("Library needs more analysis", "Analyze at least one song with five detected chords before starting performance mode.", parent=self.root)
            return
        self.performance_running = True
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self._write_performance("Listening for a song…\n")
        threading.Thread(target=self._run_performance, daemon=True).start()

    def _run_performance(self) -> None:
        try:
            self.song_predictor.run_performance()
        except Exception as error:
            self.root.after(0, self._write_performance, f"Performance stopped: {error}\n")
        finally:
            self.root.after(0, self._performance_finished)

    def stop_performance(self) -> None:
        self.song_predictor.stop_performance()
        self.iem_manager.stop_metronome()
        self.status.set("Stopping after the current recording window…")
        self.stop_button.configure(state="disabled")

    def _performance_finished(self) -> None:
        self.performance_running = False
        self.start_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        self.status.set("Performance mode stopped.")

    def _write_performance(self, message: str) -> None:
        self.performance_log.configure(state="normal")
        self.performance_log.insert(END, message)
        self.performance_log.see(END)
        self.performance_log.configure(state="disabled")

    def _close(self) -> None:
        if self.performance_running:
            self.stop_performance()
        self.iem_manager.shutdown()
        self.root.destroy()


def launch_app() -> None:
    """Start the desktop application."""

    root = Tk()
    LiveFlowApp(root)
    root.mainloop()
