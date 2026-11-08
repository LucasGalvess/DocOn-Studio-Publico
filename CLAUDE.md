# DocOn Studio · instruções para o Claude neste repositório

- Este repositório guarda o pipeline de edição de reels da DocOn Marketing Médico:
  - a skill `.claude/skills/docon-cinema`;
  - o agente `.claude/agents/docon-editor.md`;
  - a skill `.claude/skills/docon-artes` e o agente `.claude/agents/docon-designer.md` (artes estáticas);
  - o código da página DocOn Studio em `studio/index.html`.
- Comando **"Abrir DocOn Studio"**: use a skill `abrir-docon-studio`. Ela abre o Studio e liga a aba Sessão da página a esta conversa. Comentários do Studio que começam com "[DocOn Studio · conversa" seguem a mesma skill.
- Para editar vídeos, use o agente `docon-editor` (ele carrega a skill). Para artes estáticas (post, story, carrossel), use o agente `docon-designer` (skill `.claude/skills/docon-artes`).
- Em vídeos e artes, **a referência manda e o estilo é a base**: peça e siga as referências de design; estilo e identidade preenchem o resto.
- Link do Studio: https://claude.ai/artifact/SEU-STUDIO
- Primeira vez na sessão: `bash .claude/skills/docon-cinema/scripts/setup.sh` (ou configure isso como Setup script do ambiente).
- Nunca versione mídia (vídeos, áudios, renders), dados de pacientes ou transcrições de clientes.
- Ao melhorar o pipeline (scripts, regras, estilos):
  1. Teste com `run_brief.py --stage preview`.
  2. Registre a lição nova em "Lições aprendidas" do SKILL.md.
  3. Faça commit com uma mensagem em português dizendo o que mudou e por quê.
- Mudança na página do Studio: edite `studio/index.html` e republique no mesmo link. Antes de republicar, siga estes passos, nesta ordem (nenhum projeto pode recomeçar do zero):
  1. Suba `STUDIO_VERSAO` em `studio/index.html`.
  2. Crie um ponto salvo de cada projeto: `ArtifactData` `set` em `projetos/<id>/historico/pt-<epoch>` = `{label: "Antes da atualização do Studio (<versão>)", data, snap: <JSON dos campos do projeto>, blocos_n, origem: "claude-code"}`.
  3. Nunca apague nem sobrescreva `projetos/*`. Migração de formato é sempre aditiva (campos novos opcionais).
  4. A página recupera sozinha o que estava sendo editado: backup local, ponto ao abrir a versão nova, posição e desfazer.
  5. Mantenha as regras do banco do Studio (raiz só para Editores; `previas` legível por quem tem o código). Sem elas, clientes leriam todos os projetos.
- Cópia pública: `LucasGalvess/DocOn-Studio-Publico` (sem licença, direitos reservados). Ela é gerada só por `tools/publicar.py`, que tira os dados de clientes e o link do Studio e se recusa a publicar se sobrar algum. Nunca envie arquivos deste repositório ao público por outro caminho.
  - A Action `.github/workflows/publico.yml` atualiza o público a cada push no main (segredo `DOCON_PUBLICO_TOKEN`).
  - Sem a Action, depois de cada push rode `python3 tools/publicar.py <clone do público> --push`.
  - Nome novo de cliente, paciente ou campanha que entrar no repositório: acrescente em `TROCAS` e `PROIBIDO` de `tools/publicar.py`.
