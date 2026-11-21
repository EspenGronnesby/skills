---
name: hardstyle-producer
description: Gjør en opplastet låt (MP3/WAV) om til en hardstyle-remiks som ferdig organisert FL Studio-prosjekt (.flp) med stems, MIDI, euphoric + rawstyle drop og vokal i nytt tempo. Bruk når Espen laster opp en låt og vil ha en hardstyle/rawstyle-remiks eller FL Studio-filer av den.
---

# hardstyle-producer

Mål: Espen laster opp en låt og får en mappe i `Desktop\Fl studio\<Låtnavn>_Remix\` med et FL Studio-prosjekt han
bare åpner: ett mønster per instrument per seksjon, ett navngitt spor per instrument, markører, riktig tempo.
I tillegg vokalen strukket til nytt tempo og plassert, alle deler som MIDI, og en guide.
Første gang testet på MAGIC! - Rude (144 BPM, Db-dur -> 150 BPM).

Snakk norsk, kort og konkret. Programnavn, kommandoer og filnavn på engelsk. Han er nybegynner i produksjon.

## 0. Avklar først (én runde, bare det som mangler)
- Lydfilen må være lastet opp. Mangler den: be om den og stopp.
- Ønsket: standard er **"150 BPM euphoric hardstyle remix, melodic first drop, aggressive rawstyle second drop"**.
  Bruk hans ord hvis han skriver noe annet (BPM, kun euphoric, kun raw).
- Ikke spør om noe annet. Start.

## 1. Hent koden og installer (ca. 2 min, hver ny samtale)
```bash
cd /home/claude
git clone --depth 1 https://github.com/EspenGronnesby/skills /home/claude/skills 2>/dev/null || git -C /home/claude/skills pull -q
export PYTHONPATH=/home/claude/skills/hardstyle-producer/scripts
pip install --break-system-packages -q librosa soundfile mido pretty_midi resampy scipy scikit-learn mir_eval onnxruntime pedalboard
pip install --break-system-packages -q torch torchaudio --index-url https://download.pytorch.org/whl/cpu
pip install --break-system-packages -q demucs
pip install --break-system-packages -q --no-deps basic-pitch==0.4.0
```
`basic-pitch` MÅ ha `--no-deps` (den låser en gammel numpy som ikke bygger). Sjekk: `python3 -m hsp diagnose`.

## 2. Kjør pipelinen - ett steg per kommando
Hvert verktøykall har 10 min grense, så ikke bruk `run` på hele låter. Sett `P=/home/claude/<Låtnavn>_Remix`.
Kommandoene skriver `WARNING`-linjer fra basic-pitch; filtrer med `2>&1 | grep -v WARNING`.
```bash
python3 -m hsp init "<lydfil>" -p $P --request "<ønsket>"
python3 -m hsp separate-stems -p $P      # Demucs, ca. 40 s per minutt lyd. Timeout 600000.
python3 -m hsp analyze-song -p $P        # BPM, toneart, takt 1, akkorder, seksjoner, vokal
python3 -m hsp extract-midi -p $P        # Basic Pitch per stem (faithful)
python3 -m hsp clean-midi -p $P          # renset MIDI
python3 -m hsp chord-check -p $P         # akkord + bass per takt -> forslag til progresjon
```

## 3. Lås akkordprogresjonen (viktigste kvalitetssteg)
`chord-check` skriver til slutt `Forslag: --progression A,B,C,D --bars-per-chord 1 --anchor-bar N`.
- Bruk forslaget hvis det dekker mange vinduer (Rude: 13 av 33). Forskjellig rotasjon av samme fire akkorder er samme løkke.
- Kjør `chord-check --bars <refreng>` (f.eks. `17-40`) og se på takter der `bass ->` avviker. Bassen avgjør.
  På Rude så første refreng ut som Gb-Ab-**Fm**-Bbm, men siste refreng var Gb-Ab-**Db**-Bbm. Velg løkken som går igjen i flest refrenger.
- Toneart med lav konfidens: si det til Espen (dur vs. relativ moll), men fortsett.

```bash
python3 -m hsp plan-arrangement -p $P --progression <forslag> --bars-per-chord 1 --anchor-bar <N> --seed 2
```
`--anchor-bar` gjør at akkordene under den flyttede vokalen starter der de gjorde i originalen. Uten den kolliderer vokal og akkorder.

## 4. Kontroller før levering (ikke hopp over)
```bash
python3 -m hsp verify -p $P      # samme akkord under vokalen som i originalen? Må gi KONTROLL BESTÅTT
```
Den sammenligner, takt for takt, akkorden originalen hadde under hver vokaltakt med akkorden remiksen legger der.
Riktig justering gir ca. 80-90 % (Rude: 88 % i Breakdown/Drop/Outro), feil gir 0-10 % og stopper.
Seksjoner der vokalen kommer fra et parti med andre akkorder (Rude: Verse fra introen, 38 %) skal nevnes for Espen: lytt der.

## 5. Lag FL Studio-prosjektet og lever
```bash
python3 -m hsp build-flp -p $P           # fl-studio/<Låtnavn>_Remix.flp
python3 -m hsp prepare-fl-studio -p $P   # guiden peker nå på .flp-filen
python3 -m hsp preview -p $P
python3 -m hsp package -p $P --out /home/claude/deliver/<Låtnavn>_Remix
```
`build-flp` lager prosjektet direkte (ingen MIDI-import, ingen «Split by channel»):
- ett mønster per instrument per seksjon («Lead - Euphoric Drop», «Kick - Intro» ...),
- ett navngitt, farget Playlist-spor per instrument (Lead, Lead Harmony, Counter, Chords, Bass, Kick, Screech, Snare Roll, Kick Roll),
- klipp på riktig takt, seksjonsmarkører, riktig tempo, alle kanaler FLEX med egen mixer-insert,
- bygget fra `templates/hardstyle_mal.flp` (hans FL 26.1.7-prosjekt). Stopper hvis antall noter ikke stemmer.
Omorganisere et prosjekt han allerede har jobbet i (beholder lydene og endringene hans, skriver ny fil):
`python3 -m hsp build-flp -p $P --from-flp "<hans .flp>" --out "<ny fil>_organisert.flp"`

Levering:
1. Send alle filene med `SendUserFile` (status normal, display attach).
2. Hjemmet for alt er **`C:\Users\essi1\Desktop\Fl studio\`**, én mappe per låt: `Desktop\Fl studio\<Låtnavn>_Remix\`.
   Krever at mappen er koblet til samtalen. Sjekk `get_device_info`. Mangler den: be ham om **+ > Add folder > Desktop\Fl studio**.
   Sjekk med `device_list_dir` at låtmappen IKKE finnes (aldri overskriv), og skriv så filene med `device_commit_files`,
   med samme undermapper (`fl-studio\`, `arrangement\`, `midi\` ...).

## 6. Hjelp ham i FL
Normalt: `File > Open` -> `fl-studio\<Låtnavn>_Remix.flp`, deretter vokal-WAV-en inn i Playlist på takt 1.
Reserve hvis .flp ikke åpner: `File > Import > MIDI file...` -> `arrangement\arrangement.mid`. I dialogen *Import MIDI data*:
All tracks · Channel type **FLEX** · **Start new project PÅ** · **Realign events AV** · Create one channel per track PÅ ·
Set mixer tracks PÅ · Import time signatures PÅ -> **Accept**. Sjekk at tempoet viser målet (f.eks. 150), lagre som `<Låtnavn>_Remix.flp`.
Vokal: dra `arrangement\vocals_arranged_<bpm>bpm.wav` inn i Playlist helt i starten av takt 1.
Gå videre ett steg om gangen. Be om skjermbilde når du trenger å se noe.

## Hans oppsett (verifisert 21.11.2026)
- Windows-PC `espen`, FL Studio (trolig 26.1.7), FL sin Stem extractor installert, FLEX-pakker Euphoria + Essential Pianos.
- Lydbibliotek: FL Cloud-nedlastinger i `Documents\Image-Line\Downloads\FL CLOUD Sounds\` (243 lyder/68 pakker per 21.11.2026:
  rawstyle-force-sin, uptempo-hardcore-2-sin, hardcore-raver-sin, amsterdam-hard-dance-sin, born-for-hardstyle ...).
  `.fldownload.wav` kan være TOM (HHB_Kick_Oneshot_Infinity_01_F er stille, -180 dB): mål alltid nivå før bruk.
  Foreslå aldri filnavn som ikke er verifisert.

## Full produksjon med samples (stil «cinematic_raw_zaag», testet på Dezko - Ascend)
`hsp/production.py` + `hsp/produce_cli.py`: seksjonsplan (Cinematic Intro, Breakdown, Build-up, Euphoric Drop, Transition,
Build-up 2, Rawstyle Drop, Zaag 200 BPM), MIDI per del, sampler-kanaler med hans filer (stemt/strukket kopier i
`samples\edited`, originaler urørt), egne syntetiserte lyder for hull (`hsp/sounddesign.py`: screech, clap, impact,
riser, cinematic pad, rot C5) og vokalen som lydklipp. Hent hans filer med `device_stage_files`, mål lengde/toneart,
velg per rolle (kick i låtens grunntone, looper med riktig BPM), kjør `produce(...)` (se references/production_example.py
). Tempohopp (f.eks. 160->200) må han legge inn selv med en tempo-automasjon;
gi nøyaktige steg. Sjekk at alle filstier i .flp finnes på PC-en etter levering.

## Fallgruver
- **Alt i ett mønster «arrangement»**: det skjer ved MIDI-import av én flersporsfil. Løst med `build-flp`, som skriver .flp
  direkte. FL 26-detaljer i `hsp/flp.py` + `hsp/flp_organize.py`: hendelse 172 er 3 byte, Playlist-klipp er 88 byte,
  sporets navn (239) kommer etter hendelse 43, tempo = 156 (BPM×1000). Hendelse 223 i importerte mønstre er tempo-automasjon
  og skal ikke kopieres. Prosjektet kjører 96 PPQ, så notelengder rundes til nærmeste tick (< 1 ms).
- **Tempo halvert/doblet**: Ascend ble lest som 60 BPM; regel nå: under 80 dobles, over 185 halveres. Sjekk alltid at
  akkordbyttene blir hele takter.
- **MIDI forskjøvet 3 slag** når låten har lang intro: rettet i koden (beat 0 = første downbeat). Regresjonstest finnes i `tests/selftest.py`.
- **Offbeat-hi-hats og offbeat-bass** kan lure taktgridet. Koden tester både på slag og offbeat. Sjekk `downbeat.confidence` < 0.1.
- **Pitchet kick ødelegger akkordlesing** på full miks. Akkorder leses derfor fra stems.
- **Basic Pitch slår sammen raske gjentatte toner** (offbeat-bass). Bassen genereres på nytt, den kopieres ikke.
- Vokal-MIDI er usikker. `lead_from_vocal_hook.mid` er et alternativ, ikke fasit.
- Ikke påstå at FL Studio er endret. Skillen lager filer og instruksjoner.

## Avslutt
Si kort på norsk: BPM, toneart, progresjon, seksjonene og hvor vokalen ligger, hva som er usikkert, og at filene ligger i mappen.
Neste steg er å åpne .flp-filen i FL (steg 6).
