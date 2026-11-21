"""Build an organised FL Studio project: one pattern per instrument per section, each instrument on its own
named + coloured Playlist track, clips at the right bars, section markers kept.

Works on a TEMPLATE .flp saved by FL Studio that already holds the channels (e.g. FLEX on Lead/Chords/...).
Channels, mixer and plugin states are copied byte-for-byte; only patterns, playlist clips and track names/colors
are rewritten. The input file is never modified.
"""
from __future__ import annotations

import struct
from pathlib import Path

from .flp import (FLP, Event, ID_ARR_NEW, ID_CHAN_COLOR, ID_CHAN_NAME, ID_CHAN_NEW, ID_PAT_COLOR, ID_PAT_NAME, ID_PAT_NEW,
                  ID_PAT_NOTES, ID_PL_ITEMS, ID_TRACK_DATA, ID_TRACK_NAME, unpack_notes)
from .midi_io import Note

PATTERN_BASE = 20480
TRACK_COLORS = {  # BGR-ish 0x00BBGGRR as FL stores it
    "lead": 0x3C8CFF, "lead harmony": 0x5AA5FF, "counter": 0x78B4FF, "chords": 0xE6A050,
    "bass": 0x46B4FF, "kick": 0x3C3CE6, "screech": 0xB45AE6, "snare roll": 0x50C8C8, "kick roll": 0x5050C8,
}
DEFAULT_COLOR = 0x808080

# pattern-block event ids that belong to a pattern (between its 65 event and the next block)
PAT_NOTE_BLOCK = {223, 224, 226}
PAT_PROP_BLOCK = {193, 150, 157, 158, 164, 52, 171, 252, 253}  # FL 26: name, color, ... (seen in real files)


def _color(name: str) -> int:
    return TRACK_COLORS.get(name.lower(), DEFAULT_COLOR)


TEMPLATES = Path(__file__).resolve().parents[2] / "templates"


def _utf16(text: str) -> bytes:
    return (text + "\x00").encode("utf-16-le")


def add_channels(f: FLP, specs: list[dict]) -> dict[str, int]:
    """Append sampler / audio-clip channels cloned from real FL 26 channel blocks (templates/*.flpsnip).
    spec: {"name", "kind": "sampler"|"audio", "path": absolute Windows path, "color": int (optional)}.
    Each gets its own mixer insert after the highest one in use. Returns name -> rack index."""
    ev = f.events
    idx = [e.value for e in ev if e.id == ID_CHAN_NEW]
    next_ch = (max(idx) + 1) if idx else 0
    inserts = [e.value for e in ev if e.id == 104]
    next_ins = (max(inserts) + 1) if inserts else 1
    at = next(i for i, e in enumerate(ev) if e.id == ID_ARR_NEW)
    snips = {"sampler": FLP.read(TEMPLATES / "sampler_channel.flpsnip").events,
             "audio": FLP.read(TEMPLATES / "audio_channel.flpsnip").events}
    new, out = [], {}
    for sp in specs:
        if sp["name"] in out:
            continue
        for e in snips[sp["kind"]]:
            if e.id == ID_CHAN_NEW:
                e = Event(ID_CHAN_NEW, struct.pack("<H", next_ch))
            elif e.id == ID_CHAN_NAME:
                e = Event(ID_CHAN_NAME, _utf16(sp["name"]))
            elif e.id == 196:
                e = Event(196, _utf16(sp["path"]))
            elif e.id == ID_CHAN_COLOR:
                e = Event(ID_CHAN_COLOR, struct.pack("<I", sp.get("color", _color(sp["name"]))))
            elif e.id == 104:
                e = Event(104, struct.pack("<H", next_ins))
            else:
                e = Event(e.id, e.data, e.raw_len)
            new.append(e)
        out[sp["name"]] = next_ch
        next_ch += 1
        next_ins += 1
    ev[at:at] = new
    f.n_channels = next_ch
    return out


