"""FL Studio preparation: import guide + production notes (Norwegian). Nothing here claims to have
changed FL Studio - it produces assets and exact manual steps."""
from __future__ import annotations

from pathlib import Path

from . import theory as T


def import_guide(project_name: str, arr: dict, files: dict[str, str], analysis: dict) -> str:
    bpm = arr["target_bpm"]
    key = arr["key"]
    tonic, mode = T.parse_key(key)
    kick_note = T.pc_name(tonic, T.uses_flats(tonic, mode))
    lines = [
        f"# FL Studio importguide — {project_name}",
        "",
        "Status: filene er generert og validert (MIDI leses inn, riktig tempo, noter i toneart). "
        "**Ingenting er endret i FL Studio automatisk.** Følg stegene under.",
        "",
        f"- Tempo: **{bpm:g} BPM** · Toneart: **{key}** · Lengde: {arr['total_bars']} takter",
        f"- {arr['stretch_note']}",
        "",
        *([f"## 1. Åpne det ferdige prosjektet",
           f"1. `File > Open` → `{files['flp']}`.",
           "2. Ferdig organisert: ett mønster per instrument per seksjon (f.eks. «Lead - Euphoric Drop»), ett navngitt",
           "   og farget Playlist-spor per instrument, markører per seksjon, riktig tempo. Alle kanaler er FLEX.",
           "3. `File > Save as...` for å lagre din egen versjon. Gå så til steg 3 (vokal).",
           "",
           "Reserve (hvis .flp-filen ikke åpner): bruk MIDI-importen under, og kjør `build-flp --from-flp` på det",
           "lagrede prosjektet for å dele det opp.", ""] if files.get("flp") else []),
        "## 1b. Reserve: nytt prosjekt via MIDI-import" if files.get("flp") else "## 1. Nytt, tomt prosjekt",
        "Importen under starter et nytt prosjekt selv, så du trenger ikke lage et først.",
        "",
        "## 2. Importer hele arrangementet (MIDI)",
        f"1. `File > Import > MIDI file...` → velg `{files['arrangement_mid']}`.",
        "2. I dialogen *Import MIDI data* (testet i FL Studio 2025/26):",
        "   - Which tracks: **All tracks** · Channel type: **FLEX**",
        "   - **Start new project**: PÅ (nytt prosjekt, tempo hentes fra filen)",
        "   - **Realign events**: **AV** — ellers fjernes tom tid i starten og alt forskyves.",
        "   - **Create one channel per track** og **Set mixer tracks for new channels**: PÅ",
        "   - **Import time signatures**: PÅ · Import zero velocity notes: AV",
        "   - Trykk **Accept**.",
        f"3. Sjekk at tempoet øverst viser **{bpm:g}**. `File > Save as...` → `{project_name}.flp`.",
        "4. Resultat: én kanal per spor (Lead, Chords, Bass, Kick, Screech, Snare Roll …) med noter "
        "lagt i Playlist. Markørene (Intro, Breakdown, Drop …) vises øverst i Playlist.",
        "5. Alle kanaler starter som FLEX. Behold FLEX på Lead/Chords/Bass; bytt Kick/Snare/Screech til samples (steg 4).",
        "",
        "## 3. Legg inn vokalen",
    ]
    if files.get("vocals_arranged"):
        lines += [
            f"1. Dra `{files['vocals_arranged']}` fra filutforskeren inn i Playlist, på et ledig spor, **helt i starten av takt 1**.",
            "2. Den er allerede strukket til riktig tempo og plassert i seksjonene. Ikke slå på stretch i FL for denne.",
            "3. Høyreklikk lydklippet → hvis FL spør om tempo/stretch: velg **Resample/ingen endring**.",
            f"4. `arrangement/vocals_full_{int(bpm)}bpm_bar2.wav` = hele vokalen i nytt tempo, sangens takt 1 på **FL-takt 2**. Til egne vokal-chops.",
            "5. `midi/generated/lead_from_vocal_hook.mid` = vokalmelodien som lead. Vokal-transkripsjon er usikker — lytt og rett i Piano roll.",
        ]
    elif not arr.get("has_vocals"):
        lines += ["Ingen vokal ble funnet i låten (vokal-stemmen var stille), så det er ingen vokal å plassere."]
    else:
        lines += ["Vokalen er ikke plassert ennå. Kjør `separate-stems` og deretter `plan-arrangement` på nytt."]
    lines += [
        "",
        "## 4. Instrumenter (bruk det du har)",
        "| Kanal | Forslag (FL stock) | Merknad |",
        "|---|---|---|",
        "| Lead / Lead Harmony | FLEX (supersaw/hardstyle lead-preset) eller Sytrus | Lag 2–3 lag: hoved, oktav opp, bred supersaw |",
        "| Chords | FLEX supersaw-pad | Samme preset som lead gir en tett, samlet lyd |",
        "| Bass | FLEX / 3x Osc (sagtann) | Kun offbeat; sidechain mot kick |",
        f"| Kick | FPC eller Channel sampler med kick fra din pakke | Kick-halen bør være stemt i **{kick_note}** (grunntonen) |",
        "| Screech | Sampler med screech-sample fra din pakke, eller FLEX | Rawstyle-drop |",
        "| Snare Roll / Kick Roll | Channel sampler med snare/kick | Pitch automasjon opp i siste 2 takter |",
        "",
        "Sample-forslag fra ditt eget bibliotek: bygg inventaret med `hsp samples --roots <pakkemapper> --out <mappe>`, "
        "så søk med `--role kick --key <grunntone>`. Kun filer som faktisk finnes blir foreslått.",
        "",
        "## 5. Sjekk at alt stemmer",
        "- Spill fra takt 1: kicken skal treffe på hvert slag, og vokalen skal starte på en taktstrek.",
        "- Hvis vokalen ligger litt foran/bak: flytt lydklippet med **Alt + dra** (fri plassering) til det sitter.",
        "- Ingen lyd fra en kanal? Sjekk at den har et instrument, at mixer-insert ikke er mutet, og at Master ikke er mutet.",
    ]
    return "\n".join(lines) + "\n"


