# DocOn Studio · site próprio. O render pesado roda no agente na nuvem; este contêiner só serve o Studio.
FROM node:22-slim
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-numpy python3-scipy python3-soundfile python3-opencv python3-pil python3-pip ffmpeg rubberband-cli curl && rm -rf /var/lib/apt/lists/*
# voz da DocOn (gratuita, roda aqui): Kokoro pt-BR
RUN pip install --break-system-packages -q kokoro-onnx && mkdir -p /root/.docon/models/kokoro && cd /root/.docon/models/kokoro && \
    curl -sSLO https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx && \
    curl -sSLO https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin
WORKDIR /app
COPY studio ./studio
COPY .claude/skills/docon-cinema/scripts ./.claude/skills/docon-cinema/scripts
COPY web ./web
WORKDIR /app/web
RUN npm ci --omit=dev
ENV DOCON_DATA=/data PORT=8080
EXPOSE 8080
CMD ["sh", "-c", "node materiais.mjs && node server.mjs"]
