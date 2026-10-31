"""DocOn Cinema · transcrição com tempo por palavra (Parakeet TDT 0.6B v3 via sherpa-onnx, multilíngue, PT-BR ok).
Gera WORKDIR/a16.wav e WORKDIR/words_raw.json = [[palavra, inicio_s], ...].
uso: python3 transcribe.py VIDEO WORKDIR [MODELDIR]"""
import sys, os, json, subprocess
import sherpa_onnx, soundfile as sf
V, WD = sys.argv[1], sys.argv[2]; MD = sys.argv[3] if len(sys.argv) > 3 else os.path.expanduser('~/.docon/models/parakeet')
os.makedirs(WD, exist_ok=True)
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', V, '-ac', '1', '-ar', '16000', WD + '/a16.wav'], check=True)
r = sherpa_onnx.OfflineRecognizer.from_transducer(encoder=MD + '/encoder.int8.onnx', decoder=MD + '/decoder.int8.onnx', joiner=MD + '/joiner.int8.onnx',
                                                 tokens=MD + '/tokens.txt', model_type='nemo_transducer', num_threads=4)
a, sr = sf.read(WD + '/a16.wav', dtype='float32'); s = r.create_stream(); s.accept_waveform(sr, a); r.decode_stream(s)
words = []
for t, ts in zip(s.result.tokens, s.result.timestamps):
    if t.startswith(' ') or not words: words.append([t.strip(), round(float(ts), 3)])
    else: words[-1][0] += t
json.dump(words, open(WD + '/words_raw.json', 'w'), ensure_ascii=False)
print(s.result.text); print('\n' + ' '.join(f'{w}@{t:.2f}' for w, t in words))
