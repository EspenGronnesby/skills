# Espens skill-bibliotek

Mine egne skills for Claude. En skill er en mappe med en `SKILL.md`, en oppskrift Claude følger
når du ber om noe den dekker. Hver skill her er testet på ekte i en samtale og deretter
renskrevet, slik at neste gang går rett frem.

## Skills

| Skill | Hva den gjør | Krever |
|---|---|---|
| [tv-skjermsparer](tv-skjermsparer/SKILL.md) | Setter opp en Android/Google TV med egen skjermsparer: dine tema-bilder som video med sakte zoom og myke overganger, en mappe du redigerer og en «Oppdater TV»-knapp. Valgfritt: raskere TV og mindre reklame. | Mac, Android TV / Google TV, Claude koblet til datamaskinen |

## Bruk en skill

**I Claude-appen (claude.ai / desktop):**
1. Last ned skill-mappen (f.eks. `tv-skjermsparer/`) og pakk den som zip.
2. Gå til Innstillinger → Capabilities → Skills og last opp zip-filen.
3. Be Claude om oppgaven, f.eks. «sett opp skjermspareren på TV-en min».

**I Claude Code:**
```bash
git clone https://github.com/EspenGronnesby/skills.git
cp -r skills/tv-skjermsparer ~/.claude/skills/
```

## Legg til en ny skill

1. Kopier `_mal/` til en ny mappe med kort navn i kebab-case (f.eks. `faktura-oppsett/`).
2. Fyll ut `SKILL.md`: `name` (likt mappenavnet) og `description` (én setning om når den skal brukes).
3. Legg den til i tabellen over.
4. `git add . && git commit -m "Ny skill: <navn>" && git push`

Eller be Claude: «legg denne skillen til i skill-biblioteket mitt på GitHub».
