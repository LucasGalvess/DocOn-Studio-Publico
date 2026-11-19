"""DocOn · cenas breves (2.5D) sobre as imagens da mulher: pinça, bigode chinês e linhas de acordeom.
uso: python3 cenas.py CENA SAIDA [DUR] [t1,t2,...]   CENA 1|2|3 · saída: PNG 1080x1920 RGBA (alfa só na entrada/saída)"""
import sys, os, math, numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont
CENA = int(sys.argv[1]); OUT = sys.argv[2]; DUR = float(sys.argv[3]) if len(sys.argv) > 3 else 2.6
LST = [float(x) for x in sys.argv[4].split(',')] if len(sys.argv) > 4 else None
os.makedirs(OUT, exist_ok=True); W, H, K = 1080, 1920, 4
def cl(v, a=0., b=1.): return max(a, min(b, v))
def ss(a, b, v): x = cl((v - a) / (b - a)); return x * x * (3 - 2 * x)
F = os.path.expanduser('~/.docon/fonts/gf/Montserrat-%d.ttf')
def font(w, s): return ImageFont.truetype(F % w, s)
SRC = {1: 'src/v4_x4.png', 2: 'src/v3_x4.png', 3: 'src/v5_x4.png'}[CENA]
BIG = cv2.imread(os.path.join(os.path.dirname(os.path.abspath(__file__)), SRC))
# ---- parâmetros de cada cena (coordenadas na imagem 1080)
if CENA == 1:
    C0, CH0, P = (575, 680), 760, (600, 652)
    card = ('1º TESTE', ['Faça uma ', ('pinça', 1), ' na', '\nbochecha'], 'A pele está mais flácida e solta?')
elif CENA == 2:
    C0, CH0 = (544, 676), 700
    FOLDS = [[(466, 622), (432, 652), (412, 684), (420, 728)], [(619, 622), (653, 652), (673, 684), (664, 728)]]
    card = ('2º TESTE', ['Observe o ', ('bigode', 1), '\n', ('chinês', 1)], 'Mais fundo? A maquiagem marca mais?')
else:
    C0, CH0, MC = (440, 700), 760, (338, 736)
    card = ('3º TESTE', ['Sorriso largo:', '\n', ('linhas de acordeom', 1)], 'Também chamadas de “linhas de wifi”.')

