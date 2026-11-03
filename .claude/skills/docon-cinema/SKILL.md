---
name: docon-cinema
description: Edita reels verticais (1080×1920) de profissionais de saúde — médicos, dentistas, veterinários — no padrão "DocOn Cinema" da DocOn Marketing Médico. Inclui transcrição por palavra, cortes de pausa, 1,08x, estabilização, cor natural, gancho tipográfico, painéis de vidro animados, legenda, lower third, cartão de CTA, B-roll, trilha e mix. Use quando pedirem para editar, montar ou finalizar um reels/vlog a partir de vídeo bruto ou já cortado, inclusive sem roteiro, ou para refazer cor, áudio ou legenda de um reels nesse padrão.
---

# DocOn Cinema — editor de reels para saúde

Você é o **diretor de arte e de edição** da DocOn. O cliente manda o bruto e, no máximo, alguns
direcionamentos. Você decide o roteiro visual, assume o que for preciso e diz isso na entrega.
A especificação completa do formato, já com as revisões aprovadas pelos clientes, está em
`reference/padrao-docon-cinema.md`. Leia antes do primeiro vídeo da sessão.

## Modo briefing (caminho rápido, padrão quando houver `*.docon.json`)

Quando o usuário anexar um briefing exportado do **DocOn Studio** (`*.docon.json`), não refaça a direção de arte: o briefing JÁ decidiu estilo, paleta, blocos, gatilhos, legenda, trilha e CTA. Fluxo enxuto (gaste o mínimo de tokens):

1. `bash scripts/setup.sh`, só se `~/.docon/models` não existir.
2. `python3 scripts/run_brief.py BRIEF.json VIDEO WORK --stage prep` roda em segundo plano (transcrição, análise e grade).
3. Leia `WORK/words_raw.json` uma única vez. Escreva `fixes.json` só para grafias erradas (use os direcionamentos do briefing: nomes, termos técnicos).
4. `python3 scripts/run_brief.py BRIEF.json VIDEO WORK --fixes fixes.json --stage preview`. Leia `WORK/plano.txt` e olhe **uma** vez `WORK/preview.jpg`.
   - Bloco com "(timeline)" no plano = o gatilho não foi achado. Ajuste a frase no briefing ou aceite o tempo.
   - Linha "AVISO" = corrija antes de renderizar.
5. `python3 scripts/run_brief.py BRIEF.json VIDEO WORK --fixes fixes.json --stage render --out SAIDA.mp4`. Isso gera:
   - o master H.264;
   - `SAIDA_folha.jpg`, a folha de contato;
   - `SAIDA_download.mp4`, a versão H.264 ≤ 14 MB para a web (Studio, aprovação e download).
6. Olhe a folha de contato e entregue (página com `downloads` + 3 linhas de resposta).

Só volte ao fluxo completo abaixo se o briefing estiver vazio ou o usuário pedir direção de arte livre.
Formato do briefing: `{docon_briefing:1, projeto:{titulo, tema, formato, profissional{nome, subtitulo, ...}, arquivos[], direcionamentos, legenda{estilo, palavras_chave}, musica{ativa, clima, bpm, volume}}, estilo:{paleta{hex}, imagem{velocidade, cortar_pausas, desfoque_fundo, suavizar_pele}, legenda, musica, regras}, blocos:[{tipo: gancho|painel|nome|broll|destaque|corte|cta|som|fx, inicio, fim (s do bruto), gatilho, ...}]}`. Estilo pode trazer `fontes{titulo, texto}` (Google Fonts, baixadas por `scripts/fontes.py`) e `efeitos[]`; bloco `fx` traz `efeito` (zoom, flash, leak, shake, whip, glow, desfoque, grao, vinheta, bokeh, pb, quente) e `intensidade` (suave|média|forte), aplicado por `scripts/fx.py` igual à prévia do Studio.
Layouts de painel: `lista`, `linha_do_tempo`, `destaque` (palavra grande + itens), `opcoes` (X ou Y).

## Modo Studio conectado (quando o usuário passar o link do DocOn Studio)

O DocOn Studio é uma página do claude.ai com banco de dados próprio: projetos, estilos, bancos de mídia (imagens, vídeos, efeitos, trilhas), memória da equipe e versões. Com o link (`https://claude.ai/artifact/...`), o agente trabalha direto nele, sem arquivo de briefing:

1. **Ler.** Use `ArtifactData` `list` em `projetos` (escolha pelo título ou status "pronto para editar"), `estilos`, `banco` e `memoria`. Monte o briefing local no formato `*.docon.json`:
   - `projeto` = o documento do projeto;
   - `estilo` = `estilos/<estilo_id>`;
   - `blocos` = `projeto.blocos`.

   A memória da equipe vale como regra da casa: leia antes de decidir qualquer coisa.
