"""DocOn Cinema · desenho vetorial (PIL, supersample 3x): texto, ícones, pílulas, vidro.
A paleta fica em P e pode ser trocada pelo projeto com set_palette({...}) antes de criar os elementos."""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np, math
import os
F = __file__.rsplit('/', 1)[0] + '/fonts/'
if not os.path.exists(F + 'InterDisplay-Bold.ttf'): F = os.path.expanduser('~/.docon/fonts/')
# paleta padrão DocOn (dourado rosê / marfim / vidro espresso). Chaves:
#  text: texto sobre o vidro · icon: traço de ícones · accent: destaque (palavra-chave do gancho, botão)
#  key: palavra-chave na legenda · pill_bg/pill_fg: kicker · border: borda do vidro · glass: tinta do vidro
#  grad1/grad2: degradê do texto-destaque · button/button_fg: botão do cartão final
P = dict(text=(248, 243, 234), icon=(233, 196, 140), accent=(233, 196, 140), key=(242, 214, 166),
         pill_bg=(242, 214, 166), pill_fg=(52, 36, 30), border=(232, 211, 176), glass=(52, 36, 30), glass_alpha=0.60,
         grad1=(246, 222, 172), grad2=(201, 150, 96), button=(183, 110, 121), button_fg=(248, 243, 234))
def set_palette(d): P.update(d)
# aliases legados
IVORY = P['text']; ROSE = P['button']; CHAMP = P['border']; GOLD = P['icon']; GOLD_L = P['key']; ESP = P['glass']
SS = 3
_fc = {}
def font(name, size):
    k = (name, size)
    if k not in _fc: _fc[k] = ImageFont.truetype(F + name, size)
    return _fc[k]
# fontes do estilo (Studio › Estilos › Fontes): títulos no lugar da Montserrat, textos no lugar da Inter Display
FONTES = {'titulo': None, 'texto': None}
_PESO = {'Black': 900, 'ExtraBold': 800, 'Bold': 700, 'SemiBold': 600, 'Medium': 500, 'Regular': 400}
def set_fonts(titulo=None, texto=None):
    FONTES.update(titulo=None if titulo in (None, '', 'Montserrat') else titulo, texto=None if texto in (None, '', 'Inter') else texto)
def _gf(fam, peso, s):
    k = ('gf', fam, peso, s)
    if k not in _fc:
        import fontes
        p = fontes.baixar(fam, peso); _fc[k] = ImageFont.truetype(p, s) if p else None
    return _fc[k]
def MONT(w, s):
    f = FONTES['titulo'] and _gf(FONTES['titulo'], int(w), s)
    return f or font(f'Montserrat-{w}.ttf', s)
def INTER(w, s):
    f = FONTES['texto'] and _gf(FONTES['texto'], _PESO.get(w, 700), s)
    return f or font(f'InterDisplay-{w}.ttf', s)

