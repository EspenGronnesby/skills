---
name: tv-vibehack-forside
description: Bytter Google TV-forsiden med CleanYourTV (tv-vibehack) i Apple TV-stil, tilpasset brukerens valg: favoritter, rutenett, bakgrunn med velger på TV-en, språk, farger, skjermsparer- og skjermdelingsknapper, angreknapper.
---

# Ny TV-forside med CleanYourTV (tv-vibehack)

Mål: brukerens Android/Google TV får en ren forside i Apple TV-stil (github.com/Gathin23/cleanyourtv, før kalt tv-vibehack), **bygget etter brukerens egne valg**. Alt utover selve forsiden er valgfritt. Ingenting avinstalleres, og alt kan angres med knapper på Macen.

Forutsetning: TV-en er koblet til Macen via ADB. Hvis ikke, gjør steg 1–3 i skillen **tv-skjermsparer** først (verktøy, utviklermodus, finne TV-en, videresending rundt macOS-sperren og godkjenning). Vil brukeren ha egen bildeskjermsparer, gjør hele den skillen først.

Arbeid i et skall på Macen (Desktop Commander `start_process` eller device_bash). Snakk enkelt norsk. Les koden i repoet før du kjører den. Verifiser hver synlig endring med skjermbilde fra TV-en (`adb exec-out screencap -p`) og test pilnavigasjonen etter layout-endringer.

## 0. Spør først: bygg det de vil ha, ikke en kopi av testoppsettet

Bruk AskUserQuestion i to runder (maks 4 spørsmål per runde). Forklar kort hva hvert valg betyr. Det som står i parentes er hva testbrukeren valgte, ikke en fasit. Gjør bare det de svarer ja til.

**Runde 1, grunnoppsett**
1. **Favoritter:** hvilke apper øverst (list de installerte streamingappene), og om det skal være **3 store** eller **4** i favorittbåndet. (Testbruker: Stremio, Netflix, YouTube; 3 store.)
2. **Rutenett under:** 4, 5 eller 6 apper per rad. (4.)
3. **Språk på forsiden:** følg TV-ens språk, eller lås forsiden til et bestemt språk (f.eks. norsk) uten å endre resten av TV-en. (Norsk.)
4. **Behold på TV-en:** stemmeassistent, Chromecast, AirPlay, Miracast, firmware-oppdateringer, mobil-fjernkontroll, USB-avspilling (multiSelect, standard alt). Pluss Wi-Fi-passordet, som nesten alltid trengs på Google TV (steg 4).

**Runde 2, utseende og ekstra (multiSelect der det passer)**
1. **Bakgrunn:** helt svart / fast farge / bilde (egne bilder eller tema som biler, natur, rom) / dag-natt-himmel som følger klokka. Flere kan kombineres. (Bilde + himmel 55.)
2. **Bytt bakgrunn-flis på TV-en:** en flis under favorittene som åpner en bildevelger, så bakgrunnen kan byttes med fjernkontrollen. (Ja.)
3. **Fargeskjær:** forsiden lager et skjær fra logoen til appen du står på. Behold automatisk, eller overstyr per app (f.eks. svart, ingen, på YouTube så den ikke ligner Netflix). (YouTube svart.)
4. **Ekstra fliser og rader:** Skjermsparer-flis (krever skillen tv-skjermsparer), Skjermdeling-rad i Kilder/Inputs (AirPlay, Miracast, Chromecast forklart), og om de ekstra flisene skal stå i favorittbåndet eller først i rutenettet under. (Begge, først i rutenettet.)

Skjermsparer-tid hører til skillen tv-skjermsparer. Spør der om det trengs.

