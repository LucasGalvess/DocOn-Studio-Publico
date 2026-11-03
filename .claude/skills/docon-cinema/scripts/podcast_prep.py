"""DocOn Cinema · formato PODCAST (conversa a dois): monta os takes escolhidos num vídeo vertical único.

O bruto de podcast costuma ser longo (e às vezes horizontal, com as duas pessoas). Este script:
  1. corta cada trecho (take) na ordem do roteiro — a ordem da lista, não a do bruto;
  2. reenquadra para 9:16 quando o bruto é mais largo que vertical, no locutor de cada take
     (enquadramento: "esquerda" | "centro" | "direita" | número 0..1 | "auto" = rosto mais próximo do lado indicado
      pelo locutor, ou o maior rosto; sem detector de rosto, "auto" vira "centro");
  3. junta tudo em WORK/podcast.mp4 (1080x1920, H.264 + AAC), com micro fades de áudio entre os takes;
  4. grava WORK/podcast_mapa.json: [{take, locutor, src_inicio, src_fim, inicio, fim}] (inicio/fim = tempo no vídeo montado).

Depois o fluxo é o normal: podcast.mp4 vira o "bruto" do projeto (Studio e run_brief.py), e os blocos usam os tempos
do vídeo montado. Os locutores vêm do mapa (assinatura de cada um na 1ª vez que fala).

uso: python3 podcast_prep.py VIDEO TRECHOS.json WORK [--modelos DIR]
TRECHOS.json: {"trechos": [{"inicio": 12.3, "fim": 31.0, "locutor": "Entrevistadora", "enquadramento": "esquerda"}, ...]}
              (ou a lista direto). Tempos em segundos do bruto.

ZOOM EM QUEM FALA (plano aberto com os dois, mesmo vertical): cada trecho pode ter
  "zoom": 1.7            aproximação (1 = sem zoom)
  "foco": [0.24, 0.52]   posição do rosto de quem fala no quadro do bruto (0..1); sem foco, usa o enquadramento
  "transicao": 0.7       segundos do movimento de câmera até o próximo trecho (só quando os dois trechos são
                         contínuos no bruto: fim de um = início do outro; senão é corte seco)
Com zoom, a câmera é feita quadro a quadro: recorte 9:16 no rosto (rosto a ~32% da altura), movimento suave
(ease in-out) de um locutor para o outro e saída 1080x1920.
"""
import json, os, subprocess, sys

def sh(cmd):
    print('$', ' '.join(cmd), flush=True); subprocess.run(cmd, check=True)

def probe(v):
    r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height:stream_side_data=rotation:format=duration',
                        '-of', 'json', v], capture_output=True, text=True, check=True)
    j = json.loads(r.stdout); s = j['streams'][0]; w, h = int(s['width']), int(s['height'])
    rot = abs(int(float(next((d.get('rotation', 0) for d in s.get('side_data_list', []) if 'rotation' in d), 0))))
    if rot in (90, 270): w, h = h, w
    return w, h, float(j['format']['duration'])

def rostos(v, t, modelos):
    """centros x (0..1) e tamanhos dos rostos no instante t; [] sem detector."""
    task = os.path.join(modelos or '', 'face_landmarker.task')
    if not os.path.exists(task): return []
    try:
        import cv2, mediapipe as mp
        from mediapipe.tasks import python as mpt
        from mediapipe.tasks.python import vision
        cap = cv2.VideoCapture(v); cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000); ok, f = cap.read(); cap.release()
        if not ok: return []
        det = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(base_options=mpt.BaseOptions(model_asset_path=task), num_faces=3))
        r = det.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(f, cv2.COLOR_BGR2RGB)))
        out = []
        for lm in r.face_landmarks:
            xs = [p.x for p in lm]; out.append((sum(xs) / len(xs), max(xs) - min(xs)))
        return out
    except Exception as e:
        print('detector de rosto indisponível:', e, flush=True); return []

