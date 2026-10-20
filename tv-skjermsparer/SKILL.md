---
name: "tv-skjermsparer"
description: "Setter opp en Android/Google TV med egen skjermsparer (bilder med zoom og myke overganger) og valgfri rask debloat, styrt fra brukerens Mac via ADB."
---

# TV-skjermsparer (Android TV / Google TV)

Mål: brukeren ender opp med en TV der forsiden ser ut akkurat som før, men skjermspareren viser
deres egne tema-bilder som videoer med sakte zoom/panorering og myke overganger, pluss en mappe
på Macen de kan redigere og en knapp (`Oppdater TV.command`) som sender endringer til TV-en.
Valgfritt: raskere TV og mindre sporing/reklame.

Vil brukeren også ha ny forside i Apple TV-stil, en Skjermsparer-knapp på forsiden eller Skjermdeling i Inputs, gjør denne skillen først og deretter skillen **tv-vibehack-forside**.

Brukeren skal ikke gjøre noe teknisk selv utover det som MÅ skje på TV-en (utviklermodus og godkjenning).
Alt annet gjør du i et skall på brukerens Mac (device_bash eller Desktop Commander `start_process`).
Snakk enkelt norsk, ett steg om gangen, og fortell hva de skal se etter på TV-skjermen.

## 0. Avklar først (én runde med AskUserQuestion)

1. **TV-merke og system.** Bare Android TV / Google TV støttes (TCL, Sony, Philips, Xiaomi, Hisense med Google TV, Chromecast/Google TV Streamer, Nvidia Shield). Samsung (Tizen) og LG (webOS) støttes ikke: si det rett ut og tilby bare AdGuard DNS for reklame.
2. **Tema for bildene** (multiSelect): f.eks. biler/superbiler, drift, ekstremsport (kiting/twintip, surf, ski, motocross, wingsuit), natur, verdensrommet, arkitektur, dyr, egne bilder. La dem skrive egne tema/merker/personer under «Other».
3. **Egne bilder?** Hvis ja: de kan legge dem i mappen etterpå, eller gi deg en mappe på Macen nå.
4. **Tempo:** standard er 7 sek per bilde + 2 sek overgang (det testbrukeren likte best). 12 sek ble opplevd som for lenge.
5. **Når skjermspareren skal starte:** testbrukeren ville ha 1 minutt uten aktivitet.
6. **Raskere TV / mindre reklame?** (valgfritt, se steg 6). Spør hvilke forhåndsinstallerte apper de IKKE bruker.

Ukjente navn (f.eks. en person eller et merke du ikke finner): søk én gang, spør så brukeren om lenke/Instagram-navn. Ikke gjett.

## 1. Mac: verktøy

```zsh
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
which brew || echo "MANGLER HOMEBREW"   # hvis mangler: be brukeren lime inn installasjonslinjen fra brew.sh i Terminal
brew install --cask android-platform-tools
brew install ffmpeg
python3 -c "import PIL" 2>/dev/null || pip3 install --user pillow
adb version   # MÅ gi versjon. «no such file or directory» = ødelagt symlink -> brew reinstall --cask android-platform-tools
```

Alle hjelpefiler legges i `~/tv-skjermsparer-verktoy/` (lag mappen). **zsh:** en variabel med flere ord blir ikke delt opp. Bruk arrays (`PKGS=(a b c)`) og funksjoner, ikke `CMD="adb -s x shell"; $CMD`.

## 2. TV: utviklermodus (brukeren gjør dette, du guider)

1. Innstillinger → System → Om.
2. Trykk 7 ganger på **«Android TV OS-build»** (den lange koden). IKKE «Android TV OS-versjon»: det åpner bare en stor klokke (påskeegg). Si dette på forhånd.
3. Tilbake → System → **Utvikleralternativer** → slå på **USB-feilsøking**.

## 3. Finn TV-en og koble til

Finn TV-en selv, ikke be brukeren om IP:
```zsh
SUBNET=$(ipconfig getifaddr en0 | cut -d. -f1-3)
for i in $(seq 2 254); do (nc -z -G 1 $SUBNET.$i 5555 2>/dev/null && echo "TV: $SUBNET.$i") & done; wait
```
Flere treff: sjekk `adb shell getprop ro.product.model` etter tilkobling.

