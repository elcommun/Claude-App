from voicevox_core.blocking import Onnxruntime, OpenJtalk, Synthesizer, VoiceModelFile
from voicevox_core import AudioQuery, Mora
import glob, json, io, os, numpy as np, soundfile as sf, dataclasses
from scipy.signal import resample_poly
D="../dogs"
ort = Onnxruntime.load_once(filename=glob.glob("voicevox_onnxruntime*/lib/libvoicevox_onnxruntime.so")[0])
syn = Synthesizer(ort, OpenJtalk("open_jtalk_dic_utf_8-1.11"))
for f in ["0.vvm","4.vvm"]:
    with VoiceModelFile.open(f) as m: syn.load_voice_model(m)
STYLE={"kinako":10,"kinako_puppy":10,"chimaki":11}
KANA={
"L01":"ネ'エ、チ'マキ、ド'オシテ/イ'ツモ、ソコニ'/イル'ノ？",
"L02":"ココカラ'ナラ、キ'ナコガ、ヨ'ク/ミエル'カラ",
"L03":"ク'ウン、コワイ'ヨ、ヒトリボ'ッチ",
"L04":"ナカナイ'デ、ボ'クガ、ズット'/ミ'テテ/アゲル'",
"L05":"チ'マキ、フルエテル'ノ？",
"L06":"フ'、フルエテ'/ナ'ンカ、ナ'イヨ",
"L07":"キャ'ン",
"L08":"ダイジョ'オブ、コ'ンドワ、ワタシガ'/マモル'/バ'ンダヨ",
"L09":"キ'ナコ、オ'オキク/ナ'ッタネ",
"L10":"コレカラモ'、ズット'/イッショ'ダヨ",
"L11":"ウ'ン、ズット'、ネ'",
}
# speed, pitch, intonation, volume, pause_scale, wobble(pitch tremble), target dBFS rms
P={
"L01":(1.02, 0.00,1.25,1.00,0.40,0.0,-16),
"L02":(0.88,-0.03,1.00,0.95,0.90,0.0,-17),
"L03":(0.90, 0.08,1.30,0.85,0.90,0.035,-19),
"L04":(0.90,-0.02,1.05,0.95,0.60,0.0,-17),
"L05":(0.90,-0.01,1.10,0.90,0.60,0.0,-18),
"L06":(0.95,-0.01,1.15,0.95,0.90,0.025,-17),
"L07":(0.72, 0.14,1.80,1.20,0.50,0.0,-13),
"L08":(1.00, 0.00,1.20,1.00,0.50,0.0,-16),
"L09":(0.85,-0.03,0.95,0.85,1.30,0.012,-18),
"L10":(1.00, 0.02,1.30,1.05,0.60,0.0,-15),
"L11":(0.96,-0.01,1.10,0.95,0.70,0.0,-16),
}
LEAD={"L02":0.0}
def synth(l, mul=1.0):
    sp,pi,it,vo,ps,wob,_=P[l["id"]]
    aps=syn.create_accent_phrases_from_kana(KANA[l["id"]], STYLE[l["who"]])
    k=0
    for i,ap in enumerate(aps):
        moras=list(ap.moras)
        if wob:
            for j,m in enumerate(moras):
                if m.pitch>0:
                    moras[j]=dataclasses.replace(m,pitch=m.pitch+wob*(1 if k%2 else -1)); k+=1
        pm=ap.pause_mora
        if pm is not None:
            if isinstance(pm,dict): pm=Mora(**pm)
            pm=dataclasses.replace(pm,vowel_length=pm.vowel_length*ps)
        aps[i]=dataclasses.replace(ap,moras=moras,pause_mora=pm)
    if l["id"]=="L07":  # clip the ン short for a yelp
        ap=aps[0]; ms=list(ap.moras)
        ms[-1]=dataclasses.replace(ms[-1],vowel_length=ms[-1].vowel_length*1.8)
        aps[0]=dataclasses.replace(ap,moras=ms)
    q=AudioQuery.from_accent_phrases(aps)
    q=dataclasses.replace(q,speed_scale=sp*mul,pitch_scale=pi,intonation_scale=it,volume_scale=vo,
        pre_phoneme_length=0.08,post_phoneme_length=0.12,output_sampling_rate=24000,output_stereo=False)
    wav=syn.synthesis(q, STYLE[l["who"]], enable_interrogative_upspeak=True)
    x,sr=sf.read(io.BytesIO(wav),dtype="float32")
    if x.ndim>1: x=x.mean(1)
    return resample_poly(x,48000,sr).astype(np.float32)
def trim(x,sr=48000,pad=0.03):
    fr=int(sr*0.005); e=np.array([np.sqrt(np.mean(x[i:i+fr]**2)) for i in range(0,len(x),fr)])
    thr=max(e.max()*0.02,1e-4); idx=np.where(e>thr)[0]
    s=max(0,idx[0]*fr-int(pad*sr)); t=min(len(x),(idx[-1]+1)*fr+int(pad*sr))
    y=x[s:t].copy(); f=int(0.005*sr); y[:f]*=np.linspace(0,1,f); y[-f:]*=np.linspace(1,0,f)
    return y
S=json.load(open(f"{D}/script.json")); os.makedirs(f"{D}/voice",exist_ok=True)
LIP={}; track=np.zeros(int(60*48000),np.float32); rep=[]
for l in S["lines"]:
    slot=l["slot_end"]-l["t"]-0.1; mul=1.0
    while True:
        y=trim(synth(l,mul)); d=len(y)/48000
        if d<=slot or mul>=1.25: break
        mul=round(min(1.25,mul+0.03),2)
    e=np.array([np.sqrt(np.mean(y[i:i+480]**2)) for i in range(0,len(y)-480,480)])
    act=e[e>e.max()*0.1]; rms=np.sqrt(np.mean(act**2))
    y=y*(10**(P[l["id"]][6]/20)/rms); pk=np.abs(y).max()
    if pk>0.89: y*=0.89/pk
    pk=np.abs(y).max()
    sf.write(f"{D}/voice/{l['id']}.wav",y,48000,subtype="PCM_16")
    n=int(np.ceil(d*30)); spf=1600
    env=np.array([np.sqrt(np.mean(y[i*spf:(i+1)*spf]**2)) if len(y[i*spf:(i+1)*spf]) else 0 for i in range(n)])
    p95=np.percentile(env,95) or 1
    env=np.clip(env/p95,0,1); env=np.convolve(np.pad(env,1,mode='edge'),[0.25,0.5,0.25],'valid')
    env[env<0.06]=0
    LIP[l["id"]]={"t":l["t"],"dur":round(d,3),"who":l["who"],"env":[round(float(v),2) for v in env]}
    s=int(round(l["t"]*48000)); track[s:s+len(y)]+=y
    rep.append((l["id"],l["who"],round(d,2),"slot",round(l["slot_end"]-l["t"],2),"end",round(l["t"]+d,2),"/",l["slot_end"],"mul",mul,"pk",round(float(20*np.log10(pk)),1)))
sf.write(f"{D}/voice/voice_track.wav",np.clip(track,-1,1),48000,subtype="PCM_16")
open(f"{D}/voice/lipsync.js","w").write("window.LIPSYNC = "+json.dumps(LIP,ensure_ascii=False,separators=(",",":"))+";\n")
for r in rep: print(*r)
