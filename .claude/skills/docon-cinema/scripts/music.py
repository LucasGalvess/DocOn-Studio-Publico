"""DocOn Cinema · trilha de fundo sintetizada (sem direitos autorais): violão dedilhado (Karplus-Strong), pad, baixo, percussão leve.
uso: python3 music.py OUT.wav DURACAO_S [--bpm 92] [--key D] [--mood warm|calm]"""
import numpy as np, soundfile as sf, sys
from scipy.signal import lfilter, butter, sosfilt, fftconvolve
out, dur = sys.argv[1], float(sys.argv[2])
def arg(n, d): return type(d)(sys.argv[sys.argv.index(n) + 1]) if n in sys.argv else d
BPM = arg('--bpm', 92.0); KEY = arg('--key', 'D'); MOOD = arg('--mood', 'warm')
sr = 48000; rng = np.random.default_rng(11)
NOTE = {'C': 0, 'C#': 1, 'D': 2, 'D#': 3, 'E': 4, 'F': 5, 'F#': 6, 'G': 7, 'G#': 8, 'A': 9, 'A#': 10, 'B': 11}
root = 48 + NOTE[KEY]                          # C3 + tonalidade
def hz(m): return 440 * 2 ** ((m - 69) / 12)
# I – V – vi – IV (graus em semitons + tríade)
PROG = [(0, [0, 4, 7]), (7, [0, 4, 7]), (9, [0, 3, 7]), (5, [0, 4, 7])]
if MOOD == 'calm': PROG = [(0, [0, 4, 7, 11]), (9, [0, 3, 7, 10]), (5, [0, 4, 7, 11]), (7, [0, 4, 7])]
beat = 60 / BPM; bar = 4 * beat; n = int((dur + 2) * sr)
L = np.zeros(n); R = np.zeros(n)
def add(sig, t, pan=0.0, g=1.0):
    i = max(0, int(t * sr)); j = min(n, i + len(sig))
    if j <= i: return
    s = sig[:j - i] * g; L[i:j] += s * np.sqrt((1 - pan) / 2); R[i:j] += s * np.sqrt((1 + pan) / 2)
def pluck(f, d=2.2, bright=0.5):
    Np = int(sr / f); m = int(d * sr)
    x = np.zeros(m); x[:Np] = rng.uniform(-1, 1, Np)
    x[:Np] = sosfilt(butter(1, 1500 + 4000 * bright, fs=sr, output='sos'), x[:Np])
    dec = 0.996 if f < 300 else 0.993
    a = np.zeros(Np + 2); a[0] = 1; a[Np] = -dec / 2; a[Np + 1] = -dec / 2
    y = lfilter([1], a, x); y *= np.exp(-np.arange(m) / sr * 0.8)
    return y / (np.abs(y).max() + 1e-9)
def pad(freqs, d):
    m = int(d * sr); t = np.arange(m) / sr; y = np.zeros(m)
    for f in freqs:
        for det in (-0.12, 0.0, 0.11):
            ph = rng.uniform(0, 2 * np.pi); ff = f * 2 ** (det / 12)
            y += np.sin(2 * np.pi * ff * t + ph) + 0.25 * np.sin(4 * np.pi * ff * t + ph) + 0.1 * np.sin(6 * np.pi * ff * t + ph)
    env = np.minimum(1, t / 0.9) * np.minimum(1, (d - t) / 0.9).clip(0)
    y = sosfilt(butter(2, 1800, fs=sr, output='sos'), y * env); return y / (np.abs(y).max() + 1e-9)
def bass(f, d):
    m = int(d * sr); t = np.arange(m) / sr
    y = np.sin(2 * np.pi * f * t) + 0.3 * np.sin(4 * np.pi * f * t); env = np.minimum(1, t / 0.02) * np.exp(-t * 1.6)
    return y * env
def kick():
    m = int(0.35 * sr); t = np.arange(m) / sr; f = 45 + 70 * np.exp(-t * 28)
    return np.sin(2 * np.pi * np.cumsum(f) / sr) * np.exp(-t * 9)
def shaker(d=0.07):
    m = int(d * sr); x = rng.normal(0, 1, m); x = sosfilt(butter(2, [5000, 12000], btype='band', fs=sr, output='sos'), x)
    t = np.arange(m) / sr; return x * np.exp(-t * 60) / 3
def rim():
    m = int(0.12 * sr); t = np.arange(m) / sr; x = sosfilt(butter(2, [1800, 4500], btype='band', fs=sr, output='sos'), rng.normal(0, 1, m))
    return (x / 2 + 0.6 * np.sin(2 * np.pi * 820 * t)) * np.exp(-t * 45)
nbars = int(np.ceil((dur + 2) / bar)); K = kick()
for b in range(nbars):
    deg, tri = PROG[b % 4]; t0 = b * bar; base = root + deg
    sec = 0 if b < 2 else (1 if b < nbars - 2 else 2)        # intro / corpo / final
    chord = [base + 12 + iv for iv in tri]
    add(pad([hz(m) for m in chord], bar + 0.9), t0, 0, 0.16 if sec != 1 else 0.13)
    # dedilhado em colcheias: padrão 1-5-3-5-8-5-3-5 com leve swing e humanização
    pat = [0, 2, 1, 2, 3, 2, 1, 2]; notes = chord + [chord[0] + 12]
    for s in range(8):
        tt = t0 + s * beat / 2 + (0.018 if s % 2 else 0) + rng.normal(0, 0.004)
        mnote = notes[pat[s] % len(notes)] + (12 if s in (4,) else 0)
        add(pluck(hz(mnote), 1.6, 0.35 + 0.2 * rng.random()), tt, pan=(-0.35 if s % 2 else 0.3), g=(0.42 if s % 4 == 0 else 0.30) * (0.8 if sec == 0 else 1))
    if sec >= 1 or b == 1:
        add(bass(hz(base - 12), bar * 0.5), t0, 0, 0.42); add(bass(hz(base - 12 + (7 if b % 2 else 0)), bar * 0.5), t0 + 2 * beat, 0, 0.32)
    if sec == 1:
        for q in range(4):
            if q in (0, 2): add(K, t0 + q * beat, 0, 0.55)
            if q in (1, 3): add(rim(), t0 + q * beat, 0.1, 0.22)
        for s in range(8): add(shaker(), t0 + s * beat / 2 + (0.02 if s % 2 else 0), 0.45, 0.16 if s % 2 else 0.10)
# reverb (IR de ruído com decaimento exponencial, estéreo descorrelacionado)
irl = int(1.9 * sr); t = np.arange(irl) / sr
def ir(): x = rng.normal(0, 1, irl) * np.exp(-t * 3.4); x = sosfilt(butter(2, 5500, fs=sr, output='sos'), x); return x / np.sqrt((x ** 2).sum())
wl = fftconvolve(L, ir())[:n]; wr = fftconvolve(R, ir())[:n]
L, R = L + 0.30 * wl, R + 0.30 * wr
y = np.stack([L, R], 1)[:int(dur * sr)]
# fade-in curto, fade-out de 2,5 s, tom quente (corta sibilância acima de 9 kHz)
y = sosfilt(butter(2, 9000, fs=sr, output='sos'), y, axis=0)
m = len(y); fi = int(0.6 * sr); fo = int(2.5 * sr)
y[:fi] *= np.linspace(0, 1, fi)[:, None]; y[-fo:] *= np.linspace(1, 0, fo)[:, None] ** 1.5
y /= np.abs(y).max() / 0.7
sf.write(out, y.astype(np.float32), sr, subtype='FLOAT'); print('ok', round(m / sr, 2), 's', BPM, 'bpm', KEY)
