"""DocOn Artes · lê as REFERÊNCIAS de design e devolve uma base para o `referencia` do plano.

uso:
  python3 referencias.py SAIDA_DIR ref1.png ref2.jpg ref3.pdf ...

Saída:
  SAIDA_DIR/referencias.png   folha com as referências lado a lado e a paleta extraída embaixo (olhe com Read)
  SAIDA_DIR/referencia.json   rascunho {"paleta": {...}, "cores_dominantes": [...], "fundo": "escuro|claro"}
O rascunho é só o ponto de partida: olhe a folha, confira as cores e complete à mão fontes, cantos, densidade,
alinhamento, caixa do título e observações (o que se repete nas referências). A referência MANDA no plano.
"""
import colorsys, json, os, subprocess, sys, tempfile
from PIL import Image, ImageDraw, ImageFont


def abrir(caminho, tmp):
    if caminho.lower().endswith('.pdf'):                      # 1ª página do PDF
        base = os.path.join(tmp, os.path.basename(caminho))
        subprocess.run(['pdftoppm', '-png', '-r', '60', '-f', '1', '-l', '1', caminho, base], check=True)
        caminho = next(os.path.join(tmp, f) for f in sorted(os.listdir(tmp)) if f.startswith(os.path.basename(caminho)))
    return Image.open(caminho).convert('RGB')


def hexa(c): return '#%02x%02x%02x' % tuple(c)
def lum(c): return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
def sat(c): return colorsys.rgb_to_hls(*[x / 255 for x in c])[2]


def dominantes(imgs, n=10):
    tiras = [im.copy() for im in imgs]
    for t in tiras: t.thumbnail((200, 200))
    W = sum(t.width for t in tiras); H = max(t.height for t in tiras)
    mosaico = Image.new('RGB', (W, H)); x = 0
    for t in tiras: mosaico.paste(t, (x, 0)); x += t.width
    q = mosaico.quantize(colors=n, method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette()[:n * 3]; cont = sorted(q.getcolors(), reverse=True)
    return [(pal[i * 3:i * 3 + 3], c) for c, i in cont]


def sugerir(doms):
    cores = [c for c, _ in doms]; fundo = cores[0]; escuro = lum(fundo) < 128
    texto = max(cores, key=lambda c: abs(lum(c) - lum(fundo)))
    dist = lambda a, b: sum((x - y) ** 2 for x, y in zip(a, b)) ** .5
    vivas = [c for c in cores[1:] if dist(c, texto) > 45 and dist(c, fundo) > 45]       # nem fundo nem texto
    vivas.sort(key=lambda c: -(sat(c) + 0.15) * (1 + abs(lum(c) - lum(fundo)) / 255))
    key = vivas[0] if vivas else texto; acento = vivas[1] if len(vivas) > 1 else key
    return {'glass': hexa(fundo), 'text': hexa(texto), 'key': hexa(key), 'icon': hexa(key), 'grad1': hexa(key), 'grad2': hexa(acento),
            'button': hexa(acento), 'button_fg': hexa(texto if lum(acento) < 140 else fundo), 'pill_bg': hexa(key),
            'pill_fg': hexa(fundo), 'border': hexa(key)}, ('escuro' if escuro else 'claro')


def main(a):
    saida, refs = a[0], a[1:]
    os.makedirs(saida, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        imgs = [abrir(r, tmp) for r in refs]
    doms = dominantes(imgs); paleta, fundo = sugerir(doms)
    h = 520; tiras = [im.resize((max(1, int(im.width * h / im.height)), h)) for im in imgs]
    W = max(900, sum(t.width for t in tiras) + 20 * (len(tiras) + 1))
    folha = Image.new('RGB', (W, h + 240), '#151515'); d = ImageDraw.Draw(folha); x = 20
    for t in tiras: folha.paste(t, (x, 20)); x += t.width + 20
    try: f = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 18)
    except Exception: f = ImageFont.load_default()
    for k, (c, _) in enumerate(doms):
        x0 = 20 + k * 110; d.rectangle([x0, h + 50, x0 + 96, h + 140], fill=tuple(c)); d.text((x0, h + 150), hexa(c), fill='#dddddd', font=f)
    for k, (nome, cor) in enumerate(list(paleta.items())[:6]):
        x0 = 20 + k * 150; d.rectangle([x0, h + 190, x0 + 24, h + 214], fill=cor); d.text((x0 + 32, h + 192), nome, fill='#dddddd', font=f)
    folha.save(os.path.join(saida, 'referencias.png'))
    rasc = {'paleta': paleta, 'fundo': fundo, 'cores_dominantes': [hexa(c) for c, _ in doms],
            'fontes': {}, 'cantos': None, 'densidade': None, 'alinhamento': None, 'titulo_caixa': None, 'observacoes': ''}
    json.dump(rasc, open(os.path.join(saida, 'referencia.json'), 'w'), ensure_ascii=False, indent=1)
    print(json.dumps({'folha': os.path.join(saida, 'referencias.png'), 'paleta': paleta, 'fundo': fundo}, ensure_ascii=False))


if __name__ == '__main__':
    if len(sys.argv) < 3: sys.exit(__doc__)
    main(sys.argv[1:])