## 1. Repo og verktøy
```zsh
export PATH="/opt/homebrew/bin:$PATH"
cd ~/Desktop/Utvikling && git clone --depth 1 https://github.com/Gathin23/cleanyourtv.git tv-vibehack && cd tv-vibehack
python3 -m venv tools/venv && tools/venv/bin/pip install -q -r tools/requirements.txt
brew install openjdk@17 android-commandlinetools
export JAVA_HOME=/opt/homebrew/opt/openjdk@17; export PATH="$JAVA_HOME/bin:$PATH"   # sdkmanager trenger Java FØR den kjøres
yes | /opt/homebrew/share/android-commandlinetools/cmdline-tools/latest/bin/sdkmanager --sdk_root=/opt/homebrew/share/android-commandlinetools "platforms;android-34" "build-tools;34.0.0"
export ANDROID_HOME=/opt/homebrew/share/android-commandlinetools
TV_HOST=<IP> tools/venv/bin/python -I tools/tv.py --probe
```
`tools/tv.py` er en Python-ADB-klient som går rundt macOS-sperren og bruker `~/.android/adbkey`, så det kommer ingen ny godkjenning på TV-en. **zsh deler ikke opp variabler:** `P="python tv.py"; $P ...` feiler. Bruk en funksjon: `t(){ TV_HOST=<IP> tools/venv/bin/python -I tools/tv.py "$1"; }`. Bygg og installer forsiden med `TV_HOST=<IP> INPUT_KEY_SERVICE=1 launcher/build-and-install.sh` (ca. 1 min). Etter første gang er «Home already belongs to this launcher» riktig.

## 2. Backup
Lagre `pm list packages`, `pm list packages -d`, `getprop`, `settings list global|secure|system` og nåværende HOME til `~/tv-debloat/backup-<dato>/`.

## 3. Debloat
- Finn listen i `examples/` som matcher `ro.build.fingerprint` / `ro.product.device` (TCL Smart TV Pro G10 = `examples/tcl-g10-google-tv`). Les headeren.
- Lag en egen kopi i `~/tv-debloat/<tv>.txt` og kommenter ut alt brukeren vil beholde fra runde 1. Sjekk at hver pakke finnes.
- `TV_HOST=<IP> tools/disable.sh ~/tv-debloat/<tv>.txt`. Før-tilstanden lagres i `~/.cleanyourtv/` for `tools/restore.sh`.
- Sjekk forside-skjermbilde, `ping google.com` og `screensaver_components`.

## 4. Wi-Fi og oppsettsveiviseren (Google TV)
`launcherx` holder HOME så lenge den er på (testet). Slår du den av, tar `com.google.android.tungsten.setupwraith` over og må også av. Men eier setupwraith Wi-Fi-nettet, sletter Android nettet, og TV-en mister Wi-Fi og ADB.
1. Sjekk eier: `dumpsys wifi | grep -o 'cname=[^ ]*' | sort -u` og `cmd wifi list-networks`.
2. Eier setupwraith hjemmenettet, lagre det på nytt med **ekte adb** via videresendingen (tv.py dreper bakgrunnsjobber):
```zsh
adb shell "nohup setsid sh -c 'cmd wifi forget-network <ID> > /data/local/tmp/wifi.log 2>&1; sleep 3; cmd wifi connect-network <SSID> wpa2 <PASSORD> >> /data/local/tmp/wifi.log 2>&1; sleep 15; cmd wifi status | head -5 >> /data/local/tmp/wifi.log' < /dev/null > /dev/null 2>&1 &"
```
Vent ca. 35 sek, poll port 5555, les og slett loggen, og sjekk at nettet nå eies av `android.uid.shell`. Ved «error: closed» kjører du `adb disconnect; adb connect 127.0.0.1:5556`. Passordet skrives aldri til filer eller minne. Andre nett setupwraith eier blir glemt, så si fra.
3. Legg setupwraith til listen og kjør `FORCE_SETUPWRAITH=1 tools/disable.sh <liste>`. Uten passord kan brukeren glemme nettet og koble til på nytt i TV-ens innstillinger.

## 5. Forsiden etter svarene
Rediger `launcher/app/src/main/res/values/config.xml`:
- `dock_apps`: favorittene i valgt rekkefølge. `hidden_apps`: Live TV-appen (`com.tcl.tv` på TCL) og `com.neilturner.aerialviews`. `live_tv_package`: `com.tcl.tv` på TCL.
- `fill_dock`: `false` når favorittene skal være akkurat de valgte (ellers fylles tomme plasser med andre apper).

