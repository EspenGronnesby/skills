# hardstyle-producer — hurtigstart

Gjør en sang (MP3/WAV) om til redigerbare hardstyle-filer for FL Studio: analyse, stems, MIDI (original + renset),
genererte leads/akkorder/bass/screech/build-ups, ferdig arrangement-MIDI med markører, vokal strukket til nytt tempo,
importguide og mixing-notater.

## Installer (én gang)
Pakk ut mappen til `~/.claude/skills/hardstyle-producer` og kjør:

- **Mac:** `bash ~/.claude/skills/hardstyle-producer/setup.sh`
- **Windows (PowerShell):** `& "$HOME\.claude\skills\hardstyle-producer\setup.ps1"`

Skriptet installerer kun i en egen `.venv` inne i skill-mappen (ingen systemendringer), kopierer slash-kommandoene
til `~/.claude/commands/` og kjører en selvtest. Krever Python 3.11/3.12 og ffmpeg. Første stem-separasjon
laster ned Demucs-modellen (~80 MB).

## Bruk i Claude Code
Si for eksempel: *«Gjør Rude.mp3 om til en 150 BPM euphoric hardstyle remix med melodisk første drop og rawstyle
andre drop»*, eller bruk kommandoene `/analyze-song`, `/plan-arrangement`, `/prepare-fl-studio` osv.

Direkte i terminal:
```
~/.claude/skills/hardstyle-producer/bin/hsp run ~/Music/Rude.mp3 -p ~/Music/Remixes/Rude \
  --request "150 BPM euphoric hardstyle remix, melodic first drop, aggressive rawstyle second drop"
```
Åpne så `fl-studio/fl_studio_import_guide.md` i prosjektmappen.

## Prosjektmappe
```
source/  stems/  analysis/  midi/{original,cleaned,generated}/  samples/  arrangement/  fl-studio/  exports/  backups/
```
