from pathlib import Path
import sqlite3


def ConnectDB():
    db_path = Path(__file__).resolve().parents[2] / "data" / "liveflow.db"
    print(f"Creating/opening: {db_path}")

    return sqlite3.connect(db_path)

def MakeDB():
    conn = ConnectDB()
    c = conn.cursor()
    
    c.execute('''CREATE TABLE liveflow (
    song text primary key
    bpm integer
    chords text
    )''')
    
    conn.commit()
    conn.close()

def PushDB(song, bpm, chords):
    conn = ConnectDB()
    c = conn.cursor()

    c.execute('INSERT INTO liveflow VALUES
    (?, ?, ?)
    ', (song, bpm, chords)
    
    conn.commit()
    conn.close()
