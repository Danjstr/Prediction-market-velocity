"""Framed, versioned protocol between the trusted parent and the isolated parse worker (G-1).

The worker writes one stream to its standard output:

    MAGIC, then frames, then end of file.

Each frame is a one-byte type, a four-byte big-endian payload length, and the payload.
The first frame is always ``HELLO`` and the last is always ``RESULT``; nothing may follow
``RESULT``. An ``extract`` stream carries ``DIR``, ``FILE``, ``DATA``, and ``END_FILE``
frames between them, in a strict order the parent enforces. JSON payloads are canonical
JSON (``pmv.integrity``), so a payload has exactly one valid encoding.

Payload limits are fixed here and enforced by the parent before a payload is buffered.
Refusal codes are a closed set: a worker can report only an enumerated code and, where
useful, a record number. It never reports content, so no raw or protected value can reach
an error message, a log, or an agent through this channel.
"""

import struct
from enum import StrEnum
from typing import Final

MAGIC: Final = b"PMVWRK1\n"
PROTOCOL: Final = "pmv.acquisition.parse_worker"
PROTOCOL_VERSION: Final = 1
HEADER: Final = struct.Struct(">cI")
MAX_JSON_PAYLOAD: Final = 64 * 1024
MAX_DATA_PAYLOAD: Final = 1024 * 1024
MAX_NAME_PAYLOAD: Final = 4096

HELLO: Final = b"H"
RESULT: Final = b"R"
DIR: Final = b"D"
FILE: Final = b"F"
DATA: Final = b"B"
END_FILE: Final = b"E"
FRAME_TYPES: Final = frozenset({HELLO, RESULT, DIR, FILE, DATA, END_FILE})


class Operation(StrEnum):
    """What the worker is asked to do. Each operation has a fixed parameter schema."""

    PROBE = "probe"
    VERIFY = "verify"
    EXTRACT = "extract"


class RefusalCode(StrEnum):
    """Every reason a worker may give for refusing its input. Closed set; no content."""

    BAD_PARAMETERS = "bad_parameters"
    CONFINEMENT_FAILED = "confinement_failed"
    LIMITS_NOT_APPLIED = "limits_not_applied"
    INPUT_NOT_REGULAR_FILE = "input_not_regular_file"
    INPUT_TOO_LARGE = "input_too_large"
    FORMAT_REFUSED = "format_refused"
    COMPRESSION_REFUSED = "compression_refused"
    DECODED_TOO_LARGE = "decoded_too_large"
    EXPANSION_RATIO_EXCEEDED = "expansion_ratio_exceeded"
    PARSE_FAILED = "parse_failed"
    SCHEMA_MISMATCH = "schema_mismatch"
    TYPE_MISMATCH = "type_mismatch"
    ARCHIVE_REFUSED = "archive_refused"
    READER_NOT_ADOPTED = "reader_not_adopted"
    RESOURCE_EXHAUSTED = "resource_exhausted"
    INTERNAL_ERROR = "internal_error"


def frame(kind: bytes, payload: bytes) -> bytes:
    """Encode one frame. Raises ValueError if the payload exceeds its type's limit."""
    if kind not in FRAME_TYPES:
        raise ValueError("unknown frame type")
    if len(payload) > payload_limit(kind):
        raise ValueError("frame payload exceeds its limit")
    return HEADER.pack(kind, len(payload)) + payload


def payload_limit(kind: bytes) -> int:
    if kind == DATA:
        return MAX_DATA_PAYLOAD
    if kind == DIR:
        return MAX_NAME_PAYLOAD
    return MAX_JSON_PAYLOAD
