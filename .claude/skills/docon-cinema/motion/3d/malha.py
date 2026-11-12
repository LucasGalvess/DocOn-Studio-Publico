"""DocOn 3D · malha do rosto REAL de quem fala no vídeo (MediaPipe, 478 pontos com profundidade).
uso: python3 malha.py VIDEO SAIDA/malha.json
Escolhe os quadros mais frontais e neutros, tira a média, corrige a inclinação e reconstrói os triângulos.
A malha é dado biométrico do cliente: fica só na pasta de trabalho, nunca no repositório."""
import json, sys, cv2, numpy as np, mediapipe as mp, os
from mediapipe.tasks.python import vision, BaseOptions
from mediapipe.tasks.python.vision.face_landmarker import FaceLandmarksConnections as FC
opts = vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=os.path.expanduser('~/.docon/models/face_landmarker.task')), output_face_blendshapes=True, num_faces=1)
det = vision.FaceLandmarker.create_from_options(opts)
VIDEO, SAIDA = sys.argv[1], sys.argv[2]
cap = cv2.VideoCapture(VIDEO); dur = cap.get(7) / (cap.get(5) or 30); fps = cap.get(5); acc = []; info = []
for t in [x / 2 for x in range(0, int(dur * 2))]:
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(t * fps)); ok, f = cap.read()
    if not ok: continue
    r = det.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(f, cv2.COLOR_BGR2RGB)))
    if not r.face_landmarks: continue
    L = np.array([[p.x, p.y, p.z] for p in r.face_landmarks[0]]); bs = {b.category_name: b.score for b in r.face_blendshapes[0]}
    # frontal: nariz (1) centralizado entre os cantos dos olhos (33, 263); neutro: pouca expressão
    yaw = abs((L[1, 0] - L[33, 0]) - (L[263, 0] - L[1, 0])) / abs(L[263, 0] - L[33, 0])
    expr = bs['eyeBlinkLeft'] + bs['eyeBlinkRight'] + bs['browInnerUp'] + bs['jawOpen'] + bs['browOuterUpLeft'] + bs['browOuterUpRight'] + bs['mouthSmileLeft']
    info.append((yaw + expr, t, L))
info.sort(key=lambda x: x[0]); best = info[:6]; print('quadros', [(round(s, 3), t) for s, t, _ in best])
L = np.mean([b[2] for b in best], 0); H, Wd = 1920, 1080
P = np.stack([(L[:, 0] - .5) * Wd, -(L[:, 1] - .5) * H, -L[:, 2] * Wd], 1)
P -= P[[33, 263, 1]].mean(0); P /= np.linalg.norm(P[263] - P[33]) / .62     # olho a olho = 0.62 unidades (≈ 9,5 cm reais)
edges = {tuple(sorted((c.start, c.end))) for c in FC.FACE_LANDMARKS_TESSELATION}
nb = {}
for a, b in edges: nb.setdefault(a, set()).add(b); nb.setdefault(b, set()).add(a)
tris = set()
for a, b in edges:
    for c in nb[a] & nb[b]: tris.add(tuple(sorted((a, b, c))))
# remove triângulos "falsos" (que cobrem outros): mantém os de menor área quando uma aresta tem mais de 2
from collections import defaultdict
area = lambda t: np.linalg.norm(np.cross(P[t[1]] - P[t[0]], P[t[2]] - P[t[0]])) / 2
ec = defaultdict(list)
for t in tris:
    for e in [(t[0], t[1]), (t[0], t[2]), (t[1], t[2])]: ec[e].append(t)
bad = set()
for e, ts in ec.items():
    if len(ts) > 2: bad.update(sorted(ts, key=area)[2:])
tris = [t for t in tris if t not in bad]
# orienta os triângulos para fora (normal com z > 0 na frente)
out = []
cen = P.mean(0) - np.array([0, 0, .6])
for a, b, c in tris:
    n = np.cross(P[b] - P[a], P[c] - P[a]); m = (P[a] + P[b] + P[c]) / 3
    out.append([a, b, c] if np.dot(n, m - cen) > 0 else [a, c, b])
json.dump({'v': np.round(P, 5).tolist(), 'f': out, 'quadros': [t for _, t, _ in best]}, open(SAIDA, 'w'))
print(len(P), 'vértices', len(out), 'triângulos; profundidade', P[:, 2].min().round(3), P[:, 2].max().round(3))
