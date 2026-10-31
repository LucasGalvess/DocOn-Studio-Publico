// Fontes de mídia online para o DocOn Studio: busca, prévia, importação para o banco (com licença e autor) e geração com IA.
// Cada fonte só aparece se a chave estiver configurada (Openverse não precisa de chave).
//   MAGNIFIC_API_KEY (ou FREEPIK_API_KEY) · PEXELS_API_KEY · PIXABAY_API_KEY · FREESOUND_API_KEY
// As mesmas fontes existem na skill (scripts/buscar_midia.py), para a sessão e o agente.
const env = (k) => process.env[k] || '';
const MAG = () => env('MAGNIFIC_API_KEY') || env('FREEPIK_API_KEY');
const MAG_BASE = () => env('MAGNIFIC_API_BASE') || 'https://api.magnific.com';   // api.freepik.com também responde com a mesma chave
const UA = {'User-Agent': 'DocOnStudio/1.0 (+https://github.com/LucasGalvess/DocOn-Studio)'};

// licenças que permitem uso comercial em vídeo de cliente (o resto fica de fora)
const okLic = (l) => !/(^|[-\s/_])(nc|nd)([-\s/_.]|$)|noncommercial|non-commercial|noderiv/i.test(l || '');

export const FONTES = {
  magnific: {nome: 'Magnific', tipos: ['imagem', 'video', 'icone'], ativa: () => !!MAG(), ia: true, site: 'https://www.magnific.com'},
  pexels: {nome: 'Pexels', tipos: ['imagem', 'video'], ativa: () => !!env('PEXELS_API_KEY'), site: 'https://www.pexels.com'},
  pixabay: {nome: 'Pixabay', tipos: ['imagem', 'video'], ativa: () => !!env('PIXABAY_API_KEY'), site: 'https://pixabay.com'},
  freesound: {nome: 'Freesound', tipos: ['som'], ativa: () => !!env('FREESOUND_API_KEY'), site: 'https://freesound.org'},
  openverse: {nome: 'Openverse', tipos: ['imagem', 'som'], ativa: () => env('OPENVERSE_DESLIGADO') !== '1', site: 'https://openverse.org'},
};
export const fontesAtivas = () => Object.entries(FONTES).filter(([, f]) => f.ativa()).map(([k, f]) => ({id: k, nome: f.nome, tipos: f.tipos, ia: !!f.ia}));
// hosts de onde a prévia e a importação podem baixar (o servidor não vira proxy aberto)
export const HOSTS_MIDIA = [/\.pexels\.com$/, /(^|\.)pixabay\.com$/, /\.freesound\.org$/, /(^|\.)freesound\.org$/, /(^|\.)openverse\.org$/, /\.wikimedia\.org$/, /\.staticflickr\.com$/, /\.freepik\.com$/, /\.magnific\.com$/, /\.cdnpk\.net$/, /\.pinimg\.com$/];
export const hostOk = (u) => { try { const h = new URL(u).hostname; return new URL(u).protocol === 'https:' && HOSTS_MIDIA.some((r) => r.test(h)); } catch (e) { return false; } };

async function j(url, opt = {}) { const r = await fetch(url, {...opt, headers: {...UA, ...(opt.headers || {})}}); if (!r.ok) throw new Error(`${new URL(url).hostname} ${r.status}`); return r.json(); }