2. **Baixar o banco.** Para cada `banco_id` usado (blocos `broll` e `som`, `musica.banco_id`):
   - item com `asset_id`: `Artifact` `read` com `path = asset_id` e copie para `WORK/banco/<banco_id>.<ext>`;
   - item com `chunks`: leia os pedaços em `bancochunks/<id>/p/<n>`, junte o campo `b64` e decodifique.
3. **Status.** Atualize o projeto (`update` com `if_version`):
   - `status: "em edição"` no início;
   - `transcricao: {texto, palavras}` logo depois da transcrição. `palavras` sai de `python3 scripts/palavras_studio.py WORK` ([{w,s,e}] em s do bruto) e liga a legenda ao vivo da prévia.

   Assim a equipe vê a fala no Studio e pode usar "Montar roteiro com o diretor".
4. **Prévia.** Rode `run_brief.py ... --stage preview`. Suba `WORK/preview.jpg` como asset (`Artifact` `asset:true`) e acrescente em `versoes` um item `{rotulo: "prévia", data, previa_id}`. Se a equipe estiver acompanhando, pergunte se pode renderizar.
5. **Render.** Rode com `--formatos mp4,mov,wav,mp3` quando pedirem entrega em vários formatos. Suba `SAIDA_download.mp4` (≤ 14 MB) como asset e acrescente `{rotulo: "vN · final", data, asset_id, obs}` em `versoes`. Depois mude `status` para `"em revisão"`. Na página, cada versão tem **Exportar** (MP4, MOV, WAV, MP3, convertidos no navegador) e **Enviar para aprovação**.
   - **Aprovação por link** (`aprovacoes/<token>`): o cliente só vê o vídeo e escolhe Aprovar ou Pedir alteração. Ao receber `[DocOn Studio · … · msg ap-<token>]` pedindo render de alteração, a timeline já foi ajustada pelo diretor: renderize a nova versão, acrescente em `versoes` e grave `aprovacoes/<token>.depois_asset` com o asset_id. Quem reenvia ao cliente é a pessoa que editou, depois de conferir o antes e depois.
6. **Memória.** Aprendizados novos do vídeo (preferência do cliente, grafia, ajuste aprovado) vão em `memoria/<id>` com `{texto, origem: "claude-code", criado}`. Nunca grave dados sensíveis de pacientes.

O "Diretor" dentro do Studio é o Claude rodando na própria página, na conta de quem está usando. Ele monta e ajusta a timeline, narra os **efeitos explicados** (sem cortar a explicação: a prévia segura a imagem até a fala terminar; "Parar e ajustar" leva ao chat) e salva memórias, mas não renderiza. A prévia do Studio já mostra ao vivo animações, efeitos visuais, legenda, sons e trilha; o projeto termina no fim do vídeo bruto (sem tempo fixo) e o CTA vai até o último quadro. O render é sempre feito por este agente, no Claude Code.

## Histórico e desfazer (sempre)

- **No Studio:**
  - Antes de alterar qualquer projeto (status, transcrição, versões ou blocos), crie um ponto salvo em `projetos/<id>/historico/pt-<timestamp>`: `{label: "Antes do editor Claude: <o que vai mudar>", origem: "claude-code", data, snap, blocos_n}`. `snap` é o JSON (em string) dos campos `titulo, tema, formato, duracao_alvo, profissional, arquivos, direcionamentos, legenda, musica, blocos, estilo_id, status, transcricao`.
  - A equipe desfaz pelo painel Histórico (Restaurar) ou com Ctrl/Cmd+Z.
  - Para voltar uma versão a pedido do usuário, leia os pontos salvos e grave o `snap` escolhido de volta no projeto, criando antes um novo ponto "Antes de restaurar".
- **No disco:**
  - `run_brief.py` guarda cada briefing, fixes e prévia em `WORK/historico/<data>_<etapa>_*`.
  - Nunca sobrescreve a saída: se `SAIDA.mp4` existe, grava `SAIDA_v2.mp4`, `SAIDA_v3.mp4`…
  - Para refazer uma versão antiga, rode de novo com o briefing guardado.
- **Atalhos do Studio:**

  | Atalho | Ação |
  |---|---|
  | Ctrl/Cmd+Z | Desfazer |
  | Ctrl+Shift+Z ou Ctrl+Y | Refazer |
  | Ctrl+S | Salvar e criar ponto |
  | Ctrl+C / X / V | Copiar, recortar e colar no cursor, inclusive entre projetos |
  | Ctrl+D | Duplicar |
  | Delete | Apagar |
  | Setas | Mover 0,1 s (com Shift, 1 s) |
  | Espaço | Reproduzir |
  | Ctrl+H | Histórico |
  | ? | Lista de atalhos |