### 5a. Favorittbånd med færre fliser enn rutenettet (f.eks. 3 over 4)
Gjør bare dette hvis antall favoritter ≠ apper per rad. Opprinnelig deler dock og rutenett `COLUMNS`. Endringer:
- `config.xml`: `<integer name="dock_columns">3</integer>` (0 = samme som columns).
- `MainActivity`: `static int DOCK, SPAN`; i onCreate `DOCK = cfg.dockRow && dockCols > 0 ? dockCols : COLUMNS; SPAN = lcm(DOCK, COLUMNS)`. `GridLayoutManager(this, SPAN)`, og `SpanSizeLookup`: bibliotek → SPAN, `pos < DOCK` → SPAN/DOCK, ellers SPAN/COLUMNS. `DockDecoration(DOCK)`, `new AppAdapter(..., DOCK, cfg)`, `requestChildRectangleOnScreen` og hero-sjekken bruker `< DOCK`. Dockradens høyde i layout-lytteren beregnes med `tileWidthPx(..., DOCK, ...)`.
- Navigasjon via hjelpere: `colOf(p)`, `rowStartOf(p)` (docken er rad 0, rutenettet starter på DOCK), `dockColFor(gridCol) = min((int)((c+0.5)*DOCK/COLUMNS), dockFilled-1)`, `gridColFor(dockCol) = (int)((c+0.5)*COLUMNS/DOCK)`. Bruk dem i `onTileVerticalKey` (opp/ned og `GridNavigation.atHorizontalEdge` med `position-DOCK`, `count-DOCK`, `COLUMNS` for rutenettet), `onLibraryUp`, pill-ned (`focusTile(dockColFor(colOf(lastFocused)))`) og `moveBy`.
- `AppAdapter`: `getItemViewType` gir 2 for `dockRow && position < dockSize`, og i `onCreateViewHolder` regnes flisbredden med `viewType == 2 ? dockSize : MainActivity.COLUMNS`. I `tileWidthPx(inner, columns, density)` får flisene vokse 25 % når `columns <= 3` (ellers stopper de ved designbredden og får store mellomrom).
- Test: ned fra hver favoritt, høyre-kant, opp tilbake, og rader lenger ned.

### 5b. Ekstra fliser først i rutenettet
`config.xml` `string-array grid_first_apps` (f.eks. `no.espen.bakgrunn`, `no.espen.skjermsparer`). I `AppAdapter`-sorteringen: hvis en pakke ikke er favoritt men står i `grid_first_apps`, gi den rang `1000 + indeks`. `docked` teller fortsatt bare favorittene. Forsiden viser aldri sine egne fliser, så ekstra fliser må være egne små apper (steg 6). To fliser fra samme app konkurrerer om samme rang, så gi hver flis sin egen app.

### 5c. Låst språk
Legg til `res/values-<språk>/strings.xml` med de synlige tekstene (hilsener, Kilder, Innstillinger, Direkte-TV, Tilkoblet, `date_format` `EEEE d. MMMM`, forside-innstillinger, appbibliotek). Overstyr `attachBaseContext` i `MainActivity`, `LauncherSettingsActivity`, `QuickSettingsActivity` (og velgeren fra 6c): `c.setLocale(new Locale("nb","NO"))`. I `MainActivity` må du i tillegg kjøre `Locale.setDefault(...)`, ellers står datoen (TextClock) fortsatt på systemspråket.

### 5d. Fargeskjær per app
I `AppAdapter.ambientColorAt`, før den automatiske fargen: `if ("<pakke>".equals(e.pkg)) return 0xFF000000;` (svart = ingen glød), eller en annen farge per app etter brukerens valg.

## 6. Ekstra fliser og skjermer (bare det de valgte)
Lag små Android-prosjekter i `~/Desktop/Utvikling/`. Kopier gradle-wrapper, `gradlew`, `build.gradle` og `gradle.properties` fra `launcher/`, med minSdk 26, targetSdk 34, debug-signering og banner 640×360 (laget av brukerens egne bilder med Pillow, tekst nederst). Bygg med `./gradlew assembleRelease` og installer med `adb install -r`.

**6a. Skjermsparer-flis** (`no.espen.skjermsparer`, StartActivity med LEANBACK_LAUNCHER og `Theme.NoDisplay`): start `com.android.systemui/.Somnambulator` (NEW_TASK) og kall `finish()`. Fallback: `com.neilturner.aerialviews/.ui.screensaver.TestActivity`. Krever at `appops ... APP_AUTO_START allow` er satt.

**6b. Skjermdeling** (SkjermdelingActivity i samme app, exported, uten launcher-kategori): TV-navn fra `Settings.Global device_name`, fire kort (Mac: Kontrollsenter → Skjermspeiling; iPhone: sveip ned → Skjermspeiling; Windows: Win+K; Android/Chrome: Cast). Knapp til `com.realtek.airplay2/com.realtek.media.airplay2.MainActivity`. Ikke bruk Miracasts MainActivity (testmeny) eller DeviceListActivity (tom liste). Rad i Kilder: i `MainActivity.showInputs()` etter Live TV-raden, `addInputRow(rows, popup, R.drawable.ic_wifi, "Skjermdeling", -1, () -> open(share))`, med en `resolveActivity`-sjekk først.

