"""DocOn Artes · gera artes estáticas (post único, story, carrossel) no mesmo sistema visual do DocOn Studio.

uso:
  python3 arte.py PLANO.json SAIDA_DIR [--estilo estilo.json] [--identidade identidade.json]

PLANO.json (veja exemplos/):
  {"formato": "post" | "story" | "carrossel" | "quadrado",
   "tema": "...", "fundo": {"tipo": "escuro" | "claro" | "gradiente" | "foto", "foto": "/caminho.jpg"},
   "assinatura": {"nome": "Dra. …", "registro": "CRM … / RQE …", "handle": "@…"},   # só o que foi informado
   "referencia": {"paleta": {"glass": "#..", "text": "#..", "key": "#..", ...}, "fontes": {"titulo": "...", "texto": "..."},
                  "cantos": 34, "densidade": "leve" | "media" | "densa", "alinhamento": "esquerda" | "centro",
                  "titulo_caixa": "normal" | "alta", "observacoes": "..."},           # o que se tirou das referências: MANDA
                                                                                       # sobre a identidade e o estilo (que são a base)
   "slides": [{"layout": "capa", "kicker": "...", "titulo": "...", "destaque": "palavra", "subtitulo": "...", "foto": "..."},
              {"layout": "texto", "titulo": "...", "corpo": "..."},
              {"layout": "lista", "titulo": "...", "itens": [{"icone": "check", "texto": "..."}]},
              {"layout": "numero", "valor": "87%", "rotulo": "...", "texto": "...", "fonte": "estudo X (se houver)"},
              {"layout": "passos", "titulo": "...", "itens": ["...", "..."]},
              {"layout": "comparacao", "titulo": "...", "esquerda": {"titulo": "Mito", "texto": "..."}, "direita": {"titulo": "Verdade", "texto": "..."}},
              {"layout": "citacao", "frase": "...", "autor": "..."},
              {"layout": "cta", "titulo": "...", "acao": "Agende sua avaliação", "texto": "..."}]}
  post/quadrado/story usam só o primeiro slide; carrossel usa todos (2 a 10).

Layout: scripts/arte_engine.js (o MESMO motor da aba Artes do DocOn Studio; mude lá e rode tools/sync_arte_engine.py).
Cores e fontes: do estilo do DocOn Studio (paleta glass/text/key/icon/grad1/grad2/button/button_fg/pill_*), com a identidade do
cliente por cima (paleta, fontes, logo). Saída: arte_01.png… (1080 de largura), carrossel.pdf e folha.png (visão geral).
"""
import html, json, os, re, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
CINEMA = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'docon-cinema', 'scripts')
def fontes(estilo, ident, dest, ref_fontes=None):
    """baixa (Google Fonts, via fontes.py do docon-cinema) e copia as fontes para a pasta da arte; devolve o CSS @font-face."""
    sys.path.insert(0, CINEMA)
    try: import fontes as F
    except Exception: F = None
    fo = {**((estilo or {}).get('fontes') or {}), **{k: v for k, v in ((ident or {}).get('fontes') or {}).items() if v}, **{k: v for k, v in (ref_fontes or {}).items() if v}}
    css = []
    for papel, fam, pesos, padrao in [('titulo', fo.get('titulo') or 'Montserrat', [800, 600], 'Montserrat-800.ttf'), ('texto', fo.get('texto') or 'Inter', [700, 500], 'InterDisplay-Bold.ttf')]:
        for w in pesos:
            p = None
            if F:
                try: p = F.baixar(fam, w)
                except Exception: p = None
            p = p or os.path.join(CINEMA, 'fonts', padrao)
            if p and os.path.exists(p):
                nome = f'{papel}-{w}.ttf'; shutil.copy(p, os.path.join(dest, nome))
                css.append(f'@font-face{{font-family:"Doc{papel.title()}";src:url("{nome}");font-weight:{w};}}')
    return '\n'.join(css), fo

def gerar(plano, saida, estilo=None, ident=None):
    """monta e renderiza com o motor arte_engine.js (o mesmo da aba Artes do DocOn Studio)."""
    saida = os.path.abspath(saida); os.makedirs(saida, exist_ok=True); fmt = plano.get('formato', 'post')
    slides = plano.get('slides') or []
    if not slides: sys.exit('plano sem slides')
    if fmt == 'carrossel' and not (2 <= len(slides) <= 10): sys.exit('carrossel precisa de 2 a 10 slides')
    ref = plano.get('referencia') or {}                                   # a REFERÊNCIA manda; identidade e estilo são a base
    css_f, _ = fontes(estilo, ident, saida, ref.get('fontes'))
    arquivos = {}
    def copia(src):
        if not src or src in arquivos: return
        if re.match(r'^(https?:|data:|/_blob/)', src): return
        nome = f'img_{len(arquivos) + 1}{os.path.splitext(src)[1] or ".png"}'; shutil.copy(src, os.path.join(saida, nome)); arquivos[src] = nome
    for s in slides: copia(s.get('foto'))
    copia((plano.get('fundo') or {}).get('foto')); logo = (ident or {}).get('logo'); copia(logo)
    trab = {'plano': plano, 'estilo': estilo or {}, 'ident': ident or {}, 'saida': saida, 'fontes_css': css_f,
            'ft': '"DocTitulo",sans-serif', 'fx': '"DocTexto",sans-serif', 'logo': arquivos.get(logo, ''), 'arquivos': arquivos}
    tj = os.path.join(saida, 'trabalho.json'); json.dump(trab, open(tj, 'w'), ensure_ascii=False)
    r = subprocess.run(['node', os.path.join(HERE, 'render.mjs'), tj], capture_output=True, text=True)
    if r.returncode != 0: sys.exit('render falhou:\n' + (r.stdout + r.stderr)[-2000:])
    avisos = [l for l in r.stdout.splitlines() if l.startswith('{')]
    pngs = sorted(os.path.join(saida, f) for f in os.listdir(saida) if re.match(r'arte_\d\d\.png$', f))
    n = len(slides) if fmt == 'carrossel' else 1; pngs = pngs[:n]
    from PIL import Image
    ims = [Image.open(p).convert('RGB') for p in pngs]; W, H = ims[0].size
    if fmt == 'carrossel': ims[0].save(os.path.join(saida, 'carrossel.pdf'), save_all=True, append_images=ims[1:], resolution=72)
    th = [im.resize((int(W * 360 / H), 360)) for im in ims]; folha = Image.new('RGB', (sum(t.width for t in th) + 12 * (len(th) + 1), 384), (24, 22, 21)); x = 12
    for t in th: folha.paste(t, (x, 12)); x += t.width + 12
    folha.save(os.path.join(saida, 'folha.png'))
    return pngs, avisos

if __name__ == '__main__':
    a = sys.argv[1:]
    if len(a) < 2: sys.exit(__doc__)
    def opt(n): return json.load(open(a[a.index(n) + 1])) if n in a else None
    plano = json.load(open(a[0])); est = opt('--estilo') or plano.get('estilo'); idt = opt('--identidade') or plano.get('identidade')
    pngs, avisos = gerar(plano, a[1], est, idt)
    for p in pngs: print(p)
    for w in avisos: print('AVISO', w)