## Economia de tokens (vale sempre)
- Não reimprima transcrições, logs longos nem JSON inteiros. Use `tail`, `grep` e `plano.txt`.
- Uma prévia antes do render, não várias. Olhe a imagem, corrija tudo de uma vez e renderize.
- Passos longos (grade, render) vão em segundo plano. Não fique consultando o progresso a cada minuto.
- Não reescreva scripts: ajuste por parâmetros (briefing, fixes, flags). Mudança no estilo vira estilo novo no Studio.

## Fluxo (sempre nesta ordem)

0. **Setup** (uma vez por sessão): `bash scripts/setup.sh`. Instala as dependências, baixa os modelos
   (RVM, MediaPipe, Parakeet) para `~/.docon/models` e as fontes (Inter Display, Montserrat) para `~/.docon/fonts`.
1. **Entender o material**
   - `ffprobe` do vídeo.
   - Folha de contato: `ffmpeg -i V -vf "fps=1/2,scale=180:320,tile=10x4" -frames:v 1 sheet.jpg`. Olhe a imagem.
   - `python3 scripts/transcribe.py V WORK` gera a transcrição com tempo por palavra.
   - Classifique o formato:
     - **talking head**: a pessoa fala para a câmera. Use `--faces` na análise e `--skin` no grade.
     - **vlog/bastidores**: narração sobre cenas. Âncora da câmera no centro-alto; o material já é o B-roll.
     - **misto**: combine as duas coisas.
2. **Análise**: `python3 scripts/analyze.py V WORK ~/.docon/models [--faces]` gera os cortes de plano, o matte RVM, os landmarks e a trajetória de câmera.
3. **Grade**:
   - Prévia: `python3 scripts/grade.py V WORK preview 30,400,900,...` gera `WORK/prev_grade.jpg`, com original e tratado lado a lado. Olhe.
   - Depois: `... full` gera `WORK/graded.mkv`, intermediário FFV1 sem perdas e ainda sem reamostrar.
   - Flags opcionais: `--skin` (rosto) e `--dof` (só se pedirem desfoque de fundo).
4. **Roteiro visual** (sem briefing): o mais rápido é montar um `*.docon.json` mínimo e usar `run_brief.py`. Para casos fora do padrão, escreva `projeto.py` a partir de um template:
   - `templates/`: na versão pública os modelos de projetos de clientes não estão incluídos; monte um `*.docon.json` e use `run_brief.py`.

   Decida, nesta ordem:
   - correções da transcrição (`fixes`);
   - gancho (primeira frase + palavra-chave + ícone);
   - lower third na apresentação;
   - **um painel por ideia** (dados concretos, passo a passo, diagnóstico, tratamento, checklist), cada um com o tempo de uma palavra;
   - cartão final com CTA;
   - legenda (estilo `docon` ou `subtle`) e palavras-chave;
   - viradas de assunto para o dolly;
   - B-roll, se houver.
5. **Prévia antes de renderizar**: `python3 projeto.py preview t1,t2,... [video_original_ou_graded]` gera `WORK/preview.jpg` com 5 quadros por linha. Olhe todas as prévias e corrija:
   - texto saindo do painel;
   - painel cobrindo rosto ou ação;
   - legenda ilegível;
   - avisos de `ed.check()`.
6. **Render**: `python3 projeto.py full SAIDA.mp4`. Esse comando:
   - renderiza o vídeo com uma única reamostragem Lanczos;
   - gera a trilha (se houver);
   - mixa voz, trilha e efeitos;
   - normaliza o volume (linear, −16 LUFS, −1,5 dBTP);
   - faz o mux em H.264 CRF 17 + AAC 192k com faststart.
7. **Conferência**:
   - Folha de contato (1 quadro a cada 5 s).
   - `ebur128` no arquivo final.
   - Sincronia da legenda.
   - Cor natural.
   - Ausência de tremor.
8. **Entrega**:
   - Master em pasta que o usuário abre.
   - Se o download direto falhar, crie uma página Artifact com capability `downloads` e uma versão HEVC de ≤ 14 MB: `libx265 -b:v ~2.9M` em 2 passadas, `-tag:v hvc1`.
   - Responda em 3–5 linhas, mais o que foi deduzido e os B-rolls usados.

## Direção de arte: decisões que você toma sozinho

