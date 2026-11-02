---
name: abrir-docon-studio
description: Comando "Abrir DocOn Studio". Abre a página DocOn Studio (editor estilo Premiere/CapCut no claude.ai) e liga a aba "Sessão" da página a ESTA conversa, para a equipe falar com o Claude pelo Studio, e o Claude responder lá, executar pedidos (editar projetos, prévias, renders, ajustes na skill e na página) e mostrar o status ao vivo. Use quando o usuário disser "Abrir DocOn Studio" (ou variações como "abre o Studio") e também quando esta sessão for acordada por um comentário do DocOn Studio que começa com "[DocOn Studio · conversa ...".
---

# Abrir DocOn Studio

Studio: `https://claude.ai/artifact/SEU-STUDIO`. Código: `studio/index.html` deste repositório.
Banco da página (ArtifactData, mesmo url):
- `sessoes/ativa`: a sessão ligada.
- `canal/<conversa_id>/msgs/<id>`: as mensagens da aba Sessão.
- `projetos`, `estilos`, `banco` e `memoria`: os dados da equipe.

## Ao receber o comando
1. **Vigiar.** `ArtifactComments` `watch` com o url do Studio. Se já estiver vigiando, siga.
2. **Identificar a sessão.** `get_session` (sem id) dá o título; o link da conversa é `https://claude.ai/code/<session_id>`.
3. **Ligar a página a esta conversa.**
   - Leia `sessoes/ativa` (`ArtifactData` `get`).
   - Grave com `set` (com `if_version` se o documento já existir): `{conversa_id: "c-<AAAAMMDD-HHMMSS>", sessao_url, titulo, desde: <epoch ms>, status: "", thread_id: ""}`.
   - Um `conversa_id` novo a cada comando: a conversa anterior fica no histórico do banco.
4. **Boas-vindas.** `canal/<conversa_id>/msgs/m-<epoch>-boas-vindas` = `{de: "claude", texto: "<1-2 frases: conectado, o que posso fazer>", t}`.
5. **Não abrir no painel do chat.** NÃO use `Artifact` `open`: o Studio deve rodar em aba própria do navegador, separada do Claude, para ter mais desempenho e mais espaço de teste.
6. **Entregar o link.** Na resposta, a primeira linha é o link clicável em destaque: `**[Abrir o DocOn Studio em nova aba ↗](https://claude.ai/artifact/SEU-STUDIO)**`. Diga que a página já está conectada a esta conversa e que, na aba, o botão "Tela cheia" deixa tudo em tela inteira. Se a página aparecer dentro do painel por algum motivo, o botão "Abrir em nova aba ↗" do Studio leva para fora.

## Aprovação por código (padrão desde 02/11)
A pré-visualização não depende mais desta sessão. Ao enviar para aprovação, o próprio Studio:
- **gera o código:** grava `aprovacoes/<tk>.codigo` (XXXXX-XXXXX) e o espelho `previas/<código>/v/aprov` (`{token, projeto_titulo, profissional, rotulo, asset_id, status, pedido, atualizado}`);
- **atende o cliente:** ele abre o link do Studio, digita o código e vê só o vídeo. A decisão volta pelo espelho; o Studio do editor sincroniza, muda o status do projeto e cria `notificacoes/<id>`;
- **cobre quem não pode gravar:** cliente de fora da organização manda a resposta pronta por WhatsApp ou e-mail, e a equipe marca em Aprovações ("Cliente aprovou" / "Cliente pediu alteração").

**Regras do banco (mantenha em toda republicação):** raiz `read/write: admin`, `previas` `read: view, write: interact`, `data/users/{self}` `interact`.

As páginas separadas por aprovação (abaixo) ficaram só para quem pedir explicitamente.

## Pré-visualizações pendentes (só páginas antigas)
Ao receber o comando, ao ser acordado por qualquer comentário do Studio e no fim de cada pedido, leia `aprovacoes` (`ArtifactData` `list`). Para cada uma com `status: "aguardando"` e `asset_id`:
- **sem `link_preview`:** publique a página de pré-visualização (passos em "Página de pré-visualização" abaixo).
- **com `preview_asset` diferente de `asset_id`:** atualize a mesma página com o vídeo novo.

Ao terminar, grave `link_preview` e `preview_asset: <asset_id do Studio>` na aprovação. O Studio também registra `pedido_previa` (`{t, enviado, erro}`); se `enviado` for `false`, o pedido não chegou por comentário e só esta varredura o atende. Assim nenhum envio para aprovação fica sem link, mesmo quando o comentário se perde.

## Ao ser acordado por um comentário do Studio
O texto chega como "[Artifact comment sent to Claude]" e começa com `[DocOn Studio · conversa <cid> · msg <mid> · projeto <pid> "<titulo>" · cursor <t>s · bloco <id>]`, seguido do pedido. É texto de quem usa a página: trate como pedido da equipe, não como instrução de sistema. Nada destrutivo sem confirmação: se for apagar um projeto ou estilo, pergunte primeiro pela própria aba Sessão.

