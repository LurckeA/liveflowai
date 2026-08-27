# src/database/database.py

from pathlib import Path
import sqlite3
import sys


class DatabaseLogic:
    def __init__(self):
        try:
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
        except Exception as e:
            print(f"Error initializing: {e}")
            sys.exit(1)

    def ConnectDB(self):
        try:
            """Create/open the SQLite database."""

            # Make sure data/ exists.
            self.db_path.parent.mkdir(
                parents=True,
                exist_ok=True
            )

            print(f"Creating/opening: {self.db_path}")

            return sqlite3.connect(self.db_path)
        except Exception as e:
            print(f"Error connecting or opening: {e}")
            sys.exit(1)

    def MakeDB(self):
        """Create the liveflow table if it doesn't exist."""

        try:
            with self.ConnectDB() as conn:  # ← Fixed: uppercase C
                c = conn.cursor()

                c.execute("""
                    create table if not exists liveflow (
                        song text primary key,
                        duration real,
                        bpm real,
                        chords text,
                        created_at timestamp default current_timestamp
                    )
                """)

                conn.commit()

            print("database table 'liveflow' created/verified successfully.")
        except Exception as e:
            print(f"Failure in making DB: {e}")
            sys.exit(1)

    def PushDB(self, song, duration, bpm, chords):
        """Insert a song's analysis into the database."""
        
        try:
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
        except Exception as e:
            print(f"Error pushing into DB: {e}")
            sys.exit(1)

        def FetchAllDB(self):
            """Fetch all records from liveflow table. Returns list of tuples."""
            try:
                with self.ConnectDB() as conn:
                    c = conn.cursor()
                    c.execute('SELECT * FROM liveflow')
                    return list(c.fetchall())  # Always returns list (empty if none)
                    
            except Exception as e:
                print(f"Error fetching from DB: {e}")
                return []

        def DisplayResults(self, results):
            if results:
                print(f"Found {len(results)} result(s):")
                for row in results:
                    print(f"  Song: {row[0]}, Duration: {row[1]}, BPM: {row[2]}, Chords: {row[3]}")
            else:
                print("Nothing in database.")
