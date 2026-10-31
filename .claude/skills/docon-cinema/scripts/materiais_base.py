"""DocOn Cinema · materiais base: gera de forma determinística os sons, trilhas, imagens e vídeos
de apoio do DocOn Studio (tudo sintetizado aqui, sem licença de terceiros).

uso: python3 materiais_base.py PASTA [--so sons,trilhas,imagens,videos]
Saída: PASTA/<tipo>/<id>.{wav,mp4,jpg} + PASTA/catalogo.json (id, tipo, nome, tags, duração).
O Studio guarda os mesmos itens no banco com "base": true e o mesmo id; o pipeline acha o arquivo
em WORK/banco/<id>.* ou, se faltar, regera com este script.
"""
import sys, os, json, subprocess, math
import numpy as np
from scipy.signal import butter, sosfilt
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1] if len(sys.argv) > 1 else 'materiais'
SO = set(sys.argv[sys.argv.index('--so') + 1].split(',')) if '--so' in sys.argv else {'sons', 'trilhas', 'imagens', 'videos'}
SR = 48000; rng = np.random.default_rng(7); CAT = []

def sh(c): subprocess.run(c, check=True)
def wav(path, x):
    import soundfile as sf
    x = np.asarray(x, np.float32); x = x / (np.abs(x).max() + 1e-9) * 0.89
    if x.ndim == 1: x = np.stack([x, x], 1)
    sf.write(path, x, SR)
def env(n, a, r): t = np.arange(n) / SR; return np.minimum(1, t / max(a, 1e-4)) * np.exp(-t / max(r, 1e-4))
def bp(x, lo, hi): return sosfilt(butter(2, [lo, hi], 'band', fs=SR, output='sos'), x)
def lp(x, f): return sosfilt(butter(2, f, fs=SR, output='sos'), x)
def sweep_noise(d, f0, f1, shape):
    n = int(d * SR); x = rng.normal(0, 1, n); out = np.zeros(n); seg = 512
    for i in range(0, n, seg):
        k = i / n; f = f0 * (f1 / f0) ** k; out[i:i + seg] = bp(x[i:i + seg] if i == 0 else x[max(0, i - 2048):i + seg], f * 0.7, min(f * 1.4, 20000))[-len(x[i:i + seg]):]
    return out * shape(np.linspace(0, 1, n))
def bell(f, d, dec=1.2):
    t = np.arange(int(d * SR)) / SR
    return sum(a * np.sin(2 * np.pi * f * m * t) * np.exp(-t * dec * m ** 0.7) for m, a in [(1, 1), (2.01, .45), (3.02, .22), (4.2, .12)])
def item(tipo, id_, nome, tags, path, dur): CAT.append(dict(id=id_, tipo=tipo, nome=nome, tags=tags, arquivo=os.path.relpath(path, OUT), duracao=round(dur, 2)))
def to_mp4_audio(w, out):     # áudio em contêiner MP4 (AAC): aceito no banco do Studio
    sh(['ffmpeg', '-v', 'error', '-y', '-i', w, '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', out])

