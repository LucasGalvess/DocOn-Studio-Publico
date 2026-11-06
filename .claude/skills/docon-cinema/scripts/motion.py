"""DocOn Cinema · motion graphics com Hyperframes (HTML + GSAP, Apache 2.0) e Remotion (React).

Renderiza um modelo da pasta motion/ (ou uma composição própria) em PNG com transparência, 1080x1920 e 30 fps,
para o run_brief.py sobrepor ao vídeo (bloco "motion"). Cores e fontes vêm do estilo do cliente.

uso:
  python3 motion.py listar
  python3 motion.py preparar PASTA [--estilo estilo.json] [--logo logo.png]     # composição sob medida: GSAP, fontes, cores, logo
  python3 motion.py video PASTA SAIDA.mp4|.mov [--formato mp4|mov]              # Hyperframes → MP4, ou MOV ProRes 4444 transparente
  python3 motion.py remotion-video ENTRADA.jsx COMP SAIDA [--props JSON] [--alpha] [--public PASTA]
  python3 motion.py render MODELO SAIDA_DIR [--motor hyperframes|remotion] [--dur 3.0] [--vars '{"titulo": "..."}']
                         [--estilo estilo.json] [--y 40]
  MODELO = nome de um modelo (assinatura, titulo_cinetico, numero, lista) ou o caminho de uma pasta Hyperframes
           com index.html (composição própria, seguindo o contrato do Hyperframes).

Instalação (setup.sh): ~/.docon/motion/node_modules com hyperframes + gsap + remotion (DOCON_REMOTION=0 pula o Remotion).
Licenças: Hyperframes é Apache 2.0. Remotion: a DocOn usa a licença gratuita (empresa com 1 funcionário, confirmado em
06/11/2026; a gratuita vale até 3 funcionários). Se a equipe passar de 3, é preciso a licença de empresa (remotion.pro).
"""
import hashlib, html, json, os, re, shutil, subprocess, sys, glob

HERE = os.path.dirname(os.path.abspath(__file__)); SKILL = os.path.dirname(HERE)
MOT = os.path.join(SKILL, 'motion'); HOME = os.path.expanduser('~/.docon/motion'); CACHE = os.path.join(HOME, 'cache')
MODELOS = {
    'assinatura': {'motor': 'hyperframes', 'campos': {'nome': '', 'subtitulo': ''}, 'desc': 'nome + função (lower third) com barra de acento'},
    'titulo_cinetico': {'motor': 'hyperframes', 'campos': {'titulo': '', 'destaque': ''}, 'desc': 'título palavra por palavra (desfoque → nítido), palavra de destaque com mola'},
    'numero': {'motor': 'hyperframes', 'campos': {'valor': 0, 'prefixo': '', 'sufixo': '', 'rotulo': ''}, 'desc': 'número que conta até o valor, com rótulo (dado, estatística, preço)'},
    'lista': {'motor': 'hyperframes', 'campos': {'kicker': '', 'itens': []}, 'desc': 'kicker + itens com check entrando em sequência'},
}
REMOTION = {'titulo_cinetico', 'numero'}          # modelos que também existem no motor Remotion (motion/remotion/src/index.jsx)
CHROME = next((p for p in sorted(glob.glob('/opt/pw-browsers/chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell'))), None)

def _cores(estilo):
    pl = (estilo or {}).get('paleta') or {}
    return {'glass': pl.get('glass', '#34241e'), 'texto': pl.get('text', '#f8f3ea'), 'destaque': pl.get('key', '#f2d6a6'), 'acento': pl.get('icon', '#e9c48c')}

def _fontes(estilo, dest):
    """copia as fontes do estilo (Google Fonts via fontes.py, ou as da skill) para dest/titulo.ttf e dest/texto.ttf"""
    sys.path.insert(0, HERE)
    try: import fontes
    except Exception: fontes = None
    f = (estilo or {}).get('fontes') or {}
    pares = [('titulo.ttf', f.get('titulo') or 'Montserrat', 800, 'Montserrat-800.ttf'), ('texto.ttf', f.get('texto') or 'Inter', 700, 'InterDisplay-Bold.ttf')]
    for nome, fam, peso, padrao in pares:
        p = None
        if fontes and fam not in ('Montserrat', 'Inter'):
            try: p = fontes.baixar(fam, peso)
            except Exception: p = None
        p = p or os.path.join(HERE, 'fonts', padrao)
        if os.path.exists(p): shutil.copy(p, os.path.join(dest, nome))

def _gsap():
    p = os.path.join(HOME, 'node_modules', 'gsap', 'dist', 'gsap.min.js')
    if not os.path.exists(p): sys.exit('GSAP não instalado: rode scripts/setup.sh (instala hyperframes e gsap em ~/.docon/motion)')
    return p

