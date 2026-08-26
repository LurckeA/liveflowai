from pathlib import Path
import sqlite3


class DatabaseLogic:
    def __init__(self):
        # database.py
        #   -> database/
        #   -> liveflowai/
        #   -> src/
        #   -> project root
        self.db_path = (
            Path(__file__).resolve().parents[3]
            / "data"
            / "liveflow.db"
        )

    def ConnectDB(self):
        """Create/open the SQLite database."""

        # Make sure data/ exists.
        self.db_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        print(f"Creating/opening: {self.db_path}")

        return sqlite3.connect(self.db_path)

    def MakeDB(self):
        """Create the liveflow table if it doesn't exist."""

        with self.ConnectDB() as conn:
            c = conn.cursor()

            c.execute("""
                CREATE TABLE IF NOT EXISTS liveflow (
                    song TEXT PRIMARY KEY,
                    duration REAL,
                    bpm REAL,
                    chords TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.commit()

        print("Database table 'liveflow' created/verified successfully.")

    def PushDB(self, song, duration, bpm, chords):
        """Insert a song's analysis into the database."""

        with self.ConnectDB() as conn:
            c = conn.cursor()

            c.execute("""
                INSERT INTO liveflow (
                    song,
                    duration,
                    bpm,
                    chords
                )
                VALUES (?, ?, ?, ?)
            """, (
                song,
                duration,
                bpm,
                chords
            ))

            conn.commit()

        print(f"Successfully saved: {song}")
