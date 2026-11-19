"""Converte os quadros de testes.html (1080x960, tela dividida) em PNG 1080x1920 RGBA para o bloco motion do run_brief.
uso: python3 para_pipeline.py ENTRADA SAIDA [--cheia]   (--cheia: quadros 1080x1920 da cena 4)
O topo fica transparente (o vídeo da profissional aparece em cima) e a entrada/saída ganham alfa de 0,35 s."""
import sys, os, glob, cv2, numpy as np
src, dst = sys.argv[1], sys.argv[2]; cheia = '--cheia' in sys.argv; os.makedirs(dst, exist_ok=True)
fs = sorted(glob.glob(os.path.join(src, '*.png'))); n = len(fs); F = 0.35 * 30
for i, f in enumerate(fs):
    im = cv2.imread(f); k = min(1.0, (i + 1) / F, (n - i) / F)
    out = np.zeros((1920, 1080, 4), np.uint8)
    if cheia: out[..., :3] = cv2.resize(im, (1080, 1920)); out[..., 3] = int(255 * k)
    else: out[960:, :, :3] = cv2.resize(im, (1080, 960)); out[960:, :, 3] = int(255 * k)
    cv2.imwrite(os.path.join(dst, f'{i:05d}.png'), out, [cv2.IMWRITE_PNG_COMPRESSION, 1])
print('ok', n)
