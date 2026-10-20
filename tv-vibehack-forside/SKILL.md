---
name: tv-vibehack-forside
description: Bytter Google TV-forsiden med CleanYourTV (tv-vibehack) i Apple TV-stil, rydder bloat, legger til Skjermsparer-knapp og Skjermdeling i Inputs, med angreknapper.
---

# Ny TV-forside med CleanYourTV (tv-vibehack)

Mål: brukerens Android/Google TV får en ren, svart forside i Apple TV-stil (github.com/Gathin23/cleanyourtv, før kalt tv-vibehack), med favorittappene i docken, en Skjermsparer-flis, en Skjermdeling-rad i Inputs og tre knapper på Macen for å angre. Ingenting avinstalleres, alt kan reverseres.

Forutsetning: TV-en er koblet til Macen via ADB. Hvis ikke, gjør steg 1–3 i skillen **tv-skjermsparer** først (verktøy, utviklermodus, finne TV-en, videresending rundt macOS-sperren og godkjenning). Vil brukeren også ha bilskjermsparer, gjør den skillen først. Skjermsparer-flisen her starter den.

Arbeid i et skall på Macen (Desktop Commander `start_process` eller device_bash). Snakk enkelt norsk. Les koden i repoet før du kjører den.

## 0. Avklar (én runde AskUserQuestion)
1. Hvilke 3–4 apper som skal i docken (de mest brukte). Testbrukeren valgte Stremio, Netflix, YouTube + Skjermsparer-flisen.
2. Hva som skal beholdes: stemmeassistent, Chromecast, AirPlay, Miracast, firmware-oppdateringer, mobil-fjernkontroll, USB-avspilling. Standard: behold alt dette.
3. Om Wi-Fi-passordet kan oppgis. Trengs nesten alltid på Google TV (se steg 4).

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
`tools/tv.py` er en Python-ADB-klient som går rundt macOS-sperren og bruker `~/.android/adbkey`, så det kommer ingen ny godkjenning på TV-en. **zsh deler ikke opp variabler:** `P="python tv.py"; $P ...` feiler. Bruk en funksjon: `t(){ TV_HOST=<IP> tools/venv/bin/python -I tools/tv.py "$1"; }`.

## 2. Backup
Lagre `pm list packages`, `pm list packages -d`, `getprop`, `settings list global|secure|system` og nåværende HOME (`cmd package resolve-activity --brief -a android.intent.action.MAIN -c android.intent.category.HOME`) til `~/tv-debloat/backup-<dato>/`.

## 3. Debloat
- Finn listen i `examples/` som matcher `ro.build.fingerprint` / `ro.product.device` (TCL Smart TV Pro G10 = `examples/tcl-g10-google-tv`). Les headeren, som har kjente fallgruver.
- Lag en egen kopi i `~/tv-debloat/<tv>.txt` og kommenter ut det brukeren vil beholde (mobil-fjernkontroll `com.google.android.tv.remote.service`, USB-spiller `com.tcl.ui_mediaCenter`, AirPlay, Netflix osv.). Sjekk at hver pakke finnes (`pm list packages <pkg>`).
- Kjør `TV_HOST=<IP> tools/disable.sh ~/tv-debloat/<tv>.txt`. Skriptet lagrer før-tilstand i `~/.cleanyourtv/`, og `tools/restore.sh` bruker den. Tar du det i flere runder, legges nye pakker til opptaket.
- Sjekk etterpå: forside-skjermbilde, `ping google.com`, og at `screensaver_components` fortsatt peker på Aerial Views.

## 4. Wi-Fi og oppsettsveiviseren (den viktigste fallgruven på Google TV)
På Google TV holder `launcherx` HOME så lenge den er på, uansett `set-home-activity` (testet). Slår du den av, tar `com.google.android.tungsten.setupwraith` (RecoveryActivity) over, så den må også av. Men eier setupwraith Wi-Fi-nettet, sletter Android nettet når den slås av, og TV-en mister Wi-Fi og ADB.

1. Sjekk eier: `dumpsys wifi | grep -o 'cname=[^ ]*' | sort -u` og `cmd wifi list-networks`.
2. Hvis setupwraith eier hjemmenettet: lagre det på nytt som shell, med en jobb som overlever at ADB ryker. Det må gjøres med **ekte adb** (via videresendingen), ikke tv.py, fordi tv.py dreper bakgrunnsjobber:
```zsh
adb shell "nohup setsid sh -c 'cmd wifi forget-network <ID> > /data/local/tmp/wifi.log 2>&1; sleep 3; cmd wifi connect-network <SSID> wpa2 <PASSORD> >> /data/local/tmp/wifi.log 2>&1; sleep 15; cmd wifi status | head -5 >> /data/local/tmp/wifi.log' < /dev/null > /dev/null 2>&1 &"
```
Vent ca. 35 sek, poll port 5555, les loggen og slett den. Sjekk at nettet nå eier `android.uid.shell`. Får `adb` «error: closed», kjør `adb disconnect; adb connect 127.0.0.1:5556` først. Passordet skal aldri skrives til filer eller minne.
3. Andre nett som fortsatt eies av setupwraith (f.eks. en gammel hotspot) blir glemt. Si det til brukeren.
4. Legg `com.google.android.tungsten.setupwraith` til listen og kjør `FORCE_SETUPWRAITH=1 tools/disable.sh <liste>`.

Alternativ uten passord: brukeren glemmer nettet og kobler til på nytt i TV-ens innstillinger.

