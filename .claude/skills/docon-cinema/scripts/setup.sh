#!/usr/bin/env bash
# DocOn Cinema · instala dependências e baixa modelos/fontes em ~/.docon (uma vez por máquina/sessão).
set -e
SCR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
D=~/.docon; mkdir -p $D/models $D/fonts
pip install -q opencv-contrib-python-headless onnxruntime pillow numpy scipy soundfile sherpa-onnx mediapipe fonttools brotli kokoro-onnx 2>&1 | tail -1 || true
command -v ffmpeg >/dev/null || (apt-get update -qq && apt-get install -y -qq ffmpeg)
ldconfig -p | grep -q libEGL.so.1 || apt-get install -y -qq libegl1 libgles2 >/dev/null 2>&1 || true   # mediapipe
cd $D/models
[ -f rvm.onnx ] || curl -sSL -o rvm.onnx https://github.com/PeterL1n/RobustVideoMatting/releases/download/v1.0.0/rvm_mobilenetv3_fp32.onnx
[ -f face_landmarker.task ] || curl -sSL -o face_landmarker.task https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task
# voz da DocOn (Kokoro 82M, Apache 2.0): scripts/voz.py
mkdir -p kokoro
for f in kokoro-v1.0.onnx voices-v1.0.bin; do [ -f kokoro/$f ] || curl -sSL -o kokoro/$f https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/$f; done
if [ ! -d parakeet ]; then
  curl -sSL -o p.tar.bz2 https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8.tar.bz2
  tar xjf p.tar.bz2 && mv sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8 parakeet && rm p.tar.bz2
fi
cd $D/fonts
if [ ! -f InterDisplay-Bold.ttf ]; then
  curl -sSL -o inter.zip https://github.com/rsms/inter/releases/download/v4.1/Inter-4.1.zip && unzip -q -o inter.zip -d inter
  cp inter/extras/ttf/InterDisplay-{Regular,Medium,SemiBold,Bold,ExtraBold,Black}.ttf . && rm -rf inter inter.zip
fi
if [ ! -f Montserrat-800.ttf ]; then
  U=$(curl -s https://registry.npmjs.org/@fontsource/montserrat/latest | python3 -c "import json,sys;print(json.load(sys.stdin)['dist']['tarball'])")
  curl -sSL -o fsm.tgz $U && mkdir -p fsm && tar xzf fsm.tgz -C fsm
  for w in 600 700 800 900; do python3 -c "from fontTools.ttLib import TTFont; f=TTFont('fsm/package/files/montserrat-latin-$w-normal.woff2'); f.flavor=None; f.save('Montserrat-$w.ttf')"; done
  rm -rf fsm fsm.tgz
fi
# os scripts procuram as fontes em scripts/fonts → link
[ -e "$SCR/fonts" ] || ln -s $D/fonts "$SCR/fonts"
# motion graphics: Hyperframes (HTML + GSAP, Apache 2.0) e Remotion (React; DocOn na licença gratuita: 1 funcionário, limite 3). DOCON_REMOTION=0 pula o Remotion
M=$HOME/.docon/motion; mkdir -p $M
[ -f $M/package.json ] || echo '{"name":"docon-motion","private":true}' > $M/package.json
if [ ! -x $M/node_modules/.bin/hyperframes ] && command -v npm >/dev/null; then
  (cd $M && npm i --no-audit --no-fund hyperframes@0.9.17 gsap@3.15.0 >/dev/null 2>&1) || echo "aviso: não instalei o hyperframes (sem npm/rede)"
fi
if [ "${DOCON_REMOTION:-1}" = "1" ] && [ ! -x $M/node_modules/.bin/remotion ]; then
  (cd $M && npm i --no-audit --no-fund remotion@4.0.541 @remotion/cli@4.0.541 react@18.3.1 react-dom@18.3.1 >/dev/null 2>&1) || echo "aviso: não instalei o remotion"
fi
echo "DocOn Cinema pronto: modelos em $D/models, fontes em $D/fonts"
