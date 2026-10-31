"""DocOn Cinema · palavras com tempo (s do bruto) para a legenda ao vivo do DocOn Studio.

uso: python3 palavras_studio.py WORK > palavras.json
Lê WORK/words_raw.json ([[palavra, início], ...]) e escreve [{"w","s","e"}]. Grave em
projetos/<id>.transcricao.palavras (ArtifactData update, ou studio_gravar no site) junto com transcricao.texto.
"""
import sys, json, os
W = json.load(open(os.path.join(sys.argv[1], 'words_raw.json')))
out = []
for i, (w, s) in enumerate(W):
    nxt = W[i + 1][1] if i + 1 < len(W) else s + 0.6
    out.append({'w': w, 's': round(s, 2), 'e': round(min(nxt - 0.02, s + 0.7), 2)})
json.dump(out, sys.stdout, ensure_ascii=False, separators=(',', ':'))