# ------------------------------------------------------------------ sons
if 'sons' in SO:
    d = os.path.join(OUT, 'sons'); os.makedirs(d, exist_ok=True)
    S = {}
    S['whoosh-curto'] = ('Whoosh curto', 'transição, painel', sweep_noise(0.5, 400, 3500, lambda k: np.sin(np.pi * k) ** 2))
    S['whoosh-longo'] = ('Whoosh longo', 'transição, gancho', sweep_noise(1.2, 250, 5000, lambda k: np.sin(np.pi * k ** 0.8) ** 2))
    S['swoosh-reverso'] = ('Swoosh reverso', 'entrada, corte', sweep_noise(0.8, 300, 6000, lambda k: k ** 3)[::-1][::-1])
    n = int(0.14 * SR); t = np.arange(n) / SR; S['pop'] = ('Pop', 'item, ícone', np.sin(2 * np.pi * (900 - 2800 * t) * t) * env(n, 0.002, 0.03))
    n = int(0.06 * SR); S['tick'] = ('Tick', 'item, destaque', bp(rng.normal(0, 1, n), 2500, 7000) * env(n, 0.0005, 0.006) + 0.4 * np.sin(2 * np.pi * 1800 * np.arange(n) / SR) * env(n, 0.0005, 0.01))
    n = int(0.09 * SR); S['clique-suave'] = ('Clique suave', 'interface, botão', lp(rng.normal(0, 1, n), 3000) * env(n, 0.001, 0.012))
    S['ding-suave'] = ('Ding suave', 'CTA, destaque', bell(1318.5, 1.6, 2.2))
    x = np.zeros(int(1.4 * SR))
    for k, f in enumerate([1568, 1975.5, 2349.3, 3136]): b = bell(f, 1.0, 3.5) * 0.6; i = int(k * 0.07 * SR); x[i:i + len(b)] += b[:len(x) - i]
    S['brilho'] = ('Brilho (chime)', 'gancho, antes e depois', x)
    n = int(0.9 * SR); t = np.arange(n) / SR; S['impacto-grave'] = ('Impacto grave', 'gancho, dado forte', np.sin(2 * np.pi * (70 * np.exp(-t * 3) + 35) * t) * env(n, 0.003, 0.25) + 0.3 * lp(rng.normal(0, 1, n), 900) * env(n, 0.001, 0.05))
    n = int(2.0 * SR); t = np.arange(n) / SR; S['riser'] = ('Riser', 'antes do gancho ou CTA', (bp(rng.normal(0, 1, n), 1500, 9000) * 0.5 + np.sin(2 * np.pi * (200 + 600 * t ** 2) * t) * 0.4) * (t / 2.0) ** 2.2)
    x = np.concatenate([bell(1046.5, 0.25, 6), bell(1568, 0.6, 4)]); S['notificacao'] = ('Notificação', 'mensagem, agenda', x)
    S['transicao-ar'] = ('Transição de ar', 'transição suave', sweep_noise(1.0, 800, 2500, lambda k: np.sin(np.pi * k) ** 1.5) * 0.7)
    x = np.zeros(int(1.4 * SR))
    for at in (0.05, 0.33):
        n = int(0.22 * SR); t = np.arange(n) / SR; b = np.sin(2 * np.pi * (55 + 25 * np.exp(-t * 30)) * t) * env(n, 0.004, 0.06); i = int(at * SR); x[i:i + n] += b
    S['batimento'] = ('Batimento cardíaco', 'saúde, coração, tensão', x)
    for k, (nome, tags, x) in S.items():
        w = os.path.join(d, k + '.wav'); wav(w, x); m = os.path.join(d, k + '.mp4'); to_mp4_audio(w, m); item('efeito', 'base-sfx-' + k, nome, tags, m, len(x) / SR)

# ------------------------------------------------------------------ trilhas (music.py)
if 'trilhas' in SO:
    d = os.path.join(OUT, 'trilhas'); os.makedirs(d, exist_ok=True)
    for k, nome, mood, bpm, key, tags in [('acolhedora-re', 'Acolhedora em Ré', 'warm', 92, 'D', 'talking head, estética, acolhimento'),
                                          ('positiva-la', 'Leve e positiva em Lá', 'warm', 104, 'A', 'dicas, energia, antes e depois'),
                                          ('calma-fa', 'Calma em Fá', 'calm', 72, 'F', 'vlog, cuidado, explicação'),
                                          ('serena-do', 'Serena em Dó', 'calm', 80, 'C', 'pediatria, veterinária, depoimento')]:
        w = os.path.join(d, k + '.wav'); sh(['python3', os.path.join(HERE, 'music.py'), w, '45', '--bpm', str(bpm), '--key', key, '--mood', mood])
        m = os.path.join(d, k + '.mp4'); to_mp4_audio(w, m); item('trilha', 'base-trilha-' + k, nome, tags, m, 45)

