---
name: tv-full-pakke
description: Hele TV-pakken i én runde: ryddet Android/Google TV, egen bildeskjermsparer, ny Apple TV-stil forside, SmartTube uten reklame, skjermdeling og angreknapper.
---

# TV full pakke

Mål: brukeren får hele oppsettet i én økt: en ryddet og raskere Android/Google TV, egen bildeskjermsparer med bevegelse, ny forside i Apple TV-stil med skjermdeling, YouTube uten reklame (SmartTube), og knapper på Macen for å endre og angre alt.

Denne skillen er en dirigent. Den kjører de andre skillene i riktig rekkefølge og samler spørsmålene:
- **tv-skjermsparer**: oppkobling, skjermsparer, bildemappe, valgfri lett rydding og AdGuard DNS.
- **tv-vibehack-forside**: CleanYourTV-forsiden, Wi-Fi-fellen, favoritter, bakgrunn, språk, fliser og angreknapper.

Les begge SKILL.md før du starter, og følg dem for detaljene. Spørsmålene i de to skillene erstattes av spørsmålene og standardene her. Er en av dem ikke installert, si fra og hent den fra github.com/EspenGronnesby/skills.

Krav: Mac, Android TV / Google TV (ikke Samsung eller LG), Claude koblet til Macen, TV og Mac på samme Wi-Fi. Det tar ca. 1–1,5 time, mest venting på videoer og bygging.

## 0. Spørsmålene: still dem ORDRETT, hver gang
Alle brukere skal få de samme spørsmålene. Bruk AskUserQuestion med nøyaktig denne teksten, disse alternativene og denne rekkefølgen. Ikke legg til, fjern eller omformuler. «Other» (skriv selv) kommer automatisk. Hopp bare over spørsmål som er merket betinget.

### Runde 1 (ett AskUserQuestion-kall)
**Spørsmål 1**: «Hvilken TV har du?», header «TV», ett valg:
- «TCL, Sony, Philips, Xiaomi eller Hisense» (Google TV eller Android TV)
- «Chromecast, Google TV Streamer eller Shield»
- «Samsung eller LG» (støttes ikke)
- «Vet ikke» (jeg finner modellen når TV-en er koblet til)

Svarer de Samsung eller LG: si at bare reklameblokk via DNS er mulig, tilby det, og stopp resten.

**Spørsmål 2**: «Hva vil du ha på TV-en?», header «Pakke», flere valg (anbefal alle):
- «Rydde vekk reklame» (slår av reklame- og sporingstjenester, blokkerer reklame-servere, raskere TV)
- «Egne bilder på skjermsparer» (bilder med sakte zoom og myke overganger)
- «Ny forside i Apple TV-stil» (med bakgrunnsbilde og skjermdeling fra PC og telefon)
- «YouTube uten reklame» (SmartTube)

### Runde 2: Wi-Fi (betinget, bare hvis «Ny forside» er valgt)
**Spørsmål**: «For den nye forsiden må Wi-Fi-nettet lagres på nytt på TV-en. Hvordan vil du gjøre det?», header «Wi-Fi»:
- «Jeg gir deg passordet» (be om det i chatten etterpå; det lagres aldri)
- «Jeg kobler til på nytt på TV-en selv»
- «Dropp ny forside»

Still dette først når du har sjekket at setupwraith faktisk eier nettet (tv-vibehack-forside steg 4). Gjør den ikke det, hopp over spørsmålet.

### Runde 3: skjermsparer (betinget, bare hvis valgt)
**Spørsmål**: «Hvilket tema vil du ha på skjermspareren?», header «Tema», flere valg:
- «Natur»
- «Biler»
- «Ekstremsport»
- «Egne bilder» (de legger dem i mappen selv)

«Other» er for eget tema (skriv inn). Ukjente navn: søk én gang, og spør ellers om lenke.

### Runde 4: forside (betinget, bare hvis valgt)
Hent først installerte apper (`pm list packages -3` + kjente systemapper som Netflix og YouTube) og velg de 4 mest vanlige streamingappene som alternativer.

