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

Cores e fontes: do estilo do DocOn Studio (paleta glass/text/key/icon/grad1/grad2/button/button_fg/pill_*), com a identidade do
cliente por cima (paleta, fontes, logo). Saída: arte_01.png… (1080 de largura), carrossel.pdf e folha.png (visão geral).
"""
import html, json, os, re, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
CINEMA = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'docon-cinema', 'scripts')
TAM = {'post': (1080, 1350), 'carrossel': (1080, 1350), 'quadrado': (1080, 1080), 'story': (1080, 1920)}
PAL = {'glass': '#34241e', 'text': '#f8f3ea', 'key': '#f2d6a6', 'icon': '#e9c48c', 'grad1': '#f6deac', 'grad2': '#c99660',
       'button': '#b76e79', 'button_fg': '#f8f3ea', 'pill_bg': '#f2d6a6', 'pill_fg': '#34241e', 'border': '#e8d3b0'}
ICONES = {
    'check': '<circle cx="12" cy="12" r="9.5"/><path d="M7.5 12.4l3 3 6-6.4"/>',
    'heart': '<path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z"/>',
    'sparkle': '<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z"/>',
    'calendar': '<rect x="4" y="5" width="16" height="15" rx="2.5"/><path d="M4 10h16M9 3v4M15 3v4"/>',
    'target': '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="4.5"/><circle cx="12" cy="12" r="1"/>',
    'clock': '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
    'shield': '<path d="M12 3l7 3v5.5c0 4.4-3 7.7-7 9.5-4-1.8-7-5.1-7-9.5V6z"/><path d="M9 12l2 2 4-4.5"/>',
    'leaf': '<path d="M5 19c0-8 5-13 14-14-1 9-6 14-14 14z"/><path d="M5 19l7-7"/>',
    'star': '<path d="M12 3.5l2.6 5.3 5.9.9-4.3 4.1 1 5.8L12 16.9l-5.2 2.7 1-5.8-4.3-4.1 5.9-.9z"/>',
    'alert': '<path d="M12 4l9 16H3z"/><path d="M12 10v4M12 17.2v.3"/>',
    'chat': '<path d="M5 6h14v9H10l-4 3v-3H5z"/>',
    'x': '<circle cx="12" cy="12" r="9.5"/><path d="M9 9l6 6M15 9l-6 6"/>',
}
def esc(t): return html.escape(str(t or ''))
def icone(n, cls='ic'):
    return f'<svg class="{cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">{ICONES.get(n, ICONES["check"])}</svg>'

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

def realce(titulo, destaque):
    t = esc(titulo).replace('\n', '<br>')
    for d in [x.strip() for x in str(destaque or '').split(',') if x.strip()]:
        t = re.sub(re.escape(esc(d)), lambda m: f'<span class="grad">{m.group(0)}</span>', t, count=1, flags=re.I)
    return t

CSS = r"""
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:var(--w);height:var(--h);overflow:hidden}
body{font-family:"DocTexto","Inter",sans-serif;color:var(--fg);background:var(--bg);-webkit-font-smoothing:antialiased}
.arte{position:relative;width:var(--w);height:var(--h);overflow:hidden;padding:var(--safe-t) 84px var(--safe-b);display:flex;flex-direction:column;gap:34px}
.fundo{position:absolute;inset:0;z-index:0}
.fundo img{width:100%;height:100%;object-fit:cover}
.fundo:after{content:"";position:absolute;inset:0;background:var(--veu)}
.arte>*:not(.fundo){position:relative;z-index:1}
.kicker{align-self:flex-start;background:var(--pill_bg);color:var(--pill_fg);font:800 26px/1 "DocTitulo",sans-serif;letter-spacing:.12em;text-transform:uppercase;padding:14px 24px;border-radius:999px}
.centro .kicker{align-self:center}
.tit{font:800 var(--t1,92px)/1.04 "DocTitulo",sans-serif;letter-spacing:-.015em;text-wrap:balance;text-transform:var(--caixa,none)}
.tit2{font:800 var(--t2,64px)/1.08 "DocTitulo",sans-serif;letter-spacing:-.01em;text-wrap:balance;text-transform:var(--caixa,none)}
.grad{background:linear-gradient(100deg,var(--grad1),var(--grad2));-webkit-background-clip:text;background-clip:text;color:transparent}
.sub{font:500 38px/1.35 "DocTexto",sans-serif;color:var(--fg2);text-wrap:pretty}
.corpo{font:500 40px/1.45 "DocTexto",sans-serif;color:var(--fg2);text-wrap:pretty}
.corpo p+p{margin-top:24px}
.vidro{background:var(--card);border:2px solid var(--borda);border-radius:var(--r,34px);padding:44px 48px;backdrop-filter:blur(18px)}
.itens{display:grid;gap:28px}
.item{display:grid;grid-template-columns:72px 1fr;gap:26px;align-items:center;font:700 42px/1.25 "DocTexto",sans-serif}
.ic{width:72px;height:72px;color:var(--icon)}
.num{font:900 var(--tn,250px)/.95 "DocTitulo",sans-serif;letter-spacing:-.03em}
.rotulo{font:700 46px/1.2 "DocTexto",sans-serif}
.fonte{font:500 26px/1.3 "DocTexto",sans-serif;color:var(--fg3)}
.passos{display:grid;gap:30px}
.passo{display:grid;grid-template-columns:90px 1fr;gap:28px;align-items:start}
.passo b{display:grid;place-items:center;width:90px;height:90px;border-radius:50%;background:var(--key);color:var(--glass);font:800 44px/1 "DocTitulo",sans-serif}
.passo span{font:600 40px/1.3 "DocTexto",sans-serif;padding-top:18px}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:26px;flex:1;min-height:0}
.col h3{font:800 44px/1.1 "DocTitulo",sans-serif;margin-bottom:18px;display:flex;gap:14px;align-items:center}
.col h3 .ic{width:52px;height:52px}
.col p{font:500 36px/1.4 "DocTexto",sans-serif;color:var(--fg2)}
.aspas{font:900 260px/.6 "DocTitulo",serif;color:var(--key);height:120px}
.frase{font:700 var(--tq,64px)/1.2 "DocTitulo",sans-serif;text-wrap:balance}
.autor{font:600 34px/1.3 "DocTexto",sans-serif;color:var(--fg2)}
.botao{align-self:flex-start;background:var(--button);color:var(--button_fg);font:800 42px/1 "DocTexto",sans-serif;padding:30px 48px;border-radius:999px}
.centro .botao{align-self:center}
.mola{flex:1}
.conteudo{flex:1;min-height:0;display:flex;flex-direction:column;gap:34px;justify-content:var(--just,center)}
.decor{position:absolute;inset:0;z-index:0;pointer-events:none;background:radial-gradient(60% 45% at 92% 6%,color-mix(in srgb,var(--grad2) 30%,transparent),transparent 70%),radial-gradient(50% 40% at 0% 100%,color-mix(in srgb,var(--key) 14%,transparent),transparent 70%)}
.decor:after{content:"";position:absolute;width:760px;height:760px;right:-300px;top:-260px;border-radius:50%;border:3px solid color-mix(in srgb,var(--key) 22%,transparent)}
.claro .decor{background:radial-gradient(60% 45% at 92% 6%,color-mix(in srgb,var(--grad2) 22%,transparent),transparent 70%)}
.rodape{display:flex;align-items:center;gap:22px;font:600 28px/1.2 "DocTexto",sans-serif;color:var(--fg2)}
.rodape img{height:64px;max-width:300px;object-fit:contain}
.rodape .nome b{display:block;color:var(--fg);font-weight:700}
.rodape .pag{margin-left:auto;display:flex;gap:10px;align-items:center}
.rodape .pag i{width:14px;height:14px;border-radius:50%;background:var(--fg3)}
.rodape .pag i.on{width:40px;border-radius:8px;background:var(--key)}
.arrasta{display:flex;gap:12px;align-items:center;font:700 30px/1 "DocTexto",sans-serif;color:var(--key)}
.arrasta svg{width:44px;height:44px}
.foto{border-radius:var(--r,34px);overflow:hidden;flex:1;min-height:0}
.foto img{width:100%;height:100%;object-fit:cover}
.centro{text-align:center;align-items:center}
.centro .itens,.centro .passos{text-align:left}
"""
FIT_JS = """<script>
// texto que não cabe encolhe até 72% do tamanho; se ainda vazar, o render avisa (menos palavras no plano)
for (const el of document.querySelectorAll('[data-fit]')) { let k = 1; const base = parseFloat(getComputedStyle(el).fontSize);
  const tol = () => parseFloat(getComputedStyle(el).fontSize) * 0.25 + 2;
  while ((el.scrollHeight > el.clientHeight + tol() || el.scrollWidth > el.clientWidth + 2) && k > 0.72) { k -= 0.04; el.style.fontSize = (base * k) + 'px'; } }
