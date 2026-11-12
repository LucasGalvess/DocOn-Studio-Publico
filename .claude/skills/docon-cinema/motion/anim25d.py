"""DocOn · animação anatômica 2.5D a partir de uma ILUSTRAÇÃO DE REFERÊNCIA (a imagem aprovada pela equipe).

A imagem é a base, exatamente como está: a animação só move a câmera, deforma localmente (pálpebra que cai,
sobrancelha que sobe) e acende/apaga regiões reais da própria imagem (o músculo frontal é a área vermelha da testa).
Por cima: textos, etiquetas, setas, agulha e partículas no estilo DocOn.

uso:
  python3 anim25d.py preparar REF.png TRAB            # super-resolução 4x (EDSR) + pontos do rosto (MediaPipe)
  python3 anim25d.py cena N DUR_REAL TRAB SAIDA [DUR_DESENHO] [t1,t2,...]
    cenas: 1 olhar normal x pálpebra caída · 2 terço superior (tela dividida) · 3 levantador da pálpebra e toxina
           4 músculo frontal (tela dividida) · 5 dose alta/pontos errados · 6 avaliação de assimetria (tela dividida)
Saída: SAIDA/NNNNN.png 1080x1920 (cenas de tela dividida: só a metade de baixo, com transparência em cima).
Direitos: a referência precisa ser licenciada para uso comercial (banco pago, criação própria ou IA da conta da DocOn).
"""
import sys, os, json, math, glob
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__)); FONTS = os.path.expanduser('~/.docon/fonts')
W, H = 1080, 1920
def cl(x, a=0., b=1.): return min(b, max(a, x))
def ease(x): x = cl(x); return x * x * (3 - 2 * x)
def ease_out(x): x = cl(x); return 1 - (1 - x) ** 3
def eio(x): x = cl(x); return 4 * x ** 3 if x < .5 else 1 - (-2 * x + 2) ** 3 / 2
def win(t, a, b, f=.45): return ease((t - a) / f) * (1 - ease((t - (b - f)) / f))
def lerp(a, b, k): return a + (b - a) * k
def F(nome, px): return ImageFont.truetype(os.path.join(FONTS, nome), px)

# ------------------------------------------------------------------ preparar
def preparar(ref, trab):
    os.makedirs(trab, exist_ok=True); im = cv2.imread(ref)
    sr = cv2.dnn_superres.DnnSuperResImpl_create(); sr.readModel(os.path.expanduser('~/.docon/models/EDSR_x4.pb')); sr.setModel('edsr', 4)
    cv2.imwrite(os.path.join(trab, 'ref4.png'), sr.upsample(im))
    import mediapipe as mp
    from mediapipe.tasks.python import vision, BaseOptions
    det = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=os.path.expanduser('~/.docon/models/face_landmarker.task')), num_faces=1))
    r = det.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(im, cv2.COLOR_BGR2RGB)))
    if not r.face_landmarks: sys.exit('não achei o rosto na referência')
    json.dump({'lm': [[p.x * im.shape[1], p.y * im.shape[0]] for p in r.face_landmarks[0]], 'tam': [im.shape[1], im.shape[0]]}, open(os.path.join(trab, 'ref.json'), 'w'))
    print('pronto:', trab)

