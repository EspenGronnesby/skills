---
name: tv-full-pakke
description: Hele TV-pakken i én runde: ryddet Android/Google TV, egen bildeskjermsparer, ny Apple TV-stil forside, SmartTube uten reklame, skjermdeling og angreknapper.
---

# TV full pakke

Mål: brukeren får hele oppsettet i én økt: en ryddet og raskere Android/Google TV, egen bildeskjermsparer med bevegelse, ny forside i Apple TV-stil med skjermdeling, YouTube uten reklame (SmartTube), og knapper på Macen for å endre og angre alt.

Denne skillen er en dirigent. Den kjører de andre skillene i riktig rekkefølge og samler spørsmålene:
- **tv-skjermsparer**: oppkobling, skjermsparer, bildemappe, valgfri lett rydding og reklameblokk.
- **tv-vibehack-forside**: CleanYourTV-forsiden, Wi-Fi-fellen, favoritter, bakgrunn, språk, ekstra knapper og angreknapper.

Les begge SKILL.md før du starter, og følg dem for detaljene. Spørsmålene i de to skillene erstattes av spørsmålene og standardene her. Er en av dem ikke installert, si fra og hent den fra github.com/EspenGronnesby/skills.

Krav: Mac, Android TV / Google TV (ikke Samsung eller LG), Claude koblet til Macen, TV og Mac på samme Wi-Fi. Det tar ca. 1–1,5 time, mest venting på videoer og bygging.

## Ordbruk overfor brukeren
Tekniske ord hører hjemme i kommandoer og kode, ikke i meldinger og spørsmål. Bruk samme ord i alle tre TV-skillene:

| Si | Ikke si |
|---|---|
| forside | launcher, home |
| favorittene (raden øverst) | dock |
| knapp | flis, tile |
| appene under favorittene | rutenett, grid |
| slå av, rydde vekk | debloat, deaktivere pakker |
| reklameblokk | DNS, AdGuard (navnet bare hvis de spør) |
| koblingen til TV-en | ADB, port 5555, videresending |
| Kilder | Inputs |
| skjermspareren | Aerial Views, dream |
| innstillingene for forsiden | tema-overlay, config.json |
| bygge forsiden på nytt | kompilere, gradle, APK |

Menynavn på TV-en (Utvikleralternativer, USB-feilsøking) skrives som de står på skjermen.

## Mapper: én mappe per TV
Første spørsmål avgjør hvor alt havner, så flere TV-er kan styres fra samme Mac uten å skrive over hverandre. Reglene her overstyrer stiene i de to andre skillene.

| | Min egen | Noen andre (`<Navn>`) |
|---|---|---|
| Mapper brukeren ser | `~/Desktop/Privat/TV-skjermsparer`, `TV-forside` og `TV-oppsett` | `~/Desktop/Privat/TV-er/<Navn>/` med `Skjermsparer`, `Forside` og `Angre` |
| Verktøyfiler (videoer, lister, backup) | som i de andre skillene | `~/tv-verktoy/<navn>/` |
| Forside-kode | `~/Desktop/Utvikling/tv-vibehack` | kopi: `~/Desktop/Utvikling/tv-vibehack-<navn>` |

Finnes ikke `Privat/`, bruk `~/Desktop/` i stedet.

- Finnes mappen fra før, spør: «Samme TV som sist?» med **Ja, oppdater** / **Nei, ny TV**. Ny TV får `-2` bak navnet.
- Lag `TV-info.txt` i personens mappe: navn, modell, IP, Wi-Fi-navn (aldri passord), dato og hva som ble gjort.
- `fwd.py` og `lag_video.py` deles, og `fwd.py` tar TV-IP som argument. Port 5556 peker på én TV om gangen, så hver knapp starter med `pkill -f fwd.py` og starter den på nytt med sin egen TV-IP. Aldri `pgrep … ||`, for da kan knappen koble seg til forrige TV.
- IP-en kan endre seg. Svarer ikke TV-en, skann nettet og sammenlign `ro.serialno` med TV-info.txt.
- Forside-kopi: `rsync -a --exclude build --exclude .gradle tv-vibehack/ tv-vibehack-<navn>/`, og endre `config.xml` der. De ekstra appene (Skjermsparer, Bytt bakgrunn) installeres som de er.
- Ryddingen lagrer før-tilstanden i `~/.cleanyourtv/recovery-<IP>-<liste>.json`. To TV-er på ulike nett kan ha samme IP. Flytt derfor en eksisterende fil med samme IP til `~/tv-verktoy/<eier>/` før du rydder, og kopier den nye til `~/tv-verktoy/<navn>/` etterpå. Angre alt legger riktig fil tilbake før `restore.sh`.
- Si til eieren av TV-en: knappene virker bare når Macen er på samme Wi-Fi som TV-en, altså hjemme hos dem. «Tillat alltid» betyr at denne Macen kan koble til TV-en senere på det nettet. Det kan trekkes tilbake ved å slå av USB-feilsøking.

