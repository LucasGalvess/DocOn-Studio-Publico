"""DocOn Cinema · núcleo do compositor.

Um projeto (script curto escrito por vídeo) cria um `Edit`, descreve o conteúdo
(gancho, painéis, lower third, legenda, cartão final, B-roll) e chama `render()`.
Tudo é sincronizado pelas palavras da transcrição: `ed.t('palavra')` devolve o
tempo de saída (já com cortes e 1,08x) da palavra.
"""
import json, math, os, subprocess
import numpy as np, cv2, soundfile as sf
from PIL import Image, ImageDraw, ImageFilter, ImageChops
from scipy.ndimage import gaussian_filter1d
import gfx
from gfx import *
from fx import FX

W, H, FPS = 1080, 1920, 30
def ease(x): x = min(max(x, 0), 1); return x * x * (3 - 2 * x)
def ease_out(x): x = min(max(x, 0), 1); return 1 - (1 - x) ** 3
def elastic(p): return 1.0 if p >= 1 else 1 - math.exp(-6 * p) * math.cos(p * 11)
def to_np(im): return np.asarray(im).astype(np.float32) / 255
def norm(w): return w.lower().strip('.,?!:;…"“”')

def over(dst, spr, x, y, op=1.0, scale=1.0, cx=None, cy=None):
    """Compõe sprite RGBA float em dst (RGB float). (x,y)=canto sup. esq.; escala em torno de (cx,cy)."""
    if op <= 0.003: return
    if abs(scale - 1) > 1e-3:
        h0, w0 = spr.shape[:2]
        if cx is None: cx, cy = x + w0 / 2, y + h0 / 2
        spr = cv2.resize(spr, (max(1, int(w0 * scale)), max(1, int(h0 * scale))), interpolation=cv2.INTER_LINEAR)
        x, y = cx - (cx - x) * scale, cy - (cy - y) * scale
    x, y = int(round(x)), int(round(y)); h, w = spr.shape[:2]
    x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + w, W), min(y + h, H)
    if x1 <= x0 or y1 <= y0: return
    s = spr[y0 - y:y1 - y, x0 - x:x1 - x]; a = s[..., 3:4] * op
    dst[y0:y1, x0:x1] = dst[y0:y1, x0:x1] * (1 - a) + s[..., :3] * a

# ======================================================================= look (para B-roll)
_x = np.linspace(0, 1, 4096); _y = _x ** 0.94; _y = 0.5 + (_y - 0.5) * 0.92; _y = 0.015 + 0.985 * np.clip(_y, 0, None)
_hi = _y > 0.88; _y[_hi] = 0.88 + 0.12 * np.tanh((_y[_hi] - 0.88) / 0.12 * 1.15) / np.tanh(1.15)
LOOK_LUT = np.clip(_y, 0, 1).astype(np.float32)
def look(rgb):
    """mesmo look natural do grade (cinza-mundo leve + curva + saturação) para quadros RGB float."""
    m = rgb.reshape(-1, 3).mean(0); g = np.clip(m[1] / np.maximum(m, 1e-3), 0.85, 1.2); g = 1 + (g - 1) * 0.5
    img = np.clip(rgb * g, 0, 1); img = LOOK_LUT[np.clip(img * 4095, 0, 4095).astype(np.int32)]
    hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV); hsv[..., 1] = np.clip(hsv[..., 1] * 1.18, 0, 1)
    return cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)

class Reader:
    def __init__(self, path): self.cap = cv2.VideoCapture(path); self.i = -1; self.cache = {}
    def get(self, i):
        while self.i < i:
            ok, f = self.cap.read(); self.i += 1
            if not ok: f = self.last
            self.last = f
            if f.shape[0] != H or f.shape[1] != W: f = cv2.resize(f, (W, H), interpolation=cv2.INTER_CUBIC)   # proxy 720p do Studio etc.: trabalha sempre em 1080x1920
            self.cache[self.i] = cv2.cvtColor(f, cv2.COLOR_BGR2RGB).astype(np.float32) / 255
            for k in list(self.cache):
                if k < self.i - 3: del self.cache[k]
        return self.cache[i]