def drop_channels(f: FLP, names: set[str]) -> list[str]:
    """Remove template channels by name (e.g. a FLEX 'Kick' that a sampler 'Kick' replaces) and renumber
    the rest. Only safe before patterns are written (build() strips patterns afterwards anyway)."""
    ev = f.events
    starts = [i for i, e in enumerate(ev) if e.id == ID_CHAN_NEW]
    arr = next(i for i, e in enumerate(ev) if e.id == ID_ARR_NEW)
    ends = starts[1:] + [arr]
    remove, removed = [], []
    for a, b in zip(starts, ends):
        name = next((ev[j].text() for j in range(a, b) if ev[j].id == ID_CHAN_NAME), "")
        if name in names:
            # a channel block may have pattern blocks interleaved after it; only drop channel events
            j = a + 1
            while j < b and ev[j].id not in (ID_PAT_NEW,):
                j += 1
            remove.append((a, j))
            removed.append(name)
    for a, j in reversed(remove):
        del ev[a:j]
    k = 0
    for i, e in enumerate(ev):
        if e.id == ID_CHAN_NEW:
            ev[i] = Event(ID_CHAN_NEW, struct.pack("<H", k))
            k += 1
    f.n_channels = k
    return removed


def audio_item(position: int, channel: int, length: int, track: int, clip_id: int) -> bytes:
    """Audio clip on the playlist (FL 26, 88 bytes, copied from a real clip): idx = channel index."""
    b = bytearray((TEMPLATES / "audio_clip_item.bin").read_bytes())
    struct.pack_into("<IHHIHH", b, 0, position, PATTERN_BASE, channel, length, 499 - track, 0)
    struct.pack_into("<I", b, 32, clip_id)
    return bytes(b)


def channels(f: FLP) -> dict[str, int]:
    """channel name -> rack index"""
    out, cur = {}, None
    for e in f.events:
        if e.id == ID_CHAN_NEW:
            cur = e.value
        elif e.id == ID_CHAN_NAME and cur is not None:
            out[e.text()] = cur
    return out


def _strip_patterns(f: FLP) -> tuple[list[Event], int, int, Event | None]:
    """Remove every pattern block. Returns (events, index where note blocks were, index where pattern
    property blocks were, a sample 223 event to reuse)."""
    ev = f.events
    out, note_at, prop_at, ev223 = [], None, None, None
    i = 0
    while i < len(ev):
        e = ev[i]
        if e.id == ID_PAT_NEW:
            j = i + 1
            kinds = set()
            while j < len(ev) and ev[j].id in (PAT_NOTE_BLOCK | PAT_PROP_BLOCK):
                kinds.add(ev[j].id)
                if ev[j].id == 223 and ev223 is None:
                    ev223 = ev[j]
                j += 1
            # a pattern's own time markers (e.g. its 4/4 signature) follow its properties: drop with it
            if kinds & PAT_PROP_BLOCK:
                while j < len(ev) and ev[j].id in {148, 33, 34, 46, 45, 168, 101, 205}:
                    j += 1
            if kinds & PAT_NOTE_BLOCK or not kinds & PAT_PROP_BLOCK:
                note_at = len(out) if note_at is None else note_at
            else:
                prop_at = len(out) if prop_at is None else prop_at
            i = j
            continue
        out.append(e)
        i += 1
    return out, note_at, prop_at, ev223


def _pack_notes(notes: list[Note], rack: int, ppq: int, template_rest: bytes) -> bytes:
    data = bytearray()
    for n in sorted(notes, key=lambda n: (n.start, n.pitch)):
        pos = int(round(n.start * ppq))
        length = max(1, int(round(n.dur * ppq)))
        rest = bytearray(template_rest)
        rest[5] = max(1, min(127, n.vel))   # velocity
        data += struct.pack("<IHHIHH", pos, 0x4000, rack, length, n.pitch, 0) + bytes(rest)
    return bytes(data)


