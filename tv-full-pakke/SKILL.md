---
name: tv-full-pakke
description: Hele TV-pakken i én runde: ryddet Android/Google TV, egen bildeskjermsparer, ny Apple TV-stil forside, SmartTube uten reklame, skjermdeling og angreknapper.
---

# TV full pakke

Mål: brukeren får hele oppsettet i én økt, tilpasset egne valg: en ryddet og raskere Android/Google TV, egen bildeskjermsparer med bevegelse, ny forside i Apple TV-stil, YouTube uten reklame (SmartTube), skjermdeling fra PC og telefon, og knapper på Macen for å endre og angre alt.

Denne skillen er en dirigent. Den gjør ingenting på egen hånd, men kjører de andre skillene i riktig rekkefølge og samler spørsmålene:
- **tv-skjermsparer**: oppkobling, skjermsparer, bildemappe, valgfri lett rydding og AdGuard DNS.
- **tv-vibehack-forside**: CleanYourTV-forsiden, Wi-Fi-fellen, favoritter, bakgrunn, språk, fliser og angreknapper.

Les begge SKILL.md før du starter, og følg dem for detaljene. Er en av dem ikke installert, si fra og hent den fra github.com/EspenGronnesby/skills.

Krav: Mac, Android TV / Google TV (ikke Samsung eller LG), Claude koblet til Macen, TV og Mac på samme Wi-Fi. Det tar ca. 1–1,5 time, mest venting på videoer og bygging.

## 0. Alle spørsmål først (tre runder AskUserQuestion)
Brukeren skal ikke måtte svare underveis. Ta alt her, og skriv svarene i en kort plan du viser før du starter. Det i parentes er hva testbrukeren valgte, ikke standard.

**Runde 1, TV og pakke**
1. TV-merke/modell. Stopp på Samsung/LG og tilby bare AdGuard DNS.
2. Hvilke deler de vil ha (multiSelect, alt avkrysset som forslag): rydding og reklameblokk, bildeskjermsparer, ny forside, SmartTube, skjermdeling.
3. Hva som skal beholdes: stemme, Chromecast, AirPlay, Miracast, firmware-oppdateringer, mobil-fjernkontroll, USB-avspilling. (Alt.)
4. Wi-Fi-passord. Trengs for ny forside på Google TV, se tv-vibehack-forside steg 4.

**Runde 2, skjermsparer** (hvis valgt)
1. Tema for bildene, og om de har egne bilder. (Biler, drift, ekstremsport.)
2. Tempo per bilde. (7 sek + 2 sek overgang.)
3. Når den starter. (5 min. 1 min virker også når APP_AUTO_START er satt.)

**Runde 3, forside** (hvis valgt)
1. Favoritter og antall (3 store eller 4), og rutenett under (4–6). (Stremio, Netflix, YouTube; 3 over 4.)
2. Bakgrunn: svart, farge, bilde, dag/natt-himmel, og om de vil ha Bytt bakgrunn-flis. (Bilde + himmel + flis.)
3. Språk på forsiden, og fargeskjær per app. (Norsk; YouTube svart.)
4. Ekstra fliser (Skjermsparer, SmartTube, Bytt bakgrunn) i favorittbåndet eller først i rutenettet. (Først i rutenettet: Bakgrunn, Skjermsparer, SmartTube.)

Si ærlig fra om det som ikke går: Googles «Sponsored»-felt forsvinner bare med ny forside, YouTube-reklame forsvinner bare i SmartTube (ikke i vanlig YouTube), og smale bildeønsker (en bestemt ombygd bil, en Instagram-konto) finnes sjelden med fri lisens.

## 1. Rekkefølge
Lag en TaskCreate-liste med disse stegene og huk av underveis.
1. **Oppkobling**: tv-skjermsparer steg 1–3 (verktøy, utviklermodus på build-linjen, finn TV-en, fwd.py, én ren godkjenning).
2. **Backup**: tv-vibehack-forside steg 2.
3. **Rydding og reklameblokk**: kjør enten tv-vibehack-forside steg 3 (CleanYourTV-listen for modellen, med opptak for restore) eller tv-skjermsparer steg 6, ikke begge på de samme pakkene. Med ny forside: bruk CleanYourTV-listen og legg AdGuard DNS og animasjoner 0.5 fra tv-skjermsparer steg 6 oppå.
4. **Skjermsparer**: tv-skjermsparer steg 4–5 (Aerial Views, alle fire nettkilder AV, bilder fra Wikimedia med kontaktark-sjekk, mappe, videoer i 4x, Oppdater TV-knapp, timeout).
5. **Wi-Fi og forside**: tv-vibehack-forside steg 4–5 (lagre nettet på nytt, setupwraith, forside, og 5a–5d etter svarene).
6. **Ekstra apper og fliser**: tv-vibehack-forside steg 6 (Skjermsparer-flis, Skjermdeling, Bytt bakgrunn) og SmartTube (steg 2 under).
7. **Tema-mappe**: tv-vibehack-forside steg 7.
8. **Angreknapper**: tv-vibehack-forside steg 8, med alle installerte apper i Angre alt.
9. **Omstart og sluttsjekk** (steg 3 under).

Etter hvert synlige steg: skjermbilde fra TV-en, og test med fjernkontroll-kommandoer. Video i skjermspareren vises svart i skjermbilder, så spør brukeren hva de ser.

## 2. SmartTube (YouTube uten reklame)
Reklamen i vanlig YouTube kommer fra de samme serverne som videoene, så DNS-blokkering hjelper ikke. SmartTube (github.com/yuliskov/SmartTube) er en gratis YouTube-app for Android TV med åpen kildekode, uten reklame og med SponsorBlock. Si nøytralt at den bryter YouTubes vilkår, at Premium er den offisielle veien, og at den kan slutte å virke en periode når YouTube endrer noe.
```zsh
ABI=$(adb shell getprop ro.product.cpu.abi | tr -d '\r')   # TCL G10 svarer armeabi-v7a selv om brikken er 64-bit
case $ABI in arm64*) F=arm64-v8a;; x86*) F=x86;; *) F=armeabi-v7a;; esac
URL=$(curl -sL https://api.github.com/repos/yuliskov/SmartTube/releases/latest | python3 -c "import json,sys;print([a['browser_download_url'] for a in json.load(sys.stdin)['assets'] if a['name'].endswith('_$F.apk')][0])")
curl -sL -o smarttube.apk "$URL" && adb install -r smarttube.apk     # pakke: org.smarttube.stable
```
Legg `org.smarttube.stable` i `grid_first_apps` eller `dock_apps` etter svaret, bygg forsiden på nytt, åpne appen og ta skjermbilde. Innlogging gjør brukeren selv: person-ikonet øverst til venstre → legg til konto → kode på yt.be/activate. Vanlig YouTube blir liggende. Legg `pm uninstall org.smarttube.stable` til i Angre alt.

## 3. Sluttsjekk og overlevering
- Omstart via bakgrunnsjobb (`adb reboot` henger via fwd.py). Koble til igjen, og sjekk HOME, `screensaver_components`, `screen_off_timeout`, `private_dns_specifier`, deaktiverte pakker og at temaet ligger der.
- ADB: forklar at knappene slutter å virke hvis det slås av, og la brukeren velge.
- Kort sluttmelding: hva som er på TV-en nå, de tre mappene på Macen (**TV-skjermsparer** med Oppdater TV, **TV-forside** med Bruk tema, **TV-oppsett** med angreknappene), innlogging i SmartTube, og hva som ikke ble testet eller ikke gikk.
