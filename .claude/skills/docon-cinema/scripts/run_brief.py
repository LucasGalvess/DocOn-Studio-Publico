"""DocOn Cinema · modo briefing: do briefing exportado pelo DocOn Studio ao MP4 final, em um comando.

uso:
  python3 run_brief.py BRIEF.json VIDEO WORK [--out SAIDA.mp4] [--media PASTA_BROLL] [--fixes fixes.json]
                       [--stage all|prep|preview|render] [--preview t1,t2,...]

Etapas (cada uma pula se o resultado já existe em WORK):
  prep     transcreve, analisa (cortes, matte, landmarks se talking head) e faz o grade completo
  preview  monta a edição a partir do briefing e grava WORK/preview.jpg (+ WORK/plano.txt com os tempos resolvidos)
  render   vídeo final + trilha + mix + mux + folha de contato + versão H.264 ≤ 14 MB para a web (Studio, aprovação, download)

fixes.json (opcional): [{"old": "Buddercol", "new": "Border"}, {"after": "Border", "near": 8.2, "insert": [["Collie", 8.6]]}, ...]
Cada bloco do briefing é sincronizado pela frase do campo `gatilho` (busca aproximada na transcrição, perto do
tempo `inicio`). Sem gatilho, vale o tempo da timeline (segundos do bruto).
"""
import sys, os, json, re, subprocess, difflib, argparse, math
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
MODELS = os.path.expanduser('~/.docon/models')

ap = argparse.ArgumentParser(); ap.add_argument('brief'); ap.add_argument('video'); ap.add_argument('work')
ap.add_argument('--out'); ap.add_argument('--media', default=None); ap.add_argument('--fixes'); ap.add_argument('--stage', default='all')
ap.add_argument('--preview', default=None)
ap.add_argument('--formatos', default='mp4', help='mp4,mov,wav,mp3: formatos extras da entrega final')
A = ap.parse_args(); os.makedirs(A.work, exist_ok=True)
# ---- histórico: cada execução guarda o briefing (e os fixes) usados; nada é sobrescrito
import time, shutil
HIST = os.path.join(A.work, 'historico'); os.makedirs(HIST, exist_ok=True); STAMP = time.strftime('%Y%m%d-%H%M%S')
shutil.copy(A.brief, os.path.join(HIST, f'{STAMP}_{A.stage}_briefing.json'))
if A.fixes: shutil.copy(A.fixes, os.path.join(HIST, f'{STAMP}_{A.stage}_fixes.json'))
def versioned(path):
    if not os.path.exists(path): return path
    base, ext = os.path.splitext(path); k = 2
    while os.path.exists(f'{base}_v{k}{ext}'): k += 1
    return f'{base}_v{k}{ext}'
BR = json.load(open(A.brief)); PJ = BR['projeto']; ST = BR.get('estilo') or {}; IMG = ST.get('imagem', {})
TALK = PJ.get('formato', ST.get('formato')) in ('talking_head', 'misto', 'podcast')
def sh(cmd):
    print('$', ' '.join(cmd) if isinstance(cmd, list) else cmd, flush=True)
    subprocess.run(cmd, check=True, shell=isinstance(cmd, str))
def have(f): return os.path.exists(os.path.join(A.work, f))

# ------------------------------------------------------------------ prep
if A.stage in ('all', 'prep'):
    if not have('words_raw.json'): sh(['python3', HERE + '/transcribe.py', A.video, A.work, MODELS + '/parakeet'])
    if not have('shots.json'): sh(['python3', HERE + '/analyze.py', A.video, A.work, MODELS] + (['--faces'] if TALK else []))
    if not have('graded.mkv'):
        sh(['python3', HERE + '/grade.py', A.video, A.work, 'full'] + (['--skin'] if IMG.get('suavizar_pele') and TALK else []) + (['--dof'] if IMG.get('desfoque_fundo') else []) + (['--original'] if IMG.get('cor_original') else []))
    if A.stage == 'prep': sys.exit(0)

# ------------------------------------------------------------------ montar a edição
from core import *
import audio
def rgb(h): h = h.lstrip('#'); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
gfx.set_fonts((ST.get('fontes') or {}).get('titulo'), (ST.get('fontes') or {}).get('texto'))   # fontes do estilo (Google Fonts)
if ST.get('paleta'):
    gfx.set_palette({k: rgb(v) for k, v in ST['paleta'].items() if isinstance(v, str) and v.startswith('#')})
blocks = sorted(BR.get('blocos', []), key=lambda b: b.get('inicio', 0))
fixes = json.load(open(A.fixes)) if A.fixes else []
for f in fixes:
    if 'insert' in f: f['insert'] = [tuple(x) for x in f['insert']]
remove = [(b['inicio'], b['fim']) for b in blocks if b['tipo'] == 'corte']
DIN = PJ.get('formato', ST.get('formato')) == 'dinamico'      # Reels Dinâmico: sem fala; textos na tela contam a história
SOMB = {**(ST.get('sombras') or {}), **(PJ.get('sombras') or {})}  # sombra de texto e sombra geral (escurecer o fundo), em %
def _pct(v, d=0.0):
    try: return min(100.0, max(0.0, float(v))) / 100
    except (TypeError, ValueError): return d
