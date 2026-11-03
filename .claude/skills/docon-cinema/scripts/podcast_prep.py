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
    n = len(mapa); fc = ';'.join(vf + af) + ';' + ''.join(f'[v{i}][a{i}]' for i in range(n)) + f'concat=n={n}:v=1:a=1[v][a]'
    out = os.path.join(WD, 'podcast.mp4')
    sh(['ffmpeg', '-v', 'error', '-y', '-i', V, '-filter_complex', fc, '-map', '[v]', '-map', '[a]', '-c:v', 'libx264', '-preset', 'medium', '-crf', '17',
        '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', out])
    json.dump(mapa, open(os.path.join(WD, 'podcast_mapa.json'), 'w'), ensure_ascii=False, indent=1)
    print(f'podcast montado: {out} · {n} takes · {t_out:.1f} s · {"reenquadrado de " + str(w) + "x" + str(h) if largo else "já vertical"}')
    for m in mapa: print(f"  take {m['take']} {m['locutor'] or ''}: bruto {m['src_inicio']}–{m['src_fim']} → {m['inicio']}–{m['fim']}")

if __name__ == '__main__': main()
