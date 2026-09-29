"""Append-only receipts with atomic no-clobber publication and hash validation."""

import hashlib
import json
import os
import tempfile
from pathlib import Path

# Receipt schema written by this code. v2 differs from v1 only in how source
# and test hashes are computed (see normalize_source) and in declaring it.
RECEIPT_SCHEMA = "software-learning-receipt/v2"
LEGACY_RECEIPT_SCHEMA = "software-learning-receipt/v1"
# Declared in every v2 receipt: UTF-8, leading BOM removed, CRLF/CR -> LF.
SOURCE_HASH_NORMALIZATION = "lf/v1"
# Implied by v1 receipts (never written): source text was read with universal
# newlines, but acceptance tests were hashed as raw checkout bytes, so v1 test
# hashes depend on the end-of-line configuration of the executing checkout.
LEGACY_SOURCE_HASH_NORMALIZATION = "checkout-bytes/v0"


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def normalize_source(content):
    """The single normalization applied before hashing any source or test file.

    Accepts checkout bytes or text. Decodes UTF-8, drops one leading BOM and
    maps CRLF and lone CR to LF, so a Windows (CRLF) and a Linux (LF) checkout
    of the same git blob produce the same text and therefore the same hashes.
    """
    text = content.decode("utf-8") if isinstance(content, bytes) else content
    return text.removeprefix("﻿").replace("\r\n", "\n").replace("\r", "\n")


def source_sha256(content):
    """SHA-256 of one normalized file (used by the source manifest)."""
    return hashlib.sha256(normalize_source(content).encode("utf-8")).hexdigest()


def sources_digest(files):
    """Canonical digest of a {relative path: content} mapping of normalized files."""
    return digest({name: normalize_source(content) for name, content in files.items()})


def hash_normalization(record):
    """Normalization scheme of a receipt; fails on unknown schemas or schemes."""
    schema = record.get("schema_id")
    if schema == LEGACY_RECEIPT_SCHEMA:
        if "source_hash_normalization" in record:
            raise ValueError("v1 receipts cannot declare source_hash_normalization")
        return LEGACY_SOURCE_HASH_NORMALIZATION
    if schema == RECEIPT_SCHEMA:
        scheme = record.get("source_hash_normalization")
        if scheme != SOURCE_HASH_NORMALIZATION:
            raise ValueError(f"unknown source_hash_normalization: {scheme!r}")
        return scheme
    raise ValueError(f"unsupported receipt schema: {schema!r}")


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
    hash_normalization(record)  # accepts v1 and v2 only
    record["receipt_sha256"] = checksum
    return record