</script>"""

def cores(estilo, ident, fundo, ref_paleta=None):
    p = {**PAL, **((estilo or {}).get('paleta') or {}), **{k: v for k, v in ((ident or {}).get('paleta') or {}).items() if v}, **{k: v for k, v in (ref_paleta or {}).items() if v}}
    tipo = (fundo or {}).get('tipo', 'escuro')
    if tipo == 'claro':   # fundo claro: o texto passa a ser a cor do vidro
        v = {'bg': p['text'], 'fg': p['glass'], 'fg2': f"color-mix(in srgb,{p['glass']} 78%,transparent)", 'fg3': f"color-mix(in srgb,{p['glass']} 45%,transparent)",
             'card': f"color-mix(in srgb,{p['glass']} 7%,{p['text']})", 'borda': f"color-mix(in srgb,{p['glass']} 14%,transparent)", 'veu': 'none'}
    else:
        v = {'bg': p['glass'] if tipo != 'gradiente' else f"linear-gradient(160deg,{p['glass']},color-mix(in srgb,{p['glass']} 70%,{p['grad2']}))",
             'fg': p['text'], 'fg2': f"color-mix(in srgb,{p['text']} 82%,transparent)", 'fg3': f"color-mix(in srgb,{p['text']} 45%,transparent)",
             'card': f"color-mix(in srgb,{p['glass']} 62%,transparent)", 'borda': f"color-mix(in srgb,{p['border']} 40%,transparent)",
             'veu': f"linear-gradient(180deg,color-mix(in srgb,{p['glass']} 35%,transparent) 0%,color-mix(in srgb,{p['glass']} 55%,transparent) 45%,color-mix(in srgb,{p['glass']} 92%,transparent) 100%)" if tipo == 'foto' else 'none'}
    return p, v

def corpo_html(s, i, n, plano, assets):
    L = s.get('layout', 'capa'); out = []; alin = (plano.get('referencia') or {}).get('alinhamento', 'esquerda')
    if s.get('kicker'): out.append(f'<span class="kicker">{esc(s["kicker"])}</span>')
    if L == 'capa':
        if s.get('foto'): out.append(f'<div class="foto"><img src="{assets(s["foto"])}" alt=""></div>')
        else: out.append('<div class="mola"></div>')
        out.append(f'<h1 class="tit" data-fit="titulo" style="max-height:{"46%" if s.get("foto") else "62%"}">{realce(s.get("titulo"), s.get("destaque"))}</h1>')
        if s.get('subtitulo'): out.append(f'<p class="sub" data-fit="subtitulo">{esc(s["subtitulo"])}</p>')
        if plano.get('formato') == 'carrossel' and n > 1: out.append('<div class="arrasta">Arraste para o lado <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M5 12h13M13 6l6 6-6 6"/></svg></div>')
    elif L == 'texto':
        out.append(f'<h2 class="tit2" data-fit="titulo">{realce(s.get("titulo"), s.get("destaque"))}</h2>')
        out.append('<div class="corpo" data-fit="corpo" style="flex:1;min-height:0">' + ''.join(f'<p>{esc(x)}</p>' for x in str(s.get('corpo', '')).split('\n') if x.strip()) + '</div>')
    elif L == 'lista':
        if s.get('titulo'): out.append(f'<h2 class="tit2" data-fit="titulo">{realce(s.get("titulo"), s.get("destaque"))}</h2>')
        its = ''.join(f'<div class="item">{icone((it or {}).get("icone", "check") if isinstance(it, dict) else "check")}<span>{esc(it.get("texto") if isinstance(it, dict) else it)}</span></div>' for it in s.get('itens', []))
        out.append(f'<div class="vidro itens" data-fit="itens">{its}</div><div class="mola"></div>')
    elif L == 'numero':
        out.append('<div class="mola"></div>')
        out.append(f'<div class="num grad">{esc(s.get("valor"))}</div><div class="rotulo">{esc(s.get("rotulo"))}</div>')
        if s.get('texto'): out.append(f'<p class="sub" data-fit="texto">{esc(s["texto"])}</p>')
        if s.get('fonte'): out.append(f'<p class="fonte">Fonte: {esc(s["fonte"])}</p>')
        out.append('<div class="mola"></div>')
    elif L == 'passos':
        if s.get('titulo'): out.append(f'<h2 class="tit2" data-fit="titulo">{realce(s.get("titulo"), s.get("destaque"))}</h2>')
        out.append('<div class="passos" data-fit="passos">' + ''.join(f'<div class="passo"><b>{k + 1}</b><span>{esc(t)}</span></div>' for k, t in enumerate(s.get('itens', []))) + '</div><div class="mola"></div>')
    elif L == 'comparacao':
        if s.get('titulo'): out.append(f'<h2 class="tit2" data-fit="titulo">{realce(s.get("titulo"), s.get("destaque"))}</h2>')
        e, d = s.get('esquerda') or {}, s.get('direita') or {}
        out.append(f'<div class="cols"><div class="vidro col" data-fit="esquerda"><h3>{icone(e.get("icone", "x"))}{esc(e.get("titulo"))}</h3><p>{esc(e.get("texto"))}</p></div>'
                   f'<div class="vidro col" data-fit="direita"><h3>{icone(d.get("icone", "check"))}{esc(d.get("titulo"))}</h3><p>{esc(d.get("texto"))}</p></div></div>')
    elif L == 'citacao':
        out.append('<div class="mola"></div><div class="aspas">“</div>')
        out.append(f'<p class="frase" data-fit="frase">{esc(s.get("frase"))}</p>')
        if s.get('autor'): out.append(f'<p class="autor">{esc(s["autor"])}</p>')
        out.append('<div class="mola"></div>')
    elif L == 'cta':
        out.append('<div class="mola"></div>')
        out.append(f'<h2 class="tit" data-fit="titulo" style="--t1:84px">{realce(s.get("titulo"), s.get("destaque"))}</h2>')
        if s.get('texto'): out.append(f'<p class="sub" data-fit="texto">{esc(s["texto"])}</p>')
        if s.get('acao'): out.append(f'<span class="botao">{esc(s["acao"])}</span>')
        out.append('<div class="mola"></div>')
    else: sys.exit(f'layout desconhecido: {L}')
    return out, (alin == 'centro' or L in ('citacao', 'numero'))

def rodape(plano, ident, i, n, assets):
    a = plano.get('assinatura') or {}; logo = (ident or {}).get('logo')
    esq = f'<img src="{assets(logo)}" alt="">' if logo else ''
    nome = f'<span class="nome"><b>{esc(a.get("nome"))}</b>{esc(" · ".join(x for x in [a.get("registro"), a.get("handle")] if x))}</span>' if (a.get('nome') or a.get('handle')) else ''
    pag = ''.join(f'<i class="{"on" if k == i else ""}"></i>' for k in range(n)) if n > 1 else ''
    return f'<div class="rodape">{esq}{nome}<span class="pag">{pag}</span></div>'

def gerar(plano, saida, estilo=None, ident=None):
    os.makedirs(saida, exist_ok=True); fmt = plano.get('formato', 'post'); W, H = TAM.get(fmt, TAM['post'])
    slides = plano.get('slides') or []
    if not slides: sys.exit('plano sem slides')
    if fmt != 'carrossel': slides = slides[:1]
    if fmt == 'carrossel' and not (2 <= len(slides) <= 10): sys.exit('carrossel precisa de 2 a 10 slides')
    ref = plano.get('referencia') or {}                                   # a REFERÊNCIA manda; identidade e estilo são a base
    css_f, fo = fontes(estilo, ident, saida, ref.get('fontes'))
    p, v = cores(estilo, ident, plano.get('fundo'), ref.get('paleta'))
    safe_t, safe_b = (250, 300) if fmt == 'story' else (96, 84)            # story: fora da barra do topo e da caixa de resposta
    raiz = {'w': f'{W}px', 'h': f'{H}px', 'safe-t': f'{safe_t}px', 'safe-b': f'{safe_b}px', 'r': f'{int(ref.get("cantos", 34))}px',
            'caixa': 'uppercase' if ref.get('titulo_caixa') == 'alta' else 'none', **{k.replace('_', '_'): c for k, c in p.items()}, **v}
    if fmt == 'story': raiz.update({'t1': '104px', 't2': '72px'})
    if fmt == 'quadrado': raiz.update({'t1': '80px', 't2': '58px', 'tn': '210px'})
    dens = ref.get('densidade', 'media'); escala = {'leve': 1.06, 'media': 1.0, 'densa': 0.9}.get(dens, 1.0)
    copiados = {}
    def assets(src):
        if not src: return ''
        if src in copiados: return copiados[src]
        nome = f'img_{len(copiados) + 1}{os.path.splitext(src)[1] or ".png"}'; shutil.copy(src, os.path.join(saida, nome)); copiados[src] = nome; return nome
    fundo_img = (plano.get('fundo') or {}).get('foto')
    paginas = []
    for i, s in enumerate(slides):
        partes, centro = corpo_html(s, i, len(slides), plano, assets)
        partes = [x for x in partes if x not in ('<div class="mola"></div>',)]
        partes = [x.replace('<div class="mola"></div>', '') for x in partes]
        just = 'flex-end' if s.get('layout', 'capa') == 'capa' and not s.get('foto') else 'flex-start' if s.get('layout') == 'capa' else 'center'
        decor = '' if fundo_img and i == 0 else '<div class="decor"></div>'
        fundo = f'<div class="fundo"><img src="{assets(fundo_img)}" alt=""></div>' if fundo_img and (i == 0 or (plano.get('fundo') or {}).get('todas')) else ''
        root = ';'.join(f'--{k}:{val}' for k, val in raiz.items())
        doc = f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><style>{css_f}
:root{{{root}}}{CSS}
.arte{{font-size:{escala}em}}</style></head><body><div class="arte {"centro" if centro else ""} {(plano.get("fundo") or {}).get("tipo", "escuro")}" style="--just:{just}">{fundo}{decor}<div class="conteudo">{"".join(partes)}</div>{rodape(plano, ident, i, len(slides), assets)}</div>{FIT_JS}</body></html>"""
        hp = os.path.join(saida, f'arte_{i + 1:02d}.html'); open(hp, 'w').write(doc)
        paginas.append({'html': os.path.abspath(hp), 'png': os.path.abspath(os.path.join(saida, f'arte_{i + 1:02d}.png')), 'w': W, 'h': H})
    pj = os.path.join(saida, 'render.json'); json.dump({'paginas': paginas}, open(pj, 'w'))
    r = subprocess.run(['node', os.path.join(HERE, 'render.mjs'), os.path.abspath(pj)], capture_output=True, text=True)
    if r.returncode != 0: sys.exit('render falhou:\n' + (r.stdout + r.stderr)[-2000:])
    avisos = [l for l in r.stdout.splitlines() if l.startswith('{')]
    from PIL import Image
    ims = [Image.open(pg['png']).convert('RGB') for pg in paginas]
    if fmt == 'carrossel': ims[0].save(os.path.join(saida, 'carrossel.pdf'), save_all=True, append_images=ims[1:], resolution=72)
    th = [im.resize((int(W * 360 / H), 360)) for im in ims]; folha = Image.new('RGB', (sum(t.width for t in th) + 12 * (len(th) + 1), 384), (24, 22, 21)); x = 12
    for t in th: folha.paste(t, (x, 12)); x += t.width + 12
    folha.save(os.path.join(saida, 'folha.png'))
    return [pg['png'] for pg in paginas], avisos

if __name__ == '__main__':
    a = sys.argv[1:]
    if len(a) < 2: sys.exit(__doc__)
    def opt(n): return json.load(open(a[a.index(n) + 1])) if n in a else None
    plano = json.load(open(a[0])); est = opt('--estilo') or plano.get('estilo'); idt = opt('--identidade') or plano.get('identidade')
    pngs, avisos = gerar(plano, a[1], est, idt)
    for p in pngs: print(p)
    for w in avisos: print('AVISO', w)
