# Padrão DocOn Cinema — especificação de referência

Reels vertical (1080×1920) de profissional de saúde. Esta é a especificação original do formato,
já com os ajustes aprovados pelos clientes (marcados **[revisado]**).

## 0. Ficha do vídeo
- Profissional: nome completo · Especialidade / subtítulo · Tema · CTA final
- Paleta padrão (medicina humana / estética): dourado rosê #B76E79, marfim #F8F3EA, vidro espresso cor de pele.
- Se algum campo faltar: deduza do material (pasta do projeto, fala, crachá, jaleco) e **avise na entrega** o que foi deduzido.

## 1. Transcrição e cortes
- Transcrição com tempo por palavra (Parakeet TDT v3 via sherpa-onnx). Corrigir termos técnicos e nomes (ex.: "Buddercol" → "Border Collie", "aviamos" → "avaliamos").
- Cortar respiros/pausas > 0,35 s sem cortar palavras; remover tropeços e repetições.
- Fala a 1,08x (áudio com rubberband, preservando formantes); na imagem, mistura ponderada "seca" dos dois quadros vizinhos **[revisado: mistura com curva íngreme, sem fantasma]**.
- Duração-alvo 60–90 s (se o bruto for curto, entregar o que ele permite e avisar).

## 2. Imagem (antes dos gráficos)
1. Estabilização: matte RVM (rvm_mobilenetv3_fp32.onnx) para rastrear só o fundo (goodFeaturesToTrack + LK + estimateAffinePartial2D/RANSAC), outliers |dx|,|dy| ≤ 30 px, rotação ≤ 0,01 rad; gaussiano σ≈75 (travado) / σ≈14 (caminhada), reiniciado a cada plano, margem de zoom 1,07.
2. Cor: balanço de branco por plano medido em pixels neutros do fundo, protegendo a pele.
3. **[revisado] Look natural**: contraste suave (curva 0,92 em torno do meio), preto levantado ~1,5%, ombro nas altas, cores vivas (saturação +24%, pele +10%). **Sem pro-mist, sem grão, vinheta ≤ 5%.** O look "claro e suave" original (gamma 0,75 + pro-mist) foi reprovado por lavar a imagem.
4. **[revisado] Sem desfoque de fundo por padrão** (`--dof` só se o cliente pedir).
5. Pele: guided filter só no rosto a 35% (não 60%) + clareamento sutil dos dentes (landmarks MediaPipe). Só em vídeo de rosto falando (`--skin`).
6. **[revisado] Qualidade**: uma única reamostragem Lanczos (estabilização + câmera juntas), intermediário sem perdas (FFV1), nitidez leve pós-zoom (unsharp 0,45, σ 1,1), um único encode final.

## 3. Câmera
- Nada de zoom em tranco no meio da fala. Dolly lento nas viradas de assunto (1,00 → 1,05 em ~1,9 s, easing) **[revisado: era 1,10]** + aproximação contínua ~1,2% por trecho.
- Trocas secas de enquadramento (1,00 ↔ 1,04) só nas emendas de corte dentro do mesmo plano, para disfarçar o jump cut.
- Âncora do zoom no rosto (talking head) ou no centro-alto do quadro (vlog/B-roll).

## 4. Gancho (3–5 s)
- Primeira frase em tipografia animada grande (Montserrat 800/900) no centro-baixo, palavra por palavra, no tempo da fala.
- Palavra-chave enorme em degradê da paleta, pop elástico, ícone desenhado. Sem legenda nesse trecho. Light leak leve na abertura.

## 5. Painéis de vidro (o coração do formato)
- Vidro fosco: desfoque real do quadro, tinta da paleta a ~60%, borda fina, sombra suave, raio 34, em y ≈ 930–1470 (nunca no rosto).
- Conteúdo no tempo das palavras: kicker em pílula, título Inter Display, ícones/diagramas vetoriais (linha do tempo, ficha, checklist, "X ou Y", calendário…).
- Entrada ease-out com subida de 30 px; saída fade 0,3 s; conteúdo aparece junto com o vidro (nunca > 0,5 s vazio).
- Lower third no momento da apresentação. Cartão final com CTA, nome em destaque e botão.
- Glifos que as fontes não têm (✓ → ∞ ≠): desenhar como forma.

## 6. B-roll (Pexels)
- 4–7 momentos, vídeos verticais ("Portrait"), pessoas de frente, luz clara e quente, sem marcas. Nunca no gancho nem sobre a apresentação do nome.
- Alternar: corte em tela cheia 1,5–3 s / faixa inferior com degradê. Mesmo look do vídeo, zoom lento 1,00→1,05, transição de 6–8 quadros, áudio mudo. Vidro e B-roll nunca juntos.
- Sem acesso ao Pexels: listar termos de busca + minutagem e pedir os arquivos.
- Em vlog/bastidores o próprio material já é B-roll: não precisa de Pexels.

## 7. Legenda
- Estilo "docon": Inter Display Bold 54 px, y ≈ 1585, linhas ≤ 26 caracteres, quebra em vírgulas/pausas, nunca terminar em preposição; palavra surge com fade + subida 10 px, pop de 16% na ativa; palavras-chave 60 px na cor de destaque com sublinhado animado; sombra difusa, sem caixa.
- Estilo "sutil" (quando o cliente pedir legenda discreta): SemiBold 44, sem pop, sem sublinhado, chave só na cor.

## 8. Áudio
- **[revisado] Voz com tratamento leve**: highpass 80 Hz, −1,5 dB em 250 Hz, +1,5 dB em 3,3 kHz, de-esser leve, **sem compressor extra** e **loudnorm linear em duas passadas** (−16 LUFS / −1,5 dBTP). Brutos de celular/Premiere muitas vezes já chegam limitados; comprimir de novo deixa "estourado".
- Se o cliente mandar o áudio tratado: alinhar por correlação de envelope (medir defasagem por janela, conferir que não há deriva) e usar sem processar.
- Efeitos discretos: whoosh na entrada de painel/B-roll, tick nos destaques, a −19 dB da voz.
- Trilha: só se pedirem. `music.py` gera uma trilha original (sem direitos) com ducking automático sob a voz; se o cliente tiver trilha licenciada, use-a no lugar.

## 9. Entrega
- H.264 High, 1080×1920, 30 fps, CRF 17, AAC 192k, faststart, +1,3 s de respiro com o cartão final.
- Folha de contato (1 quadro a cada 5 s) e conferência: cor natural, sem tremor, painéis legíveis, legenda sincronizada, B-roll coerente.
- Download pelo claude.ai: página (Artifact) com capability `downloads`; arquivos publicados ≤ 15 MB → versão HEVC 2 passadas (~3 Mbps) **[revisado: H.264 a 3 Mbps perdeu qualidade visível]**. Master H.264 fica na pasta de entrega.
- Resposta em 3–5 linhas + lista do que foi deduzido + B-rolls usados (termo, link, minutagem).
