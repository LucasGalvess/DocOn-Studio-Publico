---
name: docon-artes
description: Cria artes estáticas de profissionais de saúde (médicos, dentistas, veterinários) para Instagram no padrão DocOn — post único (4:5), quadrado (1:1), story (9:16) e carrossel (2 a 10 lâminas, com PDF). Sempre pede e analisa REFERÊNCIAS de design, que mandam no resultado; o estilo do DocOn Studio e a identidade do cliente são só a base. Use quando pedirem post, story, carrossel, arte, peça, card ou lâmina para redes sociais.
---

# DocOn Artes

Artes em HTML/CSS renderizadas para PNG (Playwright), com as mesmas cores, fontes, pílulas, ícones e cantos dos vídeos do DocOn Studio.

## Regra principal: a referência manda

**A referência é o ponto principal de como a arte deve ser. O estilo e a identidade são só a base.** Vale desde 08/11/2026, para as artes e para os vídeos.

- Ordem de prioridade (a de cima vence):
  1. o que o cliente pediu por escrito;
  2. as **referências de design** enviadas;
  3. a identidade do cliente (logo, paleta, fontes, notas);
  4. o estilo do DocOn Studio;
  5. os padrões desta skill.
- Na prática: `plano.referencia` sobrescreve `--identidade`, que sobrescreve `--estilo` (paleta, fontes, alinhamento, caixa do título, densidade, cantos).
- Se a referência conflita com a identidade (ex.: cores diferentes da marca), siga a referência na composição (layout, hierarquia, ritmo, densidade). Use as cores da referência só se o cliente pediu "igual à referência". Na dúvida, mantenha a paleta da marca e diga na entrega o que foi adaptado.

## Fluxo

1. **Peça referências** antes de criar. Ex.: "Tem referências de design (prints, posts de que gosta, materiais da marca)? Mande 2 a 5 imagens ou PDFs."
   - Se o usuário não tiver nenhuma, use os materiais de exemplo da identidade do cliente (`clientes/<slug>.identidade.materiais` no Studio) e as artes já aprovadas. Diga que essa base foi usada.
   - Sem nada disso, siga o estilo do Studio e avise.
2. **Analise as referências**:
   - Rode `python3 scripts/referencias.py WORK/ref ref1.png ref2.pdf …`.
   - Olhe a folha `WORK/ref/referencias.png` com Read e anote o que se repete:
     - fundo: escuro, claro, gradiente ou foto;
     - paleta: confira o rascunho `referencia.json`; as cores sugeridas são só um ponto de partida;
     - fontes: serifada ou sem serifa, peso, caixa alta;
     - alinhamento;
     - densidade de texto;
     - cantos: retos ou arredondados;
     - uso de foto, ícones e pílulas;
     - posição da assinatura.
   - Passe isso para `plano.referencia` e escreva as `observacoes`.
3. **Escreva o plano** (`PLANO.json`, veja `exemplos/` e o cabeçalho de `scripts/arte.py`):
   - formato e fundo;
   - assinatura (só o que foi informado);
   - referência;
   - slides: um layout por lâmina — capa, texto, lista, numero, passos, comparacao, citacao, cta.
4. **Gere**:
   ```bash
   python3 scripts/arte.py PLANO.json SAIDA --estilo estilo.json --identidade identidade.json
   ```
   - `estilo.json` é o doc `estilos/<id>` do Studio: paleta, fontes etc.
   - `identidade.json` traz paleta, fontes e `logo` (caminho de um PNG local).
   - Saída: `arte_01.png…` (1080 de largura), `carrossel.pdf` e `folha.png`.
5. **Revise** a `folha.png` com Read **lado a lado com a folha das referências**:
   - a arte parece da mesma família da referência?
   - hierarquia clara: 1 ideia por lâmina;
   - contraste legível;
   - nada vazando: o script avisa `AVISO texto_vazando`;
   - safe area do story: 250 px no topo e 300 px embaixo, livres.
   - Corrija o plano e gere de novo. No máximo 2 rodadas antes de entregar.
6. **Entregue**:
   - Mande os PNGs (e o PDF do carrossel) com SendUserFile ou numa página de download.
   - Resuma em 3–5 linhas o que veio da referência, o que veio da identidade/estilo e o que foi deduzido.

## Modo Studio (aba Artes do DocOn Studio)

No Studio, "Novo projeto" › **Arte** cria um projeto com `formato: "arte"`. A equipe edita as lâminas em Projeto e vê a prévia ao vivo no centro. A prévia usa **o mesmo motor** da skill (`scripts/arte_engine.js`), então o PNG final sai igual.

Formato do projeto: `projetos/<id>.arte` =
- `fmt`: post, quadrado, story ou carrossel;
- `fundo`: {tipo, foto, todas};
- `assinatura`: {nome, registro, handle} (sem ela, usa o nome e o @ do profissional);
- `referencia`: como em `plano.referencia`;
- `refs`: [{asset_id, nome}], as imagens de referência enviadas;
- `pedido`;
- `slides`: como no plano; fotos ficam como `/_blob/<asset_id>`;
- `renders`: [{t, rotulo, pngs: [asset_id], pdf}];
- `status`.

