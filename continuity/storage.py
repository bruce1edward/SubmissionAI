"""Durable app records. LangGraph checkpoints use a separate native saver."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from threading import RLock, Thread, Event
import time
from uuid import uuid4

from pymongo import MongoClient, ReturnDocument
from pymongo.errors import DuplicateKeyError

BUCKETS = {"study_versions", "runs", "review_memory", "evidence_chunks"}
LEASE_SECONDS = 30


@contextmanager
def renewing_lease(refresh):
    """Keep a lease alive while its owner lives; a killed process expires in 30s."""
    stopped = Event()
    def heartbeat():
        while not stopped.wait(5):
            try:
                if not refresh():
                    break
            except Exception:
                # A storage failure prevents renewal; don't expose credentials via logs.
                break
    thread = Thread(target=heartbeat, daemon=True)
    thread.start()
    try:
        yield
    finally:
        stopped.set()
        thread.join(timeout=2)


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class BusyRun(Exception):
    pass


class SQLiteStore:
    backend = "sqlite"

    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(str(path), check_same_thread=False, timeout=10)
        self.lock = RLock()
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("CREATE TABLE IF NOT EXISTS records (bucket TEXT, id TEXT, data TEXT, PRIMARY KEY(bucket,id))")
        self.connection.execute("CREATE TABLE IF NOT EXISTS leases (id TEXT PRIMARY KEY, owner TEXT, expires REAL)")
        self.connection.commit()

    def put(self, bucket, value):
        assert bucket in BUCKETS
        with self.lock, self.connection:
            self.connection.execute("INSERT INTO records VALUES (?,?,?) ON CONFLICT(bucket,id) DO UPDATE SET data=excluded.data", (bucket, value["id"], json.dumps(value)))
        return value

    def get(self, bucket, key):
        with self.lock:
            row = self.connection.execute("SELECT data FROM records WHERE bucket=? AND id=?", (bucket, key)).fetchone()
        return json.loads(row[0]) if row else None

    def list(self, bucket, filters=None):
        with self.lock:
            rows = self.connection.execute("SELECT data FROM records WHERE bucket=?", (bucket,)).fetchall()
        values = [json.loads(row[0]) for row in rows]
        return sorted([v for v in values if all(v.get(k) == val for k, val in (filters or {}).items())], key=lambda v: v.get("created_at", ""), reverse=True)

    @contextmanager
    def lease(self, key):
        owner = uuid4().hex
        with self.lock, self.connection:
            self.connection.execute("DELETE FROM leases WHERE id=? AND expires<?", (key, time.time()))
            try:
                self.connection.execute("INSERT INTO leases VALUES (?,?,?)", (key, owner, time.time() + LEASE_SECONDS))
            except sqlite3.IntegrityError as exc:
                raise BusyRun("This operation is already running") from exc
        def refresh():
            with self.lock, self.connection:
                return self.connection.execute("UPDATE leases SET expires=? WHERE id=? AND owner=?", (time.time() + LEASE_SECONDS, key, owner)).rowcount == 1
        try:
            with renewing_lease(refresh):
                yield
        finally:
            with self.lock, self.connection:
                self.connection.execute("DELETE FROM leases WHERE id=? AND owner=?", (key, owner))

    def close(self):
        self.connection.close()


class MongoStore:
    backend = "mongodb"

    def __init__(self, settings):
        self.client = MongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=6000, connectTimeoutMS=6000)
        self.client.admin.command("ping")
        self.db = self.client[settings.mongodb_database]
        for bucket in BUCKETS:
            self.db[bucket].create_index([("study_id", 1), ("created_at", -1)])
        self.db.evidence_chunks.create_index([("package_id", 1), ("document_id", 1)])

    def put(self, bucket, value):
        assert bucket in BUCKETS
        self.db[bucket].replace_one({"_id": value["id"]}, {**value, "_id": value["id"]}, upsert=True)
        return value

    def get(self, bucket, key):
        return self.db[bucket].find_one({"_id": key}, {"_id": 0})

    def list(self, bucket, filters=None):
        assert bucket in BUCKETS
        return list(self.db[bucket].find(filters or {}, {"_id": 0}).sort("created_at", -1))

    @contextmanager
    def lease(self, key):
        owner = uuid4().hex
        try:
            self.db.leases.find_one_and_update(
                {"_id": key, "expires": {"$lt": time.time()}},
                {"$set": {"owner": owner, "expires": time.time() + LEASE_SECONDS}},
                upsert=True, return_document=ReturnDocument.AFTER,
            )
        except DuplicateKeyError as exc:
            raise BusyRun("This operation is already running") from exc
        def refresh():
            return self.db.leases.update_one({"_id": key, "owner": owner}, {"$set": {"expires": time.time() + LEASE_SECONDS}}).matched_count == 1
        try:
            with renewing_lease(refresh):
                yield
        finally:
            self.db.leases.delete_one({"_id": key, "owner": owner})

    def close(self):
        self.client.close()


def make_store(settings):
    if settings.storage_backend == "mongodb":
        return MongoStore(settings)
    return SQLiteStore(settings.data_dir / "records.sqlite3")