def down(im):
    return im.resize((im.width // SS, im.height // SS), Image.LANCZOS)

SOMBRA = 0.0      # sombra de texto do estilo (0..1): vale para todo texto desenhado com text_sprite
def text_sprite(txt, fnt, fill, shadow=0.0, shadow_r=10, track=0, pad=30):
    """RGBA sprite of text, optional diffuse shadow."""
    shadow = max(shadow, SOMBRA)
    l, t, r, b = fnt.getbbox(txt); asc, desc = fnt.getmetrics(); t = 0
    w = r - l + 2 * pad + track * len(txt); h = asc + desc + 2 * pad
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    if track:
        x = pad - l
        for ch in txt:
            d.text((x, pad - t), ch, font=fnt, fill=fill); x += fnt.getlength(ch) + track
    else:
        d.text((pad - l, pad - t), txt, font=fnt, fill=fill)
    if shadow > 0:
        a = im.split()[3]
        sh = Image.new('RGBA', im.size, (20, 12, 8, 0)); sh.putalpha(a.filter(ImageFilter.GaussianBlur(shadow_r)).point(lambda v: int(v * shadow)))
        sh.alpha_composite(im); im = sh
    return im

# ---------------- icons (drawn at SS scale, returned downsampled) ----------------
def _canvas(s):
    im = Image.new('RGBA', (s * SS, s * SS), (0, 0, 0, 0)); return im, ImageDraw.Draw(im)

def icon_check(s=64, col=None, w=7):
    col = tuple(col or P['icon'])
    im, d = _canvas(s); k = SS
    d.ellipse([2 * k, 2 * k, (s - 2) * k, (s - 2) * k], outline=col, width=int(w * k * 0.6))
    pts = [(s * .28 * k, s * .52 * k), (s * .44 * k, s * .67 * k), (s * .73 * k, s * .36 * k)]
    d.line(pts, fill=col, width=int(w * k), joint='curve')
    for p in (pts[0], pts[2]): d.ellipse([p[0] - w * k / 2, p[1] - w * k / 2, p[0] + w * k / 2, p[1] + w * k / 2], fill=col)
    return down(im)

def icon_sparkle(s=80, col=None):
    col = tuple(col or P['icon'])
    im, d = _canvas(s); k = SS; c = s * k / 2
    def star(cx, cy, R, r):
        pts = []
        for i in range(8):
            ang = i * math.pi / 4 - math.pi / 2; rad = R if i % 2 == 0 else r
            pts.append((cx + rad * math.cos(ang), cy + rad * math.sin(ang)))
        d.polygon(pts, fill=col)
    star(c, c, s * k * .48, s * k * .11)
    return down(im)

def icon_heart(s=64, col=None, w=6):
    col = tuple(col or P['icon'])
    im, d = _canvas(s); k = SS
    pts = []
    for i in range(200):
        t = i / 199 * 2 * math.pi
        x = 16 * math.sin(t) ** 3; y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((s * k / 2 + x * s * k / 38, s * k / 2 - y * s * k / 38 + s * k * .03))
    d.line(pts + [pts[0]], fill=col, width=int(w * k), joint='curve')
    return down(im)

def icon_curves(s=64, col=None, w=6):
    col = tuple(col or P['icon'])
    """silhueta de cintura (duas curvas tipo ampulheta)"""
    im, d = _canvas(s); k = SS
    for sgn in (-1, 1):
        pts = []
        for i in range(60):
            y = i / 59
            x = 0.5 + sgn * (0.30 - 0.15 * math.sin(math.pi * y) ** 1.6 + 0.06 * y)
            pts.append((x * s * k, (0.08 + 0.84 * y) * s * k))
        d.line(pts, fill=col, width=int(w * k), joint='curve')
    return down(im)

def icon_dress(s=96, col=None, w=5):
    col = tuple(col or P['icon'])
    im, d = _canvas(s); k = SS; S_ = s * k
    pts = [(.40, .08), (.36, .30), (.42, .42), (.20, .92), (.80, .92), (.58, .42), (.64, .30), (.60, .08)]
    d.line([(x * S_, y * S_) for x, y in pts], fill=col, width=int(w * k), joint='curve')
    d.line([(.40 * S_, .08 * S_), (.60 * S_, .08 * S_)], fill=col, width=int(w * k))
    d.line([(.42 * S_, .42 * S_), (.58 * S_, .42 * S_)], fill=col, width=int(w * k * .7))
    return down(im)

def icon_jeans(s=96, col=None, w=5):
    col = tuple(col or P['icon'])
    im, d = _canvas(s); k = SS; S_ = s * k
    pts = [(.26, .08), (.74, .08), (.80, .92), (.58, .92), (.50, .40), (.42, .92), (.20, .92), (.26, .08)]
    d.line([(x * S_, y * S_) for x, y in pts], fill=col, width=int(w * k), joint='curve')
    d.line([(.25 * S_, .18 * S_), (.75 * S_, .18 * S_)], fill=col, width=int(w * k * .7))
    return down(im)

def icon_bikini(s=96, col=None, w=5):
    col = tuple(col or P['icon'])
    im, d = _canvas(s); k = SS; S_ = s * k; W_ = int(w * k)
    d.line([(.30 * S_, .10 * S_), (.38 * S_, .30 * S_)], fill=col, width=W_)
    d.line([(.70 * S_, .10 * S_), (.62 * S_, .30 * S_)], fill=col, width=W_)
    d.chord([.18 * S_, .20 * S_, .50 * S_, .50 * S_], 0, 180, outline=col, width=W_)
    d.chord([.50 * S_, .20 * S_, .82 * S_, .50 * S_], 0, 180, outline=col, width=W_)
    d.line([(.10 * S_, .35 * S_), (.18 * S_, .35 * S_)], fill=col, width=W_)
    d.line([(.82 * S_, .35 * S_), (.90 * S_, .35 * S_)], fill=col, width=W_)
    d.polygon([(.20 * S_, .62 * S_), (.80 * S_, .62 * S_), (.56 * S_, .88 * S_), (.44 * S_, .88 * S_)], outline=col, width=W_)
    return down(im)

def icon_diamond(s=64, col=None, w=5):
    col = tuple(col or P['icon'])
    im, d = _canvas(s); k = SS; S_ = s * k; W_ = int(w * k)
    top = [(.22, .30), (.36, .14), (.64, .14), (.78, .30)]
    d.polygon([(x * S_, y * S_) for x, y in top + [(.50, .88)]], outline=col, width=W_)
    d.line([(.22 * S_, .30 * S_), (.78 * S_, .30 * S_)], fill=col, width=W_)
    d.line([(.36 * S_, .14 * S_), (.44 * S_, .30 * S_), (.50 * S_, .88 * S_), (.56 * S_, .30 * S_), (.64 * S_, .14 * S_)], fill=col, width=int(W_ * .7))
    return down(im)

def icon_target(s=64, col=None, w=5):
    col = tuple(col or P['icon'])
    im, d = _canvas(s); k = SS; S_ = s * k; W_ = int(w * k)
    for r in (.42, .27):
        d.ellipse([(.5 - r) * S_, (.5 - r) * S_, (.5 + r) * S_, (.5 + r) * S_], outline=col, width=W_)
    d.ellipse([.42 * S_, .42 * S_, .58 * S_, .58 * S_], fill=col)
    return down(im)

def icon_sun(s=64, col=None, w=5):
    col = tuple(col or P['icon'])
    im, d = _canvas(s); k = SS; S_ = s * k; W_ = int(w * k)
    d.ellipse([.32 * S_, .32 * S_, .68 * S_, .68 * S_], outline=col, width=W_)
    for i in range(8):
        a = i * math.pi / 4
        d.line([(.5 * S_ + .27 * S_ * math.cos(a), .5 * S_ + .27 * S_ * math.sin(a)), (.5 * S_ + .44 * S_ * math.cos(a), .5 * S_ + .44 * S_ * math.sin(a))], fill=col, width=W_)
    return down(im)

def icon_mirror(s=64, col=None, w=5):
    col = tuple(col or P['icon'])
    im, d = _canvas(s); k = SS; S_ = s * k; W_ = int(w * k)
    d.ellipse([.24 * S_, .06 * S_, .76 * S_, .74 * S_], outline=col, width=W_)
    d.line([(.5 * S_, .74 * S_), (.5 * S_, .94 * S_)], fill=col, width=W_)
    d.line([(.34 * S_, .94 * S_), (.66 * S_, .94 * S_)], fill=col, width=W_)
    d.arc([.34 * S_, .18 * S_, .60 * S_, .50 * S_], 190, 250, fill=col, width=int(W_ * .7))
    return down(im)

def pill(txt, fnt, fg=None, bg=None, padx=22, pady=10, track=3):
    fg = tuple(fg or P['pill_fg']); bg = tuple(bg or P['pill_bg'])
    t = text_sprite(txt, fnt, fg, pad=0, track=track)
    w, h = t.width + 2 * padx, t.height + 2 * pady
    im = Image.new('RGBA', (w * SS, h * SS), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, w * SS - 1, h * SS - 1], radius=h * SS // 2, fill=bg)
    im = down(im); im.alpha_composite(t, (padx, pady)); return im

def rounded_mask(w, h, r):
    im = Image.new('L', (w * SS, h * SS), 0); ImageDraw.Draw(im).rounded_rectangle([0, 0, w * SS - 1, h * SS - 1], radius=r * SS, fill=255)
    return np.asarray(im.resize((w, h), Image.LANCZOS)).astype(np.float32) / 255

def border_sprite(w, h, r, col=None, a=170, width=2):
    col = tuple(col or P['border'])
    im = Image.new('RGBA', (w * SS, h * SS), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle([width, width, w * SS - 1 - width, h * SS - 1 - width], radius=r * SS, outline=col + (a,), width=width * SS)
    return down(im)

def gold_gradient_text(txt, fnt, c1=None, c2=None, pad=40):
    c1 = c1 or P['grad1']; c2 = c2 or P['grad2']
    t = text_sprite(txt, fnt, (255, 255, 255), pad=pad)
    a = np.asarray(t)[..., 3]
    h, w = a.shape; yy = np.linspace(0, 1, h)[:, None]
    rgb = np.array(c1)[None, None] * (1 - yy[..., None]) + np.array(c2)[None, None] * yy[..., None]
    rgb = np.broadcast_to(rgb, (h, w, 3))
    out = np.dstack([rgb, a]).astype(np.uint8)
    return Image.fromarray(out, 'RGBA')

def add_shadow(im, strength=0.55, r=14, off=(0, 4)):
    a = im.split()[3]; pad = r * 2
    big = Image.new('RGBA', (im.width + 2 * pad, im.height + 2 * pad), (0, 0, 0, 0))
    sh = Image.new('RGBA', big.size, (25, 14, 10, 0))
    sa = Image.new('L', big.size, 0); sa.paste(a, (pad + off[0], pad + off[1]))
    sh.putalpha(sa.filter(ImageFilter.GaussianBlur(r)).point(lambda v: int(v * strength)))
    sh.alpha_composite(im, (pad, pad)); return sh


# ---------------- ícones extras (saúde / veterinária / vlog) ----------------
def icon_paw(s=64, col=None):
    col = tuple(col or P['icon']); im, d = _canvas(s); S_ = s * SS
    d.ellipse([.28 * S_, .48 * S_, .72 * S_, .90 * S_], fill=col)
    for cx, cy, r in ((.20, .40, .10), (.38, .22, .105), (.62, .22, .105), (.80, .40, .10)):
        d.ellipse([(cx - r) * S_, (cy - r * 1.2) * S_, (cx + r) * S_, (cy + r * 1.2) * S_], fill=col)
    return down(im)

def icon_calendar(s=64, col=None, w=5, label=None):
    col = tuple(col or P['icon']); im, d = _canvas(s); S_ = s * SS; W_ = int(w * SS)
    d.rounded_rectangle([.10 * S_, .18 * S_, .90 * S_, .90 * S_], radius=.10 * S_, outline=col, width=W_)
    d.line([(.10 * S_, .36 * S_), (.90 * S_, .36 * S_)], fill=col, width=W_)
    for x in (.32, .68): d.line([(x * S_, .08 * S_), (x * S_, .26 * S_)], fill=col, width=W_)
    if label:
        f = font('InterDisplay-Bold.ttf', int(S_ * .34)); l, t, r, b = f.getbbox(label)
        d.text(((S_ - (r - l)) / 2 - l, .40 * S_ + (.48 * S_ - (b - t)) / 2 - t), label, font=f, fill=col)
    return down(im)

def icon_doc(s=64, col=None, w=5):
    col = tuple(col or P['icon']); im, d = _canvas(s); S_ = s * SS; W_ = int(w * SS)
    d.polygon([(.22 * S_, .08 * S_), (.62 * S_, .08 * S_), (.80 * S_, .26 * S_), (.80 * S_, .92 * S_), (.22 * S_, .92 * S_)], outline=col, width=W_)
    for y in (.42, .56, .70): d.line([(.34 * S_, y * S_), (.68 * S_, y * S_)], fill=col, width=int(W_ * .8))
    return down(im)

def icon_house(s=64, col=None, w=5):
    col = tuple(col or P['icon']); im, d = _canvas(s); S_ = s * SS; W_ = int(w * SS)
    d.line([(.10 * S_, .50 * S_), (.50 * S_, .14 * S_), (.90 * S_, .50 * S_)], fill=col, width=W_, joint='curve')
    d.line([(.22 * S_, .42 * S_), (.22 * S_, .88 * S_), (.78 * S_, .88 * S_), (.78 * S_, .42 * S_)], fill=col, width=W_, joint='curve')
    d.rounded_rectangle([.42 * S_, .60 * S_, .58 * S_, .88 * S_], radius=.03 * S_, outline=col, width=int(W_ * .8))
    return down(im)

def icon_stetho(s=64, col=None, w=5):
    col = tuple(col or P['icon']); im, d = _canvas(s); S_ = s * SS; W_ = int(w * SS)
    d.arc([.12 * S_, .02 * S_, .56 * S_, .56 * S_], 0, 180, fill=col, width=W_)
    d.line([(.12 * S_, .29 * S_), (.12 * S_, .10 * S_)], fill=col, width=W_); d.line([(.56 * S_, .29 * S_), (.56 * S_, .10 * S_)], fill=col, width=W_)
    d.arc([.34 * S_, .40 * S_, .84 * S_, .90 * S_], 90, 180, fill=col, width=W_)
    d.line([(.34 * S_, .52 * S_), (.34 * S_, .65 * S_)], fill=col, width=W_)
    d.line([(.59 * S_, .90 * S_), (.66 * S_, .90 * S_)], fill=col, width=W_)
    d.arc([.40 * S_, .40 * S_, .90 * S_, .90 * S_], 270, 360, fill=col, width=W_)
    d.ellipse([.70 * S_, .30 * S_, .90 * S_, .50 * S_], outline=col, width=W_)
    return down(im)

def icon_clock(s=64, col=None, w=5):
    col = tuple(col or P['icon']); im, d = _canvas(s); S_ = s * SS; W_ = int(w * SS)
    d.ellipse([.10 * S_, .10 * S_, .90 * S_, .90 * S_], outline=col, width=W_)
    d.line([(.50 * S_, .26 * S_), (.50 * S_, .50 * S_), (.68 * S_, .60 * S_)], fill=col, width=W_, joint='curve')
    return down(im)

def icon_chat(s=64, col=None, w=5):
    col = tuple(col or P['icon']); im, d = _canvas(s); S_ = s * SS; W_ = int(w * SS)
    d.rounded_rectangle([.08 * S_, .14 * S_, .92 * S_, .70 * S_], radius=.16 * S_, outline=col, width=W_)
    d.line([(.28 * S_, .70 * S_), (.22 * S_, .88 * S_), (.44 * S_, .70 * S_)], fill=col, width=W_, joint='curve')
    for x in (.32, .50, .68): d.ellipse([(x - .045) * S_, .37 * S_, (x + .045) * S_, .46 * S_], fill=col)
    return down(im)

def icon_scale(s=64, col=None, w=5, label='kg'):
    col = tuple(col or P['icon']); im, d = _canvas(s); S_ = s * SS; W_ = int(w * SS)
    d.rounded_rectangle([.10 * S_, .14 * S_, .90 * S_, .90 * S_], radius=.16 * S_, outline=col, width=W_)
    d.arc([.28 * S_, .26 * S_, .72 * S_, .70 * S_], 200, 340, fill=col, width=W_)
    d.line([(.50 * S_, .48 * S_), (.60 * S_, .34 * S_)], fill=col, width=W_)
    f = font('InterDisplay-Bold.ttf', int(S_ * .20)); l, t, r, b = f.getbbox(label)
    d.text(((S_ - (r - l)) / 2 - l, .64 * S_ - t), label, font=f, fill=col)
    return down(im)

def icon_cake(s=64, col=None, w=5):
    col = tuple(col or P['icon']); im, d = _canvas(s); S_ = s * SS; W_ = int(w * SS)
    d.rounded_rectangle([.14 * S_, .50 * S_, .86 * S_, .90 * S_], radius=.06 * S_, outline=col, width=W_)
    d.line([(.14 * S_, .66 * S_), (.86 * S_, .66 * S_)], fill=col, width=int(W_ * .7))
    d.line([(.50 * S_, .50 * S_), (.50 * S_, .30 * S_)], fill=col, width=W_)
    d.ellipse([.43 * S_, .10 * S_, .57 * S_, .28 * S_], fill=col)
    return down(im)

def icon_dog(s=64, col=None, w=5):
    """cabeça de cão (orelhas caídas) em traço"""
    col = tuple(col or P['icon']); im, d = _canvas(s); S_ = s * SS; W_ = int(w * SS)
    d.ellipse([.24 * S_, .16 * S_, .76 * S_, .82 * S_], outline=col, width=W_)
    d.chord([.04 * S_, .14 * S_, .34 * S_, .64 * S_], 60, 300, outline=col, width=W_)
    d.chord([.66 * S_, .14 * S_, .96 * S_, .64 * S_], 240, 120, outline=col, width=W_)
    d.ellipse([.36 * S_, .38 * S_, .44 * S_, .46 * S_], fill=col); d.ellipse([.56 * S_, .38 * S_, .64 * S_, .46 * S_], fill=col)
    d.ellipse([.43 * S_, .54 * S_, .57 * S_, .64 * S_], fill=col)
    return down(im)

def icon_bolt(s=64, col=None):
    col = tuple(col or P['icon']); im, d = _canvas(s); S_ = s * SS
    d.polygon([(x * S_, y * S_) for x, y in ((.56, .06), (.22, .56), (.46, .56), (.38, .94), (.78, .40), (.54, .40), (.64, .06))], fill=col)
    return down(im)

def icon_leaf(s=64, col=None, w=5):
    col = tuple(col or P['icon']); im, d = _canvas(s); S_ = s * SS; W_ = int(w * SS)
    d.chord([.12 * S_, .12 * S_, 1.1 * S_, 1.1 * S_], 180, 270, outline=col, width=W_)
    d.chord([-.1 * S_, -.1 * S_, .88 * S_, .88 * S_], 0, 90, outline=col, width=W_)
    d.line([(.18 * S_, .82 * S_), (.70 * S_, .30 * S_)], fill=col, width=int(W_ * .8))
    return down(im)

ICONS = {k[5:]: v for k, v in dict(globals()).items() if k.startswith('icon_')}
