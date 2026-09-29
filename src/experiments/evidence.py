"""Append-only receipts with atomic no-clobber publication and hash validation."""

import hashlib
import json
import os
import tempfile
from pathlib import Path


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def publish(directory: Path, record: dict):
    directory.mkdir(parents=True, exist_ok=True)
    payload = dict(record)
    payload["receipt_sha256"] = digest(record)
    name = record["run_id"]
    if not name.startswith("RUN-") or any(
        c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_" for c in name
    ):
        raise ValueError("invalid run id")
    target = directory / (name + ".json")
    fd, temporary = tempfile.mkstemp(prefix=".receipt-", dir=directory)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(canonical(payload) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        # Unlike replace(), link() fails if destination exists. A final filename
        # is visible only after the complete payload has been flushed.
        os.link(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return target


def read_receipt(path):
    record = json.loads(Path(path).read_text("utf-8"))
    checksum = record.pop("receipt_sha256")
    if digest(record) != checksum:
        raise ValueError(f"receipt integrity failure: {path}")
    record["receipt_sha256"] = checksum
    return record