**Spørsmål 1**: «Hvilke apper bruker du mest? Velg 3 eller 4.», header «Favoritter», flere valg: de 4 appene (navn som på TV-en). «Other» for andre apper. 3 valgt gir 3 store favoritter, 4 gir 4. Rutenettet under har alltid 4 per rad.

**Spørsmål 2**: «Hva vil du ha som bakgrunn på forsiden?», header «Bakgrunn», flere valg:
- «Bilde fra skjermspareren» (mørkt, så teksten synes)
- «Dag/natt-himmel» (farge som følger klokka)
- «Bytt bakgrunn-flis på TV-en» (velg bakgrunn med fjernkontrollen)
- «Helt svart»

**Spørsmål 3**: «Hvilket språk og hvilken klokke skal forsiden ha?», header «Språk»:
- «Norsk, klokka viser 15:00» (24-timers)
- «Norsk, klokka viser 03:00» (12-timers)
- «Samme som TV-en, klokka viser 15:00» (24-timers)
- «Samme som TV-en, klokka viser 03:00» (12-timers)

Klokka: `adb shell settings put system time_12_24 24` (15:00) eller `12` (03:00, forsiden viser da 3:00 med PM ved siden av). Forsidens klokke og skjermspareren følger systemvalget. Det gjelder hele TV-en, så nevn det i planen. Norsk: tv-vibehack-forside 5c.

**Spørsmål 4**: «Hvor skal de ekstra flisene stå (Skjermsparer, YouTube uten reklame, Bytt bakgrunn)?», header «Fliser»:
- «Først i rutenettet under favorittene» (anbefalt)
- «Oppe blant favorittene»

### Faste standarder (spør ikke om disse)
- **Behold alltid:** stemmesøk/Assistant, Chromecast, AirPlay, Miracast, firmware-oppdateringer, mobil-fjernkontroll og USB-avspilling.
- **Skjermsparer:** 7 sek per bilde + 2 sek overgang, starter etter **5 minutter** (`screen_off_timeout 300000`).
- **Fargeskjær:** tilpasses automatisk til logoene. Etter at favorittene er satt, ta skjermbilde mens du står på hver favoritt. Gir to av dem nesten samme farge (f.eks. Netflix og YouTube, begge røde), behold den med sterkest merkevarefarge og gi den andre et svart skjær (tv-vibehack-forside 5d). Ellers overstyres ingenting.
- **Rutenett:** 4 apper per rad under favorittene.
- **Reklameblokk:** AdGuard DNS og animasjoner 0.5 når «Rydde vekk reklame» er valgt.
- **Skjermdeling:** følger med «Ny forside» (rad i Kilder).

### Plan før start
Vis et kort sammendrag av svarene og standardene, for eksempel: «TCL · rydding + reklameblokk · skjermsparer: biler og ekstremsport, starter etter 5 min · ny forside på norsk, klokka viser 15:00: Stremio, Netflix, YouTube (3 store) · bildebakgrunn + dag/natt + Bytt bakgrunn-flis · YouTube uten reklame · ca. 1–1,5 time». Si samtidig ærlig fra om det som ikke går: Googles «Sponsored»-felt forsvinner bare med ny forside, YouTube-reklame forsvinner bare i SmartTube (vanlig YouTube beholder reklamen), og veldig spesifikke bildeønsker finnes sjelden med fri lisens. Start så uten flere spørsmål.