## 0. Spørsmålene: still dem ORDRETT, hver gang
Alle brukere skal få de samme, korte spørsmålene. Bruk AskUserQuestion med nøyaktig denne teksten. Format per alternativ: **label** — beskrivelse (beskrivelsen legges i `description`; uten tankestrek = ingen beskrivelse). Ikke legg til, fjern eller omformuler. «Other» (skriv selv) kommer automatisk. Hopp bare over spørsmål som er merket betinget.

### Runde 1 (ett AskUserQuestion-kall)
**Spørsmål 1**: «Hvem sin TV er det? Skriv navnet hvis det er noen andre.», header «Hvem», ett valg:
- **Min egen**
- **Noen andre**

Navn skrevet i «Other» = mappenavnet. «Noen andre» uten navn: spør «Hva heter personen?» i chatten. Se «Mapper» over.

**Spørsmål 2**: «Hvilken TV er det?», header «TV», ett valg:
- **TCL, Sony, Philips, Xiaomi, Hisense**
- **Chromecast eller Shield**
- **Samsung eller LG** — støttes ikke
- **Vet ikke**

Samsung eller LG: si at bare reklameblokk er mulig, tilby det, og stopp resten. Vet ikke: les modellen når TV-en er koblet til.

**Spørsmål 3**: «Hva vil du ha?», header «Pakke», flere valg (anbefal alle):
- **Fjern reklame** — raskere TV
- **Egen skjermsparer** — dine bilder
- **Ny forside** — med skjermdeling
- **YouTube uten reklame**

### Runde 2: Wi-Fi (betinget, bare ved «Ny forside»)
**Spørsmål**: «Wi-Fi må lagres på nytt for ny forside. Hvordan?», header «Wi-Fi»:
- **Gi passordet** — lagres ikke
- **Gjør det selv**
- **Dropp ny forside**

Still det bare når setupwraith faktisk eier nettet (tv-vibehack-forside steg 4). Be om passordet i chatten etterpå. «Gjør det selv»: forklar Innstillinger → Nettverk → nettet → Glem, og koble til igjen.

### Runde 3: skjermsparer (betinget, bare hvis valgt)
**Spørsmål**: «Tema på skjermspareren?», header «Tema», flere valg:
- **Natur**
- **Biler**
- **Ekstremsport**
- **Egne bilder**

«Other» = eget tema. Ukjente navn: søk én gang, ellers spør om lenke. Egne bilder: si hvor mappen ligger når den er laget.

### Runde 4: forside (betinget, bare hvis valgt)
Hent først installerte apper (`pm list packages -3` + kjente systemapper som Netflix og YouTube) og bruk de 4 vanligste streamingappene som alternativer.

**Spørsmål 1**: «Mest brukte apper? Velg 3–4.», header «Favoritter», flere valg: de 4 appene (navn som på TV-en). 3 valgt = 3 store favoritter, 4 = 4. Appene under favorittene står alltid 4 per rad.

**Spørsmål 2**: «Bakgrunn på forsiden?», header «Bakgrunn», flere valg:
- **Bilde**
- **Dag/natt** — følger klokka
- **Bytt bakgrunn-knapp**
- **Svart**

**Spørsmål 3**: «Språk og klokke?», header «Språk»:
- **Norsk, 15:00**
- **Norsk, 03:00**
- **TV-ens språk, 15:00**
- **TV-ens språk, 03:00**

Klokka: `adb shell settings put system time_12_24 24` (15:00) eller `12` (03:00, forsiden viser da 3:00 med PM ved siden av). Det gjelder hele TV-en, så nevn det i planen. Norsk: tv-vibehack-forside 5c. Bilde = fra skjermsparer-temaet, gjort mørkt.

**Spørsmål 4**: «Hvor skal de ekstra knappene stå?», header «Knapper»:
- **Under favorittene** — anbefalt
- **Blant favorittene**

Ekstra knapper = Skjermsparer, YouTube uten reklame og Bytt bakgrunn (bare de som er valgt).

### Faste standarder (spør ikke om disse)
- **Behold alltid:** stemmesøk/Assistant, Chromecast, AirPlay, Miracast, firmware-oppdateringer, mobil-fjernkontroll og USB-avspilling.
- **Skjermsparer:** 7 sek per bilde + 2 sek overgang, starter etter **5 minutter** (`screen_off_timeout 300000`).
- **Fargeskjær:** tilpasses automatisk til logoene. Etter at favorittene er satt, ta skjermbilde mens du står på hver favoritt. Gir to av dem nesten samme farge (f.eks. Netflix og YouTube, begge røde), behold den med sterkest merkevarefarge og gi den andre et svart skjær (tv-vibehack-forside 5d). Ellers overstyres ingenting.
- **Under favorittene:** 4 apper per rad.
- **Reklameblokk:** AdGuard DNS og animasjoner 0.5 når «Fjern reklame» er valgt.
- **Skjermdeling:** følger med «Ny forside» (rad i Kilder).