**macOS blokkerer adb fra lokalnettet** («No route to host» selv om `nc` når porten). Gå rett til denne videresendingen, ikke prøv direkte først:

```python
# ~/tv-skjermsparer-verktoy/fwd.py  — bruk: python3 fwd.py <TV-IP>
import socket, threading, sys
TV=(sys.argv[1],5555)
def pipe(a,b):
    try:
        while True:
            d=a.recv(65536)
            if not d: break
            b.sendall(d)
    except Exception: pass
    finally:
        for s in (a,b):
            try: s.close()
            except Exception: pass
srv=socket.socket(); srv.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
srv.bind(("127.0.0.1",5556)); srv.listen(5)
while True:
    c,_=srv.accept(); t=socket.create_connection(TV)
    threading.Thread(target=pipe,args=(c,t),daemon=True).start()
    threading.Thread(target=pipe,args=(t,c),daemon=True).start()
```

Start den i bakgrunnen (`nohup python3 ~/tv-skjermsparer-verktoy/fwd.py <IP> >/dev/null 2>&1 &`). Alle adb-kall bruker deretter `export ANDROID_SERIAL=127.0.0.1:5556`. Har forbindelsen stått lenge og adb svarer «error: closed», kjør `adb disconnect; adb connect 127.0.0.1:5556`.

**Godkjenning, gjør det én gang og rent:**
```zsh
adb kill-server; adb start-server; adb connect 127.0.0.1:5556
```
Send så melding til brukeren: «Det kommer én dialog på TV-en. Marker avkrysningsboksen **Tillat alltid fra denne datamaskinen** (trykk OK på den så det blir hake), gå deretter til **Tillat** og trykk OK én gang.» Poll deretter `adb devices` hvert 3. sekund i opptil 60 sek **uten å koble til på nytt**. Gjentatte `adb connect` lager nye dialoger som gjør at «Tillat» ikke virker.

## 4. Skjermsparer-appen (Aerial Views)

```zsh
cd ~/tv-skjermsparer-verktoy
URL=$(curl -sL https://api.github.com/repos/theothernt/AerialViews/releases/latest | python3 -c "import json,sys;print([a['browser_download_url'] for a in json.load(sys.stdin)['assets'] if a['name'].endswith('.apk')][0])")
curl -sL -o aerialviews.apk "$URL" && adb install -r aerialviews.apk
adb shell pm grant com.neilturner.aerialviews android.permission.READ_EXTERNAL_STORAGE
adb shell settings put secure screensaver_components com.neilturner.aerialviews/.ui.screensaver.DreamActivity
adb shell appops set com.neilturner.aerialviews APP_AUTO_START allow   # TCL (Android TV 14+: AUTO_START). Uten denne starter skjermspareren aldri.
adb shell settings put system screen_off_timeout <ms>   # brukerens valg; 60000 (1 min) er testet og virker på TCL G10
```
Aerial Views' README sier at verdier under 6 min ikke virker. På TCL G10 / Google TV 12 stemte ikke det: 1 min virket. Det som manglet i første forsøk var APP_AUTO_START. Sjekk på hver TV: sett verdien, ikke rør noe, vent litt lenger enn tiden, og se etter `dumpsys dreams | grep mCurrentDreamName`.

Etter appops-kommandoen kan skjermspareren startes direkte med `adb shell am start -n com.android.systemui/.Somnambulator`. Det er nyttig for test og for en Skjermsparer-knapp.

### Konfigurer appen via fjernkontroll-kommandoer

Hjelper som trykker taster og tar skjermbilde du kan lese:
```zsh
# ~/tv-skjermsparer-verktoy/k.sh
export PATH="/opt/homebrew/bin:$PATH"; export ANDROID_SERIAL=127.0.0.1:5556
for k in "$@"; do adb shell input keyevent $k; sleep 0.6; done
sleep 1.2; adb exec-out screencap -p > ~/tv-skjermsparer-verktoy/s.png; sips -Z 1280 ~/tv-skjermsparer-verktoy/s.png >/dev/null
```
Start alltid fra hovedmenyen: `adb shell am force-stop com.neilturner.aerialviews; adb shell am start -n com.neilturner.aerialviews/.ui.MainActivity`.
Hovedmeny: 0 Media Sources, 1 Settings, 2 Test screensaver settings. Se på skjermbildet etter hvert steg og bekreft før du går videre. Et tomt skjermbilde (0 byte) betyr at TV-en viser Live TV/HDMI: trykk HOME.