## 1. Rekkefølge
Lag en TaskCreate-liste med stegene for det som er valgt, og huk av underveis.
1. **Oppkobling**: tv-skjermsparer steg 1–3 (verktøy, utviklermodus på build-linjen, finn TV-en, fwd.py, én ren godkjenning). Les modellen her hvis de svarte «Vet ikke».
2. **Backup**: tv-vibehack-forside steg 2.
3. **Rydding og reklameblokk**: med ny forside, bruk CleanYourTV-listen (tv-vibehack-forside steg 3) og legg AdGuard DNS og animasjoner fra tv-skjermsparer steg 6 oppå. Uten ny forside, bruk tv-skjermsparer steg 6. Ikke kjør begge på de samme pakkene.
4. **Skjermsparer**: tv-skjermsparer steg 4–5 med standardene over (Aerial Views, alle fire nettkilder AV, bilder fra Wikimedia med kontaktark-sjekk, mappe, videoer i 4x, Oppdater TV-knapp).
5. **Wi-Fi og forside**: Wi-Fi-spørsmålet om nødvendig, deretter tv-vibehack-forside steg 4–5 (5a ved 3 favoritter, 5b, 5c ved norsk, 5d etter fargeregelen), og klokkevalget.
6. **Ekstra apper og fliser**: tv-vibehack-forside steg 6 (Skjermsparer-flis hvis skjermsparer er valgt, Skjermdeling alltid med ny forside, Bytt bakgrunn hvis valgt) og SmartTube (steg 2 under).
7. **Tema-mappe**: tv-vibehack-forside steg 7, med bakgrunner fra skjermsparer-temaet.
8. **Angreknapper**: tv-vibehack-forside steg 8, med alle installerte apper i Angre alt.
9. **Omstart og sluttsjekk** (steg 3 under).

Etter hvert synlige steg: skjermbilde fra TV-en, og test med fjernkontroll-kommandoer. Video i skjermspareren vises svart i skjermbilder, så spør brukeren hva de ser (AskUserQuestion: «Bilder som beveger seg og glir over» / «Det hakker» / «Natur eller annet» / «Svart skjerm»).

## 2. SmartTube (YouTube uten reklame)
Reklamen i vanlig YouTube kommer fra de samme serverne som videoene, så DNS-blokkering hjelper ikke. SmartTube (github.com/yuliskov/SmartTube) er en gratis YouTube-app for Android TV med åpen kildekode, uten reklame og med SponsorBlock. Si nøytralt at den bryter YouTubes vilkår, at Premium er den offisielle veien, og at den kan slutte å virke en periode når YouTube endrer noe.
```zsh
ABI=$(adb shell getprop ro.product.cpu.abi | tr -d '\r')   # TCL G10 svarer armeabi-v7a selv om brikken er 64-bit
case $ABI in arm64*) F=arm64-v8a;; x86*) F=x86;; *) F=armeabi-v7a;; esac
URL=$(curl -sL https://api.github.com/repos/yuliskov/SmartTube/releases/latest | python3 -c "import json,sys;print([a['browser_download_url'] for a in json.load(sys.stdin)['assets'] if a['name'].endswith('_$F.apk')][0])")
curl -sL -o smarttube.apk "$URL" && adb install -r smarttube.apk     # pakke: org.smarttube.stable
```
Legg `org.smarttube.stable` i `grid_first_apps` (eller `dock_apps`) etter svaret på runde 4 spørsmål 4, bygg forsiden på nytt, åpne appen og ta skjermbilde. Innlogging gjør brukeren selv: person-ikonet øverst til venstre → legg til konto → kode på yt.be/activate. Vanlig YouTube blir liggende. Legg `pm uninstall org.smarttube.stable` til i Angre alt.

## 3. Sluttsjekk og overlevering
- Omstart via bakgrunnsjobb (`adb reboot` henger via fwd.py). Koble til igjen, og sjekk HOME, `screensaver_components`, `screen_off_timeout` (300000), `time_12_24`, `private_dns_specifier`, deaktiverte pakker og at temaet ligger der.
- ADB: forklar at knappene slutter å virke hvis det slås av, og la brukeren velge.
- Kort sluttmelding: hva som er på TV-en nå, de tre mappene på Macen (**TV-skjermsparer** med Oppdater TV, **TV-forside** med Bruk tema, **TV-oppsett** med angreknappene), innlogging i SmartTube, og hva som ikke ble testet eller ikke gikk.
