# src/liveflowai/database/database.py

from pathlib import Path
import sqlite3

class DatabaseLogic:
    def __init__(self):
        pass

    def ConnectDB(self):
        db_path = Path(__file__).resolve().parents[2] / "data" / "liveflow.db"
        print(f"Creating/opening: {db_path}")

        return sqlite3.connect(db_path)

    def MakeDB(self):
        with self.ConnectDB() as conn:
            c = conn.cursor()
            
            c.execute('''CREATE TABLE liveflow (
            song text primary key
            duration text
            bpm integer
            chords text
            )''')
            
            conn.commit()
            conn.close()

    def PushDB(self, song, duration, bpm, chords):
        self.song = song
        self.duration = duration
        self.bpm = bpm
        self.chords = chords

        with self.ConnectDB() as conn:
            c = conn.cursor()

            c.execute('INSERT INTO liveflow VALUES (?, ?, ?, ?)', (song, duration, bpm, chords))
            
            conn.commit()
            conn.close()
