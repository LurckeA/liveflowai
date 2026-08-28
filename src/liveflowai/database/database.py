# src/liveflowai/database/database.py

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

    # ============================================================
    # CONNECT
    # ============================================================

    def ConnectDB(self):
        """Create/open the SQLite database."""

        self.db_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        print(
            f"Creating/opening: {self.db_path}"
        )

        return sqlite3.connect(self.db_path)

    # ============================================================
    # CREATE DATABASE
    # ============================================================

    def MakeDB(self):
        """Create the liveflow table if it doesn't exist."""

        try:
            with self.ConnectDB() as conn:

                c = conn.cursor()

                c.execute("""
                    CREATE TABLE IF NOT EXISTS liveflow (
                        song TEXT PRIMARY KEY,
                        duration REAL,
                        bpm REAL,
                        chords TEXT,
                        created_at TIMESTAMP
                            DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                conn.commit()

            print(
                "Database table 'liveflow' "
                "created/verified successfully."
            )

        except Exception as e:

            print(
                f"Failure in making DB: {e}"
            )

    # ============================================================
    # INSERT / UPDATE
    # ============================================================

    def PushDB(
        self,
        song,
        duration,
        bpm,
        chords,
    ):
        """Insert or update a song's analysis."""

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

                    ON CONFLICT(song) DO UPDATE SET
                        duration = excluded.duration,
                        bpm = excluded.bpm,
                        chords = excluded.chords
                """, (
                    song,
                    duration,
                    bpm,
                    chords,
                ))

                conn.commit()

            print(
                f"Successfully saved: {song}"
            )

        except Exception as e:

            print(
                f"Error pushing into DB: {e}"
            )

    # ============================================================
    # FETCH EVERYTHING
    # ============================================================

    def FetchAllDB(self):
        """Fetch all records from the liveflow table."""

        try:

            with self.ConnectDB() as conn:

                c = conn.cursor()

                c.execute("""
                    SELECT
                        song,
                        duration,
                        bpm,
                        chords,
                        created_at
                    FROM liveflow
                    ORDER BY song
                """)

                rows = c.fetchall()

            return rows

        except Exception as e:

            print(
                f"Error fetching from DB: {e}"
            )

            return []

    # ============================================================
    # FETCH FIRST FIVE CHORDS
    # ============================================================

    def FetchFirstFiveChords(self, song):
        """
        Fetch the first five chords from one song.
        """

        try:

            with self.ConnectDB() as conn:

                c = conn.cursor()

                c.execute(
                    """
                    SELECT chords
                    FROM liveflow
                    WHERE song = ?
                    """,
                    (song,),
                )

                row = c.fetchone()

                if row is None:
                    return []

                chords = row[0]

                if not chords:
                    return []

                chords = [
                    chord.strip()
                    for chord in chords.split(",")
                    if chord.strip()
                ]

                return chords[:5]

        except Exception as e:

            print(
                f"Error fetching five chords: {e}"
            )

            return []

    # ============================================================
    # FETCH FIRST FIVE CHORDS FROM EVERY SONG
    # ============================================================

    def FetchAllFirstFiveChords(self):
        """
        Fetch the first five chords from every song.

        Returns:

            [
                (
                    song_name,
                    [
                        chord1,
                        chord2,
                        chord3,
                        chord4,
                        chord5,
                    ]
                ),
                ...
            ]
        """

        try:

            with self.ConnectDB() as conn:

                c = conn.cursor()

                c.execute("""
                    SELECT song, chords
                    FROM liveflow
                    ORDER BY song
                """)

                rows = c.fetchall()

            results = []

            for song, chords_string in rows:

                if not chords_string:
                    continue

                chords = [
                    chord.strip()
                    for chord in chords_string.split(",")
                    if chord.strip()
                ]

                if len(chords) < 5:
                    continue

                results.append(
                    (
                        song,
                        chords[:5],
                    )
                )

            return results

        except Exception as e:

            print(
                f"Error fetching first five chords: {e}"
            )

            return []

    # ============================================================
    # DISPLAY
    # ============================================================

    def DisplayResults(self, results):
        """Display database query results."""

        if results:

            print(
                f"Found {len(results)} result(s):"
            )

            for row in results:

                print(
                    f"  Song: {row[0]}, "
                    f"Duration: {row[1]:.2f}s, "
                    f"BPM: {row[2]:.2f}, "
                    f"Chords: {row[3]}"
                )

        else:

            print(
                "Nothing in database."
            )
