"""Cloud Firestore persistence for the event database.

Firestore is the source of truth. At startup every collection is loaded into an
in-memory SQLite working copy, which serves all queries (the participant UI polls
every 2.5s, so reading Firestore per request would be slow and costly). SQLite
triggers record every changed row in _sync_queue, and each commit pushes those
rows to Firestore. If a push fails, the queue is kept and retried on the next commit.

Each table maps to a collection of the same name (plus FIRESTORE_COLLECTION_PREFIX),
with one document per row, keyed by the row's primary key.
"""
import json
import os

import firebase_admin
from firebase_admin import credentials, firestore
from google.auth.credentials import AnonymousCredentials

from config import config

# table -> primary key column, in hydration order
TABLES = {
    'participants': 'id',
    'teams': 'id',
    'team_requests': 'id',
    'notifications': 'id',
    'level_states': 'id',
    'submissions': 'id',
    'hint_events': 'id',
    'violations': 'id',
    'admin_actions': 'id',
    'event_log': 'id',
    'settings': 'key',
}

# Columns that change on every request and only matter while the server is up.
# Changes to these alone are not pushed (they are saved along with any other change).
UNSYNCED_COLUMNS = {'participants': {'last_seen'}}

BATCH_LIMIT = 450  # Firestore allows 500 writes per batch

_client = None
_flushing = False


def _app_root():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


class _EmulatorCredential(credentials.Base):
    def get_credential(self):
        return AnonymousCredentials()


def _credentials():
    if os.getenv("FIRESTORE_EMULATOR_HOST"):
        return _EmulatorCredential()
    if config.FIREBASE_CREDENTIALS_JSON:
        return credentials.Certificate(json.loads(config.FIREBASE_CREDENTIALS_JSON))
    if config.FIREBASE_CREDENTIALS:
        path = config.FIREBASE_CREDENTIALS
        if not os.path.isabs(path):
            path = os.path.join(_app_root(), path)
        return credentials.Certificate(path)
    return credentials.ApplicationDefault()


def client():
    global _client
    if _client is None:
        if not firebase_admin._apps:
            options = {'projectId': config.FIREBASE_PROJECT_ID} if config.FIREBASE_PROJECT_ID else None
            firebase_admin.initialize_app(_credentials(), options)
        _client = firestore.client()
    return _client


def collection_name(table: str) -> str:
    return f"{config.FIRESTORE_COLLECTION_PREFIX}{table}"


def _columns(conn, table: str):
    return [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]


def setup(conn):
    """Create the change queue, load Firestore data, then start tracking changes."""
    conn.execute("""CREATE TABLE IF NOT EXISTS _sync_queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tbl TEXT NOT NULL,
        pk,
        op TEXT NOT NULL
    )""")
    conn.commit()
    hydrate(conn)
    install_triggers(conn)


def hydrate(conn):
    db = client()
    conn.execute("PRAGMA foreign_keys=OFF")
    counts = {}
    for table in TABLES:
        cols = _columns(conn, table)
        rows = []
        for doc in db.collection(collection_name(table)).stream():
            data = doc.to_dict()
            rows.append([data.get(c) for c in cols])
        if rows:
            conn.executemany(
                f"INSERT OR REPLACE INTO {table} ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                rows,
            )
        counts[table] = len(rows)
    conn.commit()
    conn.execute("PRAGMA foreign_keys=ON")
    print(f"=> Loaded from Firestore: {counts}")


def install_triggers(conn):
    for table, pk in TABLES.items():
        skip = UNSYNCED_COLUMNS.get(table, set())
        changed = " OR ".join(f"OLD.{c} IS NOT NEW.{c}" for c in _columns(conn, table) if c not in skip)
        conn.executescript(f"""
        CREATE TRIGGER IF NOT EXISTS _sync_{table}_ins AFTER INSERT ON {table} BEGIN
            INSERT INTO _sync_queue (tbl, pk, op) VALUES ('{table}', NEW.{pk}, 'upsert');
        END;
        CREATE TRIGGER IF NOT EXISTS _sync_{table}_upd AFTER UPDATE ON {table} WHEN {changed} BEGIN
            INSERT INTO _sync_queue (tbl, pk, op) VALUES ('{table}', NEW.{pk}, 'upsert');
        END;
        CREATE TRIGGER IF NOT EXISTS _sync_{table}_del AFTER DELETE ON {table} BEGIN
            INSERT INTO _sync_queue (tbl, pk, op) VALUES ('{table}', OLD.{pk}, 'delete');
        END;
        """)


def flush(conn):
    """Push all committed changes to Firestore. Called after every commit."""
    global _flushing
    if _flushing:
        return
    pending = conn.execute("SELECT id, tbl, pk, op FROM _sync_queue ORDER BY id").fetchall()
    if not pending:
        return

    _flushing = True
    try:
        # Keep only the last operation per document
        latest = {}
        for r in pending:
            key = (r['tbl'], r['pk'])
            latest.pop(key, None)
            latest[key] = r['op']

        db = client()
        writes = []
        for (table, pk), op in latest.items():
            ref = db.collection(collection_name(table)).document(str(pk))
            row = None
            if op != 'delete':
                row = conn.execute(f"SELECT * FROM {table} WHERE {TABLES[table]}=?", (pk,)).fetchone()
            writes.append((ref, dict(row) if row else None))

        for i in range(0, len(writes), BATCH_LIMIT):
            batch = db.batch()
            for ref, data in writes[i:i + BATCH_LIMIT]:
                if data is None:
                    batch.delete(ref)
                else:
                    batch.set(ref, data)
            batch.commit(timeout=10)

        conn.execute("DELETE FROM _sync_queue WHERE id <= ?", (pending[-1]['id'],))
        conn.commit()
    except Exception as e:
        print(f"Firestore sync failed ({len(pending)} change(s) queued, will retry): {e}")
    finally:
        _flushing = False