def _subst(src, vars_, dur, css):
    def rep(m):
        k = m.group(1)
        if k == 'DUR': return f'{dur:.3f}'
        if k == 'CSS': return css
        if k.endswith('_json'): return json.dumps(vars_.get(k[:-5], None), ensure_ascii=False)
        return html.escape(str(vars_.get(k, '')))
    return re.sub(r'(?:/\*)?\{\{(\w+)\}\}(?:\*/)?', rep, src)

def _frames(d):
    fs = sorted(glob.glob(os.path.join(d, '*.png')))
    return fs

def render(modelo, saida=None, motor=None, dur=3.0, vars_=None, estilo=None, y=None):
    vars_ = dict(vars_ or {}); dur = max(0.6, float(dur))
    motor = motor or (MODELOS.get(modelo, {}).get('motor') if modelo in MODELOS else 'hyperframes')
    cores = _cores(estilo); css = ':root{' + ''.join(f'--{k}:{v};' for k, v in cores.items()) + (f'--y:{float(y)};' if y not in (None, '') else '') + '}'
    chave = hashlib.sha1(json.dumps([modelo, motor, dur, vars_, cores, (estilo or {}).get('fontes'), y,
                                     os.path.getmtime(os.path.join(MOT, motor)) if os.path.isdir(os.path.join(MOT, motor)) else 0], sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]
    out = saida or os.path.join(CACHE, chave)
    if os.path.exists(os.path.join(out, '.ok')) and _frames(out): return out
    os.makedirs(out, exist_ok=True); [os.remove(f) for f in _frames(out)]
    work = os.path.join(HOME, 'work', chave); shutil.rmtree(work, ignore_errors=True); os.makedirs(work)
    env = {**os.environ, 'HYPERFRAMES_NO_TELEMETRY': '1', 'DO_NOT_TRACK': '1', 'HYPERFRAMES_SKIP_SKILLS': '1'}
    if motor == 'hyperframes':
        src = os.path.join(MOT, 'hyperframes', modelo) if modelo in MODELOS else modelo
        if not os.path.exists(os.path.join(src, 'index.html')): sys.exit(f'modelo não encontrado: {modelo}')
        proj = os.path.join(work, 'comp'); shutil.copytree(src, proj); os.makedirs(os.path.join(proj, 'assets'), exist_ok=True)
        shutil.copy(_gsap(), os.path.join(proj, 'assets', 'gsap.min.js')); shutil.copy(os.path.join(MOT, 'hyperframes', '_base.css'), os.path.join(proj, 'assets', 'base.css'))
        _fontes(estilo, os.path.join(proj, 'assets'))
        ip = os.path.join(proj, 'index.html'); txt = _subst(open(ip).read(), vars_, dur, css); open(ip, 'w').write(txt)   # lê antes de abrir para escrita
        json.dump({'name': 'docon-motion'}, open(os.path.join(proj, 'hyperframes.json'), 'w'))
        seq = os.path.join(work, 'seq')
        r = subprocess.run(['npx', '--no-install', 'hyperframes', 'render', proj, '--format', 'png-sequence', '-o', seq, '--fps', '30', '--workers', '2', '--quiet'],
                           cwd=HOME, env=env, capture_output=True, text=True)
        if r.returncode != 0: sys.exit('hyperframes falhou:\n' + (r.stdout + r.stderr)[-2500:])
    elif motor == 'remotion':
        if modelo not in REMOTION: sys.exit(f'modelo {modelo} não existe no motor remotion (tem: {", ".join(sorted(REMOTION))})')
        if not os.path.isdir(os.path.join(HOME, 'node_modules', '@remotion', 'cli')): sys.exit('Remotion não instalado: rode bash scripts/setup.sh')
        proj = os.path.join(HOME, 'remotion'); shutil.rmtree(proj, ignore_errors=True); shutil.copytree(os.path.join(MOT, 'remotion'), proj)
        os.makedirs(os.path.join(proj, 'public'), exist_ok=True); _fontes(estilo, os.path.join(proj, 'public'))
        props = {**vars_, **cores, 'duracao': dur, **({'y': float(y)} if y not in (None, '') else {})}
        seq = os.path.join(work, 'seq')
        cmd = ['npx', '--no-install', 'remotion', 'render', os.path.join(proj, 'src', 'index.jsx'), modelo.replace('_', '-'), seq, '--sequence', '--image-format=png', '--props=' + json.dumps(props, ensure_ascii=False),
               '--public-dir=' + os.path.join(proj, 'public')]
        if CHROME: cmd += ['--browser-executable=' + CHROME, '--chrome-mode=headless-shell']
        r = subprocess.run(cmd, cwd=HOME, env=env, capture_output=True, text=True)
        if r.returncode != 0: sys.exit('remotion falhou:\n' + (r.stdout + r.stderr)[-2500:])
    else: sys.exit(f'motor desconhecido: {motor}')
    fs = _frames(seq)
    if not fs: sys.exit('nenhum quadro gerado')
    for k, f in enumerate(fs): shutil.move(f, os.path.join(out, f'q_{k + 1:05d}.png'))
    open(os.path.join(out, '.ok'), 'w').write(json.dumps({'modelo': modelo, 'motor': motor, 'dur': dur, 'quadros': len(fs)}))
    shutil.rmtree(work, ignore_errors=True)
    return out

# ---------------- composições sob medida (espaço de Animação do Studio e pedidos livres)
def preparar(pasta, estilo=None, logo=None):
    """copia para PASTA/assets o GSAP, a base DocOn (cores e fontes do estilo) e a logo (assets/logo.png)."""
    a = os.path.join(pasta, 'assets'); os.makedirs(a, exist_ok=True)
    shutil.copy(_gsap(), os.path.join(a, 'gsap.min.js')); shutil.copy(os.path.join(MOT, 'hyperframes', '_base.css'), os.path.join(a, 'base.css'))
    _fontes(estilo, a)
    css = ':root{' + ''.join(f'--{k}:{v};' for k, v in _cores(estilo).items()) + '}'
    open(os.path.join(a, 'cores.css'), 'w').write(css)
    if logo and os.path.exists(logo): shutil.copy(logo, os.path.join(a, 'logo' + (os.path.splitext(logo)[1].lower() or '.png')))
    if not os.path.exists(os.path.join(pasta, 'hyperframes.json')): json.dump({'name': 'docon-animacao'}, open(os.path.join(pasta, 'hyperframes.json'), 'w'))
    return pasta

def video(pasta, saida, formato='mp4', fps=30):
    """renderiza uma composição Hyperframes (index.html) em MP4 (H.264) ou MOV (ProRes 4444 com transparência)."""
    env = {**os.environ, 'HYPERFRAMES_NO_TELEMETRY': '1', 'DO_NOT_TRACK': '1', 'HYPERFRAMES_SKIP_SKILLS': '1'}
    r = subprocess.run(['npx', '--no-install', 'hyperframes', 'render', os.path.abspath(pasta), '--format', formato, '-o', os.path.abspath(saida), '--fps', str(fps), '--quality', 'delivery', '--workers', '2', '--quiet'],
                       cwd=HOME, env=env, capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(saida): sys.exit('hyperframes falhou:\n' + (r.stdout + r.stderr)[-2500:])
    return saida

def remotion_video(entrada, comp, saida, props=None, alpha=False, publico=None):
    """renderiza uma composição Remotion própria. A pasta da ENTRADA é copiada para ~/.docon/motion (onde estão os pacotes).
    alpha=True: MOV ProRes 4444 com transparência; senão MP4 H.264."""
    if not os.path.isdir(os.path.join(HOME, 'node_modules', '@remotion', 'cli')): sys.exit('Remotion não instalado: rode bash scripts/setup.sh')
    src = os.path.dirname(os.path.abspath(entrada)); proj = os.path.join(HOME, 'remotion_custom'); shutil.rmtree(proj, ignore_errors=True); shutil.copytree(src, proj)
    cmd = ['npx', '--no-install', 'remotion', 'render', os.path.join(proj, os.path.basename(entrada)), comp, os.path.abspath(saida), '--props=' + json.dumps(props or {}, ensure_ascii=False)]
    if publico: cmd.append('--public-dir=' + os.path.abspath(publico))
    cmd += ['--codec=prores', '--prores-profile=4444', '--pixel-format=yuva444p10le', '--image-format=png'] if alpha else ['--codec=h264', '--crf=16']
    if CHROME: cmd += ['--browser-executable=' + CHROME, '--chrome-mode=headless-shell']
    r = subprocess.run(cmd, cwd=HOME, capture_output=True, text=True)
    if r.returncode != 0: sys.exit('remotion falhou:\n' + (r.stdout + r.stderr)[-2500:])
    return saida

if __name__ == '__main__':
    a = sys.argv[1:]
    if not a or a[0] == 'listar':
        for k, m in MODELOS.items(): print(f'{k:16s} {m["motor"]:11s}{" +remotion" if k in REMOTION else "          "}  {m["desc"]} · campos: {", ".join(m["campos"])}')
        sys.exit()
    def opt0(n, d=None): return a[a.index(n) + 1] if n in a else d
    if a[0] == 'preparar': print(preparar(a[1], json.load(open(opt0('--estilo'))) if opt0('--estilo') else None, opt0('--logo'))); sys.exit()
    if a[0] == 'video': print(video(a[1], a[2], opt0('--formato', 'mp4'))); sys.exit()
    if a[0] == 'remotion-video': print(remotion_video(a[1], a[2], a[3], json.loads(opt0('--props', '{}')), '--alpha' in a, opt0('--public'))); sys.exit()
    if a[0] != 'render' or len(a) < 3: sys.exit(__doc__)
    def opt(n, d=None):
        return a[a.index(n) + 1] if n in a else d
    est = json.load(open(opt('--estilo'))) if opt('--estilo') else None
    print(render(a[1], a[2], opt('--motor'), float(opt('--dur', 3.0)), json.loads(opt('--vars', '{}')), est, opt('--y')))
