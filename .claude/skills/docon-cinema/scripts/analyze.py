"""DocOn Cinema · análise: cortes de plano, matte RVM, landmarks (opcional) e trajetória de câmera (LK + RANSAC no fundo).
uso: python3 analyze.py VIDEO OUTDIR MODELSDIR [--faces]"""
import cv2, numpy as np, onnxruntime as ort, json, sys, time
V, OUT, MD = sys.argv[1:4]; FACES = '--faces' in sys.argv
cap = cv2.VideoCapture(V); N = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)); FPS = cap.get(cv2.CAP_PROP_FPS)
W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)); H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
# ---- pass 1: shot cuts
prev = None; cuts = [0]; frames_small = []
for i in range(N):
    ok, f = cap.read()
    if not ok: N = i; break
    s = cv2.resize(f, (90, 160)); h = cv2.calcHist([cv2.cvtColor(s, cv2.COLOR_BGR2HSV)], [0, 1], None, [16, 8], [0, 180, 0, 256]); cv2.normalize(h, h)
    if prev is not None:
        d = cv2.compareHist(prev[0], h, cv2.HISTCMP_BHATTACHARYYA); md = np.mean(np.abs(s.astype(int) - prev[1].astype(int)))
        if (d > 0.30 or md > 32) and i - cuts[-1] >= 8: cuts.append(i)
    prev = (h, s)
cuts.append(N)
print('frames', N, 'fps', FPS, 'shots', len(cuts) - 1, flush=True)
# ---- pass 2: matte + landmarks + trajectory
sess = ort.InferenceSession(MD + '/rvm.onnx', providers=['CPUExecutionProvider'])
fl = None
if FACES:
    import mediapipe as mp
    from mediapipe.tasks import python as mpt
    from mediapipe.tasks.python import vision
    fl = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(base_options=mpt.BaseOptions(model_asset_path=MD + '/face_landmarker.task'), running_mode=vision.RunningMode.VIDEO, num_faces=1))
cap = cv2.VideoCapture(V); sw, sh = W // 2, H // 2
alphas = np.zeros((N, H // 4, W // 4), np.uint8); lms = np.full((N, 478, 2), np.nan, np.float32); tr = np.zeros((N, 3))
prevg = pm = None; t0 = time.time(); cutset = set(cuts)
for i in range(N):
    ok, f = cap.read()
    if i in cutset: rec = [np.zeros([1, 1, 1, 1], np.float32)] * 4; prevg = None
    small = cv2.resize(f, (sw, sh), interpolation=cv2.INTER_AREA)
    src = cv2.cvtColor(small, cv2.COLOR_BGR2RGB).astype(np.float32).transpose(2, 0, 1)[None] / 255
    o = sess.run(None, {'src': src, 'r1i': rec[0], 'r2i': rec[1], 'r3i': rec[2], 'r4i': rec[3], 'downsample_ratio': np.array([0.4], np.float32)})
    pha = o[1][0, 0]; rec = o[2:6]
    alphas[i] = (cv2.resize(pha, (W // 4, H // 4), interpolation=cv2.INTER_AREA) * 255).astype(np.uint8)
    if fl is not None:
        import mediapipe as mp
        r = fl.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(small, cv2.COLOR_BGR2RGB)), int(i * 1000 / FPS))
        if r.face_landmarks: lms[i] = np.array([[p.x * W, p.y * H] for p in r.face_landmarks[0]])
    g = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    mask = cv2.erode(((pha < 0.05).astype(np.uint8) * 255), np.ones((25, 25), np.uint8))
    if mask.mean() < 0.15 * 255: mask[:] = 255           # pessoa ocupa quase tudo: usa o quadro inteiro (RANSAC filtra)
    if prevg is not None:
        pts = cv2.goodFeaturesToTrack(prevg, 400, 0.01, 12, mask=pm)
        if pts is not None and len(pts) >= 10:
            nxt, st, _ = cv2.calcOpticalFlowPyrLK(prevg, g, pts, None, winSize=(21, 21), maxLevel=3)
            good = st.ravel() == 1
            if good.sum() >= 8:
                M, _ = cv2.estimateAffinePartial2D(pts[good], nxt[good], method=cv2.RANSAC, ransacReprojThreshold=2.0)
                if M is not None:
                    sc = W / sw
                    tr[i] = [np.clip(M[0, 2] * sc, -30, 30), np.clip(M[1, 2] * sc, -30, 30), np.clip(np.arctan2(M[1, 0], M[0, 0]), -0.01, 0.01)]
    pm = mask; prevg = g
    if i % 200 == 0: print(i, N, round(time.time() - t0, 1), flush=True)
np.save(OUT + '/alphas.npy', alphas); np.save(OUT + '/lms.npy', lms); np.save(OUT + '/tr.npy', tr)
json.dump({'cuts': cuts, 'fps': FPS, 'n': N, 'w': W, 'h': H}, open(OUT + '/shots.json', 'w'))
print('done', round(time.time() - t0, 1))
