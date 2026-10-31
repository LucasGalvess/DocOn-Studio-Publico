"""DocOn Studio · ditado: transcreve um áudio curto (fala da equipe) com o mesmo modelo da skill (Parakeet via sherpa-onnx).
Usado pelo botão "Ditar" do site quando o navegador não tem reconhecimento de voz próprio.
uso: python3 ditado.py AUDIO [MODELDIR]   → imprime o texto"""
import sys, os, subprocess, tempfile
import sherpa_onnx, soundfile as sf
A = sys.argv[1]; MD = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.environ.get('DOCON_MODELOS', os.path.expanduser('~/.docon/models')), 'parakeet')
with tempfile.TemporaryDirectory() as td:
    w = os.path.join(td, 'a16.wav')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', A, '-ac', '1', '-ar', '16000', w], check=True)
    r = sherpa_onnx.OfflineRecognizer.from_transducer(encoder=MD + '/encoder.int8.onnx', decoder=MD + '/decoder.int8.onnx', joiner=MD + '/joiner.int8.onnx',
                                                     tokens=MD + '/tokens.txt', model_type='nemo_transducer', num_threads=4)
    a, sr = sf.read(w, dtype='float32'); s = r.create_stream(); s.accept_waveform(sr, a); r.decode_stream(s)
    print(s.result.text.strip())
