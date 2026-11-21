"""Minimal FL Studio .flp reader/writer (event level).

An FLP file is a header chunk ("FLhd": format, channel count, PPQ) followed by a data chunk ("FLdt")
holding a flat list of events. Event id ranges decide the payload size:
    0-63: 1 byte | 64-127: 2 bytes | 128-191: 4 bytes | 192-255: varint length + bytes
We only touch the events we understand (patterns, notes, playlist items, track names/colors, markers) and
copy every other event byte-for-byte, so plugin states (FLEX, mixer effects) survive untouched.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path

# --- event ids (FL 20+) -----------------------------------------------------
ID_CHAN_NEW = 64          # word: start of a channel block (rack index)
ID_PAT_NEW = 65           # word: start of a pattern block (1-based pattern number)
ID_ARR_NEW = 99           # word: start of an arrangement
ID_CHAN_NAME = 203        # text: channel display name
ID_PAT_COLOR = 150        # dword
ID_PAT_NAME = 193         # text
ID_PAT_NOTES = 224        # data: 24 bytes per note
ID_PL_ITEMS = 233         # data: playlist items of current arrangement
ID_TRACK_DATA = 238       # data: one playlist track
ID_TRACK_NAME = 239       # text: name of the preceding track
ID_TIMEMARKER_POS = 148   # dword
ID_TIMEMARKER_NAME = 205  # text
ID_VERSION = 199          # text
ID_CHAN_COLOR = 128       # dword
ID_FX_CHANNEL = 22        # byte: channel -> mixer insert (old); newer uses 147 dword
ID_CHAN_INSERT = 147      # dword (FL 20+)

# Exceptions to the size rule, found empirically in FL Studio 26.1.7 files (both test files parse to the
# exact end and yield correct titles/channel names only with this rule).
SPECIAL_SIZES = {172: 3}


@dataclass
class Event:
    id: int
    data: bytes
    raw_len: bytes | None = None   # original length prefix (FL sometimes writes non-minimal varints)

    @property
    def value(self) -> int:
        return int.from_bytes(self.data, "little")

    def text(self) -> str:
        d = self.data
        try:
            if len(d) >= 2 and d[1] == 0:
                return d.decode("utf-16-le").rstrip("\x00")
            return d.decode("ascii").rstrip("\x00")
        except UnicodeDecodeError:
            return d.hex()


def _varint(b: bytes, i: int) -> tuple[int, int]:
    v = shift = 0
    while True:
        c = b[i]
        i += 1
        v |= (c & 0x7F) << shift
        shift += 7
        if not c & 0x80:
            return v, i


def _enc_varint(n: int) -> bytes:
    out = bytearray()
    while True:
        c = n & 0x7F
        n >>= 7
        if n:
            out.append(c | 0x80)
        else:
            out.append(c)
            return bytes(out)


@dataclass
class FLP:
    fmt: int
    n_channels: int
    ppq: int
    events: list[Event] = field(default_factory=list)

    # ---------------- io
    @classmethod
    def read(cls, path: Path) -> "FLP":
        b = Path(path).read_bytes()
        if b[:4] != b"FLhd":
            raise ValueError("Ikke en FL Studio-fil (mangler FLhd).")
        hl = struct.unpack_from("<I", b, 4)[0]
        fmt, nch, ppq = struct.unpack_from("<hHH", b, 8)
        i = 8 + hl
        if b[i:i + 4] != b"FLdt":
            raise ValueError("Mangler FLdt-chunk.")
        dl = struct.unpack_from("<I", b, i + 4)[0]
        i += 8
        end = i + dl
        evs = []
        while i < end:
            eid = b[i]
            if i + 1 > end:
                break
            i += 1
            if eid in SPECIAL_SIZES:
                n = SPECIAL_SIZES[eid]
            elif eid < 64:
                n = 1
            elif eid < 128:
                n = 2
            elif eid < 192:
                n = 4
            else:
                j = i
                n, i = _varint(b, i)
                evs.append(Event(eid, b[i:i + n], b[j:i]))
                i += n
                continue
            evs.append(Event(eid, b[i:i + n]))
            i += n
        if i != end:
            raise ValueError("FLP-parsing kom ut av takt (ukjent hendelsesformat) — avbryter for å ikke ødelegge filen.")
        return cls(fmt, nch, ppq, evs)

    def to_bytes(self) -> bytes:
        body = bytearray()
        for e in self.events:
            body.append(e.id)
            if e.id >= 192:
                keep = e.raw_len is not None and _varint(e.raw_len, 0)[0] == len(e.data)
                body += e.raw_len if keep else _enc_varint(len(e.data))
            body += e.data
        head = b"FLhd" + struct.pack("<I", 6) + struct.pack("<hHH", self.fmt, self.n_channels, self.ppq)
        return head + b"FLdt" + struct.pack("<I", len(body)) + bytes(body)

    def write(self, path: Path) -> None:
        Path(path).write_bytes(self.to_bytes())

    # ---------------- helpers
    def find(self, eid: int) -> list[int]:
        return [i for i, e in enumerate(self.events) if e.id == eid]

    @property
    def version(self) -> str:
        i = self.find(ID_VERSION)
        return self.events[i[0]].text() if i else "?"


# ---------------- notes -------------------------------------------------------
NOTE_FMT = "<IHHIHHBBBBBBB"  # pos, flags, rack_ch, length, key, group, fine, (u8), release, midi_ch, pan, vel, modx... see below
NOTE_SIZE = 24


@dataclass
class FLNote:
    pos: int
    flags: int
    rack: int
    length: int
    key: int
    group: int
    rest: bytes  # remaining 8 bytes (fine pitch, release, midi ch, pan, velocity, mod x/y) kept verbatim

    def pack(self) -> bytes:
        return struct.pack("<IHHIHH", self.pos, self.flags, self.rack, self.length, self.key, self.group) + self.rest

    @property
    def velocity(self) -> int:
        return self.rest[5]


def unpack_notes(data: bytes) -> list[FLNote]:
    out = []
    for k in range(0, len(data) - NOTE_SIZE + 1, NOTE_SIZE):
        pos, flags, rack, length, key, group = struct.unpack_from("<IHHIHH", data, k)
        out.append(FLNote(pos, flags, rack, length, key, group, data[k + 16:k + 24]))
    return out