def posicao(enq, v, a, b, modelos):
    if isinstance(enq, (int, float)): return min(1.0, max(0.0, float(enq)))
    enq = (enq or 'auto').lower()
    fixo = {'esquerda': 0.25, 'centro': 0.5, 'direita': 0.75}
    if enq in fixo: return fixo[enq]
    fs = rostos(v, (a + b) / 2, modelos)
    if not fs: return 0.5
    return max(fs, key=lambda x: x[1])[0]                # maior rosto (quem está mais perto/no foco)

def main():
    args = sys.argv[1:]; modelos = None
    if '--modelos' in args: i = args.index('--modelos'); modelos = args[i + 1]; del args[i:i + 2]
    V, TJ, WD = args[:3]; os.makedirs(WD, exist_ok=True)
    j = json.load(open(TJ)); trechos = j['trechos'] if isinstance(j, dict) else j
    if not trechos: sys.exit('nenhum trecho')
    w, h, dur = probe(V); largo = w / h > 9 / 16 + 0.02
    cw = int(round(h * 9 / 16 / 2) * 2) if largo else w
    vf, af, mapa, t_out = [], [], [], 0.0
    for k, tr in enumerate(trechos):
        a, b = max(0.0, float(tr['inicio'])), min(dur, float(tr['fim']))
        if b - a < 0.3: continue
        crop = ''
        if largo:
            cx = posicao(tr.get('enquadramento', 'auto'), V, a, b, modelos)
            x = int(min(max(cx * w - cw / 2, 0), w - cw)); crop = f'crop={cw}:{h}:{x}:0,'
        n = len(mapa)
        vf.append(f'[0:v]trim=start={a:.3f}:end={b:.3f},setpts=PTS-STARTPTS,{crop}scale=1080:1920:flags=lanczos,setsar=1,fps=30[v{n}]')
        af.append(f'[0:a]atrim=start={a:.3f}:end={b:.3f},asetpts=PTS-STARTPTS,afade=t=in:d=0.03,afade=t=out:st={max(0, b - a - 0.04):.3f}:d=0.04[a{n}]')
        mapa.append({'take': k + 1, 'locutor': tr.get('locutor', ''), 'src_inicio': round(a, 3), 'src_fim': round(b, 3), 'inicio': round(t_out, 3), 'fim': round(t_out + b - a, 3),
                     'enquadramento': tr.get('enquadramento', 'auto')})
        t_out += b - a
    if any(float(t.get('zoom', 1) or 1) > 1.001 for t in trechos):
        camera(V, trechos, mapa, w, h, WD, af); return
    n = len(mapa); fc = ';'.join(vf + af) + ';' + ''.join(f'[v{i}][a{i}]' for i in range(n)) + f'concat=n={n}:v=1:a=1[v][a]'
    out = os.path.join(WD, 'podcast.mp4')
    sh(['ffmpeg', '-v', 'error', '-y', '-i', V, '-filter_complex', fc, '-map', '[v]', '-map', '[a]', '-c:v', 'libx264', '-preset', 'medium', '-crf', '17',
        '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', out])
    json.dump(mapa, open(os.path.join(WD, 'podcast_mapa.json'), 'w'), ensure_ascii=False, indent=1)
    print(f'podcast montado: {out} · {n} takes · {t_out:.1f} s · {"reenquadrado de " + str(w) + "x" + str(h) if largo else "já vertical"}')
    for m in mapa: print(f"  take {m['take']} {m['locutor'] or ''}: bruto {m['src_inicio']}–{m['src_fim']} → {m['inicio']}–{m['fim']}")