### Plan før start
Vis et kort sammendrag av svarene og standardene, for eksempel: «Kari (TV-er/Kari) · TCL · reklame fjernet · skjermsparer: biler og ekstremsport, starter etter 5 min · ny forside på norsk, 15:00: Stremio, Netflix, YouTube (3 store) · bilde + dag/natt + Bytt bakgrunn-knapp · YouTube uten reklame · ca. 1–1,5 time». Si samtidig ærlig fra om det som ikke går: Googles «Sponsored»-felt forsvinner bare med ny forside, YouTube-reklame forsvinner bare i SmartTube (vanlig YouTube beholder reklamen), og veldig spesifikke bildeønsker finnes sjelden med fri lisens. Start så uten flere spørsmål.

## 1. Rekkefølge
Lag en TaskCreate-liste med stegene for det som er valgt, og huk av underveis. Bruk vanlige ord i oppgavenavnene (f.eks. «Koble til TV-en», «Rydde vekk reklame», «Lage skjermsparer»).
1. **Oppkobling**: tv-skjermsparer steg 1–3 (verktøy, utviklermodus på build-linjen, finn TV-en, fwd.py, én ren godkjenning). Les modellen her hvis de svarte «Vet ikke».
2. **Backup**: tv-vibehack-forside steg 2.
3. **Rydding og reklameblokk**: med ny forside, bruk CleanYourTV-listen (tv-vibehack-forside steg 3) og legg AdGuard DNS og animasjoner fra tv-skjermsparer steg 6 oppå. Uten ny forside, bruk tv-skjermsparer steg 6. Ikke kjør begge på de samme pakkene.
4. **Skjermsparer**: tv-skjermsparer steg 4–5 med standardene over (Aerial Views, alle fire nettkilder AV, bilder fra Wikimedia med kontaktark-sjekk, mappe, videoer i 4x, Oppdater TV-knapp).
5. **Wi-Fi og forside**: Wi-Fi-spørsmålet om nødvendig, deretter tv-vibehack-forside steg 4–5 (5a ved 3 favoritter, 5b, 5c ved norsk, 5d etter fargeregelen), og klokkevalget.
6. **Ekstra apper og knapper**: tv-vibehack-forside steg 6 (Skjermsparer-knapp hvis skjermsparer er valgt, Skjermdeling alltid med ny forside, Bytt bakgrunn-knapp hvis valgt) og SmartTube (steg 2 under).
7. **Tema-mappe**: tv-vibehack-forside steg 7, med bakgrunner fra skjermsparer-temaet.
8. **Angreknapper**: tv-vibehack-forside steg 8, med alle installerte apper i Angre alt.
9. **Omstart og sluttsjekk** (steg 3 under).

Etter hvert synlige steg: skjermbilde fra TV-en, og test med fjernkontroll-kommandoer. Video i skjermspareren vises svart i skjermbilder, så spør brukeren: «Hva ser du på TV-en?» med **Bilder som glir** / **Det hakker** / **Natur** / **Svart**.

## 2. SmartTube (YouTube uten reklame)
Reklamen i vanlig YouTube kommer fra de samme serverne som videoene, så reklameblokken hjelper ikke. SmartTube (github.com/yuliskov/SmartTube) er en gratis YouTube-app for Android TV med åpen kildekode, uten reklame og med SponsorBlock. Si nøytralt at den bryter YouTubes vilkår, at Premium er den offisielle veien, og at den kan slutte å virke en periode når YouTube endrer noe.
```zsh
ABI=$(adb shell getprop ro.product.cpu.abi | tr -d '\r')   # TCL G10 svarer armeabi-v7a selv om brikken er 64-bit
case $ABI in arm64*) F=arm64-v8a;; x86*) F=x86;; *) F=armeabi-v7a;; esac
URL=$(curl -sL https://api.github.com/repos/yuliskov/SmartTube/releases/latest | python3 -c "import json,sys;print([a['browser_download_url'] for a in json.load(sys.stdin)['assets'] if a['name'].endswith('_$F.apk')][0])")
curl -sL -o smarttube.apk "$URL" && adb install -r smarttube.apk     # pakke: org.smarttube.stable
```
Legg `org.smarttube.stable` i `grid_first_apps` (eller `dock_apps`) etter svaret på runde 4 spørsmål 4, bygg forsiden på nytt, åpne appen og ta skjermbilde. Innlogging gjør brukeren selv: person-ikonet øverst til venstre → legg til konto → kode på yt.be/activate. Vanlig YouTube blir liggende. Legg `pm uninstall org.smarttube.stable` til i Angre alt.

## 3. Sluttsjekk og overlevering
- Omstart via bakgrunnsjobb (`adb reboot` henger via fwd.py). Koble til igjen, og sjekk HOME, `screensaver_components`, `screen_off_timeout` (300000), `time_12_24`, `private_dns_specifier`, deaktiverte pakker og at temaet ligger der.
- Koblingen til TV-en: forklar at knappene på Macen slutter å virke hvis USB-feilsøking slås av, og la brukeren velge.
- Kort sluttmelding: hva som er på TV-en nå, mappene på Macen (Skjermsparer med Oppdater TV, Forside med Bruk tema, og angreknappene; stier etter «Mapper»), innlogging i SmartTube, og hva som ikke ble testet eller ikke gikk.
