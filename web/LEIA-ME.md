# DocOn Studio · site próprio

O mesmo Studio do claude.ai, num endereço da DocOn, com o Claude Opus 5.5 dentro do editor e um agente de edição na nuvem que renderiza com a skill `docon-cinema`.

## Como funciona

| Parte | O que faz | Onde roda |
|---|---|---|
| `../studio/index.html` | O editor: timeline, prévia ao vivo, bancos, estilos, aprovação e exportação. É **o mesmo arquivo** do artifact. | Navegador |
| `shim.js` | Troca as capacidades do claude.ai (`window.claude.use`) pelo servidor. | Navegador |
| `server.mjs` | Login da equipe, banco em tempo real, arquivos (com Range, para o vídeo andar na timeline), diretor com Claude e link de aprovação `/aprovar/<token>`. | Hospedagem (Node 20+) |
| `agente.mjs` | Aba **Sessão** do Studio → agente gerenciado (Claude Managed Agents), com o repositório montado e ferramentas para ler e gravar o Studio e publicar versões. | Nuvem da Anthropic |

- **Diretor:** o Claude Opus 5.5 responde no chat e edita a timeline (criar, editar e apagar blocos, efeitos). O seletor de raciocínio vai de Rápido a Máximo (`low` até `max`).
  - Recusas dos classificadores seguem para o modelo reserva recomendado (`fallbacks: "default"`).
- **Agente:** recebe o pedido, monta o briefing, roda `run_brief.py` e publica o MP4 como nova versão do projeto. A página exporta MOV, WAV e MP3 a partir dele.
- **Aprovação:**
  1. O cliente abre o link, vê só o vídeo e escolhe **Aprovar** (o download começa e o projeto vira "aprovado") ou **Pedir alteração**.
  2. Se pedir alteração, o diretor aplica o ajuste na timeline (com um ponto salvo antes) e o agente renderiza a nova versão.
  3. Quem editou recebe um aviso com o antes e depois e reenvia pelo mesmo link.

## Mídia online e IA

- **Biblioteca › Online:** busca B-roll, imagens e sons em Magnific, Pexels, Pixabay, Freesound e Openverse, com prévia.
  - "Ver no vídeo" coloca o item como rascunho no cursor.
  - "Salvar no banco" guarda o arquivo com fonte, autor e licença.
- **Biblioteca › Gerar com IA:** gera imagem 9:16 (ou vídeo curto a partir de uma imagem) na conta Magnific. Você vê no vídeo, clica em "Melhorar" ou "Aprovar"; só o aprovado vai para o banco.
- **Direção › Referências:** links do Pinterest e outros como moodboard. O diretor lê, mas nunca coloca no vídeo.
- **O diretor** também busca e gera quando você pede um B-roll, deixando a escolha com você.
- **Chaves:** ficam em `.env.exemplo`. As licenças NC e ND são filtradas.

## Anexos, arquivos do computador e ditado

- **Direção › Anexos:** imagens, vídeos, áudios e documentos.
  - O diretor vê as imagens e os quadros dos vídeos e lê os documentos.
  - Ele coloca o material no vídeo com "Colocar no vídeo" ou pela ferramenta `usar_anexo`.
  - O agente recebe os anexos em `/workspace/media/anexos/`.
- **Arquivos do computador:** ficam guardados no navegador (IndexedDB) e são religados sozinhos depois de recarregar ou atualizar o Studio.
- **🎙 Ditar:** funciona na Direção e na Sessão.
  - Sem reconhecimento de voz no navegador (Firefox, Safari), o site grava a fala e transcreve no servidor com `scripts/ditado.py`, usando o modelo Parakeet que o `setup.sh` já baixa.

## Voz da DocOn

- **Padrão:** voz própria e gratuita, gerada no servidor (`scripts/voz.py`: Kokoro, voz feminina pt-BR, licença Apache 2.0). É igual em todos os computadores.
- **Perfil:** a equipe escolhe entre "assistente", "serena" e "clara" em Studio › Voz da IA (`config/voz`).
- **Azure ou ElevenLabs:** são opcionais. Para usar, defina `VOZ_PROVEDOR` e a chave correspondente (`voz-amostras.mjs` gera amostras para comparar).

## Colocar no ar (uma vez)

1. Crie a chave em console.anthropic.com. A cobrança é separada do plano do claude.ai.
2. Hospede com disco permanente (Render, Railway, Fly.io ou uma VPS).
   - Com Docker, rode a partir da raiz do repositório: `docker build -f web/Dockerfile -t docon-studio .`
   - Sem Docker: `cd web && npm ci && npm run materiais && npm start`
3. Preencha as variáveis de `.env.exemplo` no painel da hospedagem: chave, equipe, segredo e pasta de dados.
4. Para o render pelo site, crie um token do GitHub só com leitura do `docon-studio` e rode `npm run agente` uma vez. O comando imprime `DOCON_AGENTE_ID` e `DOCON_AMBIENTE_ID` para colocar nas variáveis.
5. Entre com nome e senha da equipe. `npm run materiais` já deixa os materiais base e os estilos padrão no banco.

## Custos (estimativa, confira no uso real)

- **Opus 5.5:** US$ 4 por milhão de tokens de entrada e US$ 20 por milhão de saída.
- **Diretor:** uma conversa de ajuste fica em centavos. No nível Máximo, custa mais por pedido.
- **Agente de render:** paga os tokens do agente mais o tempo do ambiente na nuvem. Use o nível `high` no agente e só suba se a qualidade pedir.

## Segurança

- **Cliente da aprovação:** não faz login. Ele só lê e muda a **própria** aprovação, e só os campos `status`, `pedido` e `eventos`, partindo de "aguardando". Projetos, bancos e memória ficam fechados (testado: 403).
- **Arquivos:** os links `/_blob/<id>` usam ids aleatórios de 128 bits.
- **Mídia e pacientes:** vídeos de pacientes ficam no disco da hospedagem e nunca no git (`web/data/` está no `.gitignore`).
- **Agente gerenciado:** a rede é limitada aos hosts de modelos e fontes. Ações de risco que pedirem permissão são negadas automaticamente e avisadas na aba Sessão.
