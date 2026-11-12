++ b/tests/reference/tap_eq_reference_check.py
import numpy as np
def peaking(fs,f0,gain_db,q):
    A=10**(gain_db/40); w=2*np.pi*f0/fs; al=np.sin(w)/(2*q); c=np.cos(w)
    b=[1+al*A,-2*c,1-al*A]; a=[1+al/A,-2*c,1-al/A]
    return [x/a[0] for x in b],[x/a[0] for x in a]
def lowshelf(fs,f0,gain_db,q):
    A=10**(gain_db/40); w=2*np.pi*f0/fs; c=np.cos(w); al=np.sin(w)/(2*q); s=2*np.sqrt(A)*al
    b0=A*((A+1)-(A-1)*c+s); b1=2*A*((A-1)-(A+1)*c); b2=A*((A+1)-(A-1)*c-s)
    a0=(A+1)+(A-1)*c+s; a1=-2*((A-1)+(A+1)*c); a2=(A+1)+(A-1)*c-s
    return [b0/a0,b1/a0,b2/a0],[1,a1/a0,a2/a0]
def mag(b,a,fs,f):
    z=np.exp(-1j*2*np.pi*f/fs); return abs((b[0]+b[1]*z+b[2]*z*z)/(a[0]+a[1]*z+a[2]*z*z))
fs=44100
for f0 in [32,1000,16000]:
    b,a=peaking(fs,f0,9,1.4142); print("peak",f0,"gain dB at f0:",round(20*np.log10(mag(b,a,fs,f0)),3))
b,a=lowshelf(fs,90,10,0.7); print("lowshelf dc dB:",round(20*np.log10(mag(b,a,fs,1)),3),"hf dB:",round(20*np.log10(mag(b,a,fs,10000)),3))
b,a=peaking(fs,1000,0,1.4142); print("zero-gain is identity:",np.allclose(b,a))
# stability of all 16 at 48k with +12
fr=[32,64,125,250,500,1000,2000,3000,4000,5000,6000,7000,8000,10000,12000,16000]
for fs in (44100,48000):
    ok=all(np.all(np.abs(np.roots(peaking(fs,f,12,1.4142)[1]))<1) for f in fr if f<0.45*fs); print(fs,"stable:",ok)