"""DocOn Artes · gera os arquivos de um projeto da aba Artes do DocOn Studio.

uso:
  python3 studio_arte.py PROJETO.json SAIDA [--estilo ESTILO.json] [--cliente CLIENTE.json] [--blobs DIR]

PROJETO.json  o doc projetos/<id> do Studio (ArtifactData get com out_dir)
ESTILO.json   o doc estilos/<estilo_id>          CLIENTE.json  o doc clientes/<slug> (traz .identidade)
DIR           pasta com os arquivos do Studio baixados (Artifact read + path=<asset_id>), nomeados <asset_id>.<ext>:
              logo da identidade, fotos das lâminas e do fundo ("/_blob/<id>" no projeto).
Monta o plano igual à prévia do Studio (assinatura, fundo, referência e lâminas) e chama arte.py.
Saída: arte_NN.png, carrossel.pdf (carrossel), folha.png e plano.json em SAIDA.
"""
import glob, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import arte


def ler(c):
    if not c: return {}
    d = json.load(open(c)); return d.get('data') if isinstance(d.get('data'), dict) and 'arte' not in d else d


def main(a):
    if len(a) < 2: sys.exit(__doc__)
    opt = lambda n: a[a.index(n) + 1] if n in a else None
    proj, saida = ler(a[0]), a[1]; est = ler(opt('--estilo')); cli = ler(opt('--cliente')); blobs = opt('--blobs')
    ar = proj.get('arte') or {}; prof = proj.get('profissional') or {}
    if not ar.get('slides'): sys.exit('o projeto não tem lâminas (arte.slides)')

    def local(src):
        m = re.match(r'^/_blob/([0-9a-f]+)', str(src or ''))
        if not m: return src
        achados = glob.glob(os.path.join(blobs or '.', m.group(1) + '*'))
        if not achados: sys.exit(f'baixe o arquivo {m.group(1)} do Studio para {blobs or "."} (Artifact read + path)')
        return achados[0]

    ig = str(prof.get('instagram') or '').lstrip('@')
    ass = {'nome': prof.get('nome') or '', 'handle': '@' + ig if ig else '', **(ar.get('assinatura') or {})}
    fundo = dict(ar.get('fundo') or {'tipo': 'escuro'})
    if fundo.get('foto'): fundo['foto'] = local(fundo['foto'])
    slides = [dict(s, **({'foto': local(s['foto'])} if s.get('foto') else {})) for s in ar['slides']]
    plano = {'formato': ar.get('fmt') or 'post', 'fundo': fundo, 'assinatura': ass, 'referencia': ar.get('referencia') or {}, 'slides': slides}
    idt = (cli or {}).get('identidade') or {}
    ident = {'paleta': idt.get('paleta') or {}, 'fontes': idt.get('fontes') or {}}
    if idt.get('logo_asset'): ident['logo'] = local('/_blob/' + idt['logo_asset'])
    estilo = {'paleta': (est or {}).get('paleta') or {}, 'fontes': (est or {}).get('fontes') or {}}
    os.makedirs(saida, exist_ok=True); json.dump(plano, open(os.path.join(saida, 'plano.json'), 'w'), ensure_ascii=False, indent=1)
    pngs, avisos = arte.gerar(plano, saida, estilo, ident)
    for p in pngs: print(p)
    for w in avisos: print('AVISO', w)


if __name__ == '__main__':
    main(sys.argv[1:])