# ======================================================================= Edit
class Edit:
    def __init__(self, video, wd, speed=1.08, tail=1.3, cut_pauses=True, min_pause=0.35, keep=0.06,
                 fixes=(), anchor_y=0.42, sharpen=0.45, vignette=0.05, remove=(), sem_fala=False):
        self.video, self.wd, self.speed, self.tail = video, wd, speed, tail
        info = json.load(open(wd + '/shots.json')); self.CUTS = info['cuts']; self.NF = info['n']; self.SFPS = info['fps']
        self.corr = np.load(wd + '/corr.npy'); self.LM = np.load(wd + '/lms.npy')
        _c = cv2.VideoCapture(video); _sw = _c.get(cv2.CAP_PROP_FRAME_WIDTH) or W; _c.release()
        if abs(_sw - W) > 1:                     # bruto fora de 1080 de largura (ex.: proxy 720p): rostos e estabilização na escala da saída
            k = W / _sw; self.LM = self.LM * k; self.corr = self.corr.copy(); self.corr[:, :2] *= k
        self.sharpen, self.vig_amt = sharpen, vignette
        raw = json.load(open(wd + '/words_raw.json'))
        # ---- correções de transcrição: {'old','new'[,'near']} troca; {'after','insert':[(w,t),..]} insere; {'old','drop':True}
        words = [] if sem_fala else [[x[0], x[1]] for x in raw]     # Reels Dinâmico: sem fala, o vídeo inteiro conta
        for fx in fixes:
            if 'insert' in fx:
                k = next(i for i, (w, s) in enumerate(words) if norm(w) == norm(fx['after']) and abs(s - fx.get('near', s)) < 0.6)
                words[k + 1:k + 1] = [list(p) for p in fx['insert']]
                continue
            for i, (w, s) in enumerate(words):
                if norm(w) == norm(fx['old']) and ('near' not in fx or abs(s - fx['near']) < 0.6):
                    if fx.get('drop'): words.pop(i)
                    else: words[i][0] = fx['new']
                    break
            else: raise KeyError('fix não encontrado: %r' % (fx,))
        dur_src = self.NF / self.SFPS
        # ---- segmentos mantidos (corta pausas > min_pause, preservando `keep` s de cada lado)
        sil = []
        if cut_pauses and words:
            a, sr = sf.read(wd + '/a16.wav'); hop = 160
            rms = np.array([np.sqrt(np.mean(a[i:i + 320] ** 2)) for i in range(0, len(a) - 320, hop)]); db = 20 * np.log10(rms + 1e-9)
            thr = np.percentile(db, 20) + 6; s_ = db < thr; i = 0
            while i < len(s_):
                if s_[i]:
                    j = i
                    while j < len(s_) and s_[j]: j += 1
                    if (j - i) * 0.01 >= min_pause and i > 0: sil.append((i * 0.01 + keep, j * 0.01 - keep))
                    i = j
                else: i += 1
        segs = []; s0 = max(0.0, words[0][1] - 0.12) if words else 0.0
        for a_, b_ in sil:
            if a_ > s0 + 0.2: segs.append((s0, a_)); s0 = b_
        end = min(dur_src - 0.02, words[-1][1] + 0.9) if words else dur_src - 0.02
        segs.append((s0, end))
        for ra, rb in sorted(remove):                       # trechos marcados como corte no briefing (tempo do bruto)
            out_ = []
            for a_, b_ in segs:
                if rb <= a_ or ra >= b_: out_.append((a_, b_)); continue
                if ra - a_ > 0.15: out_.append((a_, ra))
                if b_ - rb > 0.15: out_.append((rb, b_))
            segs = out_
        words = [w for w in words if not any(ra <= w[1] < rb for ra, rb in remove)]
        self.SEGS = segs
        self.CUM = [0]
        for a_, b_ in segs: self.CUM.append(self.CUM[-1] + b_ - a_)
        self.DUR = self.CUM[-1] / speed; self.TOTAL = self.DUR + tail
        self.WORDS = []
        for i, (w, s) in enumerate(words):
            nxt = words[i + 1][1] if i + 1 < len(words) else end
            e = min(nxt - 0.02, s + 0.7)
            self.WORDS.append(dict(w=w, s=s, e=e, os=self.src2out(s), oe=self.src2out(e)))
        self.panels, self.sfx, self.hook_items, self.brolls = [], [], [], []
        self.fx = FX()                                         # efeitos visuais dos blocos fx (scripts/fx.py)
        self.lt = None; self.ec = None; self.ec0 = None; self.ec_blur = 0.5; self.bg_blurs = []; self.textos = []; self.motions = []; self.escuros = []; self.pretos = []; self.escuro = 0.0; self.splits = []; self.cap_y0 = 1585; self.cap_split_y = None; self.logo = None; self.hook_end = 0.0; self.cap_lines = []; self.topics = []
        self.anchor_y = anchor_y
        self._face_track()
    # ---------------- tempo
    def src2out(self, t):
        for (a, b), c in zip(self.SEGS, self.CUM):
            if t < b: return (c + max(t, a) - a) / self.speed
        return self.CUM[-1] / self.speed
    def out2src(self, t):
        x = t * self.speed
        for k, ((a, b), c) in enumerate(zip(self.SEGS, self.CUM)):
            if x < self.CUM[k + 1] or k == len(self.SEGS) - 1: return a + min(x - c, b - a - 1e-4), k
    def wi(self, w, after=0.0):
        for i, d in enumerate(self.WORDS):
            if d['os'] >= after - 1e-6 and norm(d['w']) == norm(w): return i
        raise KeyError(w)
    def t(self, w, after=0.0): return self.WORDS[self.wi(w, after)]['os']
    def shot_of(self, i): return int(np.searchsorted(self.CUTS, i, side='right') - 1)
    # ---------------- estabilização + âncora
    def M_of(self, i, Z0=1.07):
        dx, dy, da = self.corr[i]; c, s = np.cos(da) * Z0, np.sin(da) * Z0; cx, cy = W / 2, H / 2
        return np.array([[c, -s, cx - c * cx + s * cy + dx * Z0], [s, c, cy - s * cx - c * cy + dy * Z0]])
    def _face_track(self):
        F = np.full((self.NF, 2), np.nan)
        for i in range(self.NF):
            if not np.isnan(self.LM[i, 0, 0]):
                M = self.M_of(i); F[i] = M[:, :2] @ self.LM[i].mean(0) + M[:, 2]
        for a, b in zip(self.CUTS, self.CUTS[1:]):
            seg = F[a:b]; ok = ~np.isnan(seg[:, 0])
            if ok.sum() < (b - a) * 0.5: seg[:] = [W / 2, H * self.anchor_y]
            else:
                idx = np.arange(b - a)
                for j in range(2): seg[:, j] = gaussian_filter1d(np.interp(idx, idx[ok], seg[ok, j]), 10, mode='nearest')
            F[a:b] = seg
        self.FACE = F
    # ---------------- câmera: empurrão lento por trecho, dolly nos temas, troca seca de enquadramento só nas emendas
    def camera(self, topics=(), push=0.012, dolly=0.05, alt=1.04):
        b = set(c / self.speed for c in self.CUM[1:-1])
        for c in self.CUTS[1:-1]:
            ts = c / self.SFPS
            if any(a < ts < bb for a, bb in self.SEGS): b.add(self.src2out(ts))
        bounds = sorted(b); tr = []; prev = 0.0
        for x in bounds + [self.TOTAL + 1]:
            if x - prev > 0.05: tr.append([prev, x])
            prev = x
        plan = []; k = 0
        for a, bb in tr:
            dl = any(abs(a - t) < 0.4 for t in topics) or any(a < t < a + 0.6 for t in topics)
            seam_in_shot = any(abs(a - c / self.speed) < 1e-3 for c in self.CUM[1:-1])
            if dl: base = 1.0; k = 1
            elif seam_in_shot: base = [1.0, alt][k % 2]; k += 1
            else: base = 1.0; k = 1
            plan.append((a, bb, base, dl))
        self.plan = plan; self.push = push; self.dolly = dolly
    # ---- zoom / câmera manual (blocos "camera" do Studio): aproxima no ponto de foco, com movimento suave entre focos
    def zoom_on(self, t0, t1, z=1.6, fx=0.5, fy=0.45, d=0.7):
        """t0..t1 em tempo de saída; fx, fy = ponto de foco no quadro (0..1), que fica a ~40% da altura da tela;
        d = duração do movimento de entrada/saída/troca de foco (ease in-out, como câmera)."""
        if not hasattr(self, 'cams'): self.cams = []
        self.cams.append((float(t0), float(t1), max(1.0, float(z)), min(max(float(fx), 0), 1), min(max(float(fy), 0), 1), max(0.05, float(d))))
        self.cams.sort()
    def _cam_state(self, t):
        for a, b, z, fx, fy, d in getattr(self, 'cams', []):
            if a <= t < b: return np.array([z, fx, fy])
        return np.array([1.0, 0.5, 0.5])
    def cam_at(self, t):
        cams = getattr(self, 'cams', [])
        if not cams: return None
        bounds = sorted({(round(a, 3), d) for a, b, z, fx, fy, d in cams} | {(round(b, 3), d) for a, b, z, fx, fy, d in cams})
        for B, d in bounds:
            if B > 0.05 and B - d / 2 <= t < B + d / 2:          # no 1º quadro do vídeo já começa no zoom
                s0, s1 = self._cam_state(B - d / 2 - 1e-3), self._cam_state(B + d / 2 + 1e-3)
                if not np.allclose(s0, s1): return s0 + (s1 - s0) * (0.5 - 0.5 * math.cos(math.pi * (t - (B - d / 2)) / d))
        return self._cam_state(t)
    def zoom_at(self, t):
        for a, b, base, dl in self.plan:
            if a <= t < b:
                z = base * (1 + self.push * (t - a) / max(b - a, 0.5))
                if dl: z *= 1 + self.dolly * ease((t - a) / 1.9)
                return z
        return 1.0
    def src_pos(self, t):
        if t >= self.DUR - 1e-6: t = self.DUR - 1e-3
        ts, k = self.out2src(t); a, b = self.SEGS[k]
        lo, hi = math.ceil(a * self.SFPS), min(int(b * self.SFPS), self.NF - 1)
        fp = min(max(ts * self.SFPS, lo), hi); i0 = int(fp); i1 = min(i0 + 1, hi); w = fp - i0
        if self.shot_of(i1) != self.shot_of(i0): i1 = i0; w = 0
        return i0, i1, w
    _vig = None
    def vignette(self):
        if self._vig is None:
            y, x = np.mgrid[0:H, 0:W]; r = np.sqrt(((x - W / 2) / (W * .62)) ** 2 + ((y - H * .45) / (H * .62)) ** 2)
            self._vig = (1 - self.vig_amt * np.clip(r - 0.35, 0, 1) ** 1.6 / 0.65 ** 1.6)[..., None].astype(np.float32)
        return self._vig
    def video_layer(self, reader, t):
        i0, i1, w = self.src_pos(t)
        w = min(max((w - 0.5) * 2.2 + 0.5, 0), 1)            # mistura ponderada "seca": sem fantasma
        z = self.zoom_at(t); ax, ay = self.FACE[i0] if w < .5 else self.FACE[i1]
        if t > self.DUR: z *= 1 + 0.01 * (t - self.DUR)
        C = np.array([[z, 0, ax - z * ax], [0, z, ay - z * ay], [0, 0, 1]])
        cs = self.cam_at(t)
        if cs is not None and (cs[0] > 1.0005 or z > 1.0005):     # zoom manual: foco a ~40% da altura, sem sair do quadro
            zt = cs[0] * z; cx, cy = cs[1] * W, cs[2] * H
            tx = min(max(W / 2 - zt * cx, W - zt * W), 0); ty = min(max(0.40 * H - zt * cy, H - zt * H), 0)
            C = np.array([[zt, 0, tx], [0, zt, ty], [0, 0, 1]])
        def warp(i):
            Ms = np.vstack([self.M_of(i), [0, 0, 1]])        # estabilização + câmera numa única reamostragem
            return cv2.warpAffine(reader.get(i), (C @ Ms)[:2].astype(np.float32), (W, H), flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_REFLECT)
        f = warp(i0) if w < 1e-3 else (warp(i1) if w > 1 - 1e-3 else warp(i0) * (1 - w) + warp(i1) * w)
        if self.sharpen: f = f + self.sharpen * (f - cv2.GaussianBlur(f, (0, 0), 1.1))
        return np.clip(f * self.vignette(), 0, 1)

    # ================================================================== elementos
    def bg_blur(self, t0, t1, k=0.4):
        """camada de desfoque do vídeo de fundo (k = 0..1, igual à % do Studio): entra em 0,4 s e sai em 0,3 s"""
        if k > 0: self.bg_blurs.append((t0, t1, k))
    def _blur_mix(self, fr, a, k):
        bl = cv2.GaussianBlur(cv2.resize(fr, (W // 6, H // 6)), (0, 0), 3)
        m = a * min(1.0, 1.7 * k)
        return fr * (1 - m) + cv2.resize(bl, (W, H)) * (1 - 0.16 * k) * m
    def panel(self, t0, t1, y=950, h=420, x=70, w=940, r=34, s=1.0):
        p = Panel(self, t0, t1, x, y, w, h, r, s); self.panels.append(p); return p
    def kicker_title(self, p, kicker, title, tsize=58, ksize=26):
        k = pill(kicker, MONT(800, ksize)); p.add(k, 56, 46, p.t0)
        y = 46 + k.height + 22
        for ln in title.split('\n'):
            sp = text_sprite(ln, INTER('Bold', tsize), P['text'], pad=0); p.add(sp, 56, y, p.t0 + 0.12); y += int(tsize * 1.18)
        return y + 16
    def row(self, p, icon, label, ry, t, size=46, sub=None, x=60):
        p.add(icon, x, ry, t, tick=True, anim='pop')
        ls = text_sprite(label, INTER('Bold', size), P['text'], pad=0)
        if sub:
            ss = text_sprite(sub, INTER('Medium', int(size * 0.7)), P['border'], pad=0)
            top = ry + (icon.height - ls.height - ss.height + 4) // 2
            p.add(ls, x + icon.width + 30, top, t + 0.05); p.add(ss, x + icon.width + 30, top + ls.height - 4, t + 0.12)
        else:
            p.add(ls, x + icon.width + 30, ry + (icon.height - ls.height) // 2, t + 0.05)
    def lower_third(self, t0, t1, name, sub, y=1300, x=70, s=1.0, align='esquerda'):
        n_ = text_sprite(name, INTER('Bold', 50), P['key'], pad=0); s_ = text_sprite(sub, INTER('Medium', 34), P['text'], pad=0)
        w = int((max(n_.width, s_.width) + 110) * s)
        if align == 'direita': x = W - x - w               # lado oposto ao rosto: assinatura encostada à direita
        elif align == 'centro': x = (W - w) // 2
        lt = Panel(self, t0, t1, x, y, w, int(170 * s), int(34 * s), s)
        lt.add(Image.new('RGBA', (6, 104), tuple(P['accent']) + (255,)), 40, 33, t0 + 0.05)
        lt.add(n_, 66, 32, t0 + 0.1); lt.add(s_, 66, 104, t0 + 0.22); self.panels.append(lt); return lt
    def end_card(self, t0, kicker, title_lines, subtitle, name, button, foot=None, icon='sparkle', h=760, y=640, s=1.0, blur=0.5):
        """cartão final: só desenha o que tem texto (kicker, subtítulo, nome e rodapé vazios somem) e a caixa encolhe junto."""
        kicker, subtitle, name, foot = (kicker or '').strip(), (subtitle or '').strip(), (name or '').strip(), (foot or '').strip()
        title_lines = [l for l in title_lines if l.strip()]
        hh = 60 + (90 if kicker else 0) + 100 * len(title_lines) + (100 if subtitle else 20) + (100 if name else 0) + 120 + (60 if foot else 0) + 60
        h = min(h, hh); y = y + int((760 - h) * s / 2)          # mesma altura central, caixa mais justa
        self.ec0 = t0; self.ec_blur = blur; ec = Panel(self, t0, self.TOTAL + 1, int(90 + 900 * (1 - s) / 2), y, int(900 * s), int(h * s), int(34 * s), s)
        def center(spr, yy, t, anim='rise'): ec.add(spr, (900 - spr.width) // 2, yy, t, anim=anim)
        yy = 70
        if kicker: center(pill(kicker, MONT(800, 28)), yy, t0); yy += 90
        else: yy = 60
        for k, ln in enumerate(title_lines):
            sp = text_sprite(ln, MONT(900, 80), P['text'], pad=0); center(sp, yy, t0 + 0.08 * (k + 1)); yy += 100
        if subtitle: yy += 20; center(text_sprite(subtitle, INTER('Medium', 36), P['border'], pad=0), yy, t0 + 0.3); yy += 80
        else: yy += 20
        if name:
            nm = gold_gradient_text(name, INTER('Bold', 54), pad=0); center(nm, yy, t0 + 0.45)
            ic = ICONS[icon](46); ec.add(ic, (900 - nm.width) // 2 - 70, yy + 4, t0 + 0.5, anim='pop'); ec.add(ic, (900 + nm.width) // 2 + 24, yy + 4, t0 + 0.55, anim='pop')
            yy += 100
        btn = Image.new('RGBA', (640 * 3, 120 * 3), (0, 0, 0, 0))
        ImageDraw.Draw(btn).rounded_rectangle([0, 0, 640 * 3 - 1, 120 * 3 - 1], radius=180, fill=tuple(P['button']) + (255,))
        btn = gfx.down(btn); bt = text_sprite(button, INTER('Bold', 42), P['button_fg'], pad=0)
        btn.alpha_composite(bt, ((640 - bt.width) // 2, (120 - bt.height) // 2 - 3)); center(btn, yy, t0 + 0.6, anim='pop')
        self.sfx.append((t0 + 0.6, 'tick'))
        if foot: center(text_sprite(foot, INTER('Medium', 30), P['border'], pad=0), yy + 150, t0 + 0.75)
        self.ec = ec; return ec

    # ---------------- gancho tipográfico: páginas de linhas; palavras consumidas em ordem a partir de WORDS[0]
    def hook(self, pages, keyword_word=None, icon='sparkle', ys=(1150, 1262, 1374), size=92, kw_size=150, kw_width=900, leak=True):
        """pages: [[linha, linha, ...], ...] em MAIÚSCULAS, cobrindo a fala do início em ordem.
        A linha que contém `keyword_word` vira o destaque grande em degradê, com ícone desenhado."""
        pages = [pg if isinstance(pg, dict) else {'lines': pg, 'ys': ys} for pg in pages]
        k = 0; starts = []
        for pg in pages:
            starts.append(self.WORDS[k]['os']); k += sum(len(ln.split()) for ln in pg['lines'])
        self.hook_end = self.WORDS[k]['os'] - 0.08 if k < len(self.WORDS) else self.DUR
        self.hook_nwords = k
        k = 0
        for pi, pg in enumerate(pages):
            t_out = (starts[pi + 1] - 0.06) if pi + 1 < len(pages) else self.hook_end
            pys = pg['ys']
            for li, ln in enumerate(pg['lines']):
                toks = ln.split(); yc = pys[li] if li < len(pys) else pys[-1] + 112 * (li - len(pys) + 1)
                if keyword_word and norm(keyword_word) in [norm(x) for x in toks]:
                    spr = gold_gradient_text(ln, MONT(900, kw_size), pad=0)
                    if spr.width > kw_width: spr = spr.resize((kw_width, int(spr.height * kw_width / spr.width)), Image.LANCZOS)
                    spr = add_shadow(spr, 0.55, 18); ti = self.WORDS[k]['os'] - 0.03
                    self.hook_items.append((to_np(spr), (W - spr.width) / 2, yc - spr.height / 2 + 10, ti, t_out, 'bigpop'))
                    ic = to_np(ICONS[icon](104)); ic2 = to_np(ICONS[icon](60))
                    self.hook_items.append((ic, W / 2 + spr.width / 2 - 120, yc - spr.height / 2 - 60, ti + 0.18, t_out, 'twinkle'))
                    self.hook_items.append((ic2, W / 2 - spr.width / 2 + 20, yc + spr.height / 2 - 40, ti + 0.28, t_out, 'twinkle'))
                    self.sfx += [(ti, 'whoosh'), (ti + 0.1, 'tick')]; k += len(toks); continue
                sprs = [add_shadow(text_sprite(w_, MONT(800, size), (255, 255, 255), pad=0), 0.6, 16) for w_ in toks]
                sp = 26; total = sum(s.width - 64 for s in sprs) + sp * (len(sprs) - 1); x = (W - total) / 2
                for s in sprs:
                    self.hook_items.append((to_np(s), x - 32, yc - s.height / 2, self.WORDS[k]['os'] - 0.04, t_out, 'pop')); x += s.width - 64 + sp; k += 1
        self.leak = leak
    def draw_hook(self, fr, t):
        for spr, x, y, ti, to, kind in self.hook_items:
            if t < ti or t > to + 0.2: continue
            p = t - ti; op = min(p / 0.1, 1) * (1 - ease((t - to) / 0.2))
            if kind == 'pop': sc = 0.55 + 0.45 * elastic(p / 0.45)
            elif kind == 'bigpop': sc = 0.3 + 0.7 * elastic(p / 0.6)
            else: sc = (0.2 + 0.8 * elastic(p / 0.5)) * (1 + 0.12 * math.sin(p * 7))
            over(fr, spr, x, y, op, max(sc, 0.05))
    def light_leak(self, fr, t, col=(1.0, 0.80, 0.52)):
        if not getattr(self, 'leak', False) or t > 2.0: return
        a = 0.42 * ease(t / 0.25) * (1 - ease((t - 0.6) / 1.4))
        if a <= 0: return
        y, x = np.mgrid[0:H:8, 0:W:8].astype(np.float32)
        c1 = np.exp(-(((x - (980 - 120 * t)) / 420) ** 2 + ((y - (260 + 80 * t)) / 520) ** 2))
        c2 = np.exp(-(((x - (80 + 90 * t)) / 300) ** 2 + ((y - (1500 - 60 * t)) / 420) ** 2)) * 0.6
        m = cv2.resize(c1 + c2, (W, H))[..., None] * a
        fr[:] = 1 - (1 - fr) * (1 - m * np.array(col, np.float32))

    # ---------------- Reels Dinâmico: texto na tela com animação suave (escrever, escala, opacidade, posição)
    def escurecer(self, t0, t1, k=0.4):
        if k > 0: self.escuros.append((t0, t1, k))
    def texto_tela(self, t0, t1, txt, anim='opacidade', saida='opacidade', y=760, align='centro', px=72, peso=800, fonte='titulo',
                   cor=None, sombra=0.45, fundo=False):
        """y = topo do bloco (px na tela 1080x1920). Entrada ~0,7 s com cauda longa; saída 0,4 s acelerando; parado entre as duas."""
        mk = (lambda s: MONT(int(peso), s)) if fonte == 'titulo' else (lambda s: INTER({400: 'Medium', 500: 'Medium', 600: 'SemiBold', 700: 'Bold', 800: 'Bold', 900: 'Black'}.get(int(peso), 'Bold'), s))
        f = mk(int(px)); col = tuple(cor or P['text']); lines = []
        for para in str(txt).split('\n'):                        # quebra em ~86% da largura
            cur = ''
            for w in para.split():
                tst = (cur + ' ' + w).strip()
                if cur and f.getlength(tst) > 0.86 * W: lines.append(cur); cur = w
                else: cur = tst
            lines.append(cur)
        lh = int(px * 1.18); widths = [f.getlength(l) for l in lines]
        def xs(i): return {'esquerda': 70, 'direita': W - 70 - widths[i]}.get(align, (W - widths[i]) / 2)
        self.textos.append(dict(t0=t0, t1=t1, lines=lines, f=f, col=col, y=y, lh=lh, xs=[xs(i) for i in range(len(lines))], anim=anim, saida=saida,
                                sombra=max(0.0, float(sombra)), fundo=fundo, cache={}, n=sum(len(l) for l in lines), wmax=max(widths or [0])))
    def _tx_sprite(self, T, n):
        if n in T['cache']: return T['cache'][n]
        pad = 40; w = int(T['wmax'] + 2 * pad + 140); h = int(T['lh'] * len(T['lines']) + 2 * pad)
        im = Image.new('RGBA', (W, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im); left = n
        for i, ln in enumerate(T['lines']):
            s = ln[:max(0, left)]; left -= len(ln)
            if s: d.text((T['xs'][i], pad + i * T['lh']), s, font=T['f'], fill=T['col'])
        if T['sombra'] > 0:
            a = im.split()[3]; sh = Image.new('RGBA', im.size, (8, 6, 5, 0))
            sh.putalpha(a.filter(ImageFilter.GaussianBlur(10)).point(lambda v: int(min(255, v * T['sombra'] * 1.6))))
            sh = ImageChops.offset(sh, 0, 6); sh.alpha_composite(im); im = sh
        spr = to_np(im); T['cache'][n] = spr
        if len(T['cache']) > 400: T['cache'].pop(next(iter(T['cache'])))
        return spr
    def draw_textos(self, fr, t):
        for T in self.textos:
            if t < T['t0'] or t > T['t1']: continue
            a_in = min(1.0, (t - T['t0']) / 0.7); a_out = max(0.0, (t - (T['t1'] - 0.4)) / 0.4)
            ei, eo_ = ease_out(a_in), ease(a_out); op = 1.0; sc = 1.0; dx = dy = 0.0; n = T['n']
            an = T['anim']
            if an == 'escrever':
                n = min(T['n'], int((t - T['t0']) / min(0.045, 1.8 / max(1, T['n'])) + 1)); op = min(1.0, (t - T['t0']) / 0.15)
            elif an == 'escala': sc = 0.86 + 0.14 * ei; op = ei
            elif an == 'subir': dy = (1 - ei) * 46; op = ei
            elif an == 'descer': dy = -(1 - ei) * 46; op = ei
            elif an == 'esquerda': dx = -(1 - ei) * 60; op = ei
            elif an == 'direita': dx = (1 - ei) * 60; op = ei
            else: op = ei
            sa = T['saida']
            if a_out > 0:
                op *= 1 - eo_
                if sa == 'escala': sc *= 1 - 0.08 * eo_
                elif sa == 'subir': dy -= 30 * eo_
                elif sa == 'descer': dy += 30 * eo_
            spr = self._tx_sprite(T, n); h = spr.shape[0]
            if T['fundo']:
                hh = int(T['lh'] * len(T['lines']) + 60); bw = int(T['wmax'] + 70); bx0 = min(T['xs']) - 35
                im = Image.new('RGBA', (bw, hh), (0, 0, 0, 0)); ImageDraw.Draw(im).rounded_rectangle([0, 0, bw - 1, hh - 1], 26, fill=tuple(P['glass']) + (140,))
                over(fr, to_np(im), bx0 + dx, T['y'] - 30 + dy, op)
            over(fr, spr, dx, T['y'] - 40 + dy, op, sc, W / 2 + dx, T['y'] + h / 2 - 40 + dy)
    # ---------------- motion graphics (Hyperframes / Remotion): sequência PNG com transparência, 30 fps, 1080x1920
    def motion(self, t0, t1, pasta):
        import glob as _g
        fs = sorted(_g.glob(os.path.join(pasta, '*.png')))
        if fs: self.motions.append(dict(t0=t0, t1=t1, fs=fs, k=-1, spr=None))
    def draw_motions(self, fr, t):
        for M in self.motions:
            if t < M['t0'] or t > M['t1']: continue
            k = min(len(M['fs']) - 1, int((t - M['t0']) * 30))
            if k != M['k']:
                im = cv2.imread(M['fs'][k], cv2.IMREAD_UNCHANGED)
                if im is None: continue
                if im.shape[1] != W or im.shape[0] != H: im = cv2.resize(im, (W, H), interpolation=cv2.INTER_AREA)
                M['spr'] = cv2.cvtColor(im, cv2.COLOR_BGRA2RGBA).astype(np.float32) / 255; M['k'] = k
            over(fr, M['spr'], 0, 0, 1.0)
    def set_logo(self, path, pos='sup_dir', tam=0.16, op=0.9):
        """logomarca do cliente: canto (sup_esq|sup_dir|inf_esq|inf_dir|centro_inf), largura em fração da tela."""
        im = Image.open(path).convert('RGBA'); w = max(40, int(W * tam)); im = im.resize((w, max(1, int(im.height * w / im.width))), Image.LANCZOS)
        m = 60; ys = {'sup': 190, 'inf': 1560 - im.height}       # fora da barra do topo e acima da legenda do post
        k = pos.split('_') if '_' in pos else ['inf', 'centro']
        x = {'esq': m, 'dir': W - m - w, 'centro': (W - w) // 2}.get(k[1], W - m - w)
        self.logo = (to_np(im), x, ys.get(k[0], 190), max(0.05, min(1.0, op)))
    def draw_logo(self, fr, t):
        spr, x, y, op = self.logo; a = op * ease_out(min(1.0, t / 0.6))
        if self.ec0 is not None and t >= self.ec0: a *= 1 - ease((t - self.ec0) / 0.3)   # o cartão final já traz o nome
        over(fr, spr, x, y, a)

    # ---------------- legenda
    NOEND = {'de', 'do', 'da', 'dos', 'das', 'a', 'as', 'o', 'os', 'e', 'no', 'na', 'nos', 'nas', 'que', 'um', 'uma', 'em', 'com', 'para', 'pra', 'pro',
             'se', 'sua', 'suas', 'seu', 'seus', 'é', 'até', 'mais', 'essa', 'esse', 'cada', 'ao', 'aos', 'por', 'pelo', 'pela', 'me', 'te', 'nossa', 'nosso'}
    def captions(self, keywords=(), style='docon', y=1585, maxc=26, start=None, end=None, s=1.0):
        maxc = max(10, round(maxc / s))          # letra maior = menos caracteres por linha
        """style 'docon': Inter Bold 54, pop 16%, palavra-chave 60px com sublinhado.
           style 'subtle': Inter SemiBold 44, sem pop, chave na cor de destaque, sem sublinhado."""
        self.cap_style = style; KEY = {norm(k) for k in keywords}
        start = self.hook_end - 0.01 if start is None else start; end = self.ec0 if end is None else end
        idx = [i for i, d in enumerate(self.WORDS) if d['os'] >= start and (end is None or d['os'] < end)]
        lines = []; cur = []
        for i in idx:
            txt = ' '.join(self.WORDS[j]['w'] for j in cur + [i])
            if cur and len(txt) > maxc:
                carry = []
                while len(cur) > 1 and norm(self.WORDS[cur[-1]]['w']) in self.NOEND: carry.insert(0, cur.pop())
                lines.append(cur); cur = carry
            cur.append(i)
            if self.WORDS[i]['w'][-1] in '.,?!:;' and len(cur) >= 2: lines.append(cur); cur = []
        if cur: lines.append(cur)
        merged = []
        for ln in lines:
            if merged and len(ln) == 1 and len(' '.join(self.WORDS[j]['w'] for j in merged[-1] + ln)) <= maxc + 4 and self.WORDS[merged[-1][-1]]['w'][-1] not in '.?!':
                merged[-1] = merged[-1] + ln
            else: merged.append(ln)
        if style == 'subtle': FN, FK, space, shadow = INTER('SemiBold', round(44 * s)), INTER('Bold', round(46 * s)), round(13 * s), 0.92
        else: FN, FK, space, shadow = INTER('Bold', round(54 * s)), INTER('Bold', round(60 * s)), round(26 * s), 0.8
        self.cap_lines = []
        for ln in merged:
            sprs = []
            for j in ln:
                kw = norm(self.WORDS[j]['w']) in KEY
                s = text_sprite(self.WORDS[j]['w'], FK if kw else FN, (getattr(self, 'cap_key', None) or P['key']) if kw and style != 'subtle' else (255, 255, 255), pad=0)
                sprs.append((j, add_shadow(s, shadow, 12, (0, 3)), kw, s.width))
            total = sum(s.width - 48 for _, s, _, _ in sprs) + space * (len(sprs) - 1); x = (W - total) / 2; items = []
            for j, s, kw, tw in sprs: items.append((j, to_np(s), x - 24, y - s.height / 2, kw, tw)); x += s.width - 48 + space
            self.cap_lines.append([self.WORDS[ln[0]]['os'] - 0.1, None, items])
        for n, cl in enumerate(self.cap_lines):
            last = self.WORDS[cl[2][-1][0]]; nxt = self.cap_lines[n + 1][0] if n + 1 < len(self.cap_lines) else (end or self.DUR)
            cl[1] = min(nxt, last['oe'] + 0.6)
    def draw_caps(self, fr, t):
        subtle = getattr(self, 'cap_style', 'docon') == 'subtle'
        oy = self.cap_oy(t)                                       # a legenda acompanha a divisão de tela / a abertura recortada
        for t0, t1, items in self.cap_lines:
            if not (t0 <= t < t1): continue
            fade = 1 - ease((t - (t1 - 0.09)) / 0.09)
            for j, spr, x, y, kw, tw in items:
                y = y + oy
                d = self.WORDS[j]; p = (t - d['os'] + 0.05) / (0.18 if subtle else 0.15)
                if p <= 0: continue
                op = ease_out(min(p, 1)) * fade; dy = (6 if subtle else 10) * (1 - ease_out(min(p, 1)))
                q = t - d['os'] + 0.05
                if subtle: pop = 0
                else: pop = 0.16 * (math.sin(min(q / 0.09, 1) * math.pi / 2) if q < 0.09 else max(0, 1 - (q - 0.09) / 0.22) ** 2) if q > 0 else 0
                h, w = spr.shape[:2]; over(fr, spr, x, y + dy, op, 1 + pop, x + w / 2, y + dy + h / 2)
                if kw:
                    u = ease_out(min(max((t - d['os']) / 0.35, 0), 1)); uw = int(tw * u)
                    if uw > 2:
                        ux, uy = int(x + 24), int(y + h / 2 + (30 if subtle else 34) + dy); seg = fr[uy:uy + (3 if subtle else 5), ux:ux + uw]
                        seg[:] = seg * (1 - 0.95 * op) + np.array(getattr(self, 'cap_key', None) or P['icon'], np.float32) / 255 * 0.95 * op

    # ---------------- B-roll (Pexels ou outro): 'full' = corte em tela cheia; 'band' = faixa inferior com degradê
    def broll(self, path, t0, t1, mode='full', trans=7 / 30):
        still = path.lower().rsplit('.', 1)[-1] in ('jpg', 'jpeg', 'png', 'webp')
        cap = None if still else cv2.VideoCapture(path); fps = 30 if still else (cap.get(cv2.CAP_PROP_FPS) or 30); frames = []
        need = 1 if still else int((t1 - t0) * fps) + 2
        while len(frames) < need:
            if still: f = cv2.imread(path); ok = f is not None
            else: ok, f = cap.read()
            if not ok: break
            h, w = f.shape[:2]; tw, th = (W, H) if mode == 'full' else (W, H // 2 + 160)
            s = max(tw / w, th / h); f = cv2.resize(f, (int(w * s + .5), int(h * s + .5)), interpolation=cv2.INTER_AREA)
            y0 = (f.shape[0] - th) // 2; x0 = (f.shape[1] - tw) // 2
            frames.append(look(cv2.cvtColor(f[y0:y0 + th, x0:x0 + tw], cv2.COLOR_BGR2RGB).astype(np.float32) / 255))
        self.brolls.append(dict(frames=frames, fps=fps, t0=t0, t1=t1, mode=mode, trans=trans)); self.sfx.append((t0, 'whoosh'))
    def draw_broll(self, fr, t):
        for b in self.brolls:
            if not (b['t0'] - 1e-3 <= t < b['t1']): continue
            if not b['frames']: continue
            k = min(int((t - b['t0']) * b['fps']), len(b['frames']) - 1); img = b['frames'][k]
            z = 1 + 0.05 * (t - b['t0']) / (b['t1'] - b['t0']); h, w = img.shape[:2]
            M = np.float32([[z, 0, w / 2 - z * w / 2], [0, z, h / 2 - z * h / 2]]); img = cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
            a = ease((t - b['t0']) / b['trans']) * (1 - ease((t - (b['t1'] - b['trans'])) / b['trans']))
            if b['mode'] == 'full': fr[:] = fr * (1 - a) + img * a
            else:
                yy = H - h; g = np.clip((np.arange(h) - 0) / 200, 0, 1)[:, None, None].astype(np.float32) * a
                fr[yy:] = fr[yy:] * (1 - g) + img * g
    def broll_active(self, t): return any(b['t0'] <= t < b['t1'] for b in self.brolls)

    # ================================================================== render
    # ---------------- divisão de tela: o vídeo sobe para a metade de cima e a animação ocupa a de baixo
    def split(self, t0, t1, shift=140, trans=0.55, cap_y=None):
        self.splits.append((t0, t1, shift, trans, cap_y))     # cap_y: para onde a legenda vai nesse trecho (None = linha da divisão)
    def split_a(self, t):
        a = 0.0
        for t0, t1, sh, tr, cy in self.splits:
            if t0 - 1e-3 <= t <= t1: a = max(a, ease_out((t - t0) / tr) * (1 - ease((t - (t1 - tr)) / tr)))
        return a
    def cap_oy(self, t):
        for t0, t1, sh, tr, cy in self.splits:
            if t0 - 1e-3 <= t <= t1:
                alvo = cy if cy is not None else self.cap_split_y
                if alvo is None: return 0
                return (ease_out((t - t0) / tr) * (1 - ease((t - (t1 - tr)) / tr))) * (alvo - self.cap_y0)
        return 0
    def render_frame(self, reader, t):
        fr = self.video_layer(reader, t)
        fx = getattr(self, 'fx', None)
        if fx and fx.items: fr = np.ascontiguousarray(fx.video(fr, t), dtype=np.float32)
        a = self.split_a(t)
        if a > 0:
            sh = int(round(a * max(s[2] for s in self.splits if s[0] - 1e-3 <= t <= s[1])))
            if sh > 0: fr[:-sh] = fr[sh:].copy(); fr[-sh:] = fr[-sh - 1:-sh]
        self.draw_broll(fr, t)
        self.light_leak(fr, t)
        if fx and fx.items: fr[:] = fx.under(fr, t)
        for b0, b1, k in self.bg_blurs:          # desfoque de fundo como camada (atrás dos grafismos)
            if b0 <= t <= b1: fr[:] = self._blur_mix(fr, ease_out((t - b0) / 0.4) * (1 - ease((t - (b1 - 0.3)) / 0.3)), k)
        k_esc = self.escuro + sum(k * ease_out((t - a) / 0.4) * (1 - ease((t - (b - 0.35)) / 0.35)) for a, b, k in self.escuros if a <= t <= b)
        if k_esc > 0: fr *= 1 - 0.6 * min(1.0, k_esc)            # sombra geral: escurece o vídeo atrás dos textos (100% = 60% mais escuro)
        if t < self.hook_end + 0.25: self.draw_hook(fr, t)
        for p in self.panels:
            if p is not self.ec: p.draw(fr, t)
        self.draw_textos(fr, t)
        self.draw_motions(fr, t)
        self.draw_caps(fr, t)
        if self.logo is not None: self.draw_logo(fr, t)
        if self.ec0 is not None and t >= self.ec0:
            if self.ec_blur > 0: fr[:] = self._blur_mix(fr, ease_out((t - self.ec0) / 0.4), self.ec_blur)   # 0,5 = o desfoque padrão de antes
            self.ec.draw(fr, t)
        if fx and fx.items: fr = fx.top(fr, t)
        k_pr = self.preto_at(t)
        if k_pr > 1e-3: fr = fr * (1 - k_pr)                     # fade preto: a última camada, por cima de vídeo, legenda e textos
        return fr
    def fade_preto(self, t0, t1, entrada):
        self.pretos.append((t0, t1, entrada))
    def preto_at(self, t):
        a = 0.0
        for t0, t1, ent in self.pretos:
            x = ease((t - t0) / max(0.05, t1 - t0))
            if ent and t <= t1: a = max(a, 1.0 if t < t0 else 1 - x)
            elif not ent and t >= t0: a = max(a, x)
        return a
    def check(self):
        """avisos: painel vazio, painel sobre B-roll, sobreposição de painéis."""
        warn = []
        ps = sorted([p for p in self.panels if p is not self.ec], key=lambda p: p.t0)
        for a, b in zip(ps, ps[1:]):
            if b.t0 < a.t1 - 0.05: warn.append(f'painéis sobrepostos {a.t0:.2f}-{a.t1:.2f} e {b.t0:.2f}')
        for p in ps:
            if self.brolls and any(bb['t0'] < p.t1 and p.t0 < bb['t1'] for bb in self.brolls): warn.append(f'painel {p.t0:.2f} sobre B-roll')
            first = min((it[3] for it in p.items), default=p.t0 + 9)
            if first - p.t0 > 0.5: warn.append(f'painel {p.t0:.2f} vazio por {first - p.t0:.2f}s')
        return warn
    def render(self, graded, out, preview=None, sheet=None):
        json.dump(sorted(self.sfx), open(self.wd + '/sfx.json', 'w'))
        reader = Reader(graded)
        if preview:
            outs = [cv2.resize((self.render_frame(reader, t) * 255).astype(np.uint8), (432, 768), interpolation=cv2.INTER_AREA) for t in sorted(preview)]
            rows = []
            for j in range(0, len(outs), 5):
                r = outs[j:j + 5]; r += [np.zeros_like(outs[0])] * (5 - len(r)); rows.append(np.hstack(r))
            cv2.imwrite(sheet or self.wd + '/preview.jpg', cv2.cvtColor(np.vstack(rows), cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 85]); return
        n_out = int(round(self.TOTAL * FPS))
        p = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                              '-c:v', 'libx264', '-preset', 'slow', '-crf', '17', '-profile:v', 'high', '-pix_fmt', 'yuv420p', out], stdin=subprocess.PIPE)
        for n in range(n_out):
            p.stdin.write((np.clip(self.render_frame(reader, n / FPS), 0, 1) * 255 + 0.5).astype(np.uint8).tobytes())
            if n % 150 == 0: print('render', n, n_out, flush=True)
        p.stdin.close(); p.wait()

class Panel:
    """Vidro fosco: desfoque real do quadro + tinta (P['glass'] a P['glass_alpha']) + borda fina + sombra suave."""
    def __init__(self, ed, t0, t1, x, y, w, h, r=34, s=1.0):
        self.t0, self.t1, self.x, self.y, self.w, self.h = t0, t1, x, y, w, h
        self.s = s          # escala do conteúdo (tamanho do painel e do texto vindos do Studio)
        self.mask = rounded_mask(w, h, r)[..., None]
        sh = Image.new('L', (w + 120, h + 120), 0); ImageDraw.Draw(sh).rounded_rectangle([60, 74, 60 + w, 74 + h], radius=r, fill=255)
        self.shadow = (np.asarray(sh.filter(ImageFilter.GaussianBlur(26))).astype(np.float32) / 255 * 0.32)[..., None]
        self.border = to_np(border_sprite(w, h, r)); self.items = []; self.sfx = ed.sfx; ed.sfx.append((t0, 'whoosh'))
        self.tint = np.array(P['glass'], np.float32) / 255; self.ta = P['glass_alpha']
    def add(self, spr, rx, ry, t, tick=False, anim='rise'):
        t = max(t, self.t0 + 0.05); a = spr if isinstance(spr, np.ndarray) else to_np(spr)
        if abs(self.s - 1) > 1e-3:
            a = cv2.resize(a, (max(1, round(a.shape[1] * self.s)), max(1, round(a.shape[0] * self.s))), interpolation=cv2.INTER_AREA if self.s < 1 else cv2.INTER_CUBIC)
            rx, ry = round(rx * self.s), round(ry * self.s)
        m = max(18, round(36 * self.s))                      # texto nunca passa da caixa de vidro: encolhe o que não cabe
        if rx < m or rx + a.shape[1] > self.w - m:
            cab = (self.w - 2 * m) if rx < m else (self.w - m - rx)
            if 0 < cab < a.shape[1]:
                k = cab / a.shape[1]; a = cv2.resize(a, (max(1, round(a.shape[1] * k)), max(1, round(a.shape[0] * k))), interpolation=cv2.INTER_AREA)
            if rx < m: rx = (self.w - a.shape[1]) // 2 if rx + a.shape[1] // 2 > 0 else m
        self.items.append((a, rx, ry, t, anim))
        if tick: self.sfx.append((t, 'tick'))
    def draw(self, fr, t):
        if t < self.t0 or t > self.t1: return
        a = ease_out((t - self.t0) / 0.35) * (1 - ease((t - (self.t1 - 0.3)) / 0.3)); dy = 30 * (1 - ease_out((t - self.t0) / 0.45))
        x, y, w, h = self.x, int(self.y + dy), self.w, self.h
        ys, xs = max(y - 60, 0), max(x - 60, 0); reg = fr[ys:y + h + 60, xs:x + w + 60]
        sh = self.shadow[ys - (y - 60):, xs - (x - 60):]; reg *= 1 - sh[:reg.shape[0], :reg.shape[1]] * a
        roi = fr[y:y + h, x:x + w]
        bl = cv2.resize(cv2.GaussianBlur(cv2.resize(roi, (w // 4, h // 4), interpolation=cv2.INTER_AREA), (0, 0), 6), (w, h))
        glass = bl * (1 - self.ta) + self.tint * self.ta; m = self.mask * a
        fr[y:y + h, x:x + w] = roi * (1 - m) + glass * m
        over(fr, self.border, x, y, a)
        for spr, rx, ry, ti, anim in self.items:
            p = (t - ti) / 0.4
            if p <= 0: continue
            op = ease_out(min(p * 1.4, 1)) * a
            if anim == 'pop':
                q = min(p, 1); sc = (0.6 + 0.4 * ease_out(q)) * (1 + 0.25 * math.sin(q * math.pi * 2.2) * (1 - q) ** 1.5 if q < 1 else 1)
                over(fr, spr, x + rx, y + ry, op, sc)
            else: over(fr, spr, x + rx, y + ry + 30 * (1 - ease_out(p)), op)