# A real pattern clip saved by FL Studio 26.1.7 (Espen's project, "Drop lead melody"), 88 bytes.
# Layout: 0 pos u32 | 4 base u16 (20480) | 6 base+pattern u16 | 8 length u32 | 12 499-track u16 | 14 group u16 |
#         16..23 flags | 24 start offset i32 | 28 end offset i32 | 32 unique clip id u32 | 36.. constants
FL26_PATTERN_CLIP = bytes.fromhex(
    "200100000050025040ce0000ef01000078000040406480804002000080d000003d000000"
    "000000000000000000000000000000000000803f0000000000000000000000000000f03f"
    "00000000ffffffff0000000000000000")
ITEM_SIZE = 88


def pack_item(position: int, pattern: int, length: int, track: int, clip_id: int) -> bytes:
    """One pattern clip in FL 26 format, full (untrimmed) pattern from tick 0 to `length`."""
    b = bytearray(FL26_PATTERN_CLIP)
    assert len(b) == ITEM_SIZE
    struct.pack_into("<IHHIHH", b, 0, position, PATTERN_BASE, PATTERN_BASE + pattern, length, 499 - track, 0)
    struct.pack_into("<iiI", b, 24, 0, length, clip_id)
    return bytes(b)


ID_TEMPO = 156          # dword: BPM * 1000
MARKER_IDS = {148, 33, 34, 46, 45, 168, 101, 205}
SIG_FLAG = 0x08000000   # marker position flag used for the time-signature marker


def _rewrite_markers(ev: list[Event], sections: list[dict], ppq: int) -> list[Event]:
    """Replace the section markers of the first arrangement with one marker per section (keeps the 4/4
    time-signature marker). Marker group layout copied from the template: 148,33,34,46,45,168,101,205."""
    ai = next(i for i, e in enumerate(ev) if e.id == ID_PL_ITEMS)
    j = ai + 1
    groups, cur = [], []
    while j < len(ev) and ev[j].id in MARKER_IDS:
        if ev[j].id == 148 and cur:
            groups.append(cur)
            cur = []
        cur.append(ev[j])
        j += 1
    if cur:
        groups.append(cur)
    keep = [g for g in groups if g[0].value & SIG_FLAG]
    proto = next((g for g in groups if not g[0].value & SIG_FLAG), None)
    if proto is None:
        return ev
    new = []
    for s in sections:
        g = [Event(e.id, e.data, e.raw_len) for e in proto]
        g[0] = Event(148, struct.pack("<I", int((s["start_bar"] - 1) * 4 * ppq)))
        g[-1] = Event(205, (s["name"] + "\x00").encode("utf-16-le"))
        new += g
    return ev[:ai + 1] + [e for g in keep for e in g] + new + ev[j:]


