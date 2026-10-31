# DocOn Studio

> **Versão pública do DocOn Studio**, mantida pela DocOn Marketing Médico. Todos os direitos reservados: pode baixar e testar, mas o uso comercial, a redistribuição e as modificações dependem de autorização da DocOn.
>
> - **Studio:** publique `studio/index.html` como página (artifact) no claude.ai, com as capacidades `db`, `assets{upload: interact}`, `sample{images: true}`, `comments`, `downloads` e `user`. Depois troque `https://claude.ai/artifact/SEU-STUDIO` pelo link da sua página.
> - **Site próprio:** veja `web/LEIA-ME.md`.


Pipeline de edição de reels verticais (1080×1920) para profissionais de saúde, no padrão **DocOn Cinema**.

| Parte | Onde | O que faz |
|---|---|---|
| Skill `docon-cinema` | `.claude/skills/docon-cinema/` | Transcrição, cortes, 1,08x, estabilização, cor natural, gancho, painéis de vidro, legenda, CTA, trilha, mix e render. |
| Agente `docon-editor` | `.claude/agents/docon-editor.md` | Diretor de arte/edição que usa a skill (modo briefing, modo Studio conectado ou direção livre). |
| DocOn Studio | `studio/index.html` + [página no claude.ai](https://claude.ai/artifact/SEU-STUDIO) | Timeline com quadros e onda do bruto, prévia ao vivo dos efeitos, materiais base (fontes, efeitos, sons, trilhas, imagens, vídeos), estilos, memória da equipe, Diretor (Claude), efeitos explicados, exportação (MP4, MOV, WAV, MP3), aprovação por link, histórico e desfazer. |
| Site próprio | `web/` (ver `web/LEIA-ME.md`) | O mesmo Studio num endereço da DocOn: login da equipe, Claude Opus 5.5 com nível de raciocínio, agente de edição na nuvem (Managed Agents) que renderiza com a skill, aprovação em `/aprovar/<token>`. |

## Como usar
1. Abra uma sessão do **Claude Code** com este repositório: claude.ai/code → escolha `DocOn-Studio`.
2. Anexe o vídeo bruto e diga, por exemplo: "use o docon-editor com o projeto X do Studio".
3. O agente lê o Studio, edita, mostra a prévia, renderiza e devolve a versão para o Studio.

## Ambiente recomendado (Claude Code na nuvem)
- **Setup script:** `bash .claude/skills/docon-cinema/scripts/setup.sh`
- **Rede:** liberar `github.com`, `objects.githubusercontent.com`, `storage.googleapis.com` e `registry.npmjs.org`.