# ------------------------------------------------------------------ imagens 1080x1920
W, H = 1080, 1920
def grad(c1, c2, ang=0.3, w=W, h=H):
    y, x = np.mgrid[0:h, 0:w].astype(np.float32); k = (x / w * math.sin(ang) + y / h * math.cos(ang)); k = (k - k.min()) / (k.max() - k.min())
    return np.array(c1, np.float32)[None, None] * (1 - k[..., None]) + np.array(c2, np.float32)[None, None] * k[..., None]
def bokeh(img, n, col, rmin, rmax, seed, alpha=0.5, offset=(0, 0)):
    h, w = img.shape[:2]; r = np.random.default_rng(seed); y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    for _ in range(n):
        cx, cy, rad = r.uniform(0, w) + offset[0], (r.uniform(0, h) + offset[1]) % (h + 2 * rmax) - rmax, r.uniform(rmin, rmax)
        x0, x1, y0, y1 = int(max(0, cx - rad - 2)), int(min(w, cx + rad + 2)), int(max(0, cy - rad - 2)), int(min(h, cy + rad + 2))
        if x1 <= x0 or y1 <= y0: continue
        dd = np.sqrt((x[y0:y1, x0:x1] - cx) ** 2 + (y[y0:y1, x0:x1] - cy) ** 2); m = np.clip((rad - dd) / 3, 0, 1) * (0.55 + 0.45 * np.clip(dd / rad, 0, 1)) * alpha * r.uniform(.4, 1)
        img[y0:y1, x0:x1] = img[y0:y1, x0:x1] * (1 - m[..., None]) + np.array(col, np.float32) * m[..., None]
    return img
def noise(img, a, seed):
    return img + np.random.default_rng(seed).normal(0, a, img.shape[:2])[..., None]
def save_jpg(img, path):
    from PIL import Image
    Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).save(path, quality=88, optimize=True)
