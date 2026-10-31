"""DocOn Cinema · efeitos visuais dos blocos "fx" do briefing (mesma lógica da prévia ao vivo do DocOn Studio).

Cada efeito é {'k': chave, 't0', 't1' (s de saída), 'I': intensidade}. `video(ed, fr, t)` age só sobre o vídeo
(antes dos grafismos: zoom, tremor, whip, desfoque, P&B, quente, brilho); `under(fr, t)` sobrepõe luz e vinheta
abaixo dos grafismos; `top(fr, t)` faz flash e grão por cima de tudo.
Chaves: zoom, flash, leak, shake, whip, glow, desfoque, grao, vinheta, bokeh, pb, quente.
"""
import math
import numpy as np, cv2

INT = {'suave': 0.6, 'média': 1.0, 'media': 1.0, 'forte': 1.5}
W, H = 1080, 1920
def eo(x): x = min(max(x, 0.0), 1.0); return 1 - (1 - x) ** 3
def _rnd(n): x = math.sin(n * 127.1 + 311.7) * 43758.5453; return x - math.floor(x)

class FX:
    def __init__(self): self.items = []; self._grain = None; self._yy = None
    def add(self, k, t0, t1, intensidade='média'): self.items.append(dict(k=k, t0=t0, t1=max(t1, t0 + 0.1), I=INT.get(intensidade, 1.0)))
    def _act(self, t):
        for e in self.items:
            if e['t0'] <= t <= e['t1']:
                d = e['t1'] - e['t0']; x = (t - e['t0']) / d
                yield e, x, math.sin(math.pi * x), min(eo((t - e['t0']) / 0.2), eo((e['t1'] - t) / 0.2))
    def video(self, fr, t):
        sc, tx, ty, blur, bright, sat, gray, sep = 1.0, 0.0, 0.0, 0.0, 1.0, 1.0, 0.0, 0.0
        for e, x, bell, fade in self._act(t):
            k, I = e['k'], e['I']
            if k == 'zoom': sc *= 1 + 0.08 * I * min(eo((t - e['t0']) / 0.12), eo((e['t1'] - t) / 0.25))
            elif k == 'shake': a = (1 - x) * 0.016 * I; tx += math.sin(t * 90) * a * W; ty += math.cos(t * 73) * a * 0.6 * H
            elif k == 'whip': s = math.sin(math.pi * x); tx += (-1 if x < 0.5 else 1) * s * 0.3 * min(1, I) * W; blur += s * 18 * I
            elif k == 'desfoque': blur += 16 * bell * I
            elif k == 'glow': bright += 0.16 * fade * I; sat += 0.1 * fade * I
            elif k == 'pb': gray = max(gray, fade * min(1, I))
            elif k == 'quente': sep = max(sep, 0.3 * fade * I); sat += 0.15 * fade
        if sc != 1 or tx or ty:
            M = np.float32([[sc, 0, (1 - sc) * W / 2 + tx], [0, sc, (1 - sc) * H * 0.45 + ty]])
            fr = cv2.warpAffine(fr, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        if blur > 0.5:
            if any(e['k'] == 'whip' for e, *_ in self._act(t)): kz = int(blur) * 2 + 1; fr = cv2.blur(fr, (kz, 1))
            else: fr = cv2.GaussianBlur(fr, (0, 0), blur / 2)
        if bright != 1 or sat != 1 or gray or sep:
            y = (fr @ np.float32([0.299, 0.587, 0.114]))[..., None]
            fr = y + (fr - y) * sat * (1 - gray)
            if sep: fr = fr * (1 - sep) + np.clip(y * np.float32([1.07, 0.74, 0.43]) * 1.25, 0, 1) * sep
            fr = np.clip(fr * bright, 0, 1)
        return fr
    def under(self, fr, t):
        for e, x, bell, fade in self._act(t):
            k, I = e['k'], min(1.0, e['I'])
            if k == 'leak':
                if self._yy is None: self._yy = np.mgrid[0:H // 4, 0:W // 4].astype(np.float32)
                yy, xx = self._yy; u = (xx * 4 + yy * 4 * 0.36) / (W + H * 0.36) - (-0.25 + 1.2 * x)
                m = np.exp(-(u / 0.09) ** 2) * 0.85 * I * bell; m = cv2.resize(m, (W, H))[..., None]
                fr = 1 - (1 - fr) * (1 - m * np.float32([1.0, 0.77, 0.47]))
            elif k == 'glow':
                g = cv2.GaussianBlur(cv2.resize(fr, (W // 8, H // 8)), (0, 0), 6); g = cv2.resize(g, (W, H))
                fr = 1 - (1 - fr) * (1 - g * 0.25 * fade * I)
            elif k == 'vinheta':
                if self._yy is None: self._yy = np.mgrid[0:H // 4, 0:W // 4].astype(np.float32)
                yy, xx = self._yy; r = np.sqrt(((xx * 4 - W / 2) / (W * 0.95)) ** 2 + ((yy * 4 - H * 0.42) / (H * 0.7)) ** 2)
                v = cv2.resize(np.clip((r - 0.38) / 0.62, 0, 1) * 0.8 * fade * I, (W, H))[..., None]; fr = fr * (1 - v)
            elif k == 'bokeh':
                lay = np.zeros((H // 2, W // 2), np.float32)
                for i in range(10):
                    s = (6 + _rnd(i + 9) * 14) / 100 * W / 2; cy = ((_rnd(i + 3) * 120 - 10) - ((t - e['t0']) * (4 + _rnd(i) * 6)) % 130) / 100 * H / 2
                    cv2.circle(lay, (int(_rnd(i + 1) * W / 2), int(cy)), int(s / 2), (0.4 + 0.6 * _rnd(i + 5)) * fade * I, -1, cv2.LINE_AA)
                lay = cv2.resize(cv2.GaussianBlur(lay, (0, 0), 6), (W, H))[..., None]
                fr = 1 - (1 - fr) * (1 - lay * np.float32([1.0, 0.89, 0.67]) * 0.75)
        return fr
    def top(self, fr, t):
        for e, x, bell, fade in self._act(t):
            k, I = e['k'], min(1.0, e['I'])
            if k == 'flash': a = x / 0.15 if x < 0.15 else 1 - (x - 0.15) / 0.85; a = 0.9 * I * a * a; fr = fr * (1 - a) + a
            elif k == 'grao':
                if self._grain is None: self._grain = [np.random.default_rng(i).normal(0, 1, (H // 2, W // 2)).astype(np.float32) for i in range(6)]
                g = cv2.resize(self._grain[int(t * 24) % 6], (W, H))[..., None] * 0.045 * fade * e['I']
                fr = np.clip(fr + g, 0, 1)
        return fr