**6c. Bytt bakgrunn-flis og bildevelger**
- I forsiden: ny `BackgroundPickerActivity` (exported, fullskjerm, svart). Den viser bildene i `getExternalFilesDir(null)/wallpapers/` som fokuserbare kort (miniatyrer via `inSampleSize`, hvit kant og 1.06-zoom på fokus, filnavn som tekst) pluss «Ingen bakgrunn». Valg kopierer filen til `files/wallpaper.jpg` (tmp + rename), eller sletter den, og starter `MainActivity` med NEW_TASK|CLEAR_TASK, fordi bakgrunnen bare leses i onCreate. Registreres i manifestet.
- Egen app `no.espen.bakgrunn` (VelgActivity med LEANBACK_LAUNCHER og `<queries><package android:name="com.gathin.tvhome"/></queries>`) som åpner `com.gathin.tvhome/.BackgroundPickerActivity`.
- Temaet må ha `"wallpaper": true`.

## 7. Tema-mappe på Macen (bakgrunn og innstillinger brukeren endrer selv)
Lag `~/Desktop/Privat/TV-forside/` (eller `~/Desktop/TV-forside/`):
- `innstillinger.json` (overlay over config.xml): `background_color`, `wallpaper`, `sky_intensity` (0–100), `columns`, `rows_below_dock` etter svarene. LES MEG forklarer også `show_stats`, `app_library`, `reduced_motion` og `advanced_effects`.
- `Aktiv bakgrunn/` (ett bilde, settes hver gang temaet sendes) og `Bakgrunner/` (bildene velgeren viser). Legg inn originalbilder, ikke ferdigbehandlede.
- `~/tv-debloat/lag_bakgrunn.py`: beskjær til 1920×1080, lysstyrke 0.42, farge 0.9, mørkere mot bunnen, JPEG < 290 KB. Kjøres ved sending, så hvilket som helst bilde kan brukes. Kjør den aldri to ganger på samme bilde.
- `Bruk tema.command`: valider JSON, behandle «Aktiv bakgrunn» til `wallpaper.jpg` og alle bilder i «Bakgrunner» til `wallpapers/` (filnavn med mellomrom → `_`). Push `wallpapers/` med adb til `/sdcard/Android/data/com.gathin.tvhome/files/wallpapers/` (slett gammel mappe først), og kjør deretter `tools/theme.sh <tmp>`. Si at valget på TV-en tilbakestilles til «Aktiv bakgrunn» når knappen kjøres.
- `Tilbakestill tema.command` (`tools/theme.sh --reset`) og `LES MEG.txt`.

## 8. Angreknapper
`~/Desktop/Privat/TV-oppsett/` med en skjult `.felles.sh` (PATH, `ANDROID_SERIAL=127.0.0.1:5556`, start fwd.py, `adb disconnect/connect`, avbryt med melding hvis TV-en ikke svarer):
- **Tilbake til Google TV-forsiden**: launcherx på og som HOME.
- **Ny forside igjen**: launcherx av, HOME = `com.gathin.tvhome/.MainActivity`.
- **Angre alt**: `tools/restore.sh <liste> com.google.android.apps.tv.launcherx`, `pm enable` på egne tidligere lister, launcherx som HOME, DNS `opportunistic`, animasjoner 1.0, `screensaver_components` tilbake til `com.google.android.apps.tv.dreamx/.service.Backdrop`, `pm uninstall` på forsiden og alle ekstra apper du installerte (aerialviews, skjermsparer, bakgrunn), og slett `/sdcard/Pictures/Skjermsparer`.

Test bytteknappene begge veier. Kjør ikke Angre alt.

## 9. Avslutt
- Sjekk HOME, `screensaver_components`, `private_dns_specifier` og at temaet ligger der.
- ADB: repoet anbefaler å slå det av. Si at knappene, «Bruk tema» og «Oppdater TV» da slutter å virke, at `ro.adb.secure=1` krever godkjenning, og la brukeren velge.
- Oppsummer kort det som ble laget etter deres valg, hvor mappene og knappene ligger, hvordan de endrer selv, og hva som ikke ble testet.
