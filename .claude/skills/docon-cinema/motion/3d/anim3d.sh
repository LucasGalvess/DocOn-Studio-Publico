#!/usr/bin/env bash
# DocOn 3D · prepara a pasta de trabalho e renderiza as cenas 3D anatômicas (rosto real do vídeo + músculos).
# uso: bash anim3d.sh VIDEO TRAB "1:5.8:5.96 3:6.9:6.40 ..."   (cena:duração_desenho:duração_real do bloco no plano.txt)
# Saída: TRAB/seq/s<N>/*.png → use no briefing como bloco motion com "pasta": "TRAB/seq/s<N>".
set -e; AQUI="$(cd "$(dirname "$0")" && pwd)"; V="$1"; T="$2"; CENAS="$3"; PORTA=${PORTA:-8799}
mkdir -p "$T/seq"; cp "$AQUI/cena.html" "$T/"; ln -sfn ~/.docon/motion/node_modules/three "$T/three"; ln -sfn ~/.docon/fonts "$T/fonts"
[ -d ~/.docon/motion/node_modules/three ] || (cd ~/.docon/motion && npm i --no-audit --no-fund three@0.170.0 >/dev/null)
[ -f "$T/malha.json" ] || python3 "$AQUI/malha.py" "$V" "$T/malha.json"
(cd "$T" && python3 -m http.server $PORTA --bind 127.0.0.1 >/dev/null 2>&1 & echo $! > "$T/.srv"); sleep 1
for c in $CENAS; do IFS=: read n dd dr <<< "$c"; PORTA=$PORTA NODE_PATH=$(npm root -g) node "$AQUI/render3d.cjs" $n $dd "$T/seq/s$n" "" $dr & done; wait
kill $(cat "$T/.srv") 2>/dev/null || true; echo "cenas em $T/seq"