## 5. Forsiden
Rediger `launcher/app/src/main/res/values/config.xml`:
- `dock_apps`: brukerens apper, og `no.espen.skjermsparer` sist hvis flisen fra steg 6 lages.
- `hidden_apps`: Live TV-appen (`com.tcl.tv` på TCL) og `com.neilturner.aerialviews`.
- `live_tv_package`: `com.tcl.tv` på TCL.

```zsh
TV_HOST=<IP> INPUT_KEY_SERVICE=1 launcher/build-and-install.sh
```
Skriptet finner launcherx selv, starter den nye forsiden før den gamle slås av, og ruller tilbake hvis HOME ikke lander riktig. Etter senere endringer i config.xml kjører du samme kommando: «Home already belongs to this launcher» er riktig. Verifiser med skjermbilde, åpne en app fra docken, HOME tilbake (`dumpsys activity activities | grep -m1 mResumedActivity`).

## 6. Skjermsparer-flis og Skjermdeling (egen mini-app)
Lag et lite Android-prosjekt (`~/Desktop/Utvikling/tv-skjermsparer-knapp`, pakke `no.espen.skjermsparer`). Kopier gradle-wrapper, `gradlew`, `build.gradle` og `gradle.properties` fra `launcher/`, med minSdk 26, targetSdk 34 og debug-signering.
- **StartActivity** (LEANBACK_LAUNCHER, `Theme.NoDisplay`, banner 640×360 laget av et av brukerens skjermsparer-bilder med teksten «Skjermsparer»): starter `com.android.systemui/.Somnambulator` med FLAG_ACTIVITY_NEW_TASK og kaller `finish()`. Fallback: `com.neilturner.aerialviews/.ui.screensaver.TestActivity`. Somnambulator virker bare når `appops set com.neilturner.aerialviews APP_AUTO_START allow` er satt.
- **SkjermdelingActivity** (exported, ingen launcher-kategori, fullskjerm, svart): tittel «Skjermdeling», TV-navnet fra `Settings.Global device_name`, og fire kort med fremgangsmåte: Mac (Kontrollsenter → Skjermspeiling), iPhone/iPad (sveip ned → Skjermspeiling), Windows (Windows-tast + K), Android/Chrome (Cast / Smart View, Chrome ⋮ → Cast). Pluss en knapp som åpner `com.realtek.airplay2/com.realtek.media.airplay2.MainActivity`. Ikke bruk `com.tcl.miracast/.MainActivity` (testmeny) eller `DeviceListActivity` (tom liste). Miracast og Chromecast går i bakgrunnen uten egen skjerm.
- Bygg med `./gradlew assembleRelease` og installer med `adb install -r`.
- Legg en rad i Inputs-menyen: i `launcher/.../MainActivity.java` i `showInputs()`, rett etter Live TV-raden:
```java
final Intent share = new Intent().setComponent(new android.content.ComponentName(
        "no.espen.skjermsparer", "no.espen.skjermsparer.SkjermdelingActivity"));
if (getPackageManager().resolveActivity(share, 0) != null) {
    if (rows.getChildCount() > 0) addSeparator(rows);
    addInputRow(rows, popup, R.drawable.ic_wifi, "Skjermdeling", -1, () -> open(share));
}
```
Bygg og installer forsiden på nytt. Test med Inputs → ned til Skjermdeling. Pass på at du ikke trykker OK på AV eller Live TV: det gir tomme skjermbilder.

## 7. Angreknapper på Macen
Lag `~/Desktop/Privat/TV-oppsett/` (eller `~/Desktop/TV-oppsett/`) med en skjult `.felles.sh` (PATH, `ANDROID_SERIAL=127.0.0.1:5556`, start fwd.py, `adb disconnect/connect`, avbryt med melding hvis TV-en ikke svarer) og `chmod +x`:
- **Tilbake til Google TV-forsiden.command**: `pm enable --user 0 com.google.android.apps.tv.launcherx` + `set-home-activity` til `launcherx/.home.HomeActivity` + HOME.
- **Ny forside igjen.command**: `pm disable-user` launcherx + `set-home-activity com.gathin.tvhome/.MainActivity` + HOME.
- **Angre alt.command**: `tools/restore.sh <liste> com.google.android.apps.tv.launcherx`, `pm enable` på alt i tidligere egne deaktiverings-lister, launcherx på og som HOME, `private_dns_mode opportunistic` + slett specifier, animasjoner 1.0, `screensaver_components com.google.android.apps.tv.dreamx/.service.Backdrop`, `pm uninstall` på com.gathin.tvhome, com.neilturner.aerialviews og no.espen.skjermsparer, slett `/sdcard/Pictures/Skjermsparer`.
- `LES MEG.txt`.

Test de to bytteknappene begge veier (`echo x | zsh "<knapp>"`, og sjekk at «Forside nå» skifter). Kjør ikke Angre alt.

## 8. Avslutt
- Sjekk at skjermsparer, DNS og forside overlever: `settings get secure screensaver_components`, `settings get global private_dns_specifier`, og HOME.
- Repoet anbefaler å slå av ADB etterpå. Si at knappene og «Oppdater TV» da slutter å virke, at `ro.adb.secure=1` krever godkjenning, og la brukeren velge.
- Oppsummer: hva som er i docken, hva som er slått av og beholdt, Wi-Fi-endringen, hvor knappene ligger, og hva som ikke ble testet.