Dette må ende slik:
- **Media Sources:** alle fire nettkilder AV. Apple, Amazon og to «community»-kilder (Jetson, Robin Fourcade) står PÅ fra start, og glemmer du én kommer naturvideoer tilbake. Sjekk alle fire bryterne på skjermbildet.
- **Local or USB storage:** PÅ, «Use folder filter» PÅ, folder name = `Skjermsparer` (skriv med `adb shell input text Skjermsparer`, OK-knappen nås med DPAD_DOWN, DPAD_RIGHT, DPAD_CENTER). Ingen andre mapper på TV-en kan inneholde ordet «Skjermsparer».
- **Settings → Overlays → Bottom Row:** Lower Slot venstre (Clock) og høyre (Metadata #1) = Empty. Sjekk at Top Row er tom.
- **Settings → Appearance → Animations → Video & photo:** Fade in 2 sekunder, Fade out 1,6 sekunder.
- Slideshow-tempo i appen er irrelevant (min. 30 s); tempoet styres av videoene.

## 5. Bilder, mappe og videoer

### Hent bilder (når brukeren vil ha tema-bilder)
Unsplash/Pexels krever nøkkel, så bruk Wikimedia Commons API (frie lisenser). Liggende JPEG ≥2000 px bredt (≥1800 for smale tema), bredde/høyde 1,3–1,9, 3–6 per søkeord, `time.sleep(4)` mellom søk (ellers HTTP 429), og en User-Agent-header. Gode søk: spesifikke modeller/aktiviteter ("Porsche 918 Spyder", "kitesurfing", "Formula Drift", "wingsuit flying").

**Kvalitetssjekk:** lag kontaktark med Pillow (nummererte miniatyrer), se på det, og slett nærbilder, interiør, utstillings- og verkstedbilder, duplikater, svart-hvitt/gamle bilder, bittesmå motiver og bilder som ikke matcher temaet. Gi gjerne beholdte filer norske, beskrivende navn.

**Vær ærlig om smale ønsker.** En bestemt ombygd bilmodell, en person eller en Instagram-konto finnes som regel ikke med fri lisens. Si hva du fant og hva som mangler, ikke last ned opphavsrettsbeskyttede bilder fra Instagram/Pinterest, og forklar at brukeren selv kan lagre bilder de liker i mappen til eget bruk.

### Mappen brukeren redigerer
`~/Desktop/Privat/TV-skjermsparer/` hvis `Privat/` finnes, ellers `~/Desktop/TV-skjermsparer/`. Én undermappe per tema (Biler, Ekstremsport, Drift, Egne ...), pluss `LES MEG.txt` og `Oppdater TV.command`. Slett aldri brukerens egne filer. Sier brukeren at slettede bilder fortsatt vises, kjør Oppdater TV.

### Videogenerator (jevn bevegelse er avgjørende)
Zoompan i 1080p hakker. Skaler til 4x, kjør zoompan til 2x og skaler ned med lanczos. Det ga jevn bevegelse i test.

```python
# ~/tv-skjermsparer-verktoy/lag_video.py  — bruk: python3 lag_video.py <bildemappe> <utmappe>
import os, random, subprocess, sys, tempfile, shutil, glob
SRC, OUT = sys.argv[1], sys.argv[2]
SHOW, FADE, FPS, GROUP = 7, 2, 30, 8
W, H = 1920, 1080
FF = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"
exts = (".jpg", ".jpeg", ".png", ".webp", ".JPG", ".JPEG", ".PNG", ".WEBP")
imgs = [p for p in glob.glob(os.path.join(SRC, "**", "*"), recursive=True) if p.endswith(exts)]
random.shuffle(imgs)
if len(imgs) < 2: sys.exit("Trenger minst 2 bilder")
tmp = tempfile.mkdtemp(); dur = SHOW + FADE; frames = int(dur * FPS)
moves = [("1+0.10*on/{d}", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),
         ("1.10-0.10*on/{d}", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),
         ("1.08", "(iw-iw/zoom)*on/{d}", "ih/2-(ih/zoom/2)"),
         ("1.08", "(iw-iw/zoom)*(1-on/{d})", "ih/2-(ih/zoom/2)"),
         ("1+0.08*on/{d}", "(iw-iw/zoom)*0.3", "(ih-ih/zoom)*0.4")]
clips = []
for i, img in enumerate(imgs):
    z, x, y = moves[i % len(moves)]; d = frames - 1
    vf = (f"scale={W*4}:{H*4}:force_original_aspect_ratio=increase:flags=bicubic,crop={W*4}:{H*4},"
          f"zoompan=z='{z.format(d=d)}':x='{x.format(d=d)}':y='{y.format(d=d)}':d={frames}:s={W*2}x{H*2}:fps={FPS},"
          f"scale={W}:{H}:flags=lanczos,format=yuv420p")
    out = os.path.join(tmp, f"c{i:03d}.mp4")
    subprocess.run([FF, "-v", "error", "-y", "-loop", "1", "-i", img, "-vf", vf, "-t", str(dur),
                    "-c:v", "h264_videotoolbox", "-b:v", "12M", out], check=True)
    clips.append(out); print(f"bilde {i+1}/{len(imgs)}", flush=True)
os.makedirs(OUT, exist_ok=True)
groups = [clips[i:i+GROUP] for i in range(0, len(clips), GROUP)]
if len(groups) > 1 and len(groups[-1]) < 2: groups[-2] += groups.pop()
for g, grp in enumerate(groups):
    out = os.path.join(OUT, f"skjermsparer_{g+1:02d}.mp4")
    inputs = sum([["-i", c] for c in grp], [])
    chain, prev, offset = [], "[0:v]", SHOW
    for i in range(1, len(grp)):
        chain.append(f"{prev}[{i}:v]xfade=transition=fade:duration={FADE}:offset={offset:.2f}[v{i}]")
        prev, offset = f"[v{i}]", offset + SHOW
    subprocess.run([FF, "-v", "error", "-y", *inputs, "-filter_complex", ";".join(chain), "-map", prev,
                    "-c:v", "h264_videotoolbox", "-b:v", "7M", "-movflags", "+faststart", out], check=True)
    print(f"video {g+1}/{len(groups)}", flush=True)
shutil.rmtree(tmp); print("ferdig:", OUT)
```
Videoene deles i grupper på 8, så skjermspareren kan stokke dem og ikke starter likt hver gang. Juster SHOW/FADE etter brukerens tempo-svar. Ca. 9 sek rendering per bilde på Apple Silicon (75 bilder ≈ 10 min). Kjører du Oppdater-knappen fra skallet ditt, poll `~/tv-skjermsparer-verktoy/videoer` for fremdrift og gi brukeren en statuslinje hvis de spør.

### Oppdater-knappen
`Oppdater TV.command` i brukerens mappe (`chmod +x`). Fyll inn TV-IP:
```zsh
#!/bin/zsh
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
MAPPE="$(cd "$(dirname "$0")" && pwd)"; TV_IP="<TV-IP>"; SERIAL="127.0.0.1:5556"
V="$HOME/tv-skjermsparer-verktoy"; UT="$V/videoer"
for v in adb ffmpeg; do command -v $v >/dev/null || { echo "Mangler $v."; read -k1; exit 1; }; done
echo "Lager videoer av bildene (tar noen minutter)..."
rm -rf "$UT"; python3 "$V/lag_video.py" "$MAPPE" "$UT" || { echo "Feil under videolaging."; read -k1; exit 1; }
echo "Kobler til TV-en..."
pgrep -f "$V/fwd.py" >/dev/null || (nohup python3 "$V/fwd.py" "$TV_IP" >/dev/null 2>&1 &)
sleep 1; adb disconnect >/dev/null 2>&1; adb connect "$SERIAL" >/dev/null; sleep 2
adb -s "$SERIAL" get-state >/dev/null 2>&1 || { echo "Fikk ikke kontakt med TV-en (på, samme Wi-Fi?)."; read -k1; exit 1; }
echo "Sender til TV-en..."
adb -s "$SERIAL" shell rm -rf /sdcard/Pictures/Skjermsparer
adb -s "$SERIAL" shell mkdir -p /sdcard/Pictures/Skjermsparer
antall=0
for f in "$UT"/*.mp4; do adb -s "$SERIAL" push "$f" /sdcard/Pictures/Skjermsparer/ >/dev/null 2>&1 && antall=$((antall+1)); done
adb -s "$SERIAL" shell am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE -d file:///sdcard/Pictures/Skjermsparer >/dev/null 2>&1
sleep 3; echo "Ferdig! $antall videoer ligger i skjermspareren."; read -k1
```
Uten media-scan-broadcasten finner skjermspareren 0 filer. Kjør knappen selv første gang (`echo x | zsh "…/Oppdater TV.command"`).

`LES MEG.txt`: legg bilder i undermappene (nye mapper blir også med) → dobbeltklikk Oppdater TV → vent ca. 10 min til det står Ferdig. Liggende bilder ser best ut. Første gang kan macOS spørre om Terminal får bruke lokalnettet: svar ja.

### Verifiser
Start med `am start -n com.android.systemui/.Somnambulator` eller appens testknapp (hovedmeny → DPAD_DOWN ×2 → DPAD_CENTER). Video vises som svart i `screencap`, så spør brukeren med AskUserQuestion hva de ser (bilder som beveger seg og glir over / hakker / natur / svart). Natur = en nettkilde står fortsatt på. Hakking = 4x-oppskaleringen mangler. Avslutt med BACK og HOME.

## 6. Valgfritt: raskere TV og mindre reklame (forsiden skal se lik ut)

- Bare `pm disable-user --user 0 <pakke>`, aldri avinstaller. Lagre listen i `~/tv-skjermsparer-verktoy/disabled.txt` og lag `restore.sh` som kjører `pm enable` på hver linje.
- Bruk zsh-arrays (`PKGS=(a b c); for p in $PKGS`). Med en vanlig streng deaktiveres bare den første pakken.
- Hent `pm list packages -s` og `dumpsys meminfo` først og velg ut fra det. Trygge eksempler (TCL/Google TV): `tv.samba.ssm.ui` (Samba TV-sporing), `com.tcl.channelplus`, `com.tcl.waterfall.overseas`, `com.tcl.esticker`, `com.tcl.exhibit`, `com.tcl.messagebox`, `com.tcl.logkit`, `com.tcl.ocean.instructions`, `com.tcl.repairguide`, `com.tcl.smartalexa`, `com.tcl.usercenter`, `com.tcl.magiconnectfree`, `com.tcl.gamebar`, `com.android.printspooler`, `com.google.android.videos`, `com.google.android.youtube.tvmusic`, `com.google.android.play.games`, `com.google.android.feedback`, pluss apper brukeren sa de ikke bruker.
- Ikke rør: launcher (`launcherx`), Play Store, GMS, Chromecast (`mediashell`), AirPlay/Miracast, `com.tcl.tv`, `tvinput`, `systemserver`, `guard`, `dashboard`, `katniss` (stemme), `com.tcl.ttvs` (TCLs firmware-oppdatering).
- Animasjoner 0.5: `settings put global window_animation_scale 0.5` (+ `transition_animation_scale`, `animator_duration_scale`).
- Reklameblokk: `settings put global private_dns_mode hostname` og `settings put global private_dns_specifier dns.adguard-dns.com`. Verifiser med `adb shell ping -c1 doubleclick.net` (skal gi 127.0.0.1/0.0.0.0) og at google.com svarer.
- Vær ærlig: Googles «Sponsored»-felt og det store banneret på forsiden kan ikke fjernes uten å bytte forside (se **tv-vibehack-forside**). Bakgrunnsfarge kan heller ikke endres på Google TV-forsiden.

## 7. Avslutt

- Omstart: `adb reboot` henger via videresendingen. Kjør den i bakgrunnen, vent 70 sek til port 5555 svarer, og koble til på nytt (godkjenningen huskes).
- Etter omstart: sjekk at `screensaver_components`, `private_dns_specifier`, `screen_off_timeout` og antall deaktiverte pakker sitter.
- Stopp videresendingen (`pkill -f fwd.py`) og `adb disconnect`.
- Kort oppsummering til brukeren: hva skjermspareren viser, tempo, når den starter, hvor mappen ligger og hvordan knappen brukes, hva som ble slått av (og at alt kan reverseres), og hva som ikke lot seg gjøre.