if 'imagens' in SO:
    d = os.path.join(OUT, 'imagens'); os.makedirs(d, exist_ok=True)
    import cv2
    def rays(c1, c2):
        im = grad(c1, c2, 0.1); y, x = np.mgrid[0:H, 0:W].astype(np.float32); a = np.arctan2(y + 200, x - W * 0.85)
        r = (np.sin(a * 22) * 0.5 + 0.5) ** 6 * np.clip(1 - np.sqrt((x - W * .85) ** 2 + (y + 200) ** 2) / 2200, 0, 1); return im + r[..., None] * 90
    def waves(c1, c2, c3):
        im = grad(c1, c2, 0.5); y, x = np.mgrid[0:H, 0:W].astype(np.float32)
        for k in range(5): yy = H * (0.35 + 0.1 * k) + 90 * np.sin(x / W * 2 * math.pi * (1 + k * 0.3) + k); m = np.clip((y - yy) / 260, 0, 1) * 0.12; im = im * (1 - m[..., None]) + np.array(c3, np.float32) * m[..., None]
        return im
    def glass(c1, c2):
        im = grad(c1, c2, 0.4)
        for (cx, cy, rr, col) in [(250, 500, 380, (255, 235, 210)), (850, 1150, 460, (255, 255, 255)), (420, 1600, 300, (240, 210, 190))]:
            o = np.zeros_like(im); cv2.circle(o, (cx, cy), rr, col, -1); m = np.zeros(im.shape[:2], np.float32); cv2.circle(m, (cx, cy), rr, 1, -1)
            m = cv2.GaussianBlur(m, (0, 0), 40) * 0.22; im = im * (1 - m[..., None]) + o * m[..., None]
        return im
    IM = [('gradiente-champanhe', 'Degradê champanhe', 'fundo, estética, CTA', lambda: noise(grad((246, 226, 196), (196, 150, 105)), 2, 1)),
          ('gradiente-salvia', 'Degradê sálvia', 'fundo, veterinária, natural', lambda: noise(grad((214, 230, 214), (92, 138, 120)), 2, 2)),
          ('gradiente-azul-clinico', 'Degradê azul clínico', 'fundo, clínica, confiança', lambda: noise(grad((222, 236, 248), (52, 104, 160)), 2, 3)),
          ('gradiente-rose', 'Degradê rosé', 'fundo, estética, feminino', lambda: noise(grad((250, 226, 226), (183, 110, 121)), 2, 4)),
          ('bokeh-dourado', 'Bokeh dourado (escuro)', 'fundo, CTA, noite', lambda: noise(bokeh(grad((40, 30, 26), (18, 13, 11)), 70, (255, 214, 150), 20, 90, 5, .55), 3, 5)),
          ('bokeh-claro', 'Bokeh claro', 'fundo, leve, consultório', lambda: noise(bokeh(grad((248, 240, 230), (226, 210, 192)), 60, (255, 255, 255), 30, 120, 6, .6), 2, 6)),
          ('textura-papel', 'Textura de papel', 'fundo, editorial', lambda: cv2.GaussianBlur(noise(grad((243, 236, 224), (232, 222, 206)), 9, 7), (0, 0), 0.8)),
          ('raios-de-luz', 'Raios de luz', 'fundo, abertura', lambda: noise(rays((60, 44, 36), (20, 15, 13)), 2, 8)),
          ('ondas-suaves', 'Ondas suaves', 'fundo, painel, apresentação', lambda: noise(waves((240, 232, 222), (210, 190, 170), (183, 110, 121)), 2, 9)),
          ('vidro-fosco', 'Vidro fosco', 'fundo, glass, moderno', lambda: noise(glass((230, 214, 200), (150, 112, 96)), 2, 10))]
    for k, nome, tags, fn in IM:
        p = os.path.join(d, k + '.jpg'); save_jpg(fn(), p); item('imagem', 'base-img-' + k, nome, tags, p, 0)

