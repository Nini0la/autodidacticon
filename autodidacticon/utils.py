from __future__ import annotations

import hashlib
import itertools
import re
import threading
import time
from datetime import UTC, datetime

_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_ULID_LOCK = threading.Lock()
_ULID_COUNTER = itertools.count(max(1, int(time.time() * 1000)))


def now_utc_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def normalize_whitespace(value: str) -> str:
    return " ".join(value.split())


def normalize_title(title: str) -> str:
    return normalize_whitespace(title).strip().lower()


def normalize_text_for_hash(value: str) -> str:
    return normalize_whitespace(value).strip().lower()


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def stable_content_hash(value: str) -> str:
    return sha256_hex(normalize_text_for_hash(value))


def deterministic_card_key(topic_id: str, concept_id: str, card_type: str, version_seed: str) -> str:
    return sha256_hex(f"{topic_id}{concept_id}{card_type}{version_seed}")


def generate_ulid() -> str:
    with _ULID_LOCK:
        n = next(_ULID_COUNTER)
    out: list[str] = []
    while n > 0:
        n, rem = divmod(n, 32)
        out.append(_ALPHABET[rem])
    encoded = "".join(reversed(out)) or "0"
    return ("0" * 26 + encoded)[-26:]


def parse_version(version_seed: str) -> int:
    digits = "".join(re.findall(r"\d+", version_seed))
    if not digits:
        return 1
    return max(1, int(digits))