gfx.SOMBRA = _pct(SOMB.get('texto'), 0.0)
ed = Edit(A.video, A.work, speed=float(IMG.get('velocidade', 1.0 if DIN else 1.08)), tail=1.3, cut_pauses=(IMG.get('cortar_pausas', True) is not False) and not DIN,
          fixes=fixes, remove=remove, sem_fala=DIN)
ed.escuro = _pct(SOMB.get('geral'), 0.0)
T = ed.t; NW = [norm(d['w']) for d in ed.WORDS]; plan = []

def find(phrase, near=None, after_out=None):
    """tempo de saída da primeira palavra da frase-gatilho (busca aproximada; desempata pelo tempo mais próximo de `near`)."""
    toks = [norm(x) for x in str(phrase or '').split() if norm(x)]
    if not toks: return None
    n = len(toks); best = None
    for i in range(len(NW) - n + 1):
        if after_out is not None and ed.WORDS[i]['os'] < after_out - 0.05: continue
        r = difflib.SequenceMatcher(None, ' '.join(toks), ' '.join(NW[i:i + n])).ratio()
        if r < 0.72: continue
        dist = abs(ed.WORDS[i]['s'] - near) if near is not None else 0
        key = (round(r, 2), -dist)
        if best is None or key > best[0]: best = (key, i)
    return ed.WORDS[best[1]]['os'] if best else None
def when(b, default_out):
    t = find(b.get('gatilho'), b.get('inicio'))
    src = 'gatilho' if t is not None else 'timeline'
    if t is None: t = default_out
    return t, src
def out_of(src_t): return ed.src2out(src_t)
import glob
BANK = os.path.join(A.work, 'banco')            # o agente baixa aqui os itens do banco do Studio: <id>.<ext>
def bank_file(bid):
    if not bid: return None
    m = sorted(glob.glob(os.path.join(BANK, bid + '.*'))); m = [x for x in m if not x.endswith('.wav')] or m
    return m[0] if m else None
def bank_wav(bid):
    f = bank_file(bid)
    if not f: return None
    w = os.path.join(BANK, bid + '.wav')
    if not os.path.exists(w): subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', f, '-vn', '-ac', '2', '-ar', '48000', w], check=True)
    return w

# ---- gancho (sempre a partir da primeira palavra)
hk = next((b for b in blocks if b['tipo'] == 'gancho'), None)
icon_hook = (hk or {}).get('icone') or 'sparkle'
if hk and hk.get('frase'):
    nwords = len(hk['frase'].split())
else:  # primeira frase da fala
    nwords = next((i + 1 for i, d in enumerate(ed.WORDS) if d['w'][-1] in '.?!'), min(12, len(ed.WORDS)))
nwords = min(max(nwords, 3), 18)
kw = norm((hk or {}).get('palavra_chave', ''))
words = [ed.WORDS[i]['w'].upper() for i in range(min(nwords, len(ed.WORDS)))]   # sem fala (Reels Dinâmico): nenhuma palavra
pages, lines, cur = [], [], ''
for w in words:
    if kw and norm(w) == kw:
        if cur: lines.append(cur); cur = ''
        lines.append(w); continue
    if len(cur) + len(w) + 1 > 15 and cur: lines.append(cur); cur = w
    else: cur = (cur + ' ' + w).strip()
    if w[-1] in '.?!' and cur: lines.append(cur + '|'); cur = ''        # '|' = fim de frase: fecha a página
if cur: lines.append(cur)
pg = []
for ln in lines:
    end = ln.endswith('|'); pg.append(ln.rstrip('|'))
    cap = 4 if kw and any(norm(x) == kw for x in ' '.join(pg).split()) else 3
    if end or len(pg) == cap: pages.append(pg); pg = []
if pg: pages.append(pg)
while any(len(p) > 4 for p in pages):                                   # frase longa demais: divide a página
    k = next(i for i, p in enumerate(pages) if len(p) > 4); pages[k:k + 1] = [pages[k][:3], pages[k][3:]]
def posy(b, d):  # pos_y do Studio = % do topo onde o bloco começa (vazio = posição padrão)
    v = (b or {}).get('pos_y')
    try: return d if v in (None, '') else float(v) / 100 * 1920
    except (TypeError, ValueError): return d
# tamanho vindo do Studio: escala (% do tamanho total do bloco) e texto_px (px do texto principal na tela de 1080)
TXT_BASE = {'painel': 45, 'cta': 80, 'gancho': 82, 'nome': 50}
def lado(b):     # pos_x do Studio: "esquerda" | "centro" | "direita" ("" = padrão DocOn)
    v = str((b or {}).get('pos_x') or '').lower()
    return v if v in ('esquerda', 'centro', 'direita') else ''
def escala(b):
    try: v = float((b or {}).get('escala') or 0)
    except (TypeError, ValueError): v = 0
    if v <= 0 and (b or {}).get('tipo') == 'painel' and lado(b) in ('esquerda', 'direita'): return 0.72   # painel de lado: mais estreito
    return min(1.6, max(0.4, v / 100)) if v > 0 else 1.0
