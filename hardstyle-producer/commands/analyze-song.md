---
description: Analyser en sang (BPM, toneart, akkorder, struktur, vokal)
argument-hint: <prosjektmappe> [valg]
---
Bruk skillen **hardstyle-producer**. Kjør:

`~/.claude/skills/hardstyle-producer/bin/hsp analyze-song -p $ARGUMENTS`

(Windows: `& "$HOME\.claude\skills\hardstyle-producer\bin\hsp.ps1" analyze-song -p $ARGUMENTS`)

Svar på norsk, kort og konkret. Rapporter BPM (med halv/dobbel), toneart med konfidens og relativ toneart, akkordløkke, seksjoner, vokalområder og alt med lav konfidens.
Påstå aldri at FL Studio er endret — skillen lager filer og instruksjoner.
