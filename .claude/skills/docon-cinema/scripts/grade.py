"""DocOn Cinema · grade por quadro (sem reamostrar): balanço de branco por plano, look natural, pele/dentes e DOF opcionais.
Também calcula a correção de estabilização (corr.npy), aplicada depois numa única reamostragem no compositor.
uso: python3 grade.py VIDEO WORKDIR [preview i,j,k | full] [--dof] [--skin]"""
import cv2, numpy as np, sys, json, subprocess
from scipy.ndimage import gaussian_filter1d
V, WD, mode = sys.argv[1:4]; DOF = '--dof' in sys.argv; SKIN = '--skin' in sys.argv
info = json.load(open(WD + '/shots.json')); CUTS = info['cuts']; N = info['n']; W, H = info['w'], info['h']
tr = np.load(WD + '/tr.npy'); AL = np.load(WD + '/alphas.npy'); LM = np.load(WD + '/lms.npy')
NS = len(CUTS) - 1
def shot_of(i): return int(np.searchsorted(CUTS, i, side='right') - 1)
# ---- estabilização: sigma 75 (travado) / 14 (caminhando), reduzido até caber na margem do zoom 1,07
Z = 1.07; MX = (Z - 1) / 2 * W * 0.95; MY = (Z - 1) / 2 * H * 0.95
corr = np.zeros((N, 3)); sig_used = []
for k in range(NS):
    a, b = CUTS[k], CUTS[k + 1]
    raw = np.cumsum(np.vstack([[0, 0, 0], tr[a + 1:b]]), 0)
    vel = np.abs(np.diff(gaussian_filter1d(raw[:, :2], 5, axis=0, mode='nearest'), axis=0)).mean() if b - a > 3 else 0
    sig = 14 if vel > 1.2 else 75
    while True:
        sm = np.stack([gaussian_filter1d(raw[:, j], sig, mode='nearest') for j in range(3)], 1); c = sm - raw
        if (np.abs(c[:, 0]).max() <= MX and np.abs(c[:, 1]).max() <= MY) or sig <= 4: break
        sig *= 0.85
    c[:, 0] = np.clip(c[:, 0], -MX, MX); c[:, 1] = np.clip(c[:, 1], -MY, MY)
    corr[a:b] = c; sig_used.append(round(sig, 1))
