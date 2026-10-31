"""DocOn Cinema · mídia online para B-roll, imagens e sons (mesmas fontes do site: web/fontes.mjs).

uso:
  python3 buscar_midia.py buscar "dermatologist clinic" --tipo video [--fontes pexels,pixabay] [--n 6] --saida PASTA
  python3 buscar_midia.py gerar "mãos de médica aplicando protetor" --saida PASTA          (IA Magnific, imagem 9:16)
Saída: PASTA/<fonte>_<id>.<ext> (prévia baixada) + PASTA/itens.json [{arquivo, fonte, id, tipo, titulo, autor, licenca, pagina, duracao}].
Chaves no ambiente: MAGNIFIC_API_KEY (ou FREEPIK_API_KEY), PEXELS_API_KEY, PIXABAY_API_KEY, FREESOUND_API_KEY. Openverse dispensa chave.
A sessão sobe os arquivos como assets do Studio e grava em buscas/<id>.itens (com asset_id); só entram no banco depois de aprovados.
Licenças não comerciais (NC) e sem derivação (ND) ficam de fora.
"""
import os, sys, json, time, re, argparse, urllib.request, urllib.parse
E = os.environ.get
MAG = E('MAGNIFIC_API_KEY') or E('FREEPIK_API_KEY') or ''
MAG_BASE = E('MAGNIFIC_API_BASE', 'https://api.magnific.com')
UA = {'User-Agent': 'DocOnStudio/1.0'}
def get(url, headers=None, data=None):
    req = urllib.request.Request(url, data=json.dumps(data).encode() if data is not None else None, headers={**UA, **(headers or {}), **({'Content-Type': 'application/json'} if data is not None else {})})
    with urllib.request.urlopen(req, timeout=40) as r: return json.loads(r.read())
def okLic(l): return not re.search(r'(^|[-\s/_])(nc|nd)([-\s/_.]|$)|noncommercial|non-commercial|noderiv', (l or '').lower())
q = urllib.parse.quote

def pexels(t, tipo):
    h = {'Authorization': E('PEXELS_API_KEY')}
    if tipo == 'video':
        r = get(f'https://api.pexels.com/videos/search?query={q(t)}&orientation=portrait&per_page=15', h); out = []
        for v in r['videos']:
            f = sorted([x for x in v['video_files'] if x.get('file_type') == 'video/mp4'], key=lambda x: abs((x.get('height') or 0) - 1920))[0]
            out.append(dict(fonte='pexels', id=str(v['id']), tipo='video', titulo=t, url=f['link'], thumb=v['image'], pagina=v['url'], autor=v['user']['name'], licenca='Licença Pexels (uso comercial, sem atribuição obrigatória)', duracao=v['duration']))
        return out
    r = get(f'https://api.pexels.com/v1/search?query={q(t)}&orientation=portrait&per_page=15', h)
    return [dict(fonte='pexels', id=str(p['id']), tipo='imagem', titulo=p.get('alt') or t, url=p['src']['large2x'], thumb=p['src']['medium'], pagina=p['url'], autor=p['photographer'], licenca='Licença Pexels (uso comercial, sem atribuição obrigatória)') for p in r['photos']]
def pixabay(t, tipo):
    k = E('PIXABAY_API_KEY')
    if tipo == 'video':
        r = get(f'https://pixabay.com/api/videos/?key={k}&q={q(t)}&per_page=15&safesearch=true')
        return [dict(fonte='pixabay', id=str(v['id']), tipo='video', titulo=v['tags'], url=(v['videos'].get('large') or {}).get('url') or v['videos']['medium']['url'], thumb=v['videos']['medium'].get('thumbnail'), pagina=v['pageURL'], autor=v['user'], licenca='Licença Pixabay (uso comercial; não revender o arquivo isolado)', duracao=v['duration']) for v in r['hits']]
    r = get(f'https://pixabay.com/api/?key={k}&q={q(t)}&image_type=photo&orientation=vertical&per_page=15&safesearch=true')
    return [dict(fonte='pixabay', id=str(p['id']), tipo='imagem', titulo=p['tags'], url=p['largeImageURL'], thumb=p['webformatURL'], pagina=p['pageURL'], autor=p['user'], licenca='Licença Pixabay (uso comercial; não revender o arquivo isolado)') for p in r['hits']]
def freesound(t, tipo):
    f = q('license:("Creative Commons 0" OR "Attribution") duration:[0 TO 30]')
    r = get(f'https://freesound.org/apiv2/search/text/?query={q(t)}&filter={f}&fields=id,name,previews,license,username,duration,url&page_size=15&token={E("FREESOUND_API_KEY")}')
    return [dict(fonte='freesound', id=str(s['id']), tipo='som', titulo=s['name'], url=s['previews']['preview-hq-mp3'], pagina=s['url'], autor=s['username'], licenca=s['license'], duracao=s['duration']) for s in r['results'] if okLic(s['license'])]
