"""One-time copy of the old local SQLite database (data/event.db) into Firestore.

Usage (from ctrl-alt-escape/):
    .venv/bin/python backend/migrate_to_firestore.py           # refuses if Firestore already has participants
    .venv/bin/python backend/migrate_to_firestore.py --force   # overwrite matching documents anyway
"""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(__file__))

from firestore_sync import BATCH_LIMIT, TABLES, client, collection_name

SQLITE_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'event.db')


def main():
    if not os.path.exists(SQLITE_PATH):
        sys.exit(f"No local database at {os.path.abspath(SQLITE_PATH)}")

    db = client()
    if '--force' not in sys.argv and any(db.collection(collection_name('participants')).limit(1).stream()):
        sys.exit("Firestore already has participants. Re-run with --force to overwrite.")

    src = sqlite3.connect(SQLITE_PATH)
    src.row_factory = sqlite3.Row
    for table, pk in TABLES.items():
        rows = [dict(r) for r in src.execute(f"SELECT * FROM {table}")]
        for i in range(0, len(rows), BATCH_LIMIT):
            batch = db.batch()
            for row in rows[i:i + BATCH_LIMIT]:
                batch.set(db.collection(collection_name(table)).document(str(row[pk])), row)
            batch.commit()
        print(f"{table}: {len(rows)} copied")
    print("Done.")


if __name__ == '__main__':
    main()