/* resultado padrão: {fonte, id, tipo, titulo, thumb, url (arquivo para importar), pagina, autor, licenca, duracao, largura, altura} */
async function pexels(q, tipo) {
  const h = {Authorization: env('PEXELS_API_KEY')};
  if (tipo === 'video') { const r = await j(`https://api.pexels.com/videos/search?query=${encodeURIComponent(q)}&orientation=portrait&per_page=18`, {headers: h});
    return r.videos.map((v) => { const f = v.video_files.filter((x) => x.file_type === 'video/mp4').sort((a, b) => Math.abs((a.height || 0) - 1920) - Math.abs((b.height || 0) - 1920))[0] || v.video_files[0];
      return {fonte: 'pexels', id: String(v.id), tipo: 'video', titulo: q, thumb: v.image, url: f?.link, pagina: v.url, autor: v.user?.name, licenca: 'Licença Pexels (uso comercial, sem atribuição obrigatória)', duracao: v.duration, largura: f?.width, altura: f?.height}; }); }
  const r = await j(`https://api.pexels.com/v1/search?query=${encodeURIComponent(q)}&orientation=portrait&per_page=24`, {headers: h});
  return r.photos.map((p) => ({fonte: 'pexels', id: String(p.id), tipo: 'imagem', titulo: p.alt || q, thumb: p.src.medium, url: p.src.large2x || p.src.original, pagina: p.url, autor: p.photographer, licenca: 'Licença Pexels (uso comercial, sem atribuição obrigatória)', largura: p.width, altura: p.height}));
}
async function pixabay(q, tipo) {
  const k = env('PIXABAY_API_KEY');
  if (tipo === 'video') { const r = await j(`https://pixabay.com/api/videos/?key=${k}&q=${encodeURIComponent(q)}&per_page=18&safesearch=true`);
    return r.hits.map((v) => { const f = v.videos.large?.url ? v.videos.large : v.videos.medium; return {fonte: 'pixabay', id: String(v.id), tipo: 'video', titulo: v.tags, thumb: f.thumbnail || v.videos.tiny?.thumbnail, url: f.url, pagina: v.pageURL, autor: v.user, licenca: 'Licença Pixabay (uso comercial; não revender o arquivo isolado)', duracao: v.duration, largura: f.width, altura: f.height}; }); }
  const r = await j(`https://pixabay.com/api/?key=${k}&q=${encodeURIComponent(q)}&image_type=photo&orientation=vertical&per_page=24&safesearch=true`);
  return r.hits.map((p) => ({fonte: 'pixabay', id: String(p.id), tipo: 'imagem', titulo: p.tags, thumb: p.webformatURL, url: p.largeImageURL, pagina: p.pageURL, autor: p.user, licenca: 'Licença Pixabay (uso comercial; não revender o arquivo isolado)', largura: p.imageWidth, altura: p.imageHeight}));
}
async function freesound(q) {
  const filtro = encodeURIComponent('license:("Creative Commons 0" OR "Attribution") duration:[0 TO 30]');
  const r = await j(`https://freesound.org/apiv2/search/text/?query=${encodeURIComponent(q)}&filter=${filtro}&fields=id,name,previews,license,username,duration,url,images&page_size=24&token=${env('FREESOUND_API_KEY')}`);
  return r.results.filter((s) => okLic(s.license)).map((s) => ({fonte: 'freesound', id: String(s.id), tipo: 'som', titulo: s.name, thumb: s.images?.waveform_m, url: s.previews['preview-hq-mp3'], pagina: s.url, autor: s.username, licenca: s.license, duracao: s.duration}));
}
async function openverse(q, tipo) {
  const kind = tipo === 'som' ? 'audio' : 'images';
  const r = await j(`https://api.openverse.org/v1/${kind}/?q=${encodeURIComponent(q)}&license_type=commercial,modification&page_size=24${kind === 'images' ? '&aspect_ratio=tall' : ''}`);
  return r.results.filter((x) => okLic(x.license)).map((x) => ({fonte: 'openverse', id: x.id, tipo: tipo === 'som' ? 'som' : 'imagem', titulo: x.title, thumb: x.thumbnail, url: x.url, pagina: x.foreign_landing_url, autor: x.creator, licenca: `${(x.license || '').toUpperCase()} ${x.license_version || ''}`.trim() + (x.license === 'cc0' || x.license === 'pdm' ? '' : ' (dar crédito ao autor)'), duracao: x.duration ? x.duration / 1000 : undefined, largura: x.width, altura: x.height}));
}
// Magnific (antiga Freepik): conferir os caminhos em docs.magnific.com ao configurar a chave
async function magnific(q, tipo) {
  const h = {'x-magnific-api-key': MAG(), 'x-freepik-api-key': MAG(), 'Accept-Language': 'pt-BR'};
  if (tipo === 'video') { const r = await j(`${MAG_BASE()}/v1/videos?term=${encodeURIComponent(q)}&limit=18&filters[orientation]=vertical`, {headers: h});
    return (r.data || []).map((v) => ({fonte: 'magnific', id: String(v.id), tipo: 'video', titulo: v.name || v.title || q, thumb: v.thumbnails?.[0]?.url || v.thumbnail?.url || v.preview?.url, url: null, pagina: v.url, autor: v.author?.name, licenca: v.premium ? 'Magnific Premium (sua assinatura)' : 'Magnific Free (crédito: “Designed by Freepik”)', duracao: v.duration})); }
  const r = await j(`${MAG_BASE()}/v1/resources?term=${encodeURIComponent(q)}&limit=24&order=relevance&filters[content_type][photo]=1&filters[orientation][portrait]=1`, {headers: h});
  return (r.data || []).map((p) => ({fonte: 'magnific', id: String(p.id), tipo: 'imagem', titulo: p.title || q, thumb: p.image?.source?.url, url: null, pagina: p.url, autor: p.author?.name, licenca: p.licenses?.[0]?.type === 'premium' ? 'Magnific Premium (sua assinatura)' : 'Magnific Free (crédito: “Designed by Freepik”)'}));
}
async function magnificDownload(item) {   // a Magnific pede que o download seja registrado a cada uso
  const h = {'x-magnific-api-key': MAG(), 'x-freepik-api-key': MAG()};
  const r = await j(`${MAG_BASE()}/v1/${item.tipo === 'video' ? 'videos' : 'resources'}/${encodeURIComponent(item.id)}/download`, {headers: h});
  return r.data?.url || r.data?.[0]?.url || r.url;
}
const BUSCA = {pexels, pixabay, freesound, openverse, magnific};
export async function buscar(fonte, q, tipo) {
  const f = FONTES[fonte]; if (!f || !f.ativa()) throw new Error('fonte não configurada');
  if (!f.tipos.includes(tipo)) return [];
  return (await BUSCA[fonte](q, tipo)).filter((x) => x.thumb || x.url);
}
export async function urlDoArquivo(item) { return item.fonte === 'magnific' ? magnificDownload(item) : item.url; }