# ------------------------------------------------------------------ cena
class Cena:
    def __init__(s, trab, n, dur):
        s.n, s.dur = n, dur; s.src = cv2.cvtColor(cv2.imread(os.path.join(trab, 'ref4.png')), cv2.COLOR_BGR2RGB).astype(np.float32) / 255
        J = json.load(open(os.path.join(trab, 'ref.json'))); s.L = np.array(J['lm']); s.K = s.src.shape[1] / J['tam'][0]
        s.split = n in (2, 4, 6); s.OW, s.OH = (W, 960) if s.split else (W, H)
        L = s.L
        # músculo do lado exposto: o olho e a sobrancelha do lado com mais vermelho na testa
        lado_e = s._verm(L[334]) > s._verm(L[105])
        s.eyeM, s.eyeS = (473, 468) if lado_e else (468, 473)
        s.lidM, s.lidS = (386, 159) if lado_e else (159, 386)
        s.browM, s.browS = ([336, 334, 300] if lado_e else [107, 105, 70]), ([107, 105, 70] if lado_e else [336, 334, 300])
        # máscara do frontal: o vermelho da própria imagem na testa (acima das sobrancelhas)
        ys = min(L[10][1], L[109][1], L[338][1]) - 60; yb = max(L[336][1], L[107][1]) + 8
        xs = sorted([L[103][0], L[332][0], L[70][0], L[300][0]]); x0, x1 = xs[0] - 30, xs[-1] + 30
        r, g, b = s.src[..., 0], s.src[..., 1], s.src[..., 2]; k = s.K
        m = ((r - g) > .22) & (r > .45); box = np.zeros_like(m); box[int(ys * k):int(yb * k), int(x0 * k):int(x1 * k)] = True
        s.front = cv2.GaussianBlur((m & box).astype(np.float32), (0, 0), 3 * k)
        s.fonts = {'kick': F('Montserrat-800.ttf', 22), 'tit': F('Montserrat-800.ttf', 52), 'sub': F('InterDisplay-SemiBold.ttf', 30), 'tag': F('InterDisplay-Bold.ttf', 24)}
    def _verm(s, p):
        x, y = int(p[0] * s.K), int((p[1] - 30) * s.K); a = s.src[max(0, y - 60):y + 60, max(0, x - 60):x + 60]
        return float(((a[..., 0] - a[..., 1]) > .22).mean())
    # --- deformações locais (em coordenadas da imagem 740): pálpebra que desce, sobrancelha que sobe
    def disp(s, X, Y, st):
        D = np.zeros_like(X)
        for lid, a in [(s.lidM, st.get('lidM', 0)), (s.lidS, st.get('lidS', 0))]:
            if not a: continue
            cx, ly = s.L[lid]; up = ly - 26
            hx = np.exp(-((X - cx) / 24) ** 2)
            if a > 0: hy = np.clip((Y - up) / 14, 0, 1) * np.clip(1 - (Y - ly) / (a + 3), 0, 1)
            else: hy = np.clip((Y - up) / 14, 0, 1) * np.clip(1 - (Y - ly) / 6, 0, 1)
            D += a * hx * hy
        for br, a in [(s.browM, st.get('browM', 0)), (s.browS, st.get('browS', 0))]:
            if not a: continue
            P = s.L[br]; cx = P[:, 0].mean(); by = P[:, 1].mean(); sx = (P[:, 0].max() - P[:, 0].min()) / 1.6 + 10
            hx = np.exp(-((X - cx) / sx) ** 2); hy = np.clip((Y - (by - 70)) / 55, 0, 1) * np.clip(1 - (Y - (by + 6)) / 34, 0, 1)
            D += a * hx * hy
        return D
    def quadro(s, cam, st, fx):
        cx, cy, cw = cam; sc = s.OW / cw
        u, v = np.meshgrid(np.arange(s.OW, dtype=np.float32), np.arange(s.OH, dtype=np.float32))
        X = cx + (u - s.OW / 2) / sc; Y = cy + (v - s.OH / 2) / sc
        Y = Y - s.disp(X, Y, st)
        img = cv2.remap(s.src, (X * s.K).astype(np.float32), (Y * s.K).astype(np.float32), cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        fr = cv2.remap(s.front, (X * s.K).astype(np.float32), (Y * s.K).astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)[..., None]
        if fx.get('dim'):                 # músculo bloqueado: perde a cor
            gray = img.mean(2, keepdims=True); img = img * (1 - fr * fx['dim'] * .85) + (gray * .9 + .1) * fr * fx['dim'] * .85
        if fx.get('act'):                 # contração: o músculo acende
            a = fx['act']; img = img + fr * a * np.array([.22, .02, -.02], np.float32) + fr * a * .08
        if fx.get('band'):                # terço superior
            y0, y1, k = fx['band']; hb = (np.clip((Y - y0) / 4, 0, 1) * np.clip((y1 - Y) / 4, 0, 1))[..., None] * k
            img = img * (1 - hb * .22) + hb * .22 * np.array([.95, .78, .45], np.float32)
            for yy in (y0, y1): img += (np.exp(-((Y - yy) * sc / 2.2) ** 2)[..., None] * k * np.array([.55, .38, .12], np.float32))
        if fx.get('scan') is not None:
            img += np.exp(-((Y - fx['scan']) * sc / 3) ** 2)[..., None] * np.array([.6, .45, .15], np.float32)
        img = np.clip(img, 0, 1)
        return Image.fromarray((img * 255).astype(np.uint8)), (cx, cy, cw, sc)
    def P(s, cam, p):           # ponto 740 → pixel de saída
        cx, cy, cw, sc = cam; return ((p[0] - cx) * sc + s.OW / 2, (p[1] - cy) * sc + s.OH / 2)
    # --- camadas por cima
    def rotulo(s, im, t, a, b, kick, tit, real='', sub='', x=48, y=150, esc=1.0):
        k = win(t, a, b, .5)
        if k <= 0: return
        f = s.fonts; ft = F('Montserrat-800.ttf', int(52 * esc)); fs = F('InterDisplay-SemiBold.ttf', int(30 * esc)); fk = F('Montserrat-800.ttf', int(22 * esc))
        linhas = s._quebra(tit, ft, (W - 2 * x - 60))
        w = max([ft.getlength(l) for l in linhas] + [fs.getlength(sub) if sub else 0, fk.getlength(kick) + 40]) + 56
        h = int(28 + fk.size + 26 + len(linhas) * ft.size * 1.12 + (fs.size * 1.5 if sub else 0) + 26)
        lay = Image.new('RGBA', im.size, (0, 0, 0, 0)); d = ImageDraw.Draw(lay); dy = (1 - ease_out((t - a) / .7)) * 22; y = y + dy
        d.rounded_rectangle([x, y, x + w, y + h], 28, fill=(250, 246, 240, 225)); kw = fk.getlength(kick.upper()) + 30
        d.rounded_rectangle([x + 28, y + 26, x + 28 + kw, y + 26 + fk.size + 18], 99, fill=(52, 36, 30, 255)); d.text((x + 43, y + 35), kick.upper(), font=fk, fill=(242, 214, 166, 255))
        yy = y + 26 + fk.size + 30
        for l in linhas:
            xx = x + 28
            for wd in l.split(' '):
                cor = (168, 103, 47, 255) if real and wd.strip('.,').lower() in real.lower().split() else (43, 29, 23, 255)
                d.text((xx, yy), wd, font=ft, fill=cor); xx += ft.getlength(wd + ' ')
            yy += ft.size * 1.12
        if sub: d.text((x + 28, yy + 6), sub, font=fs, fill=(43, 29, 23, 200))
        sh = lay.split()[3].filter(ImageFilter.GaussianBlur(18)).point(lambda v: int(v * .18)); sombra = Image.new('RGBA', im.size, (52, 36, 30, 0)); sombra.putalpha(sh)
        lay = Image.alpha_composite(sombra, lay); lay.putalpha(lay.split()[3].point(lambda v: int(v * k))); im.alpha_composite(lay)
    def _quebra(s, txt, f, maxw):
        out, cur = [], ''
        for w in txt.split():
            if f.getlength((cur + ' ' + w).strip()) > maxw and cur: out.append(cur); cur = w
            else: cur = (cur + ' ' + w).strip()
        return out + ([cur] if cur else [])
    def tag(s, im, t, a, b, txt, xy, dx=0, dy=0):
        k = win(t, a, b, .4)
        if k <= 0: return
        f = s.fonts['tag']; w = f.getlength(txt) + 58; x, y = xy[0] + dx - w / 2, xy[1] + dy
        lay = Image.new('RGBA', im.size, (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
        d.rounded_rectangle([x, y, x + w, y + 46], 14, fill=(255, 252, 247, 240), outline=(52, 36, 30, 70), width=2)
        d.ellipse([x + 16, y + 17, x + 28, y + 29], fill=(192, 71, 60, 255)); d.text((x + 38, y + 9), txt, font=f, fill=(43, 29, 23, 255))
        lay.putalpha(lay.split()[3].point(lambda v: int(v * k))); im.alpha_composite(lay)
    def seta(s, im, xy, L, k, cor=(52, 36, 30)):
        if k <= 0 or L < 2: return
        d = ImageDraw.Draw(im); x, y = xy; a = int(255 * k)
        d.line([(x, y), (x, y - L)], fill=cor + (a,), width=6); d.polygon([(x - 14, y - L + 4), (x + 14, y - L + 4), (x, y - L - 20)], fill=cor + (a,))
    def particulas(s, im, pts, alpha):
        if alpha <= 0 or not len(pts): return
        lay = Image.new('RGBA', im.size, (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
        for x, y, r in pts: d.ellipse([x - r, y - r, x + r, y + r], fill=(47, 143, 201, 200))
        glow = lay.filter(ImageFilter.GaussianBlur(5)); core = Image.new('RGBA', im.size, (0, 0, 0, 0)); dc = ImageDraw.Draw(core)
        for x, y, r in pts: dc.ellipse([x - r * .45, y - r * .45, x + r * .45, y + r * .45], fill=(225, 245, 255, 230))
        lay = Image.alpha_composite(Image.alpha_composite(glow, lay), core); lay.putalpha(lay.split()[3].point(lambda v: int(v * alpha))); im.alpha_composite(lay)
    def agulha(s, im, tip, ang, k, comp):
        if k <= 0: return
        lay = Image.new('RGBA', im.size, (0, 0, 0, 0)); d = ImageDraw.Draw(lay); ux, uy = math.cos(ang), math.sin(ang)
        x0, y0 = tip; x1, y1 = x0 + ux * comp * .45, y0 + uy * comp * .45; x2, y2 = x0 + ux * comp, y0 + uy * comp
        d.line([(x0, y0), (x1, y1)], fill=(150, 156, 162, 255), width=5); d.line([(x0 + 1, y0 - 1), (x1 + 1, y1 - 1)], fill=(235, 238, 240, 255), width=2)
        nx, ny = -uy, ux; hw = comp * .07
        d.polygon([(x1 + nx * hw * .5, y1 + ny * hw * .5), (x1 - nx * hw * .5, y1 - ny * hw * .5), (x1 + ux * 22 - nx * hw * .55, y1 + uy * 22 - ny * hw * .55), (x1 + ux * 22 + nx * hw * .55, y1 + uy * 22 + ny * hw * .55)], fill=(242, 214, 166, 255))
        bx, by = x1 + ux * 22, y1 + uy * 22
        d.polygon([(bx + nx * hw, by + ny * hw), (bx - nx * hw, by - ny * hw), (x2 - nx * hw, y2 - ny * hw), (x2 + nx * hw, y2 + ny * hw)], fill=(255, 255, 255, 120), outline=(160, 170, 178, 255))
        lq = .55; d.polygon([(bx + nx * hw * .8, by + ny * hw * .8), (bx - nx * hw * .8, by - ny * hw * .8), (bx + (x2 - bx) * lq - nx * hw * .8, by + (y2 - by) * lq - ny * hw * .8), (bx + (x2 - bx) * lq + nx * hw * .8, by + (y2 - by) * lq + ny * hw * .8)], fill=(110, 185, 225, 150))
        lay.putalpha(lay.split()[3].point(lambda v: int(v * k))); im.alpha_composite(lay)
    def levantador(s, im, cam, lid_off, act, dim, k):
        """músculo levantador da pálpebra superior (visão frontal, em transparência): leque da borda da pálpebra até o teto da órbita"""
        if k <= 0: return
        L = s.L; e = L[s.eyeM]; lid = L[s.lidM]; c362, c263 = (L[362], L[263]) if s.eyeM == 473 else (L[133], L[33])
        xa, xb = min(c362[0], c263[0]) + 8, max(c362[0], c263[0]) - 6; ly = lid[1] + lid_off - 2
        top = (e[0] + 4, lid[1] - 44); n = 18
        lay = Image.new('RGBA', im.size, (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
        cor = np.array([200, 62, 52]) * (1 - dim) + np.array([150, 140, 136]) * dim; cor = tuple(int(c) for c in cor)
        poly = [s.P(cam, (xa, ly)), s.P(cam, (xb, ly)), s.P(cam, (top[0] + 9, top[1])), s.P(cam, (top[0] - 9, top[1]))]
        d.polygon(poly, fill=cor + (int(150 + 60 * act),))
        for i in range(n + 1):
            f = i / n; p0 = s.P(cam, (lerp(xa, xb, f), ly)); p1 = s.P(cam, (lerp(top[0] - 9, top[0] + 9, f), top[1]))
            d.line([p0, p1], fill=(255, 210, 200, int(110 * (1 - dim))) if i % 2 else (120, 30, 25, 90), width=2)
        d.line(poly + [poly[0]], fill=(255, 240, 230, 200), width=3)
        lay = lay.filter(ImageFilter.GaussianBlur(.6)); lay.putalpha(lay.split()[3].point(lambda v: int(v * k))); im.alpha_composite(lay)

    def render(s, t):
        L = s.L; st, fx = {}, {}; extra = []
        eM = L[s.eyeM]; eS = L[s.eyeS]; mid = (eM + eS) / 2
        if s.n == 1:
            cam = (mid[0] + 4 * math.sin(t * .4), mid[1] - 12, lerp(300, 270, eio(t / s.dur)))
            st['lidM'] = 7.5 * eio((t - 1.7) / 2.0)
        elif s.n == 3:
            cam = (eM[0] + 6, eM[1] - 18, lerp(210, 185, eio(t / s.dur)))
            pulse = .5 + .5 * math.sin(t / 1.3 * math.pi - math.pi / 2) if t < 2.6 else 0
            dim = eio((t - 3.3) / 1.4); st['lidM'] = -2.5 * pulse if t < 2.6 else 7.5 * eio((t - 4.6) / 1.5)
        elif s.n == 5:
            cam = (mid[0] + 10, mid[1] - 50, lerp(400, 370, eio(t / s.dur)))
            dim = eio((t - 2.2) / 2.0); fx['dim'] = dim; d = eio((t - 3.5) / 2.0)
            st.update(browM=6 * d, browS=6 * d, lidM=6 * eio((t - 3.7) / 2.0), lidS=6 * eio((t - 3.7) / 2.0))
        else:
            cam = (L[1][0] + 8, L[168][1] + 6, 640)
            if s.n == 2: fx['band'] = (min(L[10][1], L[109][1]) - 28, max(L[107][1], L[336][1]) + 6, eio((t - .8) / 1.2))
            if s.n == 4:
                c = max(0, math.sin((t - .9) / 2.7 * math.pi)) if .9 < t < s.dur - .4 else 0
                fx['act'] = c; st.update(browM=-6 * c, browS=-6 * c, lidM=-2 * c, lidS=-2 * c)
            if s.n == 6:
                fx['scan'] = lerp(L[10][1] - 40, L[152][1] + 10, eio((t - .4) / 2.6)) if t < 3.2 else None
                c = (max(0, math.sin((t - 3.4) / 2.6 * math.pi)) if t > 3.4 else 0) + (max(0, math.sin((t - 6.2) / 2.6 * math.pi)) if 6.2 < t < 8.8 else 0)
                fx['act'] = c * .8; st.update(browM=-7 * c, browS=-3 * c, lidM=-2 * c, lidS=-1 * c)
        im, cm = s.quadro(cam, st, fx); im = im.convert('RGBA')
        # ---- camadas
        if s.n == 1:
            s.rotulo(im, t, .3, s.dur + 1, 'Depois da toxina', 'A pálpebra pode descer', 'descer', 'e o olhar fica pesado')
            s.tag(im, t, .9, s.dur + 1, 'olhar normal', s.P(cm, (eS[0], eS[1] + 26))); s.tag(im, t, 2.7, s.dur + 1, 'pálpebra caída', s.P(cm, (eM[0], eM[1] + 26)))
        if s.n == 3:
            lev_k = 1; s.levantador(im, cm, st['lidM'], pulse, dim, 1)
            tip = (eM[0] + 10, L[s.lidM][1] - 40); nIn, nOut = eio((t - 2.5) / .6), eio((t - 4.1) / .5)
            off = 220 * (1 - nIn) + 260 * nOut; tp = s.P(cm, tip); ang = -math.pi / 2 + .45
            s.agulha(im, (tp[0] + math.cos(ang) * off, tp[1] + math.sin(ang) * off), ang, 1 if 2.3 < t < 4.7 else 0, 520)
            rng = np.random.default_rng(5); pts = []
            for i in range(160):
                a1, b, c, d = rng.random(4); age = max(0, t - (3.0 + a1 * 1.1)); k = 1 - math.exp(-age * 1.5)
                q = (tip[0] + (b - .5) * 44 * k, tip[1] + k * (12 + c * 26)); pq = s.P(cm, q); pts.append((pq[0], pq[1], 5 + 3 * d))
            s.particulas(im, [p for i, p in enumerate(pts) if t > 3.0], cl((t - 3.0) / .3) * (1 - .5 * eio((t - 5.3) / 1.4)))
            s.rotulo(im, t, .2, 2.6, 'Ptose palpebral', 'O músculo que levanta a pálpebra', 'levanta pálpebra')
            s.rotulo(im, t, 2.6, 4.7, 'Ptose palpebral', 'A toxina pode chegar até ele', 'chegar até ele')
            s.rotulo(im, t, 4.7, s.dur + 1, 'Ptose palpebral', 'A pálpebra desce', 'desce', 'Um efeito temporário')
            s.tag(im, t, .9, 2.7, 'músculo levantador da pálpebra', s.P(cm, (eM[0], L[s.lidM][1] - 58)))
        if s.n == 5:
            pts_inj = [(L[103][0] + 10, L[103][1] + 40), (L[67][0], L[67][1] + 40), (L[151][0], L[151][1] + 6), (L[297][0], L[297][1] + 40), (L[332][0] - 8, L[332][1] + 45),
                       (L[105][0] + 6, L[105][1] - 8), (L[334][0] - 4, L[334][1] - 8), (L[109][0], L[109][1] + 20), (L[338][0], L[338][1] + 20), (L[9][0], L[9][1] - 4)]
            rng = np.random.default_rng(3); pts = []
            for i in range(420):
                a1, b, c, d = rng.random(4); kk = int(a1 * len(pts_inj)); x0, y0 = pts_inj[kk]; age = max(0, t - (.3 + kk * .2))
                if age <= 0: continue
                sp = (1 - math.exp(-age * 1.2)) * (4 + 16 * c); th = b * 6.283; q = (x0 + math.cos(th) * sp, y0 + math.sin(th) * sp * .8 + 3 * age * d)
                pq = s.P(cm, q); pts.append((pq[0], pq[1], 3.5 + 2.5 * d))
            s.particulas(im, pts, cl((t - .3) / .3) * (1 - .45 * eio((t - 5) / 2)))
            s.rotulo(im, t, .2, 3.7, 'Aplicação inadequada', 'Dose alta ou pontos errados', 'pontos errados')
            s.rotulo(im, t, 3.7, s.dur + 1, 'Resultado', 'Sobrancelha e pálpebra descem', 'descem', 'O olhar fica mais caído')
        if s.n in (2, 4, 6):
            esc = .7; lx, ly0 = 30, 34
            if s.n == 2: s.rotulo(im, t, .5, s.dur + 1, 'Terço superior', 'Testa, sobrancelhas e pálpebras', '', x=lx, y=ly0, esc=esc)
            if s.n == 4:
                s.rotulo(im, t, .5, s.dur + 1, 'Músculo frontal', 'Eleva as sobrancelhas', 'Eleva', 'e ajuda a abrir o olhar', x=lx, y=ly0, esc=esc)
                for br in (s.browM, s.browS): p = s.P(cm, (L[br][:, 0].mean(), L[br][:, 1].mean() - 38)); s.seta(im, p, 70 * fx['act'] + 1, cl(fx['act'] * 3))
            if s.n == 6:
                s.rotulo(im, t, .5, s.dur + 1, 'Avaliação', 'Contração, força e assimetrias', '', x=lx, y=ly0, esc=esc)
                c = fx['act'] / .8
                for br, Lm, txt, dx in ((s.browM, 80, 'contrai mais', 90), (s.browS, 34, 'contrai menos', -90)):
                    p = s.P(cm, (L[br][:, 0].mean(), L[br][:, 1].mean() - 40)); s.seta(im, p, Lm * c + 1, cl(c * 3))
                    s.tag(im, t, 3.6, s.dur + 1, txt, (p[0], p[1] - Lm - 92), dx=dx)
            # tela dividida: o painel entra e sai junto com o vídeo (mesma curva do core.split)
            a = ease_out(t / .55) * (1 - ease((t - (s.dur - .55)) / .55)); full = Image.new('RGBA', (W, H), (0, 0, 0, 0))
            d = ImageDraw.Draw(im); d.rectangle([0, 0, W, 4], fill=(201, 150, 96, 255))
            full.alpha_composite(im, (0, int(960 + (1 - a) * 960))); return full
        return im

def main(a):
    if a[0] == 'preparar': return preparar(a[1], a[2])
    n, dur, trab, out = int(a[1]), float(a[2]), a[3], a[4]; dd = float(a[5]) if len(a) > 5 and a[5] else dur
    K = dd / dur; os.makedirs(out, exist_ok=True); C = Cena(trab, n, dd)
    ts = [float(x) for x in a[6].split(',')] if len(a) > 6 else [i / 30 * K for i in range(int(math.ceil(dur * 30)) + 2)]
    for i, t in enumerate(ts):
        C.render(t).save(os.path.join(out, (f't{t}' if len(a) > 6 else f'{i:05d}') + '.png'), compress_level=1)
    print('ok', n, len(ts))

if __name__ == '__main__':
    if len(sys.argv) < 3: sys.exit(__doc__)
    main(sys.argv[1:])
