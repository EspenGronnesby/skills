# Eksempel: slik ble Dezko - Ascend produsert (stil cinematic_raw_zaag, G#m, 160->200 BPM).
import json
from pathlib import Path
from hsp.produce_cli import produce
FC=r"C:\Users\essi1\Documents\Image-Line\Downloads\FL CLOUD Sounds"
def w(*p): return "\\".join((FC,)+p)
picks={
 "Kick": w("hardcore-raver-sin","SHA_G#_Kick_06_4401593.wav"),
 "Raw Kick": w("rawstyle-force-sin","SRSF_G#_Kick_61_4352767.wav"),
 "Zaag Kick": w("uptempo-hardcore-2-sin","SUH2_200_G_Zaag_Kick_Loop_38_4316370.wav"),
 "Kick Roll": w("amsterdam-hard-dance-sin","SHDD_155_Kick_Roll_45_4326987.wav"),
 "Clap": "GEN:HSP_Clap_01.wav",
 "Clap Loop": w("rawstyle-force-sin","SRSF_160_Clap_Loop_03_4352431.wav"),
 "Snare": w("rawstyle-force-sin","SRSF_Snare_20_4352944.wav"),
 "Snare Build": w("rawstyle-force-sin","SRSF_160_Snare_Build_Up_01_4352465.wav"),
 "Screech": "GEN:HSP_Screech_02_C.wav",
 "Screech FX": w("hardstyle-uns","US_HS_FX_160_screech_11_WET_3505941.wav"),
 "Riser": "GEN:HSP_Noise_Riser_8s.wav",
 "Tension Riser": w("born-for-hardstyle","WABFH_Build_Up_07_155BPM_Tension_Riser_533113.wav"),
 "Uplifter": w("uptempo-hardcore-2-sin","SUH2_200_G#_Uplifter_17_4316788.wav"),
 "Reverse Crash": w("amsterdam-hard-dance-sin","SHDD_Crash_11_Reversed_4327047.wav"),
 "Impact": w("hardstyle-vol-1-rer","REVHS1 Sub Drops 02_3242557.wav"),
 "Noise FX": w("uptempo-hardcore-2-sin","SUH2_200_Noise_FX_02_4316766.wav"),
 "Vocal Shout": w("amsterdam-hard-dance-sin","SHDD_160_Male_Vocal_Shout__Drop_It_V2_4327432.wav"),
 "Shout Hardcore": w("uptempo-hardcore-2-sin","SUH2_200_Male_Vocal_Shout__Hardcore_4316522.wav"),
 "Shout Rave": w("uptempo-hardcore-2-sin","SUH2_200_Male_Vocal_Shout__Don't_Stop_The_Rave_4316528.wav"),
 "Cinematic Pad": "GEN:HSP_Cinematic_Pad_C.wav",
 "Atmosphere": w("laniakea-sounds-cinematic-tools","LSCT_Cinematic_Atmosphere_04_100BPM_E_279648.wav"),
}
info=produce(Path('/home/claude/ascend/Ascend_Remix'), picks, Path('/mnt/user-data/uploads/Image-Line/Downloads/FL CLOUD Sounds'),
  r"C:\Users\essi1\Documents\Image-Line\FL Studio\Projects\Ascend_Remix", ["E","G#m","F#","C#m"], 2)
print(json.dumps({k:v for k,v in info.items() if k!='samplers'},indent=1,ensure_ascii=False))