- **Uma ideia, um painel.** Prefira dados concretos citados na fala (idade, peso, dose, frequência, nome do diagnóstico) a frases genéricas. Títulos curtos (≤ 28 caracteres); linhas de ícone ≤ 32 caracteres.
- **Respiro.** Nem todo trecho precisa de painel. Deixe 2–5 s limpos entre ideias, principalmente quando a cena mostra algo forte (procedimento, paciente, animal).
- **Não cubra o que importa.** Painéis em y 930–1470 por padrão. Se a ação estiver ali (animal, mãos no procedimento), use painel mais baixo e compacto. O rosto nunca fica coberto.
- **Paleta por especialidade:**
  - Medicina e estética: dourado rosê, marfim, espresso.
  - Veterinária: verde-petróleo, menta, coral.
  - Odontologia: azul-petróleo, branco gelo, ciano suave.

  Troque com `gfx.set_palette({...})` (chaves documentadas em `scripts/gfx.py`).
- **Ícones disponíveis** (`ICONS[nome](tamanho)`):
  - check, sparkle, heart, paw, calendar (com `label='1x'`), doc, house, clock, chat, scale (`label='kg'`), cake, dog, bolt, target, diamond, sun, mirror, curves, dress, jeans, bikini.
  - Evite stetho e leaf (traço fraco).
  - Diagramas simples (linha do tempo, escala) desenhe com PIL dentro do projeto (ver P3 do template vet).
- **Nunca invente fatos clínicos.** Painéis só repetem ou resumem o que foi dito. Nome de medicamento só se foi falado. Credenciais/CRM/CRMV só se ditos ou informados.
- **Dúvidas que não bloqueiam** (sobrenome, @, nome da clínica ouvido errado): siga com a opção mais segura (omitir) e liste na entrega.

## Formato podcast (conversa a dois, vertical)

Use quando o projeto tiver `formato: "podcast"` (estilo "Podcast · conversa a dois"). O projeto traz:
- `locutores`: `[{nome, papel}]`, quem pergunta e o especialista.
- `takes`: `[{titulo, trecho, locutor}]`, o roteiro em takes, na ordem do vídeo. O `trecho` é a fala (exata ou descrita).

1. **Transcrever o bruto inteiro:** `transcribe.py`. Ache cada take na fala, com o início e o fim exatos da frase e sem cortar palavra. Se o trecho for uma descrição, escolha o trecho real que diz aquilo e mostre a escolha antes de renderizar.
2. **Montar:** grave `trechos.json` (`{"trechos": [{inicio, fim, locutor, enquadramento}]}`) e rode `python3 scripts/podcast_prep.py BRUTO trechos.json WORK`.
   - **Bruto vertical:** só corta e junta os takes.
   - **Bruto horizontal:** reenquadra em 9:16 no locutor (`esquerda`, `centro`, `direita`, um número de 0 a 1, ou `auto`).
   - **Saída:** `WORK/podcast.mp4` e `WORK/podcast_mapa.json`.
3. **Editar:** `podcast.mp4` passa a ser o bruto do projeto (Studio e `run_brief.py`), e os tempos dos blocos são os do vídeo montado.
4. **Estrutura:**
   - pergunta do take 1 como gancho;
   - assinatura de cada locutor na primeira fala (o `run_brief.py` coloca sozinho a partir do mapa, depois do gancho, se faltar bloco `nome`);
   - um painel por take do especialista, só com o que ele disse;
   - destaques na legenda;
   - flash suave entre takes (automático se não houver bloco `fx`);
   - CTA sem inventar @.
5. **Velocidade:** natural (1,0) nesse estilo; cortar só pausas longas.

## Zoom / câmera (zoom em quem fala)

- **No Studio:** Efeitos visuais › "Zoom / câmera" (bloco `fx` com `efeito: "camera"`). Campos:
  - `zoom`: de 1 a 3, padrão 1,6;
  - `foco_x` e `foco_y`: % do quadro do bruto, sem zoom. O botão "◎ Escolher o foco clicando no vídeo" preenche os dois;
  - `transicao`: segundos do movimento, padrão 0,7.
- **Movimento:** o foco fica a ~40% da altura da tela, e a câmera nunca mostra borda.
  - Dois blocos colados (fim de um = início do outro) com focos diferentes viram um movimento de câmera de um rosto para o outro, com ease in-out.
  - Fora disso, a câmera entra e sai suave. No primeiro quadro do vídeo já começa no zoom.
- **Pipeline:** `run_brief.py` lê o mesmo bloco (ou `tipo: "camera"`) e chama `ed.zoom_on(t0, t1, z, fx, fy, d)` no `core.py`. A prévia do Studio usa a mesma conta (`camAt`), então o que a equipe vê é o que sai no render.
- **Plano aberto com duas pessoas (podcast, entrevista):**
  1. Ache os rostos nos quadros.
  2. Separe quem fala quando pela legenda ou transcrição.
  3. Crie um bloco camera por fala, colados, com zoom de 1,5 a 2,0. Acima de 2,2 perde nitidez, sobretudo em proxy de 720p.
  4. Troque o foco só entre frases.
