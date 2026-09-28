# voice + bgm + sfx をダッキング付きでミックス → soundtrack.wav (48k stereo)
import numpy as np, json, wave, sys
SR=48000; N=SR*60
def rd(p):
    w=wave.open(p); sr=w.getframerate(); ch=w.getnchannels(); a=np.frombuffer(w.readframes(w.getnframes()),dtype=np.int16).astype(np.float32)/32768
    a=a.reshape(-1,ch)
    assert sr==SR, (p,sr)
    if ch==1: a=np.repeat(a,2,axis=1)
    out=np.zeros((N,2),np.float32); n=min(N,len(a)); out[:n]=a[:n]; return out
SP=sys.argv[1]
v=rd(SP+'/voice/voice_track.wav'); b=rd(SP+'/audio/bgm.wav'); s=rd(SP+'/audio/sfx.wav')
# ダッキング用エンベロープ（声の有無）
env=np.abs(v[:,0]); win=int(SR*0.25)
k=np.ones(win)/win; e=np.convolve(env,k,'same'); e=np.clip(e/ (np.percentile(e[e>1e-4],50)+1e-9),0,1)
# attack/release smoothing
g=np.zeros(N,np.float32); a_=1-np.exp(-1/(SR*0.05)); r_=1-np.exp(-1/(SR*0.4)); cur=0
for i in range(0,N,64):
    tgt=e[i]; cur+= (a_ if tgt>cur else r_)*64*(tgt-cur); g[i:i+64]=cur
duck=1-0.45*np.clip(g,0,1)
mix=1.0*v + float(sys.argv[2] if len(sys.argv)>2 else 0.5)*b*duck[:,None] + 0.8*s*(1-0.25*np.clip(g,0,1))[:,None]
pk=np.max(np.abs(mix)); mix=mix/pk*0.93 if pk>0.93 else mix
# 最後はきっちり無音へ
fade=np.ones(N); fade[-int(SR*0.3):]=np.linspace(1,0,int(SR*0.3)); mix*=fade[:,None]
o=wave.open(SP+'/soundtrack.wav','wb'); o.setnchannels(2); o.setsampwidth(2); o.setframerate(SR)
o.writeframes((np.clip(mix,-1,1)*32767).astype(np.int16).tobytes()); o.close()
for sec in range(0,60,5): print(sec, round(float(np.sqrt(np.mean(mix[sec*SR:(sec+5)*SR]**2))),3))
