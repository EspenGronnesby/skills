# Arkitektur — hardstyle-producer

## Verktøyvalg (vurdert november 2026)
| Behov | Valgt | Hvorfor | Forkastet / vurdert |
|---|---|---|---|
| Stems | Demucs htdemucs (htdemucs_ft for høy kvalitet) | Beste åpne kildekode-separasjon, fungerer på Mac/Win/CPU | Libretta (wrapper rundt samme stack, 3 commits, 1 stjerne) |
| Lyd → MIDI | Basic Pitch (ONNX, `--no-deps`) | Polyfon, modell følger med pakken, ingen TensorFlow | maystudios audio-to-midi (samme motor, men ingen opprensing) |
| Analyse | librosa + egen grid/akkord-logikk | Robust, kjent; egen logikk for hardstyle-problemer (offbeat-bass, pitchet kick) | Essentia (tung Windows-installasjon) |
| Tempo-strekk | Spotify Pedalboard (Rubber Band) | Høy kvalitet, pip-installerbar på alle OS | librosa time_stretch (dårligere lyd) |
| MIDI | mido (skriving/validering) | Full kontroll over tempo, markører, spor | music21 (unødvendig tungt), PyTheory (overlapper egen teori-modul) |
| FL-kontroll | MIDI-import + guide (verifiserbar) | Fungerer i alle FL-versjoner | FL Studio MCP: alpha, 0 stjerner, macOS-først; Windows kun delvis og utestet. Playlist kan ikke styres via FL sitt script-API |

## Dataflyt
```
source/ ─► separate-stems ─► stems/*.wav ─► analyze-song ─► analysis/song_analysis.json
                                   │                          (grid, toneart, akkorder, seksjoner, vokal)
                                   └► extract-midi ─► midi/original/*_faithful.mid
                                                  └► clean-midi ─► midi/cleaned/*.mid
analysis + request ─► plan-arrangement ─► arrangement/arrangement.{json,md,mid} + vocals_arranged_<bpm>bpm.wav
                                      └► prepare-fl-studio ─► fl-studio/*.md     └► preview ─► exports/preview_rough.*
```

## Viktige designvalg
- **Alt internt i beats** fra takt 1 (første downbeat). Bytte tempo = skrive samme beats med nytt tempo.
- **Fast grid**: tempo finjusteres med onset-kam (±1 %), taktstart velges blant 8 hypoteser (på slag / offbeat × 4)
  med akkordskifte-novelty + lavfrekvente onsets. Hindrer at offbeat-bass/hats lurer gridet.
- **Akkorder fra stems** (other + bass + ½ vokal) når de finnes — pitchede kicks ødelegger ellers bass-kroma.
- **Faithful vs cleaned**: faithful endres aldri utover tempo-mapping; cleaned rapporterer noter utenfor toneart i
  stedet for å «rette» dem.
- **Lekkasje-gate**: noter i takter der stemmen er >22 dB under sitt maks fjernes (Demucs-lekkasje).
- **Caching**: steg merkes ferdige med kildens hash; `--force` for å kjøre på nytt.
- **Backups**: alt som regenereres kopieres til `backups/<tidsstempel>/` først.

## Utvide
- Ny generator: legg en funksjon i `compose.py` som returnerer `list[Note]`, og en gren i `cli.cmd_generate`.
- Ny seksjonstype: legg til i `arrange.TEMPLATE` og i `render()`.
- FL Studio MCP senere: legg en `fl_mcp.py` som kun brukes når `diagnose` har bekreftet tilkobling, og logg hver
  demonstrert operasjon i `project.json` før den omtales som støttet.