def card_img():
    pad = 28; f1, f2, f3 = font(700, 21), font(800, 48), font(500, 29)
    lines = [[]]
    for it in card[1]:
        if isinstance(it, str) and it.startswith('\n'): lines.append([]); it = it[1:]
        if it == '': continue
        lines[-1].append(it)
    tw = max(sum(f2.getlength(x if isinstance(x, str) else x[0]) for x in ln) for ln in lines); sw = f3.getlength(card[2])
    w = int(max(tw, sw, 200) + 2 * pad); h = int(pad + 40 + 16 + 58 * len(lines) + 12 + 38 + pad)
    im = Image.new('RGBA', (w + 40, h + 40), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    sh = Image.new('RGBA', im.size, (0, 0, 0, 0)); ImageDraw.Draw(sh).rounded_rectangle([20, 26, 20 + w, 26 + h], 22, fill=(0, 0, 0, 110))
    im.alpha_composite(Image.fromarray(cv2.GaussianBlur(np.asarray(sh), (0, 0), 10))); d = ImageDraw.Draw(im)
    d.rounded_rectangle([20, 20, 20 + w, 20 + h], 22, fill=(251, 246, 239, 255))
    pw = f1.getlength(card[0]) + 3 * len(card[0]) + 28; d.rounded_rectangle([20 + pad, 20 + pad, 20 + pad + pw, 20 + pad + 36], 18, fill=(58, 36, 23))
    x = 20 + pad + 14
    for ch in card[0]: d.text((x, 20 + pad + 7), ch, font=f1, fill=(246, 231, 214)); x += f1.getlength(ch) + 3
    y = 20 + pad + 36 + 14
    for ln in lines:
        x = 20 + pad
        for it in ln:
            t, ac = (it, 0) if isinstance(it, str) else it
            d.text((x, y), t, font=f2, fill=(196, 113, 47) if ac else (43, 26, 16)); x += f2.getlength(t)
        y += 58
    d.text((20 + pad, y + 8), card[2], font=f3, fill=(106, 84, 68))
    return im
CARD = card_img()

def soft_poly(ov, pts, color, layers, off=(0, 0)):
    for wdt, a in layers:
        cv2.polylines(ov, [np.int32([(x + off[0], y + off[1]) for x, y in pts])], False, (*color, int(255 * a)), wdt, cv2.LINE_AA)

def frame(t):
    z = 1 - 0.07 * ss(0, DUR, t); ch = CH0 * z; cw = ch * 9 / 16
    cx, cy = C0[0] + 6 * math.sin(t * 0.8), C0[1] - 8 * ss(0, DUR, t)
    x0, y0 = cx - cw / 2, cy - ch / 2
    # recorte em 4x com margem, efeitos em coordenadas 4x
    X0, Y0, X1, Y1 = int((x0 - 20) * K), int((y0 - 20) * K), int((x0 + cw + 20) * K), int((y0 + ch + 20) * K)
    X0, Y0 = max(0, X0), max(0, Y0); reg = BIG[Y0:Y1, X0:X1].astype(np.float32)
    hh, ww = reg.shape[:2]; gx, gy = np.meshgrid(np.arange(ww, dtype=np.float32), np.arange(hh, dtype=np.float32))
    def L(p): return ((p[0] * K - X0), (p[1] * K - Y0))
    ov = np.zeros((hh, ww, 4), np.uint8)
    if CENA == 1:
        k = ss(0.55, 1.05, t) * (1 - ss(1.75, 2.45, t))                  # pinça e soltura lenta (flacidez)
        px, py = L(P); s = 60 * K; r2 = (gx - px) ** 2 + (gy - py) ** 2; g = np.exp(-r2 / (2 * s * s))
        mx = px + (gx - px) * (1 + 0.12 * k * g); my = py + (gy - py) * (1 + 0.35 * k * g) + 10 * K * k * g   # aperta na vertical e levanta
        reg = cv2.remap(reg, mx, my, cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)
        ar = ss(0.25, 0.6, t) * (1 - ss(2.2, 2.55, t))
        if k > 0.01:
            cv2.ellipse(ov, (int(px), int(py + 30 * K)), (int(60 * K), int(20 * K)), 0, 0, 360, (90, 40, 30, int(55 * k)), -1, cv2.LINE_AA)
            cv2.ellipse(ov, (int(px), int(py - 4 * K)), (int(46 * K), int(14 * K)), 0, 0, 360, (255, 238, 226, int(70 * k)), -1, cv2.LINE_AA)
        ov = cv2.GaussianBlur(ov, (0, 0), 14 * K)
        if ar > 0.01:
            gap = (150 - 100 * ss(0.4, 1.0, t)) * K
            for sg in (-1, 1):
                a, b = (px, py + sg * (gap + 70 * K)), (px, py + sg * gap)
                cv2.line(ov, (int(a[0]), int(a[1])), (int(b[0]), int(b[1])), (232, 150, 80, int(235 * ar)), int(5 * K), cv2.LINE_AA)
                tri = np.int32([(b[0] - 12 * K, b[1] + sg * 14 * K), (b[0], b[1] - sg * 3 * K), (b[0] + 12 * K, b[1] + sg * 14 * K)]); cv2.fillPoly(ov, [tri], (232, 150, 80, int(235 * ar)), cv2.LINE_AA)
            rk = ss(0.9, 1.3, t) * (1 - ss(2.1, 2.5, t))
            if rk > 0.01:
                for a in range(0, 360, 20): cv2.ellipse(ov, (int(px), int(py)), (int(92 * K), int(92 * K)), 0, a, a + 11, (232, 150, 80, int(220 * rk)), int(3 * K), cv2.LINE_AA)
    elif CENA == 2:
        k = ss(0.35, 1.35, t); mk = ss(1.25, 2.2, t); gk = ss(0.2, 0.6, t) * (1 - ss(1.2, 1.6, t))
        for side, f in enumerate(FOLDS):
            pts = [L(p) for p in f]; sg = -1 if side == 0 else 1
            soft_poly(ov, pts, (88, 38, 28), [(int(26 * K), 0.12 * k), (int(15 * K), 0.18 * k), (int(7 * K), 0.30 * k), (int(3 * K), 0.42 * k)])
            soft_poly(ov, pts, (255, 232, 216), [(int(4 * K), 0.22 * k)], off=(sg * 6 * K, -2 * K))
        ov = cv2.GaussianBlur(ov, (0, 0), 2.2 * K)
        rng = np.random.default_rng(3)
        for side, f in enumerate(FOLDS):
            pts = np.array([L(p) for p in f], np.float32)
            for i in range(110):
                sgi = rng.integers(0, len(pts) - 1); u = rng.random(); p = pts[sgi] * (1 - u) + pts[sgi + 1] * u
                dx, dy = (rng.random() - .5) * 40 * K * (1 - mk), (rng.random() - .5) * 18 * K * (1 - mk); a = cl(mk * 1.4 - rng.random() * 0.4)
                if a > 0: cv2.circle(ov, (int(p[0] + dx), int(p[1] + dy)), int((1 + 1.2 * rng.random()) * K), (236, 200, 166, int(200 * a)), -1, cv2.LINE_AA)
        if gk > 0.01:
            for side, f in enumerate(FOLDS):
                sg = -1 if side == 0 else 1; pts = [L((x + sg * 16, y)) for x, y in f]
                for i in range(len(pts) - 1):
                    a, b = np.array(pts[i]), np.array(pts[i + 1]); n = int(np.linalg.norm(b - a) / (12 * K)) + 1
                    for j in range(0, n, 2): p, q = a + (b - a) * j / n, a + (b - a) * min(1, (j + 1) / n); cv2.line(ov, tuple(np.int32(p)), tuple(np.int32(q)), (232, 150, 80, int(230 * gk)), int(3 * K), cv2.LINE_AA)
    else:
        k = ss(0.3, 1.0, t)                                               # bochecha sobe (sorriso) e linhas aparecem uma a uma
        cxl, cyl = L((440, 690)); s = 95 * K; g = np.exp(-((gx - cxl) ** 2 + (gy - cyl) ** 2) / (2 * s * s))
        reg = cv2.remap(reg, gx, gy + 10 * K * k * g, cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)
        mx_, my_ = L(MC)
        for i, r in enumerate((92, 128, 164, 200)):
            a = ss(0.6 + i * 0.28, 1.0 + i * 0.28, t)
            if a <= 0: continue
            for wdt, al in ((int(9 * K), 0.10), (int(5 * K), 0.18), (int(2 * K), 0.40)):
                cv2.ellipse(ov, (int(mx_), int(my_ - 6 * K)), (int(r * K), int(r * 1.05 * K)), 0, -32 - 2 * i, 30 + 2 * i, (96, 44, 34, int(255 * al * a)), wdt, cv2.LINE_AA)
            cv2.ellipse(ov, (int(mx_), int(my_ - 6 * K)), (int((r + 4) * K), int((r + 4) * 1.05 * K)), 0, -32 - 2 * i, 30 + 2 * i, (255, 232, 216, int(255 * 0.22 * a)), int(2 * K), cv2.LINE_AA)
        ov = cv2.GaussianBlur(ov, (0, 0), 1.6 * K)
    a = ov[..., 3:4].astype(np.float32) / 255; reg = reg * (1 - a) + ov[..., 2::-1].astype(np.float32) * a   # ov em RGB -> BGR
    # recorte final 9:16
    ox, oy = x0 * K - X0, y0 * K - Y0; M = np.float32([[W / (cw * K), 0, -ox * W / (cw * K)], [0, H / (ch * K), -oy * H / (ch * K)]])
    fr = cv2.warpAffine(np.clip(reg, 0, 255).astype(np.uint8), M, (W, H), flags=cv2.INTER_AREA)
    im = Image.fromarray(cv2.cvtColor(fr, cv2.COLOR_BGR2RGB)).convert('RGBA')
    ck = ss(0.15, 0.5, t) * (1 - ss(DUR - 0.3, DUR, t)); c = CARD.copy(); c.putalpha(Image.fromarray((np.asarray(c)[..., 3] * ck).astype(np.uint8)))
    im.alpha_composite(c, (48, int(150 + 20 * (1 - ss(0.15, 0.55, t)))))
    fa = min(1, t / 0.25, (DUR - t) / 0.25); arr = np.asarray(im).copy(); arr[..., 3] = int(255 * cl(fa))
    return arr

ts = LST or [i / 30 for i in range(int(round(DUR * 30)))]
for i, t in enumerate(ts): cv2.imwrite(os.path.join(OUT, f'{i:05d}.png'), cv2.cvtColor(frame(t), cv2.COLOR_RGBA2BGRA), [cv2.IMWRITE_PNG_COMPRESSION, 1])
print('ok', CENA, len(ts))
