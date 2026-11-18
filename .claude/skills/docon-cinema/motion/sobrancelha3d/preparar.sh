#!/usr/bin/env bash
# DocOn · cena 3D "perda de pelos das sobrancelhas" (rosto escaneado + sobrancelhas fio a fio + corte do folículo).
# uso: bash preparar.sh PASTA   → baixa o modelo, gera a pele 4K e os fios, monta PASTA/www. Depois:
#   (cd PASTA/www && python3 -m http.server 8811 &) ; node render.cjs quadros 40   (de dentro de PASTA)
# Modelo: "Lee Perry-Smith" head scan, Infinite-Realities, CC BY 3.0 (dar o crédito na entrega). Nada disto vai para o git.
set -e; A=$(cd "$(dirname "$0")" && pwd); P=${1:?pasta}; mkdir -p "$P/modelo" "$P/www/fonts" "$P/scripts"; cd "$P"
B=https://raw.githubusercontent.com/mrdoob/three.js/r160/examples/models/gltf/LeePerrySmith
for f in LeePerrySmith.glb Map-COL.jpg Infinite-Level_02_Tangent_SmoothUV.jpg; do [ -f modelo/$f ] || curl -sf -o modelo/$f $B/$f; done
cp "$A"/pele.py "$A"/fios.py "$A"/render.cjs scripts/
python3 - <<'PY'
import cv2, numpy as np            # máscara das sobrancelhas originais (1024)
im=cv2.imread('modelo/Map-COL.jpg'); L=cv2.cvtColor(im,cv2.COLOR_BGR2LAB)[...,0].astype(float); loc=cv2.GaussianBlur(L,(0,0),12)
m=np.zeros(L.shape,np.uint8); m[225:320,350:680]=((loc-L)[225:320,350:680]>14).astype(np.uint8)*255
m=cv2.morphologyEx(m,cv2.MORPH_OPEN,np.ones((2,2),np.uint8)); m=cv2.morphologyEx(m,cv2.MORPH_CLOSE,np.ones((5,5),np.uint8))
n,lab,st,_=cv2.connectedComponentsWithStats(m); keep=[i for i in range(1,n) if st[i,4]>300]; cv2.imwrite('mask_brow1k.png',np.isin(lab,keep).astype(np.uint8)*255)
PY
python3 scripts/pele.py && python3 scripts/fios.py
cp "$A"/cena.html www/; cp modelo/LeePerrySmith.glb modelo/Infinite-Level_02_Tangent_SmoothUV.jpg pele4k.jpg fios.json www/
ln -sfn ~/.docon/motion/node_modules/three www/three; cp ~/.docon/fonts/gf/Montserrat-{500,600,700,800}.ttf www/fonts/ 2>/dev/null || true
echo pronto