# ------------------------------------------------------------------ vídeos 1080x1920, 6 s em loop (gerados em 540x960 e ampliados)
if 'videos' in SO:
    d = os.path.join(OUT, 'videos'); os.makedirs(d, exist_ok=True)
    import cv2
    w, h, F, N = 540, 960, 30, 180
    def write(path, gen):
        grain = 'grao' in path        # ruído não comprime: o grão fica em 540x960 (o editor amplia ao sobrepor)
        p = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{w}x{h}', '-r', str(F), '-i', '-', '-vf', 'null' if grain else 'scale=1080:1920:flags=lanczos',
                              '-c:v', 'libx264', '-preset', 'slow', '-crf', '30' if grain else '24', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', path], stdin=subprocess.PIPE)
        for i in range(60 if grain else N): p.stdin.write(np.clip(gen(i / N), 0, 255).astype(np.uint8).tobytes())
        p.stdin.close(); p.wait()
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    BG = grad((34, 26, 22), (14, 10, 9), 0.2, w, h)
    R = np.random.default_rng(11); P = [(R.uniform(0, w), R.uniform(0, h), R.uniform(8, 40), R.uniform(.3, 1), R.uniform(0, 2 * math.pi)) for _ in range(40)]
    def bokeh_f(k):
        im = BG.copy(); lay = np.zeros((h, w), np.float32)
        for (x0, y0, r, a, ph) in P:
            cx = x0 + 18 * math.sin(2 * math.pi * k + ph); cy = (y0 - k * h) % (h + 80) - 40
            cv2.circle(lay, (int(cx), int(cy)), int(r), a * (0.6 + 0.4 * math.sin(2 * math.pi * k + ph)), -1, cv2.LINE_AA)
        lay = cv2.GaussianBlur(lay, (0, 0), 3); return im + lay[..., None] * np.array([255, 205, 140], np.float32) * 0.6
    def leak_f(k):
        im = BG * 0.6; c1 = np.exp(-(((xx - w * (0.2 + 0.6 * k)) / 220) ** 2 + ((yy - h * (0.3 + 0.2 * math.sin(2 * math.pi * k))) / 520) ** 2))
        c2 = np.exp(-(((xx - w * (0.9 - 0.5 * k)) / 160) ** 2 + ((yy - h * 0.75) / 380) ** 2)) * (0.5 + 0.5 * math.sin(2 * math.pi * k))
        return im + c1[..., None] * np.array([255, 170, 90], np.float32) * 0.9 + c2[..., None] * np.array([255, 110, 80], np.float32) * 0.6
    Q = [(R.uniform(0, w), R.uniform(0, h), R.uniform(1, 3.2), R.uniform(.5, 1.5), R.uniform(0, 6.28)) for _ in range(160)]
    def part_f(k):
        lay = np.zeros((h, w), np.float32)
        for (x0, y0, r, sp, ph) in Q:
            cx = x0 + 10 * math.sin(2 * math.pi * k * 2 + ph); cy = (y0 - k * h * sp) % h
            cv2.circle(lay, (int(cx), int(cy)), max(1, int(r)), 0.6 + 0.4 * math.sin(2 * math.pi * (k * 3) + ph), -1, cv2.LINE_AA)
        glow = cv2.GaussianBlur(lay, (0, 0), 4) * 1.6 + lay; return BG + glow[..., None] * np.array([255, 214, 150], np.float32)
    def grad_f(k):
        a = 0.3 + 0.6 * math.sin(2 * math.pi * k); kk = np.clip((xx / w * math.sin(a) + yy / h * math.cos(a)) / 1.3, 0, 1)
        c1 = np.array([246, 222, 190], np.float32) * (0.9 + 0.1 * math.sin(2 * math.pi * k)); c2 = np.array([183, 110, 121], np.float32)
        return c1 * (1 - kk[..., None]) + c2 * kk[..., None]
    def rays_f(k):
        a = np.arctan2(yy + 100, xx - w * 0.8); r = (np.sin(a * 18 + 2 * math.pi * k) * 0.5 + 0.5) ** 6 * np.clip(1 - np.sqrt((xx - w * .8) ** 2 + (yy + 100) ** 2) / 1100, 0, 1)
        return BG * 1.2 + r[..., None] * np.array([255, 220, 170], np.float32) * 0.55
    G0 = [np.random.default_rng(100 + i).normal(0, 22, (h, w)).astype(np.float32) for i in range(6)]
    def grain_f(k): return np.repeat(128 + G0[int(k * N) % 6][..., None], 3, 2)
    for k, nome, tags, fn in [('bokeh-flutuante', 'Bokeh flutuante', 'fundo, CTA, sobreposição', bokeh_f), ('light-leak-dourado', 'Light leak dourado', 'transição, sobreposição (modo tela)', leak_f),
                              ('particulas-douradas', 'Partículas douradas', 'gancho, CTA, brilho', part_f), ('gradiente-animado', 'Degradê animado', 'fundo, cartão final', grad_f),
                              ('raios-de-luz', 'Raios de luz animados', 'abertura, fundo', rays_f), ('grao-de-filme', 'Grão de filme (sobreposição)', 'textura, modo sobrepor', grain_f)]:
        p = os.path.join(d, k + '.mp4'); write(p, fn); item('video', 'base-vid-' + k, nome, tags, p, (60 if 'grao' in k else N) / F)

old = json.load(open(os.path.join(OUT, 'catalogo.json'))) if os.path.exists(os.path.join(OUT, 'catalogo.json')) else []
CAT = [c for c in old if c['id'] not in {x['id'] for x in CAT}] + CAT
json.dump(CAT, open(os.path.join(OUT, 'catalogo.json'), 'w'), ensure_ascii=False, indent=1)
print(len(CAT), 'itens em', OUT)