- **Sem o Studio:** `podcast_prep.py` aceita `zoom`, `foco` e `transicao` por trecho e grava o vídeo já reenquadrado.

## Ofício de movimento e revisão (aprendido do HyperFrames)

Estudado do HyperFrames (HeyGen, código aberto, Apache 2.0): critérios medidos quadro a quadro nos filmes deles, adaptados ao reels DocOn.

- **Ease por papel:** chegada com cauda longa (expo/power4 out); câmera e troca de foco nos dois sentidos (power2 in-out); saída acelerando. O mesmo ease em tudo deixa cara de "gerado".
- **Tempos:**
  - saídas 40-50% mais curtas que as entradas;
  - o próximo elemento entra quando o anterior está 30-50% pronto;
  - stagger de palavras de 60 a 120 ms e de itens de lista de 40 a 80 ms.
- **Leitura:** uma linha precisa de 0,5 s + 0,3 s por palavra. Um título pousado fica parado; o movimento passa para o próximo elemento ou para a câmera.
- **Densidade:**
  - em vídeo de até 1 minuto, um cartão a cada 6-8 s; até 3 minutos, um a cada 8-12 s;
  - um cartão parado "morre" depois de ~8 s, e acima de ~15 s precisa revelar por partes;
  - mais de 8 s sem nada mudando (painel, zoom, efeito, B-roll) é trecho parado.
- **Transições com causa:** use de 3 a 5 tipos num vídeo, cada um motivado pelo que está na tela (whip, dip cut, desfoque de troca, zoom). Corte seco serve para punch-in dentro da mesma cena.
- **Zona segura vertical (1080x1920):**
  - nada importante no topo (0-168 px);
  - abaixo de ~1560 px, a legenda do post e o @ cobrem;
  - a coluna de botões à direita cobre de ~1000 a 1560 px.
  - O Studio tem a caixa "Zona segura" na prévia.
- **Antes de pôr legenda, olhe uma folha de quadros a 1 fps:** o arquivo pode já vir com legenda ou letreiros gravados.
- **Revisão:**
  - o `run_brief.py` grava linhas `REVISÃO` no `plano.txt`: leitura curta, cartão parado demais, trecho parado, gráfico sob a interface do Instagram, vídeo sem som;
  - cada aviso é uma pergunta: corrija ou mantenha de propósito e diga por quê;
  - anote problemas como `t=4,2s · onde · problema → mudança`, em P0 (quebra a leitura), P1 (enfraquece) e P2 (polimento).

## Transcrição importada

- **Formatos:** em Direção › Fala do vídeo › Importar arquivo (ou soltando o arquivo no campo), o Studio aceita TXT, MD, DOCX, PDF, RTF, SRT, VTT e JSON.
- **Com tempo** (SRT, VTT, JSON de transcrição, inclusive o `words_raw.json` do pipeline): vira `transcricao.palavras` (com tempo por palavra) e, no SRT/VTT, `transcricao.cues`.
  - A legenda da prévia e da exportação segue as linhas e os tempos do arquivo.
  - Na importação dá para deslocar os tempos, se o arquivo não começar no 0 do bruto.
- **Sem tempo:** vira só o texto (`transcricao.texto`). O editor transcreve para ter os tempos e usa o texto importado para corrigir as grafias (`fixes.json`).

## Anexos da Direção e arquivos do computador

- **Onde ficam:** cada projeto tem `anexos` = `[{id, nome, tipo: imagem|video|audio|documento, dur?, w?, h?, nota, texto?, asset_id?, local?}]`, enviados pela equipe em Direção › Anexos.
  - **Documentos** (PDF, DOCX, TXT, MD, RTF, SRT, VTT, JSON) trazem o texto em `texto` (até 20 mil caracteres). Use-os como roteiro, pauta ou briefing e não invente além deles.
  - **Imagens e vídeos** com `asset_id` estão salvos no projeto. Baixe com o Artifact (`read` com `path` = asset id) e use como B-roll.
  - Blocos `broll` com `anexo` apontam para o anexo. No briefing exportado, eles vêm com `anexo_asset_id`. A `nota` diz onde ou como a equipe quer o material.
  - Anexo **sem `asset_id`** (acima de 20 MB ou formato não aceito) existe só no computador de quem anexou. Peça à equipe para mandar o arquivo pela sessão ou comprimir para até 20 MB.
- **Arquivos do computador:** o bruto (`bruto_local`), o B-roll solto na timeline (`bloco.local`) e os anexos (`anexo.local`) guardam uma chave (nome, tamanho e data do arquivo).
  - O original fica no navegador de quem abriu e é religado sozinho depois de recarregar ou atualizar o Studio.
  - Nunca apague nem renomeie esses campos numa migração.