def camera(V, trechos, mapa, w, h, WD, af):
    """zoom em quem fala: recorte 9:16 por trecho e movimento suave entre trechos contínuos (quadro a quadro)."""
    import numpy as np, cv2
    bw = min(w, h * 9 / 16); bh = bw * 16 / 9; ok = [t for t in trechos if min(float(t['fim']), 1e9) - max(0.0, float(t['inicio'])) >= 0.3]
    def janela(tr):
        z = max(1.0, float(tr.get('zoom', 1) or 1)); ww, wh = bw / z, bh / z
        fo = tr.get('foco')
        if isinstance(fo, (list, tuple)) and len(fo) == 2: fx, fy = float(fo[0]), float(fo[1])
        else: fx, fy = posicao(tr.get('enquadramento', 'centro'), V, float(tr['inicio']), float(tr['fim']), None), 0.42
        x = min(max(fx * w - ww / 2, 0), w - ww); y = min(max(fy * h - 0.32 * wh, 0), h - wh)
        return np.array([x, y, ww, wh], float)
    W = [janela(t) for t in ok]
    cont = [abs(float(ok[k]['fim']) - float(ok[k + 1]['inicio'])) < 0.05 for k in range(len(ok) - 1)]
    ease = lambda u: 0.5 - 0.5 * np.cos(np.pi * min(max(u, 0), 1))
    def jan(k, t):                        # t = tempo no vídeo montado
        m = mapa[k]; d = float(ok[k].get('transicao', 0.7) or 0.7)
        if k + 1 < len(ok) and cont[k] and t > m['fim'] - d / 2: return W[k] + (W[k + 1] - W[k]) * ease((t - (m['fim'] - d / 2)) / d)
        dp = float(ok[k - 1].get('transicao', 0.7) or 0.7) if k else 0
        if k and cont[k - 1] and t < m['inicio'] + dp / 2: return W[k - 1] + (W[k] - W[k - 1]) * ease((t - (m['inicio'] - dp / 2)) / dp)
        return W[k]
    # áudio: mesmos cortes; micro fades só nos cortes secos
    afs = []
    for k, m in enumerate(mapa):
        a, b = m['src_inicio'], m['src_fim']; fi = '' if k and cont[k - 1] else ',afade=t=in:d=0.03'; fo = '' if k + 1 < len(mapa) and cont[k] else f',afade=t=out:st={max(0, b - a - 0.04):.3f}:d=0.04'
        afs.append(f'[0:a]atrim=start={a:.3f}:end={b:.3f},asetpts=PTS-STARTPTS{fi}{fo}[a{k}]')
    wav = os.path.join(WD, 'podcast_audio.wav')
    sh(['ffmpeg', '-v', 'error', '-y', '-i', V, '-filter_complex', ';'.join(afs) + ';' + ''.join(f'[a{k}]' for k in range(len(mapa))) + f'concat=n={len(mapa)}:v=0:a=1[a]',
        '-map', '[a]', '-ar', '48000', wav])
    out = os.path.join(WD, 'podcast.mp4')
    enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', '1080x1920', '-r', '30', '-i', '-', '-i', wav,
                            '-map', '0:v', '-map', '1:a', '-c:v', 'libx264', '-preset', 'medium', '-crf', '17', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k',
                            '-shortest', '-movflags', '+faststart', out], stdin=subprocess.PIPE)
    nf = 0
    for k, m in enumerate(mapa):
        a, b = m['src_inicio'], m['src_fim']
        dec = subprocess.Popen(['ffmpeg', '-v', 'error', '-ss', f'{a:.3f}', '-t', f'{b - a:.3f}', '-i', V, '-an', '-vf', 'fps=30', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-'], stdout=subprocess.PIPE)
        fsz = w * h * 3; total = int(round((m['fim']) * 30))
        while nf < total:
            buf = dec.stdout.read(fsz)
            if len(buf) < fsz: break
            f = np.frombuffer(buf, np.uint8).reshape(h, w, 3); x, y, ww, wh = jan(k, nf / 30)
            M = np.array([[1080 / ww, 0, -x * 1080 / ww], [0, 1920 / wh, -y * 1920 / wh]], np.float32)
            enc.stdin.write(cv2.warpAffine(f, M, (1080, 1920), flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_REPLICATE).tobytes()); nf += 1
        dec.stdout.close(); dec.wait()
    enc.stdin.close(); enc.wait()
    json.dump(mapa, open(os.path.join(WD, 'podcast_mapa.json'), 'w'), ensure_ascii=False, indent=1)
    print(f'podcast montado com zoom em quem fala: {out} · {len(mapa)} trechos · {nf / 30:.1f} s')
    for m in mapa: print(f"  take {m['take']} {m['locutor'] or ''}: bruto {m['src_inicio']}–{m['src_fim']} → {m['inicio']}–{m['fim']}")

if __name__ == '__main__': main()