def openverse(t, tipo):
    k = 'audio' if tipo == 'som' else 'images'
    r = get(f'https://api.openverse.org/v1/{k}/?q={q(t)}&license_type=commercial,modification&page_size=15' + ('&aspect_ratio=tall' if k == 'images' else ''))
    return [dict(fonte='openverse', id=x['id'], tipo='som' if tipo == 'som' else 'imagem', titulo=x.get('title'), url=x['url'], thumb=x.get('thumbnail'), pagina=x.get('foreign_landing_url'), autor=x.get('creator'), licenca=f"{x.get('license', '').upper()} {x.get('license_version') or ''}".strip(), duracao=(x.get('duration') or 0) / 1000 or None) for x in r['results'] if okLic(x.get('license'))]
def magnific(t, tipo):     # conferir os caminhos em docs.magnific.com
    h = {'x-magnific-api-key': MAG, 'x-freepik-api-key': MAG}
    kind = 'videos' if tipo == 'video' else 'resources'
    r = get(f'{MAG_BASE}/v1/{kind}?term={q(t)}&limit=15' + ('&filters[content_type][photo]=1&filters[orientation][portrait]=1' if kind == 'resources' else ''), h); out = []
    for x in r.get('data', []):
        try: url = get(f'{MAG_BASE}/v1/{kind}/{x["id"]}/download', h)['data']['url']     # registra o download (exigência da licença)
        except Exception: continue
        out.append(dict(fonte='magnific', id=str(x['id']), tipo=tipo, titulo=x.get('title') or x.get('name') or t, url=url, pagina=x.get('url'), autor=(x.get('author') or {}).get('name'), licenca='Magnific (licença da sua conta)'))
    return out
FONTES = dict(magnific=(lambda: bool(MAG), ('imagem', 'video')), pexels=(lambda: bool(E('PEXELS_API_KEY')), ('imagem', 'video')), pixabay=(lambda: bool(E('PIXABAY_API_KEY')), ('imagem', 'video')),
              freesound=(lambda: bool(E('FREESOUND_API_KEY')), ('som',)), openverse=(lambda: True, ('imagem', 'som')))
def baixar(it, pasta):
    ext = {'video': '.mp4', 'som': '.mp3'}.get(it['tipo'], '.jpg'); dst = os.path.join(pasta, f"{it['fonte']}_{re.sub(r'[^A-Za-z0-9_-]', '', it['id'])[:40]}{ext}")
    req = urllib.request.Request(it['url'], headers=UA)
    with urllib.request.urlopen(req, timeout=120) as r, open(dst, 'wb') as f: f.write(r.read())
    return dst

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('acao', choices=['buscar', 'gerar']); ap.add_argument('texto'); ap.add_argument('--tipo', default='video')
    ap.add_argument('--fontes', default=''); ap.add_argument('--n', type=int, default=6); ap.add_argument('--saida', required=True)
    A = ap.parse_args(); os.makedirs(A.saida, exist_ok=True); itens = []
    if A.acao == 'buscar':
        alvo = [f for f in (A.fontes.split(',') if A.fontes else FONTES) if f in FONTES and FONTES[f][0]() and A.tipo in FONTES[f][1]]
        for f in alvo:
            try: achados = globals()[f](A.texto, A.tipo)
            except Exception as e: print('falhou', f, e, file=sys.stderr); continue
            for it in achados[:max(1, A.n // max(1, len(alvo)) + 1)]:
                try: it['arquivo'] = baixar(it, A.saida); itens.append(it); print('ok', f, it['titulo'][:50] if it.get('titulo') else it['id'])
                except Exception as e: print('download falhou', f, e, file=sys.stderr)
    else:
        if not MAG: sys.exit('defina MAGNIFIC_API_KEY')
        h = {'x-magnific-api-key': MAG, 'x-freepik-api-key': MAG}
        t = get(f'{MAG_BASE}/v1/ai/mystic', h, dict(prompt=A.texto + '. Vertical 9:16, luz natural, sem texto na imagem, sem marcas, aparência real e profissional.', aspect_ratio='social_story_9_16', resolution='2k'))
        tid = (t.get('data') or t)['task_id']
        for _ in range(100):
            time.sleep(3); s = get(f'{MAG_BASE}/v1/ai/mystic/{tid}', h).get('data', {})
            if str(s.get('status', '')).lower() in ('completed', 'done', 'success'):
                for k, u in enumerate(s.get('generated', [])[:4]):
                    it = dict(fonte='magnific-ia', id=f'{tid}_{k}', tipo='imagem', titulo=A.texto[:60], url=u, licenca='Gerado com IA na sua conta Magnific', origem='ia', prompt=A.texto)
                    it['arquivo'] = baixar(it, A.saida); itens.append(it)
                break
            if 'fail' in str(s.get('status', '')).lower(): sys.exit('geração falhou')
    json.dump(itens, open(os.path.join(A.saida, 'itens.json'), 'w'), ensure_ascii=False, indent=1)
    print(len(itens), 'itens em', A.saida)
