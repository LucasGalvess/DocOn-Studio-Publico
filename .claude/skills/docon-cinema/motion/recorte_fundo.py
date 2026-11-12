"""DocOn · abertura "profissional recortada na frente de outro vídeo" (formato comentário/react).

O vídeo de apoio ocupa a tela inteira como fundo; a profissional aparece recortada do próprio fundo (RVM em alta),
menor e enquadrada embaixo, e no fim some em dissolve para o vídeo normal.
uso: python3 recorte_fundo.py BRUTO FUNDO SAIDA [--dur 6] [--escala .62] [--fundo_zoom 1.3] [--fundo_y .3] [--t0_fundo 0]
  BRUTO: vídeo da profissional (cor original; os quadros 0..dur são os do início do reels)
  FUNDO: vídeo de apoio (ex.: o caso que ela comenta)
Saída: SAIDA/NNNNN.png 1080x1920 (opaco; nos últimos 0,5 s fica transparente para revelar o vídeo normal).
Use no briefing: bloco motion com "pasta": SAIDA, "inicio": 0, "fim": dur e "legenda_y" (ex.: 1760) para a legenda descer.
"""
import sys, os, argparse
import numpy as np, cv2, onnxruntime as ort

ap = argparse.ArgumentParser(); ap.add_argument('bruto'); ap.add_argument('fundo'); ap.add_argument('saida')
ap.add_argument('--dur', type=float, default=6.0); ap.add_argument('--escala', type=float, default=.62)
ap.add_argument('--fundo_zoom', type=float, default=1.3); ap.add_argument('--fundo_y', type=float, default=.3)
ap.add_argument('--t0_fundo', type=float, default=0.0)
ap.add_argument('--lado', default='direita', choices=['direita', 'esquerda', 'centro']); ap.add_argument('--sobra', type=float, default=.12)   # quanto do quadro da profissional passa da borda lateral
A = ap.parse_args(); os.makedirs(A.saida, exist_ok=True)
W, H = 1080, 1920
def ease(x): x = min(max(x, 0), 1); return x * x * (3 - 2 * x)
sess = ort.InferenceSession(os.path.expanduser('~/.docon/models/rvm.onnx'), providers=['CPUExecutionProvider'])
rec = [np.zeros([1, 1, 1, 1], np.float32)] * 4
cb = cv2.VideoCapture(A.bruto); fps = cb.get(cv2.CAP_PROP_FPS) or 30
cf = cv2.VideoCapture(A.fundo); cf.set(cv2.CAP_PROP_POS_MSEC, A.t0_fundo * 1000); ffps = cf.get(cv2.CAP_PROP_FPS) or 30
n = int(round(A.dur * 30)) + 2; last_bg = None
# fundo: amplia, sobe (olhos no alto) e desfoca/escurece a faixa de baixo (onde costuma ter texto gravado)
yy = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]; banda = np.clip((yy - .52) / .14, 0, 1)
for i in range(n):
    t = i / 30
    cb.set(cv2.CAP_PROP_POS_FRAMES, int(round(t * fps))); ok, f = cb.read()
    if not ok: break
    while cf.get(cv2.CAP_PROP_POS_MSEC) / 1000 <= A.t0_fundo + t + 1e-3:
        okb, b = cf.read()
        if not okb: break
        last_bg = b
    b = last_bg
    s = max(W / b.shape[1], H / b.shape[0]) * A.fundo_zoom; bb = cv2.resize(b, (int(b.shape[1] * s), int(b.shape[0] * s)), interpolation=cv2.INTER_LANCZOS4)
    x0 = (bb.shape[1] - W) // 2; y0 = int((bb.shape[0] - H) * A.fundo_y); bg = bb[y0:y0 + H, x0:x0 + W].astype(np.float32) / 255
    blur = cv2.GaussianBlur(bg, (0, 0), 22) * .55; bg = bg * (1 - banda) + blur * banda
    # recorte da profissional (RVM a 1/2 da resolução, alfa ampliado)
    f = cv2.resize(f, (W, H)); small = cv2.resize(f, (W // 2, H // 2), interpolation=cv2.INTER_AREA)
    src = cv2.cvtColor(small, cv2.COLOR_BGR2RGB).astype(np.float32).transpose(2, 0, 1)[None] / 255
    o = sess.run(None, {'src': src, 'r1i': rec[0], 'r2i': rec[1], 'r3i': rec[2], 'r4i': rec[3], 'downsample_ratio': np.array([.5], np.float32)}); rec = o[2:6]
    a = cv2.resize(o[1][0, 0], (W, H), interpolation=cv2.INTER_CUBIC); a = np.clip((a - .04) / .92, 0, 1)
    fg = f.astype(np.float32) / 255
    # saída: o recorte cresce do canto até a tela cheia (com o zoom 1,07 do compositor) e cobre o fundo: sem duplicar a pessoa
    p = ease((t - (A.dur - .6)) / .6); k = A.escala + (1.07 - A.escala) * p; a = a + (1 - a) * p
    fw, fh = int(W * k), int(H * k); fgs = cv2.resize(fg, (fw, fh), interpolation=cv2.INTER_AREA); al = cv2.resize(a, (fw, fh), interpolation=cv2.INTER_AREA)[..., None]
    X0c = (W - fw + int(A.sobra * fw)) if A.lado == 'direita' else (-int(A.sobra * fw) if A.lado == 'esquerda' else (W - fw) // 2)
    X0 = int(X0c + ((W - fw) / 2 - X0c) * p); Y0 = int((H - fh) + ((H - fh) / 2 - (H - fh)) * p)
    sh = cv2.GaussianBlur(al, (0, 0), 18)[..., None] if al.ndim == 2 else cv2.GaussianBlur(al[..., 0], (0, 0), 18)[..., None]
    out = bg.copy(); xa, xb = max(0, X0), min(W, X0 + fw); ca, cb_ = xa - X0, xb - X0      # recorte preso à borda: o que passa da tela é cortado
    ya, yb = max(0, Y0), min(H, Y0 + fh); ra, rb = ya - Y0, yb - Y0
    reg = out[ya:yb, xa:xb]; al = al[ra:rb]; fgs = fgs[ra:rb]
    sh = sh[ra:rb]; sy = 14; shr = np.zeros_like(sh); shr[sy:, :] = sh[:-sy, :]
    reg *= 1 - .45 * shr[:, ca:cb_]                                      # sombra suave atrás do recorte
    reg[:] = reg * (1 - al[:, ca:cb_]) + fgs[:, ca:cb_] * al[:, ca:cb_]
    rgba = np.dstack([out, np.ones((H, W, 1), np.float32)])

    cv2.imwrite(os.path.join(A.saida, f'{i:05d}.png'), (rgba * 255).astype(np.uint8), [cv2.IMWRITE_PNG_COMPRESSION, 1])   # BGR do OpenCV + alfa = BGRA
print('ok', n)