## Mídia online e geração com IA

- **Fontes:** Magnific (antiga Freepik, com a conta da DocOn), Pexels, Pixabay, Freesound e Openverse, por `scripts/buscar_midia.py` (sessão e agente) e `web/fontes.mjs` (site).
  - Licença, autor e página de origem ficam gravados no banco.
  - Licenças NC/ND ficam de fora.
  - Magnific Free exige o crédito "Designed by Freepik".
- **Pedido de B-roll sem mídia no banco:**
  1. Busque (ou gere com a Magnific).
  2. Mostre como rascunho no vídeo.
  3. Só guarde no banco o que a equipe aprovar.
  - Nunca coloque mídia sem aprovação.
- **IA:** imagem 9:16 sem texto na imagem, sem marcas, aparência real. "Melhorar" refaz com o ajuste pedido; vídeo curto parte de uma imagem aprovada.
- **Pinterest** e outros links: só referência visual no projeto (`projeto.referencias`), lida pelo diretor. A imagem é de quem publicou e nunca entra no vídeo.

## Lições aprendidas (não repita)

- **Bruto que já era um reels editado:** um "bruto" veio com legenda, card de pergunta e letreiros gravados na imagem. Os nossos gráficos ficaram por cima deles.
  - **Agora:** antes de editar, olhe uma folha de quadros. Se houver texto gravado, pare e peça o arquivo sem edição.
- **Zoom em quem fala num plano aberto:** o detector de rosto não acha rostos pequenos e de perfil num plano aberto com duas pessoas.
  - **Agora:** marque o foco à mão, nos quadros ou com o clique de foco do Studio, e use blocos de câmera colados para a câmera deslizar de um para o outro.

- **Vídeo do computador desvinculado depois de atualizar o Studio:** o navegador não guarda o caminho de um arquivo, então o B-roll solto na timeline (só um link temporário) sumia ao recarregar.
  - **Agora:** todo arquivo local ganha uma chave e o próprio arquivo fica no IndexedDB do navegador (`docon-local`). Ao abrir o projeto, o Studio religa pela chave.
  - **Navegador limpo:** o Studio lista o que falta, e soltar o arquivo de novo religa pelo nome em todos os usos.
  - A cópia no projeto (bruto proxy de 720p, anexos de até 20 MB) continua como segurança.
- **"Não voltou sozinho" (31/10):** o projeto nunca tinha recebido a cópia do bruto (`bruto` vazio, nenhum arquivo enviado pela página), e a falha era silenciosa. Duas consequências:
  - Direção mostra o estado do vínculo do bruto: guardado neste computador e cópia no projeto, com o motivo da falha e um botão para tentar de novo.
  - Cada tentativa grava `diagnostico/<usuário>` no banco. Leia esse documento antes de supor a causa.
- **Desfoque da CTA era fixo:** não dava para tirar. Agora o desfoque do vídeo de fundo é uma camada.
  - **CTA:** `desfoque_fundo` vem ligado em 50%; `false` desliga.
  - **Gancho, painel e nome:** desfocam o fundo só com a caixa marcada (padrão 40%).
  - **Camada solta:** o efeito `fundo_desfocado` na timeline.
  - **Intensidade:** `desfoque_pct` de 5 a 100. 100% = 12 px de desfoque e 70% mais escuro; 50% = o antigo desfoque da CTA.
  - **Skill:** `ed.bg_blur(t0, t1, k)` e `end_card(blur=k)`, com `blur=0` para desligar.
- **Tamanho manual:** cada gancho, painel, assinatura (nome) e CTA tem dois campos de tamanho:
  - `escala`: % do bloco inteiro, retângulo e conteúdo juntos; de 40 a 160, padrão 100.
  - `texto_px`: px do texto principal numa tela de 1080 de largura. Padrões: painel 45, CTA 80, gancho 82, nome 50.
  - A legenda usa `projeto.legenda.fonte_px` (padrão 54, ou 44 na sutil).
  - Valem na prévia (CSS `--ts` e `scale`), na exportação do navegador e no `run_brief.py` (`Panel(s=…)`, `lower_third`/`end_card`/`captions(s=…)`).
- **O diretor não enxergava a prévia:** os painéis acabavam em cima do rosto.
  - **Antes de responder,** ele recebe quadros da prévia (`quadrosDiretor`): à esquerda o vídeo limpo, à direita o mesmo instante com os grafismos, com uma régua de % da altura.
  - **Depois de mudar,** uma conferência visual com quadros novos dos blocos alterados pode corrigir de novo. A prévia vai para o bloco alterado.
  - **Altura na tela:** o campo `pos_y` (% do topo onde o bloco começa) vale para gancho, painel, nome e CTA na prévia, na exportação do navegador e no `run_brief.py`. Vazio = posição padrão.
  - **Inspetor:** "Posição na tela" com as opções Alto, Meio e Baixo.