def production_notes(arr: dict, analysis: dict) -> str:
    key = arr["key"]
    tonic, mode = T.parse_key(key)
    kn = T.pc_name(tonic, T.uses_flats(tonic, mode))
    a = analysis
    unc = []
    if a["tempo"].get("confidence", 1) < 0.3:
        unc.append(f"Tempo-sikkerhet er lav ({a['tempo']['confidence']}). Alternativer: "
                   + ", ".join(str(c['bpm']) for c in a['tempo']['candidates'][:3]))
    if a["key"]["confidence"] < 0.05:
        unc.append(f"Toneart usikker: {a['key']['key']} vs {a['key']['alternatives'][0]['key']} "
                   f"(relativ: {a['key']['relative']}). Lytt på bassnoten i refrenget.")
    if a["downbeat"]["confidence"] < 0.1:
        unc.append("Taktstart (takt 1) er usikker — sjekk at vokal og kick sitter på grid.")
    low_ch = [c for c in a["chords_per_bar"] if c.get("confidence", 1) < 0.05]
    if low_ch:
        unc.append(f"{len(low_ch)} takter har usikker akkord (se chord_progression.json, felt 'alternative').")
    return "\n".join([
        f"# Produksjonsnotater — {key}, {arr['target_bpm']:g} BPM",
        "",
        "## Usikkerhet i analysen",
        *(f"- {u}" for u in unc), *(["- Ingen store usikkerheter flagget."] if not unc else []),
        "",
        "## Status på innstillinger",
        "- **Brukt og verifisert:** ingen innstillinger er satt i FL Studio automatisk ennå.",
        "- **Foreslått — du setter dem selv:** verdiene under er startpunkt.",
        "- **Krever lytting:** alt som er merket (lytt).",
        "",
        "## Mixing — startverdier (FL stock-plugins)",
        "| Hva | Plugin | Startverdi | |",
        "|---|---|---|---|",
        "| Gain staging | Fruity Balance / kanalvolum | Hver kanal topper rundt −6 til −10 dBFS før master | |",
        "| Kick | Parametric EQ 2 | Høypass 25–30 Hz; kick-halen stemt i " + kn + " | (lytt) |",
        "| Sidechain bass/lead/chords | Fruity Limiter (COMP-modus) med sidechain fra kick-insert | Ratio 4:1–8:1, attack 0–1 ms, release 80–150 ms, threshold til −4 til −8 dB GR | (lytt) |",
        "| Lead | Parametric EQ 2 | Høypass 150–250 Hz, evt. +2 dB rundt 3–5 kHz for presence | (lytt) |",
        "| Lead | Fruity Reeverb 2 (send) | Decay 2–4 s, pre-delay 20–40 ms, 100 % wet på send-kanal | (lytt) |",
        "| Lead | Fruity Delay 3 (send) | 1/4 eller 3/16 synket til tempo, feedback 20–35 % | (lytt) |",
        "| Chords | Fruity Stereo Shaper / Stereo Enhancer | Bredere enn lead, men mono under ca. 150 Hz | (lytt) |",
        "| Bass | Parametric EQ 2 | Lavpass rundt 2–4 kHz, kutt under 40 Hz | (lytt) |",
        "| Master | Fruity Limiter | Ceiling −0.3 dB, kun lett limiting for referanse | (lytt) |",
        "",
        "## Hardstyle-prinsipper brukt i MIDI-en",
        "- Lead: 8-takters frase — motiv (1–2), sekvens (3–4), gjentak (5–6), klimaks (7), oppløsning (8).",
        "- Sterke slag lander på akkordtoner; svake slag kan ha gjennomgangstoner fra skalaen.",
        "- Lead Harmony = diatonisk ters under, akkordtone på sterke slag.",
        "- Rawstyle-dropen bruker parallell moll (samme grunntone, mørkere skala) for kontrast.",
        "- Build-up: skarptromme-roll 1/4 → 1/8 → 1/16 → 1/32 med økende velocity, pause på siste slag.",
        "",
        "## Automasjon du må lage selv (forslag)",
        "- Build-up: høypassfilter på chords/lead fra ~100 Hz til ~1 kHz over hele build-upen.",
        "- Snare roll: pitch +12 semitoner de siste 2 taktene.",
        "- Riser/white noise: volum opp over build-up, kutt ved pre-drop pause.",
    ]) + "\n"