np.save(WD + '/corr.npy', corr); print('sigmas', sig_used, flush=True)
# ---- balanço de branco por plano (pixels neutros do fundo; mundo-cinza como reserva)
cap = cv2.VideoCapture(V); mids = {(CUTS[k] + CUTS[k + 1]) // 2: k for k in range(NS)}; gains = {}
for i in range(N):
    ok, f = cap.read()
    if i in mids:
        k = mids[i]; bg = cv2.resize(AL[i], (W, H)) < 10; hsv = cv2.cvtColor(f, cv2.COLOR_BGR2HSV)
        n = bg & (hsv[..., 1] < 60) & (hsv[..., 2] > 80) & (hsv[..., 2] < 245)
        if n.sum() < 2000: n = (hsv[..., 1] < 60) & (hsv[..., 2] > 60) & (hsv[..., 2] < 245)
        b_, g_, r_ = f[n].mean(0) if n.sum() > 500 else f.reshape(-1, 3).mean(0)
        gb, gr = np.clip(g_ / b_, 0.85, 1.5), np.clip(g_ / r_, 0.80, 1.15)
        gains[k] = np.array([1 + (gb - 1) * 0.8, 1.0, (1 + (gr - 1) * 0.8) * 1.01], np.float32)  # 80% + um toque quente
print('gains', {k: v.round(3).tolist() for k, v in gains.items()}, flush=True)
# ---- curva natural: contraste suave, preto levemente levantado, ombro nas altas
x = np.linspace(0, 1, 4096); y = x ** 0.94; y = 0.5 + (y - 0.5) * 0.92; y = 0.015 + 0.985 * np.clip(y, 0, None)
k0 = 0.88; hi = y > k0; y[hi] = k0 + (1 - k0) * np.tanh((y[hi] - k0) / (1 - k0) * 1.15) / np.tanh(1.15)
LUT = np.clip(y, 0, 1).astype(np.float32)
FACE_OVAL = [10,338,297,332,284,251,389,356,454,323,361,288,397,365,379,378,400,377,152,148,176,149,150,136,172,58,132,93,234,127,162,21,54,103,67,109]
HOLES = [[33,7,163,144,145,153,154,155,133,173,157,158,159,160,161,246],[362,382,381,380,374,373,390,249,263,466,388,387,386,385,384,398],
         [70,63,105,66,107,55,65,52,53,46],[300,293,334,296,336,285,295,282,283,276],[61,146,91,181,84,17,314,405,321,375,291,409,270,269,267,0,37,39,40,185]]
INNER = [78,95,88,178,87,14,317,402,318,324,308,415,310,311,312,13,82,81,80,191]
def process(i, f):
    k = shot_of(i); img = f.astype(np.float32) / 255
    a = cv2.resize(AL[i], (W, H)).astype(np.float32) / 255
    ycc = cv2.cvtColor(f, cv2.COLOR_BGR2YCrCb)
    skin = ((ycc[..., 1] > 135) & (ycc[..., 1] < 178) & (ycc[..., 2] > 80) & (ycc[..., 2] < 130) & (ycc[..., 0] > 50)).astype(np.float32)
    skin = cv2.GaussianBlur(skin, (0, 0), 6)
    g = gains[k]; img = np.clip(img * (g * (1 - skin[..., None]) + g ** 0.35 * skin[..., None]), 0, 1)
    lm = LM[i]
    if SKIN and not np.isnan(lm[0, 0]):
        fm = np.zeros((H, W), np.uint8); cv2.fillPoly(fm, [lm[FACE_OVAL].astype(np.int32)], 255)
        for idx in HOLES: cv2.fillPoly(fm, [cv2.convexHull(lm[idx].astype(np.int32))], 0)
        fmf = cv2.GaussianBlur(cv2.erode(fm, np.ones((9, 9), np.uint8)).astype(np.float32) / 255, (0, 0), 7)
        x0, y0 = np.maximum(lm.min(0).astype(int) - 40, 0); x1, y1 = np.minimum(lm.max(0).astype(int) + 40, [W, H])
        if x1 - x0 > 40 and y1 - y0 > 40:
            roi = img[y0:y1, x0:x1]; sm = cv2.ximgproc.guidedFilter(roi, roi, radius=max(4, int((x1 - x0) / 40)), eps=0.0025)
            w = (fmf[y0:y1, x0:x1] * 0.35)[..., None]; img[y0:y1, x0:x1] = roi * (1 - w) + sm * w
            tm = np.zeros((H, W), np.uint8); cv2.fillPoly(tm, [lm[INNER].astype(np.int32)], 255)
            lab = cv2.cvtColor(img[y0:y1, x0:x1], cv2.COLOR_BGR2Lab); t = cv2.GaussianBlur(tm[y0:y1, x0:x1].astype(np.float32) / 255, (0, 0), 1.5)
            tw = t * np.clip((lab[..., 0] - 45) / 20, 0, 1) * np.clip((40 - np.abs(lab[..., 2])) / 30, 0, 1)
            lab[..., 2] -= lab[..., 2].clip(0) * 0.45 * tw; lab[..., 1] *= 1 - 0.25 * tw; lab[..., 0] = np.minimum(lab[..., 0] + 6 * tw, 100)
            img[y0:y1, x0:x1] = cv2.cvtColor(lab, cv2.COLOR_Lab2BGR)
    if DOF:
        aa = cv2.GaussianBlur(a, (0, 0), 2)[..., None]; bw = 1 - aa
        bl = cv2.GaussianBlur(img * bw, (0, 0), 7) / np.maximum(cv2.GaussianBlur(bw, (0, 0), 7)[..., None], 1e-3)
        img = img * aa + bl * 0.90 * (1 - aa)
    img = LUT[np.clip(img * 4095, 0, 4095).astype(np.int32)]
    L = img.mean(2, keepdims=True); img = np.clip(img + np.clip((L - 0.65) / 0.35, 0, 1) * np.array([-0.006, 0, 0.004], np.float32), 0, 1)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV); hsv[..., 1] = np.clip(hsv[..., 1] * (1.24 - 0.14 * skin), 0, 1)
    img = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
    return (np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)
if mode == 'preview':
    want = sorted(int(x) for x in sys.argv[4].split(',')); cap = cv2.VideoCapture(V); outs = []
    for i in range(max(want) + 1):
        ok, f = cap.read()
        if i in want: outs.append(np.hstack([cv2.resize(f, (W // 4, H // 4)), cv2.resize(process(i, f), (W // 4, H // 4))]))
    rows = [np.hstack(outs[j:j + 4] + [np.zeros_like(outs[0])] * (4 - len(outs[j:j + 4]))) for j in range(0, len(outs), 4)]
    cv2.imwrite(WD + '/prev_grade.jpg', np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 88])
else:
    cap = cv2.VideoCapture(V)
    p = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}', '-r', str(info['fps']), '-i', '-',
                          '-c:v', 'ffv1', '-level', '3', '-pix_fmt', 'bgr0', WD + '/graded.mkv'], stdin=subprocess.PIPE)
    for i in range(N):
        ok, f = cap.read(); p.stdin.write(process(i, f).tobytes())
        if i % 200 == 0: print(i, N, flush=True)
    p.stdin.close(); p.wait()
