"""DocOn Cinema · áudio: cortes + 1,08x (rubberband) + voz leve + música com ducking + efeitos + loudnorm linear.
Uso a partir do projeto:  audio.build(ed, out_wav, music=None, music_db=-20, voice='light'|'raw', sfx_db=-19, voice_file=None)
  voice='raw' não trata a voz (use quando o cliente mandar áudio já tratado; voice_file = trilha já alinhada à saída)."""
import numpy as np, soundfile as sf, subprocess, json
from scipy.signal import butter, sosfilt
SR = 48000
def _run(args): subprocess.run(['ffmpeg', '-v', 'error', '-y'] + args, check=True)
def _loudnorm_linear(inp, out, I=-16, TP=-1.5, pre=''):
    r = subprocess.run(['ffmpeg', '-hide_banner', '-y', '-i', inp, '-af', (pre + ',' if pre else '') + f'loudnorm=I={I}:TP={TP}:LRA=11:print_format=json', '-f', 'null', '-'], capture_output=True, text=True).stderr
    m = json.loads(r[r.rfind('{'):r.rfind('}') + 1])
    ln = (f"loudnorm=I={I}:TP={TP}:LRA=11:linear=true:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
          f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}")
    _run(['-i', inp, '-af', (pre + ',' if pre else '') + ln, '-ar', str(SR), '-ac', '2', out])
def whoosh(rng, d=0.5):
    n = int(d * SR); t = np.arange(n) / SR; x = rng.normal(0, 1, n); out = np.zeros(n)
    for i in range(0, n, 512):
        f = 600 + 3200 * np.sin(np.pi * min(i / n, 1)) ** 2
        out[i:i + 512] = sosfilt(butter(2, [f * 0.6, min(f * 1.6, 20000)], btype='band', fs=SR, output='sos'), x[max(0, i - 2048):i + 512])[-len(out[i:i + 512]):]
    y = out * np.sin(np.pi * t / d) ** 2 * np.exp(-1.2 * t / d); return y / np.abs(y).max()
def tick():
    t = np.arange(int(0.09 * SR)) / SR; y = (np.sin(2 * np.pi * 2400 * t) * 0.6 + np.sin(2 * np.pi * 3600 * t) * 0.3) * np.exp(-t / 0.012); return y / np.abs(y).max()
def build(ed, out, music=None, music_db=-20.0, duck_db=7.0, voice='light', sfx_db=-19.0, voice_file=None):
    wd = ed.wd; tmp = wd + '/_a'
    import os; os.makedirs(tmp, exist_ok=True)
    if voice_file is None:
        _run(['-i', ed.video, '-vn', '-ac', '2', '-ar', str(SR), '-c:a', 'pcm_f32le', tmp + '/src.wav'])
        a, _ = sf.read(tmp + '/src.wav'); parts = []; fd = int(0.008 * SR)
        for x, y in ed.SEGS:
            p = a[int(x * SR):int(y * SR)].copy(); r = np.linspace(0, 1, fd)[:, None]; p[:fd] *= r; p[-fd:] *= r[::-1]; parts.append(p)
        sf.write(tmp + '/cut.wav', np.concatenate(parts), SR, subtype='FLOAT')
        chain = f'rubberband=tempo={ed.speed}:pitch=1:formant=preserved:transients=smooth' if abs(ed.speed - 1) > 1e-3 else 'anull'
        if voice == 'light':
            chain += ',highpass=f=80,equalizer=f=250:t=q:w=1.0:g=-1.5,equalizer=f=3300:t=q:w=1.2:g=1.5,deesser=i=0.25:m=0.5:f=0.5'
        _run(['-i', tmp + '/cut.wav', '-af', chain, '-ar', str(SR), '-ac', '2', '-c:a', 'pcm_f32le', tmp + '/v.wav'])
        v, _ = sf.read(tmp + '/v.wav')
    else:
        v, _ = sf.read(voice_file)
        if v.ndim == 1: v = np.stack([v, v], 1)
    n = int(round(ed.TOTAL * SR)); voice_ = np.zeros((n, 2)); m = min(n, len(v)); voice_[:m] = v[:m]
    f = int(0.02 * SR); r = np.linspace(0, 1, f)[:, None]; voice_[:f] *= r; voice_[m - f:m] *= r[::-1]
    # nível de referência da voz (RMS das partes faladas)
    mono = voice_.mean(1); hop = int(0.05 * SR); nb = n // hop
    env = np.sqrt((mono[:nb * hop].reshape(nb, hop) ** 2).mean(1) + 1e-12); edb = 20 * np.log10(env)
    vref = np.percentile(edb[edb > edb.max() - 40], 70)
    mix = voice_.copy()
    if music:
        mu, _ = sf.read(music)
        if mu.ndim == 1: mu = np.stack([mu, mu], 1)
        mm = np.zeros((n, 2)); k = min(n, len(mu)); mm[:k] = mu[:k]
        mb = mm.mean(1); menv = np.sqrt((mb[:nb * hop].reshape(nb, hop) ** 2).mean(1) + 1e-12); mref = np.percentile(20 * np.log10(menv), 70)
        g0 = 10 ** ((vref + music_db - mref) / 20)                     # música em music_db abaixo da voz
        speaking = (edb > vref - 18).astype(float)                      # ducking: atack 60 ms, release 450 ms
        g = np.zeros(nb); s = 0.0
        for i in range(nb):
            tgt = speaking[i]; c = 0.55 if tgt > s else 0.10; s += (tgt - s) * c; g[i] = s
        gain = g0 * 10 ** (-duck_db * g / 20)
        gain = np.interp(np.arange(n), np.arange(nb) * hop + hop / 2, gain)
        gain[-int(ed.tail * SR):] *= np.linspace(1, 1.6, int(ed.tail * SR))   # sobe um pouco no respiro final
        mix += mm * gain[:, None]
    rng = np.random.default_rng(3); Wh, Ti = whoosh(rng), tick(); lvl = 10 ** ((vref + sfx_db) / 20) * 2.5
    cache = {}
    for ent in json.load(open(wd + '/sfx.json')):
        t, kind = ent[0], ent[1]; g = ent[2] if len(ent) > 2 else 1.0
        if str(kind).startswith('file:'):                       # efeito do banco do Studio (wav já convertido)
            fp = kind[5:]
            if fp not in cache:
                x, _ = sf.read(fp); cache[fp] = x.mean(1) if x.ndim > 1 else x
            s_ = cache[fp] / (np.abs(cache[fp]).max() + 1e-9); st = int(max(t, 0) * SR)
        else:
            s_ = Wh if kind == 'whoosh' else Ti * 0.8; st = int(max(t - (0.18 if kind == 'whoosh' else 0), 0) * SR)
        e = min(st + len(s_), n)
        if e > st: mix[st:e] += (s_[:e - st] * lvl * g)[:, None]
    sf.write(tmp + '/mix_pre.wav', mix.astype(np.float32), SR, subtype='FLOAT')
    if voice == 'raw' and voice_file is not None:
        pk = np.abs(mix).max(); lim = 10 ** (-1.5 / 20)
        if pk > lim: mix *= lim / pk
        sf.write(out, mix.astype(np.float32), SR, subtype='FLOAT')
    else:
        _loudnorm_linear(tmp + '/mix_pre.wav', out, -16, -1.5)
    return out