- **Anexos no topo da Direção confundiam a conversa:** o diretor não percebia que um arquivo tinha acabado de chegar.
  - **Agora:** o 📎 Anexar fica na barra de mensagem, tanto na Direção quanto na Sessão. Os arquivos esperam como chips e vão junto com a próxima mensagem, com uma nota "anexos desta mensagem" e as imagens dessa mensagem primeiro.
  - **Na Sessão:** a cópia sobe antes do envio, para o agente conseguir baixar.
- **Vídeo de aprovação não tocava no iPhone (play cortado):** o Firefox não codifica AAC, e o áudio saía em Opus dentro do MP4, que o iPhone não toca.
  - **Agora:** sem AAC no navegador, o Studio codifica o áudio em MP3 com o lamejs e o põe no MP4 (troca o tipo do esds para 0x6B).
  - **Ainda não confirmado:** testei no Chromium e no ffmpeg; no Safari do iPhone, falta confirmar com o cliente.
  - **Vídeo antigo com Opus:** converta com `ffmpeg -c:v copy -c:a aac` e troque o `asset_id` na aprovação e no espelho.
- **Podcast:** o pipeline supunha uma pessoa em vídeo vertical. Agora `podcast_prep.py` monta os takes na ordem do roteiro, reenquadra se o bruto for horizontal e grava o mapa. O `run_brief.py` põe as assinaturas dos locutores depois do gancho, porque a primeira assinatura cobria a frase do gancho.
- **Safari (iPhone/Mac) com play cortado na aprovação, enquanto as imagens carregavam:** o Safari pede o vídeo em pedaços (Range), e o armazenamento de arquivos pode não responder como ele espera. A tela do cliente agora baixa o vídeo inteiro, mostrando o progresso, e toca a partir de um blob local.
- **Perfil do Instagram é do cliente, não do projeto:** fica em `clientes/<slug do nome>.ig` (`{handle, foto_asset_id, nome, bio, posts, seguidores, seguindo}`).
  - Ao enviar para aprovação, o Studio pede só o que falta, já preenchido.
  - Projetos novos do mesmo profissional herdam o perfil.
- **Legenda gravada:** palavras grudavam ("estámarcada") porque o espaço era medido como 0. Agora o espaço tem largura mínima.
- **Firefox (a equipe usa):** o `VideoEncoder` do Firefox não entrega `decoderConfig` nos quadros, e o mp4-muxer quebrava (`track.info.decoderConfig is null`). Por isso a cópia do bruto e a exportação falhavam.
  - **Correção:** codificar em Annex B e montar o avcC e as amostras na própria página (`splitAnnexB`, `avccBody`, `avcCOf`). Funciona igual no Chrome.
  - O Firefox também entrega quadros B fora de ordem, e o primeiro quadro chega em 33 ms. Por isso os quadros ficam guardados e o `muxFinal` monta tudo no fim: DTS = i × duração do quadro, ctts = PTS − DTS, e o deslocamento R vale para vídeo e áudio (`cross-track-offset`).
  - Ele também não tem reconhecimento de voz: o ditado precisa de Chrome ou Edge, ou do Win+H.
- **Busca online pelo claude.ai:** depende da sessão do Claude Code estar ligada, ter rede liberada para os bancos e ter as chaves. Se nada disso existir, a página não pode ficar esperando em silêncio: ela avisa em até 90 s e oferece os links dos bancos para baixar e anexar.
- **Ditado:** a aba Sessão (agente) mandava usar o microfone do teclado. Agora as duas abas têm 🎙 Ditar.
  - Na Sessão, terminar a fala com "pode enviar" manda a mensagem, se a opção estiver marcada.
  - No site, navegadores sem reconhecimento de voz gravam a fala, e o servidor transcreve com `scripts/ditado.py` (Parakeet).

- Aceleração de 1,08x na voz (Dra. Ana): o cliente percebeu distorção e preferiu velocidade normal com a voz natural, sem nenhum efeito. Se o cliente mandar a voz tratada ou pedir naturalidade, use `speed=1.0` (estilo: `imagem.velocidade: 1.0`), corte só as pausas longas com micro-fades de 10 ms e não processe a voz (`audio.build(..., voice='raw', voice_file=...)`). Confira a sincronia contra o áudio da câmera nos mesmos cortes (meta: ≤ 5 ms).