Os links de referência ficam em `projetos/<id>.referencias`.

**Pedido "Crie as LÂMINAS da ARTE do projeto <id>":**
1. Leia o projeto e o estilo `estilos/<estilo_id>`.
2. Leia a identidade em `clientes/<slug>`.
3. Baixe as referências (`Artifact` `read` + `path` = asset_id), analise com `referencias.py` e olhe a folha.
4. Escreva `arte.slides` e `arte.referencia` com `ArtifactData` `update` + `if_version`, sem tocar no resto do projeto. Antes, crie um ponto salvo em `projetos/<id>/historico`.
5. Não gere PNG: a equipe revisa no Studio primeiro.
6. Responda na Sessão em 2–3 linhas: o que veio da referência e o que foi deduzido.

**Pedido "Gere os ARQUIVOS da ARTE do projeto <id>":**
1. Salve o projeto, o estilo e o cliente com `ArtifactData` `get` + `out_dir`.
2. Baixe para uma pasta os assets usados: logo da identidade, fotos das lâminas e do fundo.
3. Rode:
   ```bash
   python3 scripts/studio_arte.py PROJETO.json SAIDA --estilo ESTILO.json --cliente CLIENTE.json --blobs PASTA
   ```
4. Olhe a `folha.png`.
5. Suba os PNGs e o PDF com `Artifact` `asset:true` (até 25 por chamada).
6. Acrescente em `arte.renders` {t, rotulo, pngs, pdf} e atualize `arte.status`.

**Use exatamente as lâminas do projeto:** a equipe já revisou. Se algo vazar ou estiver errado, avise em vez de mudar.

**Mudou o layout?** Edite só `scripts/arte_engine.js` e rode:
```bash
python3 tools/sync_arte_engine.py
```
Depois republique o Studio, seguindo o CLAUDE.md.

## Formatos

| formato | tamanho | uso |
|---|---|---|
| `post` | 1080×1350 (4:5) | post único do feed |
| `quadrado` | 1080×1080 | feed, anúncio |
| `story` | 1080×1920 (9:16) | story; topo e base reservados para a interface |
| `carrossel` | 1080×1350 × 2–10 | capa com gancho → conteúdo → CTA; pontos de página e "Arraste para o lado" na capa |

## Texto e conteúdo (CFM e Instagram)

- **Capa do carrossel**: gancho curto, de até 8 palavras no título. Use `destaque` em 1–3 palavras.
- **Lâmina interna**: uma ideia; até ~35 palavras no corpo e até 5 itens por lista.
- **Última lâmina**: CTA sem promessa. Ex.: "Agende sua avaliação", "Converse com sua médica".
- **Ética médica (CFM 2.336/2023)**:
  - não prometa resultado nem use antes/depois sem autorização expressa do cliente;
  - não use superlativos ("o melhor", "garantido");
  - não exponha paciente identificável.
  - Número ou estatística só com fonte informada (campo `fonte`). Não invente dados.
- **Assinatura**: nome, CRM/RQE, @ e clínica só se informados. Nunca invente.
- Português do Brasil, com acentos; revise a grafia antes de gerar.

## Ajustes finos

- `referencia.paleta` aceita as chaves do estilo: `glass` (fundo), `text`, `key` (destaque), `icon`, `grad1`, `grad2`, `button`, `button_fg`, `pill_bg`, `pill_fg`, `border`.
- `referencia.fontes` = `{titulo, texto}`. Use nomes do Google Fonts; o script baixa com `docon-cinema/scripts/fontes.py`.
- `fundo.tipo: "foto"` + `fundo.foto`: foto de fundo com véu escuro. `fundo.todas: true` aplica a foto a todas as lâminas.
  - Use só fotos do cliente, do banco do Studio ou de bancos livres (Pexels/Unsplash/Pixabay).
- Ícones: check, heart, sparkle, calendar, target, clock, shield, leaf, star, alert, chat, x.
- Layout novo: acrescente em `LAYOUTS` e em `corpo()` de `scripts/arte_engine.js`. Teste com os 3 exemplos, rode `tools/sync_arte_engine.py`, republique o Studio e registre aqui.

## Lições aprendidas

- 08/11/2026: o layout saiu do Python para `arte_engine.js`, que serve a prévia do Studio e o PNG final. Duas cópias do layout (Python e JS) iam divergir. `tools/sync_arte_engine.py --check` acusa diferença.
- Na referência, o "destaque" (`key`) arrasta ícones, degradê, pílula e borda; o "fundo" (`glass`) arrasta o texto da pílula. Assim uma cor só já muda a arte inteira.

- A detecção de texto vazando precisa de tolerância (`fontSize*0.25+2`). Sem ela, títulos com acento encolhiam à toa.
- Capa sem foto fica vazia: a camada `.decor` (brilho + anel) segura o espaço. Mantenha-a sutil.
- O CTA centraliza pelo wrapper `.conteudo` (`--just`), não por margem.
- O extrator de paleta pega fundo e texto bem. Já o destaque (`key`) às vezes sai apagado: confira sempre na folha antes de usar.