def bgk(b):   # desfoque do fundo (0..1): CTA ligado por padrão (50%), outros só com a caixa marcada (40%)
    b = b or {}; tp = b.get('tipo')
    if tp == 'fx': on, d = b.get('efeito') == 'fundo_desfocado', 50
    elif tp == 'cta': on, d = b.get('desfoque_fundo') is not False, 50
    elif tp in ('painel', 'gancho', 'nome'): on, d = b.get('desfoque_fundo') is True, 40
    else: return 0.0
    if not on: return 0.0
    try: v = float(b.get('desfoque_pct') or d)
    except (TypeError, ValueError): v = d
    return min(1.0, max(0.05, v / 100))
def txt(b):
    try: v = float((b or {}).get('texto_px') or 0)
    except (TypeError, ValueError): v = 0
    base = TXT_BASE.get((b or {}).get('tipo'), 0)
    return min(3.0, max(0.3, v / base)) if v > 0 and base else 1.0
HK_S = escala(hk) * txt(hk)
HOOK_C = posy(hk, 0.56 * 1920) + 195           # centro do gancho (padrão 1270)
def ys_for(pg):
    hs = [(150 if kw and kw in [norm(x) for x in l.split()] else 112) * HK_S for l in pg]; y = HOOK_C - sum(hs) / 2; out = []
    for h in hs: out.append(y + h / 2); y += h
    return tuple(int(v) for v in out)
if DIN or not ed.WORDS: pages = []            # sem fala não há gancho falado: use blocos "texto"
if pages: ed.hook([{'lines': p, 'ys': ys_for(p)} for p in pages], keyword_word=kw or None, icon=icon_hook, kw_width=min(1000, int(860 * HK_S)), size=int(92 * HK_S), kw_size=int(150 * HK_S))
if IMG.get('cor_original'): ed.leak = False; ed.vig_amt = 0.0; ed._vig = None     # cor original: sem flash de luz e sem vinheta sobre a pessoa
if hk and bgk(hk) > 0: ed.bg_blur(0, ed.hook_end + 0.2, bgk(hk)); plan.append(f'desfoque de fundo com o gancho {round(bgk(hk) * 100)}%')
plan.append(f'gancho {ed.hook_end:.2f}s · {nwords} palavras · {len(pages)} página(s)')

# ---- CTA (precisa vir antes da legenda)
cta = next((b for b in blocks if b['tipo'] == 'cta'), None)
if cta:
    t0, src = when(cta, out_of(cta['inicio']))
    t0 = min(t0, ed.TOTAL - 2.5)                     # o cartão final sempre aparece inteiro e vai até o último quadro
    ed.end_card(t0 - 0.05, (cta['kicker'] if 'kicker' in cta else (PJ.get('tema') or 'DOCON')).upper()[:34], (cta.get('titulo') or 'Me conta nos comentários').split('\n')[:2],
                cta.get('subtitulo') or '', (PJ['profissional'].get('nome') or '') if cta.get('mostrar_nome') is not False else '', cta.get('botao') or 'Agende sua avaliação',
                foot=cta.get('rodape') or None, icon=cta.get('icone') or icon_hook, y=int(posy(cta, 640)), s=escala(cta) * txt(cta), blur=bgk(cta))
    plan.append(f'cta {t0:.2f}s ({src})')

