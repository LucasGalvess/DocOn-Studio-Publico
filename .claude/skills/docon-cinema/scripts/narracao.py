"""DocOn Cinema · narração dos "Efeitos explicados" com a voz da DocOn (para o Studio no claude.ai).

uso: python3 narracao.py PEDIDO.json PASTA [--perfil assistente]
PEDIDO.json = documento narracoes/<projeto> do Studio ({pedido: [{id, texto, base}], perfil}).
Gera PASTA/<id>.mp3 para cada linha e PASTA/itens.json = {id: {texto, base, arquivo}}.
Depois: suba os MP3 como assets (Artifact asset:true, até 25 por chamada) e grave em narracoes/<projeto>
  itens.<id> = {texto, base, asset_id} e status "pronto".
"""
import sys, os, json, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import voz
ap = argparse.ArgumentParser(); ap.add_argument('pedido'); ap.add_argument('pasta'); ap.add_argument('--perfil', default=None)
A = ap.parse_args(); os.makedirs(A.pasta, exist_ok=True)
P = json.load(open(A.pedido)); P = P.get('data', P); perfil = A.perfil or P.get('perfil') or 'assistente'
itens = {}
for it in P.get('pedido', []):
    f = os.path.join(A.pasta, it['id'] + '.mp3'); voz.falar(it['texto'], f, perfil)
    itens[it['id']] = {'texto': it['texto'], 'base': it.get('base', ''), 'arquivo': f}; print('ok', it['id'], it['texto'][:60])
json.dump(itens, open(os.path.join(A.pasta, 'itens.json'), 'w'), ensure_ascii=False, indent=1)
