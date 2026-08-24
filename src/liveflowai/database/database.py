from pathlib import Path
import json
import sqlite3


class DatabaseLogic:
    def __init__(self):
        # Project root:
        # database_logic.py
        #   -> liveflowai/
        #   -> src/
        #   -> project root
        self.db_path = (
            Path(__file__).resolve().parents[3]
            / "data"
            / "liveflow.db"
        )

    def ConnectDB(self):
        """Create and return a SQLite database connection."""
        try:
            # Make sure the data directory exists.
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            print(f"Opening database: {self.db_path}")

            return sqlite3.connect(self.db_path)

        except sqlite3.Error as e:
            print(f"Database connection error: {e}")
            raise

    def MakeDB(self):
        """Create the liveflow table if it does not already exist."""
        try:
            with self.ConnectDB() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS liveflow (
                        song TEXT PRIMARY KEY,
                        duration REAL,
                        bpm INTEGER,
                        chords TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                conn.commit()

            print("Database table 'liveflow' created/verified successfully.")

        except sqlite3.Error as e:
            print(f"Database creation error: {e}")
            raise

    def PushDB(self, song, duration, bpm, chords):
        """
        Insert a song into the database.

        If the song already exists, update its duration, BPM,
        and chords instead of creating a duplicate.
        """
        try:
            # Store chords as JSON so a Python list can be
            # reconstructed when reading it back.
            if isinstance(chords, list):
                chords = json.dumps(chords)

            with self.ConnectDB() as conn:
                conn.execute("""
                    INSERT INTO liveflow (
                        song,
                        duration,
                        bpm,
                        chords
                    )
                    VALUES (?, ?, ?, ?)

                    ON CONFLICT(song)
                    DO UPDATE SET
                        duration = excluded.duration,
                        bpm = excluded.bpm,
                        chords = excluded.chords
                """, (
                    song,
                    duration,
                    bpm,
                    chords
                ))

                conn.commit()

            print(f"Successfully inserted/updated: {song}")
            return True

        except sqlite3.Error as e:
            print(f"Database insert error: {e}")
            return False

    def GetSong(self, song_name):
        """Retrieve one song from the database."""
        try:
            with self.ConnectDB() as conn:
                cursor = conn.execute("""
                    SELECT
                        song,
                        duration,
                        bpm,
                        chords,
                        created_at
                    FROM liveflow
                    WHERE song = ?
                """, (song_name,))

                result = cursor.fetchone()

            if result is None:
                return None

            chords = result[3]

            # Convert JSON back into a Python list.
            if chords:
                try:
                    chords = json.loads(chords)
                except json.JSONDecodeError:
                    pass

            return {
                "song": result[0],
                "duration": result[1],
                "bpm": result[2],
                "chords": chords,
                "created_at": result[4],
            }

        except sqlite3.Error as e:
            print(f"Database retrieval error: {e}")
            return None

    def GetAllSongs(self):
        """Retrieve all songs from the database."""
        try:
            with self.ConnectDB() as conn:
                cursor = conn.execute("""
                    SELECT
                        song,
                        duration,
                        bpm,
                        chords,
                        created_at
                    FROM liveflow
                    ORDER BY created_at DESC
                """)

                results = cursor.fetchall()

            songs = []

            for result in results:
                chords = result[3]

                if chords:
                    try:
                        chords = json.loads(chords)
                    except json.JSONDecodeError:
                        pass

                songs.append({
                    "song": result[0],
                    "duration": result[1],
                    "bpm": result[2],
                    "chords": chords,
                    "created_at": result[4],
                })

            return songs

        except sqlite3.Error as e:
            print(f"Database retrieval error: {e}")
            return []

    def DeleteSong(self, song_name):
        """Delete a song from the database."""
        try:
            with self.ConnectDB() as conn:
                cursor = conn.execute("""
                    DELETE FROM liveflow
                    WHERE song = ?
                """, (song_name,))

                conn.commit()

            if cursor.rowcount > 0:
                print(f"Deleted song: {song_name}")
                return True

            print(f"Song not found: {song_name}")
            return False

        except sqlite3.Error as e:
            print(f"Database deletion error: {e}")
            return False