# ---- blocos
topics = []; kws = [k.strip() for k in (PJ.get('legenda', {}).get('palavras_chave') or '').split(',') if k.strip()]
ic = lambda n, s=70: ICONS.get(n, ICONS['check'])(s)
for b in blocks:
    tp = b['tipo']
    if tp in ('gancho', 'cta', 'corte'): continue
    t0, src = when(b, out_of(b['inicio']))
    if t0 >= ed.TOTAL - 0.2: plan.append(f'AVISO {tp} depois do fim do vídeo ({b["inicio"]}s): ignorado'); continue
    if tp == 'fx' and b.get('efeito') == 'camera': tp = 'camera'   # Zoom / câmera do Studio
    if tp == 'fx' and b.get('efeito') == 'fade_preto':             # fade até 100% preto por cima de tudo (entrada: começa preto; saída: termina preto)
        ent = b.get('direcao') == 'entrada' or (b.get('direcao') not in ('entrada', 'saida') and float(b['inicio']) < 0.5)
        t0 = 0.0 if ent and float(b['inicio']) < 0.05 else t0; t1 = min(max(out_of(b['fim']), t0 + 0.2), ed.TOTAL)
        ed.fade_preto(t0, t1, ent); plan.append(f'fade preto {"entrada" if ent else "saída"} {t0:.2f}-{t1:.2f}'); continue
    if tp == 'fx' and b.get('efeito') == 'escurecer':              # sombra geral num trecho
        t1 = min(max(out_of(b['fim']), t0 + 0.3), ed.TOTAL); k = _pct(b.get('escuro_pct'), 0.4); ed.escurecer(t0, t1, k); plan.append(f'escurecer fundo {t0:.2f}-{t1:.2f} {round(k * 100)}%'); continue
    if tp == 'motion':                                             # motion graphics: modelo Hyperframes ou Remotion (scripts/motion.py)
        t1 = min(max(out_of(b['fim']), t0 + 0.6), ed.TOTAL)
        try:
            import motion as _mo
            pre = b.get('pasta') and os.path.expanduser(b['pasta'])          # sequência já renderizada (ex.: animação 3D sob medida)
            if b.get('pasta') and not (os.path.isdir(pre) and any(f.endswith('.png') for f in os.listdir(pre))):
                plan.append(f'AVISO motion {t0:.2f}-{t1:.2f} sem quadros em {pre}'); continue
            pasta = pre or _mo.render(b.get('modelo') or 'titulo_cinetico', None, b.get('motor') or None, t1 - t0, b.get('variaveis') or {}, ST, b.get('pos_y'))
            ed.motion(t0, t1, pasta); plan.append(f'motion {t0:.2f}-{t1:.2f} {b.get("motor") or "hyperframes"}:{b.get("modelo")}' + (' · tela dividida' if b.get('divisao') else ''))
            if b.get('divisao'): ed.split(t0, t1, int(b.get('desloca') or 140))
            elif b.get('legenda_y'): ed.split(t0, t1, 0, cap_y=int(b['legenda_y']))     # ex.: abertura recortada: só a legenda muda de altura
        except SystemExit as e: plan.append(f'AVISO motion {b.get("modelo")} não renderizou: {str(e)[:200]}')
        continue
    if tp == 'texto':                                              # texto na tela (Reels Dinâmico e qualquer estilo)
        t1 = min(max(out_of(b['fim']), t0 + 0.8), ed.TOTAL)
        try: px = float(b.get('texto_px') or 72)
        except (TypeError, ValueError): px = 72
        cor = b.get('cor') or 'text'; cor = rgb(cor) if str(cor).startswith('#') else tuple(P.get(cor, P['text']))
        ed.texto_tela(t0, t1, b.get('texto') or '', anim=b.get('animacao') or 'opacidade', saida=b.get('saida') or 'opacidade', y=int(posy(b, 0.40 * 1920)),
                      align=lado(b) or 'centro', px=px, peso=int(b.get('peso') or 800), fonte=b.get('fonte') or 'titulo', cor=cor,
                      sombra=_pct(b.get('sombra'), max(0.45, gfx.SOMBRA)), fundo=bool(b.get('fundo')))
        plan.append(f'texto {t0:.2f}-{t1:.2f} {b.get("animacao") or "opacidade"} · {(b.get("texto") or "")[:40]!r}'); continue
    if tp == 'camera':                               # zoom / câmera manual do Studio (aproxima em quem fala, troca de foco com movimento)
        t1 = out_of(b['fim']); t1 = ed.TOTAL + 1 if t1 >= ed.DUR - 0.05 else t1   # até o fim do bruto: segue no zoom até o último quadro
        def _n(v, d):
            try: return float(v) / 100 if v not in (None, '') else d
            except (TypeError, ValueError): return d
        ed.zoom_on(t0, t1, float(b.get('zoom') or 1.6), _n(b.get('foco_x'), 0.5), _n(b.get('foco_y'), 0.45), float(b.get('transicao') or 0.7))
        plan.append(f'câmera {t0:.2f}-{t1:.2f} zoom {b.get("zoom")}x foco {b.get("foco_x")}%,{b.get("foco_y")}%'); continue
    if tp == 'fx':                                   # efeito visual: dura o que a timeline diz (sem mínimo de 1,6 s)
        t1 = min(max(out_of(b['fim']), t0 + 0.15), ed.TOTAL)
        if b.get('efeito') == 'fundo_desfocado': ed.bg_blur(t0, t1, bgk(b)); plan.append(f'desfoque de fundo {t0:.2f}-{t1:.2f} {round(bgk(b) * 100)}%'); continue
        ed.fx.add(b.get('efeito', 'zoom'), t0, t1, b.get('intensidade', 'média')); plan.append(f'fx {b.get("efeito")} {t0:.2f}-{t1:.2f} ({src})'); continue
    t1 = min(max(out_of(b['fim']), t0 + 1.6), ed.TOTAL)
    if ed.ec0 is not None: t1 = min(t1, ed.ec0 - 0.1)
    if bgk(b) > 0: ed.bg_blur(t0 - 0.1, t1, bgk(b)); plan.append(f'desfoque de fundo com {tp} {round(bgk(b) * 100)}%')
    if tp == 'destaque': kws += [k.strip() for k in (b.get('palavras') or '').split(',') if k.strip()]; continue
    if tp == 'nome':
        ed.lower_third(t0 - 0.05, t1, b.get('nome') or PJ['profissional'].get('nome', ''), b.get('subtitulo') or PJ['profissional'].get('subtitulo', ''), y=int(posy(b, 1290)), s=escala(b) * txt(b), align=lado(b) or 'esquerda')
        topics.append(t0); plan.append(f'nome {t0:.2f}-{t1:.2f} ({src}) {b.get("nome")}'); continue
    if tp == 'som':
        w = bank_wav(b.get('banco_id'))
        if w: ed.sfx.append((t0, 'file:' + w, {'discreto': 1.0, 'médio': 1.8, 'presente': 3.0}.get(b.get('volume'), 1.0))); plan.append(f'som {t0:.2f} {b.get("nome")}')
        else: plan.append(f'AVISO efeito sem arquivo (banco_id {b.get("banco_id")}): baixe para WORK/banco/')
        continue
    if tp == 'broll':
        f = b.get('arquivo') or ''
        cand = [bank_file(b.get('banco_id')) or '', f, os.path.join(A.media or '', f), os.path.join(os.path.dirname(A.brief), f)]
        path = next((c for c in cand if c and os.path.isfile(c)), None)
        if path: ed.broll(path, t0, min(t1, t0 + 3.0), mode='band' if b.get('modo') == 'faixa' else 'full'); plan.append(f'broll {t0:.2f} {f}')
        else: plan.append(f'AVISO broll sem arquivo em {b["inicio"]}s · busca: {b.get("busca")}')
        continue
    if tp == 'painel':
        items = [i for i in b.get('itens', []) if i.get('texto')]; lay = b.get('layout', 'lista')
        tit = (b.get('titulo') or '').strip(); n = len(items)
        h = 46 + 52 + 22 + (0 if lay == 'destaque' or not tit else 64 * len(tit.split('\n'))) + (112 if lay == 'destaque' else 0) + \
            (150 if lay == 'linha_do_tempo' else 230 if lay == 'opcoes' else 92 * n) + (330 + (52 if b.get('preco_de') else 0) - 8 * n if lay == 'preco' else 0) + 30
        if lay == 'preco': h = 120 + (64 * len(tit.split('\n')) + 16 if tit else 8) + 266 + (52 if b.get('preco_de') else 0) + (54 if b.get('chamada') else 0) + 84 * n + 30   # medida real do painel de preço
        h = min(max(h, 220), 760 if lay == 'preco' else 540); y = int(min(max(1200 - h / 2, 930), 1470 - h)) if b.get('pos_y') in (None, '') else int(min(max(posy(b, 0), 60), 1880 - h))
        es, tx = escala(b), txt(b)
        if es != 1 or tx != 1:     # painel menor/maior (retângulo inteiro) e texto maior/menor por dentro
            h = int(h * es * tx)
            if b.get('pos_y') in (None, ''): y = int(min(max(1200 - h / 2, 930), 1470 - h))
            y = int(min(max(y, 40), 1880 - h))
        px = {'esquerda': 70, 'direita': int(70 + 940 * (1 - es))}.get(lado(b), int(70 + 940 * (1 - es) / 2))
        p = ed.panel(t0 - 0.1, t1, y=y, h=h, x=px, w=int(940 * es), r=int(34 * es), s=es * tx); topics.append(t0)
        it_t = [find(i.get('gatilho'), b['inicio'] - 1, t0 - 0.3) for i in items]
        it_t = [x if x is not None and x < t1 - 0.3 else t0 + 0.35 + 0.45 * k for k, x in enumerate(it_t)]
        if lay == 'destaque':
            p.add(pill(b.get('kicker') or 'DESTAQUE', MONT(800, 26)), 56, 46, p.t0)
            big = gold_gradient_text(tit or '—', MONT(900, 92), pad=0)
            if big.width > 820: big = big.resize((820, int(big.height * 820 / big.width)))
            p.add(big, 56, 118, t0 + 0.05, anim='pop'); ed.sfx.append((t0 + 0.05, 'tick')); yy = 246
            for k, it in enumerate(items): ed.row(p, ic(it.get('icone'), 64), it['texto'], yy + 84 * k, it_t[k], size=42)
        elif lay == 'preco':                                       # preço de oferta: moeda pequena, valor grande, centavos e selo (ex.: no PIX)
            yy = ed.kicker_title(p, b.get('kicker') or 'OFERTA', tit, tsize=52) if tit else (p.add(pill(b.get('kicker') or 'OFERTA', MONT(800, 26)), 56, 46, p.t0) or 128)
            cur = b.get('moeda', 'R$') if b.get('moeda') is not None else 'R$'
            if b.get('preco_de'):
                de = text_sprite(f"de {cur} {b['preco_de']} por", INTER('Medium', 38), P['text'], pad=0); dd = ImageDraw.Draw(de)
                x0 = INTER('Medium', 38).getlength('de '); x1 = INTER('Medium', 38).getlength(f"de {cur} {b['preco_de']}"); dd.line([(x0, de.height * .55), (x1, de.height * .55)], fill=tuple(P['text']) + (255,), width=3)
                p.add(de, 56, yy, p.t0 + 0.15); yy += 52
            if b.get('chamada'): p.add(text_sprite(str(b['chamada']), INTER('Medium', 40), P['text'], pad=0), 56, yy, p.t0 + 0.15); yy += 54
            val = gold_gradient_text(str(b.get('preco') or '0'), MONT(900, 320), c1=P['text'], c2=P['grad1'], pad=0); val = val.crop(val.getbbox() or (0, 0, val.width, val.height))   # rente às letras (sem o vão da fonte)
            cs = text_sprite(cur, MONT(800, 84), P['text'], pad=0); ce = text_sprite(b['centavos'], MONT(800, 84), P['text'], pad=0) if b.get('centavos') else None
            sel = pill(str(b['condicao']).upper(), INTER('Bold', 36), fg=P.get('button_fg', P['text']), bg=P.get('button', P['key']), padx=26, pady=14, track=2) if b.get('condicao') else None
            side = max(ce.width if ce else 0, sel.width if sel else 0); W_ = cs.width + 16 + val.width + 16 + side; H_ = max(val.height, 20 + (ce.height + 16 if ce else 0) + (sel.height if sel else 0))
            pr = Image.new('RGBA', (W_, H_), (0, 0, 0, 0)); pr.alpha_composite(cs, (0, 22)); pr.alpha_composite(val, (cs.width + 16, 0)); sx = cs.width + 32 + val.width; sy = 22
            if ce: pr.alpha_composite(ce, (sx, sy)); sy += ce.height + 16
            if sel: pr.alpha_composite(sel, (sx, sy))
            if pr.width > 828: pr = pr.resize((828, int(pr.height * 828 / pr.width)), Image.LANCZOS)
            g = b.get('preco_gatilho') or b.get('preco'); tp = find(str(g), b['inicio'] - 1, t0 - 0.3) if g else None
            tp = tp if tp is not None and tp < t1 - 0.5 else t0 + 0.3
            p.add(pr, 56, yy + 6, tp, anim='pop'); ed.sfx.append((tp, 'tick')); yy += pr.height + 30
            for k, it in enumerate(items): ed.row(p, ic(it.get('icone'), 64), it['texto'], yy + 84 * k, it_t[k], size=42)
        elif lay == 'linha_do_tempo':
            yy = ed.kicker_title(p, b.get('kicker') or 'PASSO A PASSO', tit, tsize=52) if tit else (p.add(pill(b.get('kicker') or 'PASSO A PASSO', MONT(800, 26)), 56, 46, p.t0) or 130)
            xs = [int(140 + k * (660 / max(n - 1, 1))) for k in range(n)] if n > 1 else [470]; ly = yy + 40
            line = Image.new('RGBA', (940, 12), (0, 0, 0, 0)); ImageDraw.Draw(line).line([(xs[0], 6), (xs[-1], 6)], fill=tuple(P['border']) + (120,), width=3); p.add(line, 0, ly - 6, p.t0 + 0.1)
            for k, (it, x) in enumerate(zip(items, xs)):
                dot = Image.new('RGBA', (120, 120), (0, 0, 0, 0)); dd = ImageDraw.Draw(dot); dd.ellipse([24, 24, 96, 96], fill=tuple(P['icon']) + (255,)); dd.ellipse([46, 46, 74, 74], fill=tuple(P['glass']) + (255,))
                p.add(dot.resize((40, 40), Image.LANCZOS), x - 20, ly - 20, it_t[k], tick=True, anim='pop')
                ls = text_sprite(it['texto'], INTER('Bold', 38), P['text'], pad=0); p.add(ls, max(10, x - ls.width // 2), ly + 40, it_t[k] + 0.05)
        elif lay == 'opcoes':
            yy = ed.kicker_title(p, b.get('kicker') or 'QUAL VOCÊ PREFERE?', tit, tsize=56) if tit else 130
            xs = [int(470 + (k - (n - 1) / 2) * min(310, 820 / max(n, 1))) for k in range(n)]
            for k, (it, x) in enumerate(zip(items, xs)):
                p.add(ic(it.get('icone'), 140), x - 70, yy, it_t[k], tick=True, anim='pop')
                ls = text_sprite(it['texto'], INTER('Bold', 38), P['text'], pad=0); p.add(ls, x - ls.width // 2, yy + 146, it_t[k] + 0.05)
                if k < n - 1:
                    ou = text_sprite('ou', INTER('Medium', 32), P['key'], pad=0); p.add(ou, (x + xs[k + 1]) // 2 - ou.width // 2, yy + 56, it_t[k] + 0.2)
        else:
            yy = ed.kicker_title(p, b.get('kicker') or '', tit, tsize=52) if tit else (p.add(pill(b.get('kicker') or '', MONT(800, 26)), 56, 46, p.t0) or 128)
            for k, it in enumerate(items): ed.row(p, ic(it.get('icone')), it['texto'], yy + 92 * k, it_t[k], size=44)
        plan.append(f'painel {t0:.2f}-{t1:.2f} ({src}) {lay} · {b.get("kicker")} · itens {[round(x, 2) for x in it_t]}')

# ---- podcast (conversa a dois): assinatura de cada locutor na 1ª fala e transição curta entre os takes (mapa do podcast_prep.py)
if PJ.get('formato') == 'podcast' and os.path.exists(os.path.join(A.work, 'podcast_mapa.json')):
    mapa = json.load(open(os.path.join(A.work, 'podcast_mapa.json'))); papeis = {l.get('nome'): l.get('papel', '') for l in PJ.get('locutores', [])}
    ja = {(b.get('nome') or '').strip().lower() for b in blocks if b['tipo'] == 'nome'}; vistos = set()
    for m in mapa:
        nm = (m.get('locutor') or '').strip()
        if nm and nm.lower() not in ja and nm.lower() not in vistos:
            t0 = max(out_of(m['inicio'] + 0.4), ed.hook_end + 0.25 if out_of(m['inicio']) < ed.hook_end + 0.5 else 0); t1 = min(out_of(m['fim']) - 0.2, t0 + 3.6)   # depois do gancho, sem cobrir a frase
            if t1 - t0 > 1.2: ed.lower_third(t0, t1, nm, papeis.get(nm, ''), y=1290); topics.append(t0); plan.append(f'podcast: assinatura de {nm} em {t0:.2f}s')
            vistos.add(nm.lower())
    if not any(b['tipo'] == 'fx' for b in blocks):
        for m in mapa[1:]:
            tb = out_of(m['inicio']); ed.fx.add('flash', max(0, tb - 0.05), tb + 0.25, 'suave'); plan.append(f'podcast: transição no take {m["take"]} ({tb:.2f}s)')
ed.camera(topics=sorted(topics))
leg = PJ.get('legenda', {}).get('estilo', ST.get('legenda', {}).get('estilo', 'docon'))
if DIN: leg = 'nenhuma'                        # sem fala, sem legenda
LG = PJ.get('logo') or {}
if LG.get('ativo') and (LG.get('asset_id') or LG.get('arquivo')):     # logomarca do cliente (identidade): baixe para WORK/banco/<asset_id>.png
    lp = bank_file(LG.get('asset_id')) or next((c for c in [LG.get('arquivo') or '', os.path.join(A.media or '', LG.get('arquivo') or '')] if c and os.path.isfile(c)), None)
    if lp: ed.set_logo(lp, LG.get('pos') or 'sup_dir', _pct(LG.get('tam'), 0.16), _pct(LG.get('op'), 0.9)); plan.append(f'logo {LG.get("pos") or "sup_dir"} {LG.get("tam") or 16}%')
    else: plan.append(f'AVISO logo sem arquivo (asset {LG.get("asset_id")}): baixe para WORK/banco/')
if leg != 'nenhuma':
    kwords = sorted({w for k in kws for w in k.split()})
    try: cap_s = min(2.5, max(0.4, float((PJ.get('legenda') or {}).get('fonte_px') or 0) / (44 if leg == 'subtle' else 54))) or 1.0
    except (TypeError, ValueError): cap_s = 1.0
    if not (PJ.get('legenda') or {}).get('fonte_px'): cap_s = 1.0
    _lg = PJ.get('legenda') or {}
    cap_y = int(_lg.get('y') or (float(_lg['pos_y']) / 100 * 1920 + 38 if _lg.get('pos_y') not in (None, '') else (1600 if leg == 'subtle' else 1585)))   # legenda.y (px) ou pos_y (% da tela, do Studio)
    if _lg.get('cor_destaque'): ed.cap_key = rgb(_lg['cor_destaque'])                     # cor das palavras em destaque (Studio: legenda.cor_destaque)
    ed.captions(style='subtle' if leg == 'subtle' else 'docon', y=cap_y, maxc=30 if leg == 'subtle' else 26, keywords=kwords, s=cap_s)
    ed.cap_y0 = cap_y; ed.cap_split_y = int((PJ.get('legenda') or {}).get('y_divisao') or 940)
warn = ed.check(); plan += ['AVISO ' + w for w in warn]
# ---- revisão de ofício (critérios medidos dos filmes do HyperFrames, adaptados ao reels DocOn): avisos, não regras
def revisao():
    av = []; ev = sorted({round(x, 2) for p in ed.panels for x in (p.t0, p.t1)} | {round(f['t0'], 2) for f in ed.fx.items}
                       | {round(x['t0'], 2) for x in ed.textos} | {round(x['t1'], 2) for x in ed.textos} | {round(a, 2) for a, *_ in getattr(ed, 'cams', [])} | {round(b, 2) for _, b, *_ in getattr(ed, 'cams', [])} | {0.0, round(ed.TOTAL, 2)})
    for a, b in zip(ev, ev[1:]):
        if b - a > 8.0 and a > ed.hook_end: av.append(f'trecho parado {a:.1f}-{b:.1f}s ({b - a:.0f} s sem painel, zoom, efeito ou B-roll): ponha um destaque, um punch-in ou um B-roll')
    for bb in blocks:
        if bb['tipo'] == 'texto':
            nw = len((bb.get('texto') or '').split()); d = out_of(bb['fim']) - out_of(bb['inicio']); need = 0.5 + 0.3 * nw + (0.045 * len(bb.get('texto') or '') if bb.get('animacao') == 'escrever' else 0)
            if d < need: av.append(f'texto "{(bb.get("texto") or "")[:30]}" fica {d:.1f}s para {nw} palavras (leitura pede {need:.1f}s)')
            continue
        if bb['tipo'] != 'painel': continue
        nw = len(' '.join([bb.get('kicker') or '', bb.get('titulo') or ''] + [i.get('texto') or '' for i in bb.get('itens', [])]).split())
        t0b, t1b = out_of(bb['inicio']), out_of(bb['fim'])
        if t1b - t0b < 0.5 + 0.3 * nw: av.append(f'painel "{bb.get("kicker") or bb.get("titulo")}" fica {t1b - t0b:.1f}s para {nw} palavras (leitura pede {0.5 + 0.3 * nw:.1f}s)')
        if t1b - t0b > 15 and len(bb.get('itens', [])) < 3: av.append(f'painel "{bb.get("kicker") or bb.get("titulo")}" parado {t1b - t0b:.0f}s: acima de ~8-15 s o cartão "morre"; divida ou revele por partes')
    for p in ed.panels:
        if p is getattr(ed, 'ec', None): continue
        if p.y < 168: av.append(f'gráfico em {p.t0:.1f}s começa em y={p.y}: o topo (0-168 px) fica sob a barra do Instagram')
        if p.y + p.h > 1560: av.append(f'gráfico em {p.t0:.1f}s desce até y={p.y + p.h}: abaixo de ~1560 px a legenda do post e o @ do Instagram cobrem')
    if ed.TOTAL > 20 and not (BR.get('projeto', {}).get('musica') or {}).get('ativa') and not ed.sfx: av.append('vídeo sem trilha e sem efeitos sonoros: confirme que é de propósito')
    return av
REV = revisao(); plan += ['REVISÃO ' + w for w in REV]
open(os.path.join(A.work, 'plano.txt'), 'w').write(f'duração final {ed.TOTAL:.2f}s · segmentos {[(round(a, 2), round(b, 2)) for a, b in ed.SEGS]}\n' + '\n'.join(plan) + '\n')
print(open(os.path.join(A.work, 'plano.txt')).read())

# ------------------------------------------------------------------ preview / render
G = os.path.join(A.work, 'graded.mkv')
if A.stage in ('all', 'preview') and (A.preview or A.stage == 'preview'):
    ts = [float(x) for x in A.preview.split(',')] if A.preview else [round(x, 1) for x in
          sorted({0.6, ed.hook_end - 0.3} | {max(p.t0 + 0.9, p.t1 - 0.6) for p in ed.panels if p is not ed.ec} | ({ed.ec0 + 0.8} if ed.ec0 else set()))][:20]
    ed.render(G, None, preview=ts, sheet=os.path.join(A.work, 'preview.jpg')); shutil.copy(os.path.join(A.work, 'preview.jpg'), os.path.join(HIST, f'{STAMP}_preview.jpg'))
    print('prévia:', os.path.join(A.work, 'preview.jpg'), ts)
    if A.stage == 'preview': sys.exit(0)
if A.stage in ('all', 'render'):
    out = versioned(A.out or os.path.join(A.work, 'final.mp4'))      # nunca sobrescreve uma entrega anterior
    ed.render(G, os.path.join(A.work, 'video_only.mp4'))
    mu = PJ.get('musica', {}); music = None
    vol = {'discreta': -15, 'média': -12, 'presente': -9}.get(mu.get('volume', 'discreta'), -15)
    if mu.get('ativa'):
        music = bank_wav(mu.get('banco_id')) or (mu.get('arquivo') if mu.get('arquivo') and os.path.isfile(mu.get('arquivo')) else os.path.join(A.work, 'music.wav'))
        if not os.path.isfile(music): sh(['python3', HERE + '/music.py', music, f'{ed.TOTAL + 0.5:.2f}', '--bpm', str(mu.get('bpm', 92)), '--key', 'D', '--mood', mu.get('clima', 'warm')])
    if PJ.get('efeitos_sonoros') is False: ed.sfx[:] = [x for x in ed.sfx if str(x[1]).startswith('file:')]   # só a voz original (mantém sons escolhidos no Studio)
    audio.build(ed, os.path.join(A.work, 'mix.wav'), music=music, music_db=vol, duck_db=7, voice='light')
    sh(['ffmpeg', '-v', 'error', '-y', '-i', os.path.join(A.work, 'video_only.mp4'), '-i', os.path.join(A.work, 'mix.wav'), '-map', '0:v', '-map', '1:a', '-c:v', 'copy',
        '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-shortest', '-movflags', '+faststart', out])
    base = os.path.splitext(out)[0]
    fm = {f.strip().lower() for f in A.formatos.split(',')}
    if 'mov' in fm: sh(['ffmpeg', '-v', 'error', '-y', '-i', out, '-c', 'copy', '-f', 'mov', base + '.mov'])
    if 'wav' in fm: sh(['ffmpeg', '-v', 'error', '-y', '-i', out, '-vn', '-c:a', 'pcm_s16le', '-ar', '48000', base + '.wav'])
    if 'mp3' in fm: sh(['ffmpeg', '-v', 'error', '-y', '-i', out, '-vn', '-c:a', 'libmp3lame', '-b:a', '192k', base + '.mp3'])
    sh(['ffmpeg', '-v', 'error', '-y', '-i', out, '-vf', 'fps=1/5,scale=216:384,tile=5x4', '-frames:v', '1', base + '_folha.jpg'])
    kbps = max(900, int((14 * 8 * 1024) / (ed.TOTAL + 0.5)) - 140)       # cabe em ~14 MB com AAC 128k
    lg = os.path.join(A.work, 'x265pass')
    # H.264 (não HEVC): a versão da web precisa tocar em qualquer navegador, inclusive Chrome no Windows
    sh(['ffmpeg', '-v', 'error', '-y', '-i', out, '-c:v', 'libx264', '-preset', 'slow', '-b:v', f'{kbps}k', '-pass', '1', '-passlogfile', lg, '-an', '-f', 'null', '/dev/null'])
    sh(['ffmpeg', '-v', 'error', '-y', '-i', out, '-c:v', 'libx264', '-preset', 'slow', '-b:v', f'{kbps}k', '-pass', '2', '-passlogfile', lg, '-profile:v', 'high',
        '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart', base + '_download.mp4'])
    r = subprocess.run(['ffmpeg', '-nostats', '-i', out, '-af', 'ebur128=peak=true', '-f', 'null', '-'], capture_output=True, text=True).stderr
    I = re.findall(r'I:\s+(-?[\d.]+) LUFS', r); Pk = re.findall(r'Peak:\s+(-?[\d.]+) dBFS', r)
    print(f'PRONTO {out} · {ed.TOTAL:.1f}s · {I[-1] if I else "?"} LUFS · pico {Pk[-1] if Pk else "?"} dBTP · download {base}_download.mp4 · folha {base}_folha.jpg')
