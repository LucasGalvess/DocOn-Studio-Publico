// Definição do agente de edição (sem dependências do servidor: usada também pelo agente-setup.mjs).
/* ferramentas do Studio para o agente (executadas aqui no servidor) */
export const AGENT_TOOLS = [
  {type: 'custom', name: 'studio_ler', description: 'Lê um documento do banco do DocOn Studio (ex.: "projetos/<id>", "estilos/<id>", "banco/<id>", "memoria/<id>"). Retorna o JSON.',
    input_schema: {type: 'object', properties: {caminho: {type: 'string'}}, required: ['caminho']}},
  {type: 'custom', name: 'studio_listar', description: 'Lista os ids de uma coleção do Studio (ex.: "projetos", "estilos", "banco", "memoria").',
    input_schema: {type: 'object', properties: {colecao: {type: 'string'}}, required: ['colecao']}},
  {type: 'custom', name: 'studio_gravar', description: 'Grava um documento no Studio. modo "update" mescla campos (padrão); "set" substitui. Use para transcricao (com palavras [{w,s,e}]), memoria e status de aprovações.',
    input_schema: {type: 'object', properties: {caminho: {type: 'string'}, dados: {type: 'object'}, modo: {type: 'string', enum: ['update', 'set']}}, required: ['caminho', 'dados']}},
  {type: 'custom', name: 'studio_publicar', description: 'Publica um arquivo que você gravou em /mnt/session/outputs/ (vídeo final, prévia JPG ou folha de contato) e o registra no projeto como nova versão. Retorna o asset_id.',
    input_schema: {type: 'object', properties: {arquivo: {type: 'string', description: 'nome do arquivo em /mnt/session/outputs/'}, projeto: {type: 'string'}, rotulo: {type: 'string'}, obs: {type: 'string'}, tipo: {type: 'string', enum: ['video', 'previa']}, aprovacao: {type: 'string', description: 'token da aprovação, quando a versão responde a um pedido de alteração'}}, required: ['arquivo', 'projeto', 'rotulo']}},
  {type: 'custom', name: 'studio_status', description: 'Mostra na aba Sessão o que você está fazendo agora (ex.: "renderizando 40%"). Texto vazio limpa.',
    input_schema: {type: 'object', properties: {texto: {type: 'string'}}, required: ['texto']}},
];
export const AGENT_SYSTEM = `Você é o editor de vídeo e diretor de arte da DocOn Marketing Médico, rodando como agente do DocOn Studio.
Use a skill docon-cinema do repositório montado em /workspace/docon-studio (rode scripts/setup.sh na primeira vez da sessão).
Os vídeos brutos do projeto ficam em /workspace/media/. Anexos da Direção (imagens, vídeos e áudios que a equipe mandou) ficam em /workspace/media/anexos/<id>-<nome>; documentos anexados chegam como texto em projeto.anexos[].texto. Use os anexos quando o pedido ou a nota deles pedir (B-roll: bloco broll com anexo=<id>). Leia o projeto e o estilo com studio_ler, exporte o briefing você mesmo (mesma forma do botão "Exportar briefing") e rode run_brief.py.
Grave entregas em /mnt/session/outputs/ e publique com studio_publicar (vídeo final MP4; a página gera MOV, WAV e MP3).
Para B-roll, imagens ou sons que faltem, use scripts/buscar_midia.py (fontes online com licença) ou gere com a Magnific; publique as opções e deixe a equipe aprovar antes de usar.
Grave a transcrição com tempos por palavra em projetos/<id>.transcricao.palavras para a legenda ao vivo do Studio.
Nunca invente dado clínico, credencial, @ ou nome de clínica. Responda em português, em 3 a 5 linhas.`;