def build(template_flp: Path, out_flp: Path, tracks: dict[str, list[Note]], sections: list[dict],
          split_sections: bool = True, bpm: float | None = None,
          samplers: list[dict] | None = None, audio_clips: list[dict] | None = None) -> dict:
    """tracks: instrument name -> notes in beats from song bar 1. sections: [{name,start_bar,length_bars}].
    samplers: [{"name", "path"}] -> sampler channels with the user's sample (notes in `tracks` under that name).
    audio_clips: [{"name", "path", "start_bar", "seconds"}] -> audio clip channel + clip on its own track."""
    f = FLP.read(template_flp)
    ppq = f.ppq
    extra = [dict(s, kind="sampler") for s in (samplers or [])] + [dict(a, kind="audio") for a in (audio_clips or [])]
    # remove template channels that this song does not use, and those a sampler replaces
    unused = {n for n in channels(f) if n not in tracks}
    drop_channels(f, unused | {x["name"] for x in extra})
    if extra:
        add_channels(f, extra)
    chans = channels(f)
    missing = [t for t in tracks if t not in chans]
    if missing:
        raise ValueError(f"Malen mangler kanaler: {missing}. Kanalnavn i malen: {list(chans)}")
    # note template bytes (fine pitch, release, midi ch, pan, vel, mod) from an existing note if any
    rest = bytes([120, 0, 64, 0, 64, 100, 128, 128])
    for e in f.events:
        if e.id == ID_PAT_NOTES and len(e.data) >= 24:
            rest = unpack_notes(e.data)[0].rest
            break
    ev, note_at, prop_at, ev223 = _strip_patterns(f)
    if note_at is None or prop_at is None:
        # no pattern blocks in template: notes go before first channel, props before arrangement
        note_at = next(i for i, e in enumerate(ev) if e.id == ID_CHAN_NEW)
        prop_at = next(i for i, e in enumerate(ev) if e.id == ID_ARR_NEW)

    order = [t for t in tracks] + [a["name"] for a in (audio_clips or []) if a["name"] not in tracks]
    note_blocks, prop_blocks, items, summary = [], [], [], []
    pat = 0
    for ti, name in enumerate(order):
        if name not in tracks:
            continue                      # audio-clip track: no patterns
        notes = tracks[name]
        spans = ([(s["name"], (s["start_bar"] - 1) * 4, s["length_bars"] * 4) for s in sections]
                 if split_sections else [("", 0, max((n.end for n in notes), default=0))])
        for sname, b0, blen in spans:
            sel = [Note(n.start - b0, n.dur, n.pitch, n.vel) for n in notes if b0 <= n.start < b0 + blen]
            if not sel:
                continue
            pat += 1
            pname = f"{name} - {sname}" if sname else name
            note_blocks += [Event(ID_PAT_NEW, struct.pack("<H", pat))]
            # NB: event 223 from a MIDI import is a tempo automation point - never copied into new patterns
            note_blocks.append(Event(ID_PAT_NOTES, _pack_notes(sel, chans[name], ppq, rest)))
            prop_blocks += [Event(ID_PAT_NEW, struct.pack("<H", pat)),
                            Event(ID_PAT_NAME, (pname + "\x00").encode("utf-16-le")),
                            Event(ID_PAT_COLOR, struct.pack("<I", _color(name)))]
            items.append((int(b0 * ppq), pat, int(blen * ppq), ti))
            summary.append({"pattern": pat, "name": pname, "track": ti + 1, "start_bar": b0 // 4 + 1,
                            "bars": blen // 4, "notes": len(sel)})
    # insert blocks (prop block first so note_at index stays valid if prop_at > note_at)
    ev[prop_at:prop_at] = prop_blocks
    ev[note_at:note_at] = note_blocks
    # playlist items of the (first) arrangement
    ai = next(i for i, e in enumerate(ev) if e.id == ID_PL_ITEMS)
    for a in audio_clips or []:
        tr = order.index(a["name"])
        length = int(round(a["seconds"] * (bpm or 150) / 60 * ppq))
        items.append((int((a["start_bar"] - 1) * 4 * ppq), ("audio", chans[a["name"]]), length, tr))
        summary.append({"pattern": None, "name": a["name"] + " (lyd)", "track": tr + 1,
                        "start_bar": a["start_bar"], "bars": round(length / ppq / 4, 1), "notes": 0})
    items.sort(key=lambda x: (x[0], x[3]))
    blobs = []
    for cid, (pos, pt, ln, tr) in enumerate(items):
        if isinstance(pt, tuple):
            blobs.append(audio_item(pos, pt[1], ln, tr, cid + 1))
        else:
            blobs.append(pack_item(pos, pt, ln, tr, cid + 1))
    ev[ai] = Event(ID_PL_ITEMS, b"".join(blobs))
    # track names + colours. FL order per track: 238 (data), 43, [239 name]
    newev, k, pending = [], 0, None
    for e in ev:
        if e.id == ID_TRACK_NAME and 0 < k <= len(order):
            continue                                   # replace old names on the tracks we use
        if e.id == ID_TRACK_DATA and pending is not None:
            newev.append(pending)                      # name of previous track (no 43 seen)
            pending = None
        newev.append(e)
        if e.id == ID_TRACK_DATA:
            k += 1
            if k <= len(order):
                d = bytearray(e.data)
                struct.pack_into("<I", d, 4, _color(order[k - 1]))
                newev[-1] = Event(ID_TRACK_DATA, bytes(d))
                pending = Event(ID_TRACK_NAME, (order[k - 1] + "\x00").encode("utf-16-le"))
        elif e.id == 43 and pending is not None:
            newev.append(pending)
            pending = None
    if pending is not None:
        newev.append(pending)
    if bpm:
        newev = [Event(ID_TEMPO, struct.pack("<I", int(round(bpm * 1000)))) if e.id == ID_TEMPO else e for e in newev]
    newev = _rewrite_markers(newev, sections, ppq)
    f.events = newev
    out_flp = Path(out_flp)
    if out_flp.exists():
        raise FileExistsError(f"{out_flp} finnes allerede — overskriver aldri.")
    f.write(out_flp)
    return {"patterns": pat, "clips": len(items), "tracks": order, "detail": summary}


def verify(path: Path) -> dict:
    """Re-read a built FLP and report patterns, notes per pattern and clip placement."""
    f = FLP.read(path)
    pats, names, cur = {}, {}, None
    for e in f.events:
        if e.id == ID_PAT_NEW:
            cur = e.value
        elif e.id == ID_PAT_NOTES and cur is not None:
            pats[cur] = unpack_notes(e.data)
        elif e.id == ID_PAT_NAME and cur is not None:
            names[cur] = e.text()
    items = []
    for e in f.events:
        if e.id == ID_PL_ITEMS:
            n = ITEM_SIZE
            for k in range(0, len(e.data), n):
                pos, base, idx, length, rv = struct.unpack_from("<IHHIH", e.data, k)
                items.append({"bar": pos // (4 * f.ppq) + 1, "pattern": idx - base, "track": 500 - rv,
                              "bars": length / (4 * f.ppq)})
            break
    tnames = [e.text() for e in f.events if e.id == ID_TRACK_NAME]
    return {"version": f.version, "patterns": {k: (names.get(k, "?"), len(v), sorted({n.rack for n in v}))
                                               for k, v in pats.items()},
            "items": items, "track_names": tnames[:12]}


def tracks_from_flp(path: Path) -> dict[str, list[Note]]:
    """Notes of an existing project per channel, in absolute beats. If the playlist has pattern clips, each
    clip contributes its pattern's notes at the clip position (respecting clip start/end trimming); patterns
    not on the playlist are ignored. If the playlist is empty (fresh MIDI import), all patterns count from 0."""
    f = FLP.read(path)
    chans = {v: k for k, v in channels(f).items()}
    pats, cur = {}, None
    for e in f.events:
        if e.id == ID_PAT_NEW:
            cur = e.value
        elif e.id == ID_PAT_NOTES and cur is not None:
            pats.setdefault(cur, []).extend(unpack_notes(e.data))
    clips = []
    for e in f.events:
        if e.id == ID_PL_ITEMS:
            for k in range(0, len(e.data) - ITEM_SIZE + 1, ITEM_SIZE):
                pos, base, idx, length = struct.unpack_from("<IHHI", e.data, k)
                so, eo = struct.unpack_from("<ii", e.data, k + 24)
                if base and idx > base:
                    clips.append((pos, idx - base, max(0, so), eo if eo > 0 else length))
            break
    if not clips:
        clips = [(0, p, 0, 1 << 30) for p in pats]
    out: dict[str, list[Note]] = {}
    for pos, pnum, so, eo in clips:
        for n in pats.get(pnum, []):
            if so <= n.pos < eo:
                name = chans.get(n.rack, f"Channel {n.rack}")
                out.setdefault(name, []).append(
                    Note((pos + n.pos - so) / f.ppq, n.length / f.ppq, n.key, n.velocity))
    return {k: sorted(v, key=lambda n: (n.start, n.pitch)) for k, v in out.items()}
