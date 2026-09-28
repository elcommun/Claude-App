from voicevox_core.blocking import Onnxruntime, OpenJtalk, Synthesizer, VoiceModelFile
from voicevox_core import AudioQuery, Mora
import glob, json, io, sys, numpy as np, soundfile as sf, dataclasses
ANIM="../anim"
ort = Onnxruntime.load_once(filename=glob.glob("voicevox_onnxruntime*/lib/libvoicevox_onnxruntime.so")[0])
syn = Synthesizer(ort, OpenJtalk("open_jtalk_dic_utf_8-1.11"))
with VoiceModelFile.open("0.vvm") as m: syn.load_voice_model(m)
STYLE={"poko":3,"kira":8}
# kana (AquesTalk-like): / no pause, 、 pause, ' accent, _ devoiced, ？ interrogative
KANA={
"L01":"コ'ンヤワ、ホシガ'/イ'ッパイダナア",
"L02":"ア'ッ、ナガレ'ボシ、エ'、コッチ'ニ/ク'ル？",
"L03":"イ'タタタ、ド'オシヨオ、ソ'ラニ/カエレ'ナイ",
"L04":"ダイジョ'オブ？、ボ'ク/ポ'コ、キミワ'？",
"L05":"キ'ラ、ヨアケ'マデニ/モドラ'ナイト、ワタシ'、キエチャウ'ノ",
"L06":"マカセ'テ、ロケットジャ'ンプ",
"L07":"ヤッパ'リ、ム'リダヨ",
"L08":"ウ'ウン、ゼッタイ'、アキラメ'ナイ",
"L09":"マチ'ノ/ミンナ'、チカラ'オ/カ_シテ'",
"L10":"ワ'ア、マチ'ノ/_ヒカリ'ガ、ミチニ'/ナ'ッテ/イク'",
"L11":"イクヨ'、キ'ラ、イッケ'エエエ",
"L12":"アリ'ガトオ、ポ'コ、ズット'、ソ'ラカラ/ミテ'ルネ",
"L13":"ウ'ン、マタ'ネ、キ'ラ",
}
EMO={ # speed, pitch, intonation, volume, pause_scale
"normal":(1.04,0.00,1.20,1.0,0.6),
"surprised":(1.10,0.03,1.40,1.1,0.5),
"sad":(0.94,-0.01,1.00,0.9,1.0),
"excited":(1.10,0.04,1.40,1.15,0.7),
"determined":(1.04,0.02,1.30,1.1,0.8),
"shout":(1.08,0.05,1.40,1.2,0.7),
"wonder":(0.96,0.01,1.25,1.0,1.0),
"gentle":(0.97,0.00,1.12,0.95,0.7),
"happy":(1.08,0.04,1.35,1.1,0.7),
}
# extra per-line pause (seconds) after phrase index: dramatic pauses
EXTRA={"L02":{1:0.1},"L03":{0:0.1},"L07":{0:0.1},"L10":{0:0.15}}
LEAD={"L07":0.0}
def synth(l, speed_mul=1.0):
    sp,pi,it,vo,ps=EMO[l["emotion"]]
    aps=syn.create_accent_phrases_from_kana(KANA[l["id"]], STYLE[l["who"]])
    for i,ap in enumerate(aps):
        if ap.pause_mora is not None:
            pm=ap.pause_mora
            if isinstance(pm,dict): pm=Mora(**pm)
            pm=dataclasses.replace(pm,vowel_length=pm.vowel_length*ps + EXTRA.get(l["id"],{}).get(i,0))
            aps[i]=dataclasses.replace(ap,pause_mora=pm)
    q=AudioQuery.from_accent_phrases(aps)
    q=dataclasses.replace(q,speed_scale=sp*speed_mul,pitch_scale=pi,intonation_scale=it,volume_scale=vo,
        pre_phoneme_length=0.08,post_phoneme_length=0.12,output_sampling_rate=24000,output_stereo=False)
    wav=syn.synthesis(q, STYLE[l["who"]], enable_interrogative_upspeak=True)
    x,sr=sf.read(io.BytesIO(wav),dtype="float32")
    if x.ndim>1: x=x.mean(1)
    from scipy.signal import resample_poly
    x=resample_poly(x,48000,sr).astype(np.float32)
    return x
def trim(x,sr=48000,pad=0.03):
    fr=int(sr*0.005); e=np.array([np.sqrt(np.mean(x[i:i+fr]**2)) for i in range(0,len(x),fr)])
    thr=max(e.max()*0.02, 1e-4)
    idx=np.where(e>thr)[0]; s=max(0,idx[0]*fr-int(pad*sr)); t=min(len(x),(idx[-1]+1)*fr+int(pad*sr))
    y=x[s:t].copy(); f=int(0.005*sr); y[:f]*=np.linspace(0,1,f); y[-f:]*=np.linspace(1,0,f)
    return y
S=json.load(open(f"{ANIM}/script.json"))
import os; os.makedirs(f"{ANIM}/voice",exist_ok=True)
rep=[]
for l in S["lines"]:
    slot=l["slot_end"]-l["t"]; mul=1.0
    while True:
        y=trim(synth(l,mul)); d=len(y)/48000
        if d<=slot-0.05 or mul>=1.3: break
        mul=round(mul+0.04,2)
    e=np.array([np.sqrt(np.mean(y[i:i+480]**2)) for i in range(0,len(y)-480,480)])
    act=e[e>e.max()*0.1]; rms=np.sqrt(np.mean(act**2))
    tgt=10**((-17 if l["emotion"] in ("sad","gentle") else -15)/20)
    y=y*(tgt/rms); pk=np.abs(y).max()
    if pk>0.89: y*=0.89/pk
    pk=np.abs(y).max()
    sf.write(f"{ANIM}/voice/{l['id']}.wav",y,48000,subtype="PCM_16")
    rep.append((l["id"],l["who"],l["emotion"],round(d,2),round(slot,2),mul,round(float(20*np.log10(pk+1e-9)),1)))
for r in rep: print(r)