/* geração com IA (Magnific): imagem vertical a partir de um texto; a tarefa roda em segundo plano e é consultada */
export async function gerarImagem(prompt, opts = {}) {
  const h = {'x-magnific-api-key': MAG(), 'x-freepik-api-key': MAG(), 'Content-Type': 'application/json'};
  const r = await j(`${MAG_BASE()}/v1/ai/mystic`, {method: 'POST', headers: h, body: JSON.stringify({prompt, aspect_ratio: 'social_story_9_16', resolution: opts.resolucao || '2k', ...(opts.estilo ? {styling: {style: opts.estilo}} : {})})});
  return {tarefa: r.data?.task_id || r.task_id, tipo: 'imagem'};
}
export async function gerarVideo(prompt, imagemUrl) {   // imagem → vídeo curto (B-roll animado)
  const h = {'x-magnific-api-key': MAG(), 'x-freepik-api-key': MAG(), 'Content-Type': 'application/json'};
  const r = await j(`${MAG_BASE()}/v1/ai/image-to-video/kling-v2-1-pro`, {method: 'POST', headers: h, body: JSON.stringify({image: imagemUrl, prompt, duration: '5'})});
  return {tarefa: r.data?.task_id || r.task_id, tipo: 'video'};
}
export async function statusGeracao(tarefa, tipo) {
  const h = {'x-magnific-api-key': MAG(), 'x-freepik-api-key': MAG()};
  const r = await j(`${MAG_BASE()}/v1/ai/${tipo === 'video' ? 'image-to-video/kling-v2-1-pro' : 'mystic'}/${encodeURIComponent(tarefa)}`, {headers: h});
  const d = r.data || r; return {status: String(d.status || '').toLowerCase(), urls: d.generated || []};
}
// Pinterest: só como REFERÊNCIA (moodboard). A imagem é de quem publicou: não entra no vídeo.
export async function referencia(url) {
  if (!/^https:\/\/([a-z]+\.)?pinterest\.[a-z.]+\/|^https:\/\/pin\.it\//.test(url)) throw new Error('link do Pinterest inválido');
  const r = await j(`https://www.pinterest.com/oembed.json?url=${encodeURIComponent(url)}`);
  return {fonte: 'pinterest', url, titulo: r.title || '', thumb: r.thumbnail_url || '', autor: r.author_name || '', so_referencia: true};
}