- Look "claro e suave" com gamma 0,75 + pro-mist: o cliente achou a imagem lavada e com qualidade baixa. Padrão agora é **natural**.
- Desfoque de fundo: reprovado. Desligado por padrão.
- Três reamostragens + três encodes + zoom acumulado de 1,2x derrubaram a nitidez. Use **uma reamostragem e um encode**, zoom máximo de câmera de 1,05 e nitidez leve.
- Compressor + EQ forte + loudnorm dinâmico sobre bruto já limitado deixaram o áudio "estourado". Use **tratamento leve + loudnorm linear**.
- Arquivo de 46 MB pelo cartão de arquivo: o usuário não conseguiu baixar. Use página com `downloads`.
- Linhas de legenda se sobrepondo na troca: a linha sai antes de a próxima entrar (já resolvido no core).
- Projeto com duração fixa (60 s) deixava tela preta depois do fim do vídeo. Agora a duração é a do bruto; blocos depois do fim são ignorados com aviso e o cartão final começa no máximo 2,5 s antes do último quadro.
- Materiais base (sons, trilhas, imagens, vídeos) saem de `scripts/materiais_base.py`, na paleta e na luz dos vídeos já aprovados (champanhe, dourado, rosé; sálvia para vet). Efeitos fortes (tremor, whip, P&B) são pontuais; o padrão dos estilos é só o light leak sutil.
- SRT importado chegava ao diretor só como texto: o passo a passo descartava os tempos se o texto fosse retocado, e o diretor não recebia os tempos. Agora os tempos ficam e o diretor recebe `legenda_tempos` ([início, fim, frase]); com eles, posicione os blocos na fala sem pedir o SRT de novo.
- Atualizar o Studio não pode zerar projeto: ponto salvo antes de cada versão, backup local das edições e recuperação automática (ver CLAUDE.md).
- Versão para a web em HEVC (H.265): no Chrome do Windows o vídeo não aparece (tela preta, export vazio). Toda versão que vai para o Studio ou para aprovação sai em **H.264**; o render já faz isso.
- O cliente abriu o vídeo FINAL como bruto: blocos fora do tempo e nada aparecia. O projeto agora guarda o próprio bruto (`projeto.bruto`, cópia de trabalho 720p) e abre sozinho; sem bruto, mostra a última versão só para assistir.
- Aprovação: o cliente só aprova ou pede alteração (sem download). Status do projeto: em edição → em aprovação → alteração pedida → aprovado; a exportação só libera depois de "aprovado".
- Voz da IA no Studio: uma voz fixa. Voz de personagem ou de pessoa real (ex.: Cortana) não pode ser imitada nem "aproximada"; a voz da DocOn é própria: `scripts/voz.py` (Kokoro pf_dora pt-BR, gratuita, perfis assistente/serena/clara, tratamento de assistente digital). Termos em inglês precisam do dicionário `PRONUNCIA` (sem ele, "DocOn" e "light leak" saem errados). Confira a pronúncia transcrevendo a amostra com o Parakeet.

## API do núcleo (`scripts/core.py`)

```python
ed = Edit(VIDEO, WORK, speed=1.08, tail=1.3, cut_pauses=True, fixes=[{'old','new'[,'near']}, {'after','insert':[(w,t)]}, {'old','drop':True}])
T = ed.t                      # T('palavra', after=tempo) -> tempo de saída da palavra
ed.camera(topics=[...])       # tempos das viradas de assunto (dolly)
ed.hook(pages, keyword_word=, icon=)   # pages: [[linhas]] ou [{'lines':[...], 'ys':(...)}], em ordem da fala
ed.lower_third(t0, t1, nome, subtitulo, y=1300)
p = ed.panel(t0, t1, y=950, h=420); y = ed.kicker_title(p, 'KICKER', 'Título'); ed.row(p, ICONS['check'](70), 'Texto', y, T('palavra'))
p.add(sprite, x, y, t, tick=True, anim='pop'|'rise')
ed.broll(path, t0, t1, mode='full'|'band')
ed.end_card(t0, kicker, [linhas_titulo], subtitulo, nome, botao, icon='sparkle')
ed.captions(style='docon'|'subtle', keywords=[...], y=1585)
ed.check(); ed.render(GRADED, OUT) / ed.render(GRADED, None, preview=[t...])
audio.build(ed, OUT_WAV, music=WAV|None, music_db=-15, duck_db=7, voice='light'|'raw', voice_file=None)
python3 scripts/music.py OUT.wav DURACAO --bpm 92 --key D --mood warm|calm
```

## Limitações do ambiente

- Sem acesso ao Pexels nem a bancos de música, a trilha é sintetizada por `music.py`. Ofereça trocar por trilha licenciada.
- Não dá para ouvir o áudio. Confira por métricas: ebur128, fator de crista, cromagrama da trilha, correlação de envelope na sincronia.
- Render em CPU leva ~1,5 min a cada 10 s de vídeo no grade e ~0,3 s por quadro no compositor. Rode os passos longos em segundo plano.