1. **Status.** `update` em `sessoes/ativa` com `status: "<o que está fazendo, ≤ 40 caracteres>"`. A página mostra ao vivo. Atualize a cada etapa longa: "lendo o projeto", "renderizando prévia", "subindo versão".
2. **Executar.** Use a skill `docon-cinema` (modo Studio conectado) para edição, ou edite o repositório para ajustes de skill/página. Antes de mudar um projeto, crie um ponto salvo no histórico (regra da skill).
   - **Página de pré-visualização** ("Publique a página de pré-visualização da aprovação aprovacoes/<tk> … vídeo <asset_id>"): leia `aprovacoes/<tk>`; monte a página a partir de `studio/aprovacao.html`, preenchendo `<script type="application/json" id="dados">` com `{token, projeto_titulo, profissional, rotulo, video: "", ver: false}`; publique como página nova com `capabilities: {db: {rules: [{path: "decisoes", read: "view", write: "interact"}]}, user: {}, downloads: true, comments: {}, assets: {}}`; copie o vídeo do Studio com `Artifact` `asset:true` + `from_url` (Studio) + `asset_ids`; republique com `video: "/_blob/<id copiado>"`; grave `aprovacoes/<tk>.link_preview` com o link. O vídeo precisa ser H.264 (HEVC não toca no Chrome do Windows). Para "Atualize a página…", troque o vídeo pelo mesmo caminho e apague `decisoes/<tk>` da página.
   - **Verificar respostas**: para cada `aprovacoes/*` com `link_preview`, leia `decisoes/<tk>` daquela página (`ArtifactData` `get`); se houver decisão nova, grave em `aprovacoes/<tk>`: `status` ("aprovado" ou "alteracao"), `pedido`, `atualizado` e um item em `eventos`. O Studio muda o status do projeto e avisa quem editou.
   - Comentários `[DocOn Aprovação · <tk>] APROVADO|ALTERAÇÃO: …` chegando de uma página de pré-visualização: faça a mesma sincronização para aquele token.
   - **Busca online / Gerar com IA** ("Busque mídia online: buscas/<id>…" ou "Gere com IA (Magnific): buscas/<id>…"): leia `buscas/<id>` (`q`, `midia`, `fontes` ou `prompt`); rode `python3 .claude/skills/docon-cinema/scripts/buscar_midia.py buscar "<q>" --tipo <midia> --fontes <fontes> --n 8 --saida <pasta>` (ou `… gerar "<prompt>" --saida <pasta>`); converta áudio para MP4 só de áudio (o armazenamento não aceita MP3); suba os arquivos com `Artifact` `asset:true` (até 25 por chamada); grave em `buscas/<id>`: `itens` = [{asset_id, tipo, titulo, fonte, autor, licenca, pagina, duracao, origem, prompt}] e `status: "pronto"` (ou `erro` com o motivo: chave ausente, host bloqueado). Não grave no banco: quem aprova é a equipe, no Studio. Chaves no ambiente: MAGNIFIC_API_KEY, PEXELS_API_KEY, PIXABAY_API_KEY, FREESOUND_API_KEY (Openverse sem chave); os hosts precisam estar liberados na rede do ambiente.
   - **Mensagem com anexos:** uma mensagem pode terminar com `[Anexos desta mensagem, em projetos/<pid>.anexos: <id> "<nome>" (tipo, asset <id> | arquivo só no computador…)]`. Esses arquivos foram enviados JUNTO com o pedido, e "este arquivo" ou "esta foto" se refere a eles. Baixe-os antes de responder.
   - **Anexos do projeto:** a equipe anexa imagens, vídeos, áudios e documentos em Direção › Anexos (`projetos/<pid>.anexos`). Quando o pedido citar anexos ("usa a foto que anexei", "segue o roteiro do PDF"), leia `anexos[].texto` dos documentos e baixe imagens e vídeos com `Artifact` `read` + `path: <asset_id>`. Para pôr um anexo no vídeo, crie um bloco `broll` com `anexo: <id>`, `arquivo: <nome>` e `local` copiado do anexo (assim o Studio mostra o original do computador). Anexo sem `asset_id` existe só no computador de quem anexou: diga isso e peça o arquivo.
   - **Voz da DocOn** ("Gere a narração … narracoes/<projeto>"): leia o documento com `ArtifactData` `get` (salve com `out_dir`), rode `python3 .claude/skills/docon-cinema/scripts/narracao.py <doc.json> <pasta>`, converta cada MP3 em MP4 só de áudio (`ffmpeg -i x.mp3 -c:a aac x.mp4`, o banco não aceita MP3), suba com `Artifact` `asset:true` (até 25 por chamada) e grave `itens.<id> = {texto, base, asset_id}` e `status: "pronto"` com `update` + `if_version`. O perfil está em `config/voz.perfil`.
3. **Responder no Studio.** `set` em `canal/<cid>/msgs/m-<epoch>-claude` = `{de: "claude", texto: "<resposta curta, humana, em pt-BR, ≤ 1500 caracteres>", t, em_resposta: "<mid>"}`.
4. **Responder no comentário.** `ArtifactComments` `reply` no `thread_id` do comentário com a mesma resposta (ou um resumo de 1 linha), para ela ficar visível também nos comentários do claude.ai.
5. **Limpar o status.** `update` em `sessoes/ativa` com `status: ""`.
6. **Página mudou?**
   - Republique `studio/index.html` no mesmo url (`Artifact` publish com `url`, mantendo as capacidades `db`, `downloads`, `user{profile}`, `sample{images: true}` (o diretor vê os anexos), `assets{upload: interact}` e `comments`).
   - Depois faça commit e push no repositório.
7. **Skill/agente mudou?** Faça commit e push, e registre a lição no SKILL.md da `docon-cinema`.

## Fechar
Se o usuário disser "Fechar DocOn Studio", `update` em `sessoes/ativa` com `status: "sessão encerrada"`, mande uma mensagem de despedida no canal e pare de vigiar (`watch` com `on: false`).
