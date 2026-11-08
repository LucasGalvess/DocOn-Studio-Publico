/* DocOn Artes · motor de layout (fonte única).
   O MESMO código desenha a prévia no DocOn Studio (aba Artes) e o PNG final da skill (render.mjs, via arte.py).
   Depois de mudar este arquivo, rode `python3 tools/sync_arte_engine.py` para copiar para studio/index.html.
   Sem dependências, sem DOM no momento de montar (só strings); `ajustar(raiz)` roda no navegador. */
const ArteEngine = (() => {
  const TAM = {post: [1080, 1350], carrossel: [1080, 1350], quadrado: [1080, 1080], story: [1080, 1920]};
  const FORMATOS = {post: 'Post único (4:5)', quadrado: 'Quadrado (1:1)', story: 'Story (9:16)', carrossel: 'Carrossel (4:5, 2 a 10 lâminas)'};
  const LAYOUTS = {
    capa: {n: 'Capa', campos: ['kicker', 'titulo', 'destaque', 'subtitulo', 'foto']},
    texto: {n: 'Texto', campos: ['kicker', 'titulo', 'destaque', 'corpo']},
    lista: {n: 'Lista com ícones', campos: ['kicker', 'titulo', 'destaque', 'itens_icone']},
    numero: {n: 'Número em destaque', campos: ['kicker', 'valor', 'rotulo', 'texto', 'fonte']},
    passos: {n: 'Passos', campos: ['kicker', 'titulo', 'destaque', 'itens']},
    comparacao: {n: 'Comparação', campos: ['kicker', 'titulo', 'destaque', 'esquerda', 'direita']},
    citacao: {n: 'Citação', campos: ['kicker', 'frase', 'autor']},
    cta: {n: 'Chamada final (CTA)', campos: ['kicker', 'titulo', 'destaque', 'texto', 'acao']},
  };
  const PAL = {glass: '#34241e', text: '#f8f3ea', key: '#f2d6a6', icon: '#e9c48c', grad1: '#f6deac', grad2: '#c99660',
    button: '#b76e79', button_fg: '#f8f3ea', pill_bg: '#f2d6a6', pill_fg: '#34241e', border: '#e8d3b0'};
  const ICONES = {
    check: '<circle cx="12" cy="12" r="9.5"/><path d="M7.5 12.4l3 3 6-6.4"/>',
    heart: '<path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z"/>',
    sparkle: '<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z"/>',
    calendar: '<rect x="4" y="5" width="16" height="15" rx="2.5"/><path d="M4 10h16M9 3v4M15 3v4"/>',
    target: '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="4.5"/><circle cx="12" cy="12" r="1"/>',
    clock: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
    shield: '<path d="M12 3l7 3v5.5c0 4.4-3 7.7-7 9.5-4-1.8-7-5.1-7-9.5V6z"/><path d="M9 12l2 2 4-4.5"/>',
    leaf: '<path d="M5 19c0-8 5-13 14-14-1 9-6 14-14 14z"/><path d="M5 19l7-7"/>',
    star: '<path d="M12 3.5l2.6 5.3 5.9.9-4.3 4.1 1 5.8L12 16.9l-5.2 2.7 1-5.8-4.3-4.1 5.9-.9z"/>',
    alert: '<path d="M12 4l9 16H3z"/><path d="M12 10v4M12 17.2v.3"/>',
    chat: '<path d="M5 6h14v9H10l-4 3v-3H5z"/>',
    x: '<circle cx="12" cy="12" r="9.5"/><path d="M9 9l6 6M15 9l-6 6"/>',
  };
  const esc = (t) => String(t == null ? '' : t).replace(/[&<>"']/g, (c) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  const icone = (n, cls = 'ic') => `<svg class="${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">${ICONES[n] || ICONES.check}</svg>`;
  const limpo = (o) => Object.fromEntries(Object.entries(o || {}).filter(([, v]) => v));
  /* a REFERÊNCIA manda; identidade e estilo são a base */
  /* na referência, "destaque" (key) e "fundo" (glass) arrastam as cores ligadas a eles, a menos que venham explícitas */
  const expandir = (rp) => { const r = limpo(rp); const o = {...r};
    if (r.key) for (const k of ['icon', 'grad1', 'grad2', 'pill_bg', 'border']) if (!r[k]) o[k] = r.key;
    if (r.glass && !r.pill_fg) o.pill_fg = r.glass;
    return o; };
  const paleta = (estilo, ident, ref) => ({...PAL, ...limpo(estilo?.paleta), ...limpo(ident?.paleta), ...expandir(ref?.paleta)});
  const fontes = (estilo, ident, ref) => { const f = {...limpo(estilo?.fontes), ...limpo(ident?.fontes), ...limpo(ref?.fontes)}; return {titulo: f.titulo || 'Montserrat', texto: f.texto || 'Inter'}; };
  const reEsc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  function realce(titulo, destaque) {
    let t = esc(titulo).replace(/\n/g, '<br>');
    for (const d of String(destaque || '').split(',').map((x) => x.trim()).filter(Boolean)) t = t.replace(new RegExp(reEsc(esc(d)), 'i'), (m) => `<span class="grad">${m}</span>`);
    return t;
  }
  function cores(p, tipo) {
    const cm = (a, pct, b = 'transparent') => `color-mix(in srgb,${a} ${pct}%,${b})`;
    if (tipo === 'claro') return {bg: p.text, fg: p.glass, fg2: cm(p.glass, 78), fg3: cm(p.glass, 45), card: cm(p.glass, 7, p.text), borda: cm(p.glass, 14), veu: 'none'};
    return {bg: tipo === 'gradiente' ? `linear-gradient(160deg,${p.glass},${cm(p.glass, 70, p.grad2)})` : p.glass, fg: p.text, fg2: cm(p.text, 82), fg3: cm(p.text, 45),
      card: cm(p.glass, 62), borda: cm(p.border, 40),
      veu: tipo === 'foto' ? `linear-gradient(180deg,${cm(p.glass, 35)} 0%,${cm(p.glass, 55)} 45%,${cm(p.glass, 92)} 100%)` : 'none'};
  }
  const CSS = `
.arte,.arte *{margin:0;padding:0;box-sizing:border-box}
.arte{position:relative;width:var(--w);height:var(--h);overflow:hidden;padding:var(--safe-t) 84px var(--safe-b);display:flex;flex-direction:column;gap:34px;font-family:var(--fx);color:var(--fg);background:var(--bg);-webkit-font-smoothing:antialiased;text-align:left}
.fundo{position:absolute;inset:0;z-index:0}
.fundo img{width:100%;height:100%;object-fit:cover}
.fundo:after{content:"";position:absolute;inset:0;background:var(--veu)}
.arte>*:not(.fundo):not(.decor){position:relative;z-index:1}
.kicker{align-self:flex-start;background:var(--pill_bg);color:var(--pill_fg);font:800 26px/1 var(--ft);letter-spacing:.12em;text-transform:uppercase;padding:14px 24px;border-radius:999px}
.centro .kicker{align-self:center}
.tit{font:800 var(--t1,92px)/1.04 var(--ft);letter-spacing:-.015em;text-wrap:balance;text-transform:var(--caixa,none)}
.tit2{font:800 var(--t2,64px)/1.08 var(--ft);letter-spacing:-.01em;text-wrap:balance;text-transform:var(--caixa,none)}
.grad{background:linear-gradient(100deg,var(--grad1),var(--grad2));-webkit-background-clip:text;background-clip:text;color:transparent}
.sub{font:500 38px/1.35 var(--fx);color:var(--fg2);text-wrap:pretty}
.corpo{font:500 40px/1.45 var(--fx);color:var(--fg2);text-wrap:pretty}
.corpo p+p{margin-top:24px}
.vidro{background:var(--card);border:2px solid var(--borda);border-radius:var(--r,34px);padding:44px 48px}
.itens{display:grid;gap:28px}
.item{display:grid;grid-template-columns:72px 1fr;gap:26px;align-items:center;font:700 42px/1.25 var(--fx)}
.ic{width:72px;height:72px;color:var(--icon)}
.num{font:900 var(--tn,250px)/.95 var(--ft);letter-spacing:-.03em}
.rotulo{font:700 46px/1.2 var(--fx)}
.fonte{font:500 26px/1.3 var(--fx);color:var(--fg3)}
.passos{display:grid;gap:30px}
.passo{display:grid;grid-template-columns:90px 1fr;gap:28px;align-items:start}
.passo b{display:grid;place-items:center;width:90px;height:90px;border-radius:50%;background:var(--key);color:var(--glass);font:800 44px/1 var(--ft)}
.passo span{font:600 40px/1.3 var(--fx);padding-top:18px}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:26px;flex:1;min-height:0}
.col h3{font:800 44px/1.1 var(--ft);margin-bottom:18px;display:flex;gap:14px;align-items:center}
.col h3 .ic{width:52px;height:52px}
.col p{font:500 36px/1.4 var(--fx);color:var(--fg2)}
.aspas{font:900 260px/.6 var(--ft);color:var(--key);height:120px}
.frase{font:700 var(--tq,64px)/1.2 var(--ft);text-wrap:balance}
.autor{font:600 34px/1.3 var(--fx);color:var(--fg2)}
.botao{align-self:flex-start;background:var(--button);color:var(--button_fg);font:800 42px/1 var(--fx);padding:30px 48px;border-radius:999px}
.centro .botao{align-self:center}
.conteudo{flex:1;min-height:0;display:flex;flex-direction:column;gap:34px;justify-content:var(--just,center)}
.decor{position:absolute;inset:0;z-index:0;pointer-events:none;background:radial-gradient(60% 45% at 92% 6%,color-mix(in srgb,var(--grad2) 30%,transparent),transparent 70%),radial-gradient(50% 40% at 0% 100%,color-mix(in srgb,var(--key) 14%,transparent),transparent 70%)}
.decor:after{content:"";position:absolute;width:760px;height:760px;right:-300px;top:-260px;border-radius:50%;border:3px solid color-mix(in srgb,var(--key) 22%,transparent)}
.claro .decor{background:radial-gradient(60% 45% at 92% 6%,color-mix(in srgb,var(--grad2) 22%,transparent),transparent 70%)}
.rodape{display:flex;align-items:center;gap:22px;font:600 28px/1.2 var(--fx);color:var(--fg2)}
.rodape img{height:64px;max-width:300px;object-fit:contain}
.rodape .nome b{display:block;color:var(--fg);font-weight:700}
.rodape .pag{margin-left:auto;display:flex;gap:10px;align-items:center}
.rodape .pag i{width:14px;height:14px;border-radius:50%;background:var(--fg3)}
.rodape .pag i.on{width:40px;border-radius:8px;background:var(--key)}
.arrasta{display:flex;gap:12px;align-items:center;font:700 30px/1 var(--fx);color:var(--key)}
.arrasta svg{width:44px;height:44px}
.foto{border-radius:var(--r,34px);overflow:hidden;flex:1;min-height:0}
.foto img{width:100%;height:100%;object-fit:cover}
.centro{text-align:center;align-items:center}
.centro .itens,.centro .passos{text-align:left}
`;
  const itemTxt = (it) => (it && typeof it === 'object') ? (it.texto || '') : (it || '');
  function corpo(s, i, n, plano, url) {
    const L = s.layout || 'capa'; const out = []; const alin = plano.referencia?.alinhamento || 'esquerda';
    const tit = (cls = 'tit2') => s.titulo ? `<h2 class="${cls}" data-fit="titulo">${realce(s.titulo, s.destaque)}</h2>` : '';
    if (s.kicker) out.push(`<span class="kicker">${esc(s.kicker)}</span>`);
    if (L === 'capa') {
      if (s.foto) out.push(`<div class="foto"><img src="${esc(url(s.foto))}" alt=""></div>`);
      out.push(`<h1 class="tit" data-fit="titulo" style="max-height:${s.foto ? '46%' : '62%'}">${realce(s.titulo, s.destaque)}</h1>`);
      if (s.subtitulo) out.push(`<p class="sub" data-fit="subtitulo">${esc(s.subtitulo)}</p>`);
      if (plano.formato === 'carrossel' && n > 1) out.push('<div class="arrasta">Arraste para o lado <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M5 12h13M13 6l6 6-6 6"/></svg></div>');
    } else if (L === 'texto') {
      out.push(tit());
      out.push('<div class="corpo" data-fit="corpo" style="flex:1;min-height:0">' + String(s.corpo || '').split('\n').filter((x) => x.trim()).map((x) => `<p>${esc(x)}</p>`).join('') + '</div>');
    } else if (L === 'lista') {
      out.push(tit());
      out.push(`<div class="vidro itens" data-fit="itens">${(s.itens || []).map((it) => `<div class="item">${icone((it && it.icone) || 'check')}<span>${esc(itemTxt(it))}</span></div>`).join('')}</div>`);
    } else if (L === 'numero') {
      out.push(`<div class="num grad">${esc(s.valor)}</div><div class="rotulo">${esc(s.rotulo)}</div>`);
      if (s.texto) out.push(`<p class="sub" data-fit="texto">${esc(s.texto)}</p>`);
      if (s.fonte) out.push(`<p class="fonte">Fonte: ${esc(s.fonte)}</p>`);
    } else if (L === 'passos') {
      out.push(tit());
      out.push('<div class="passos" data-fit="passos">' + (s.itens || []).map((t, k) => `<div class="passo"><b>${k + 1}</b><span>${esc(itemTxt(t))}</span></div>`).join('') + '</div>');
    } else if (L === 'comparacao') {
      out.push(tit()); const e = s.esquerda || {}, d = s.direita || {};
      out.push(`<div class="cols"><div class="vidro col" data-fit="esquerda"><h3>${icone(e.icone || 'x')}${esc(e.titulo)}</h3><p>${esc(e.texto)}</p></div><div class="vidro col" data-fit="direita"><h3>${icone(d.icone || 'check')}${esc(d.titulo)}</h3><p>${esc(d.texto)}</p></div></div>`);
    } else if (L === 'citacao') {
      out.push('<div class="aspas">“</div>', `<p class="frase" data-fit="frase">${esc(s.frase)}</p>`);
      if (s.autor) out.push(`<p class="autor">${esc(s.autor)}</p>`);
    } else if (L === 'cta') {
      out.push(`<h2 class="tit" data-fit="titulo" style="--t1:84px">${realce(s.titulo, s.destaque)}</h2>`);
      if (s.texto) out.push(`<p class="sub" data-fit="texto">${esc(s.texto)}</p>`);
      if (s.acao) out.push(`<span class="botao">${esc(s.acao)}</span>`);
    } else throw new Error('layout desconhecido: ' + L);
    return [out.filter(Boolean).join(''), alin === 'centro' || L === 'citacao' || L === 'numero'];
  }
  function rodape(plano, i, n, logo) {
    const a = plano.assinatura || {};
    const nome = (a.nome || a.handle) ? `<span class="nome"><b>${esc(a.nome)}</b>${esc([a.registro, a.handle].filter(Boolean).join(' · '))}</span>` : '';
    const pag = n > 1 ? Array.from({length: n}, (_, k) => `<i class="${k === i ? 'on' : ''}"></i>`).join('') : '';
    return `<div class="rodape">${logo ? `<img src="${esc(logo)}" alt="">` : ''}${nome}<span class="pag">${pag}</span></div>`;
  }
  /* uma página: {w, h, css, html}. ctx = {estilo, ident, url(src) → endereço da imagem, logo (endereço ou ''), ft, fx (font-family CSS)} */
  function pagina(plano, i, ctx = {}) {
    const fmt = plano.formato || 'post'; const [W, H] = TAM[fmt] || TAM.post;
    let slides = plano.slides || []; if (fmt !== 'carrossel') slides = slides.slice(0, 1);
    const s = slides[i] || {}; const n = slides.length; const ref = plano.referencia || {}; const url = ctx.url || ((x) => x);
    const p = paleta(ctx.estilo, ctx.ident, ref); const tipo = plano.fundo?.tipo || 'escuro'; const v = cores(p, tipo); const fo = fontes(ctx.estilo, ctx.ident, ref);
    const [st, sb] = fmt === 'story' ? [250, 300] : [96, 84];            // story: fora da barra do topo e da caixa de resposta
    const raiz = {w: W + 'px', h: H + 'px', 'safe-t': st + 'px', 'safe-b': sb + 'px', r: (+ref.cantos >= 0 && ref.cantos !== '' && ref.cantos != null ? +ref.cantos : 34) + 'px',
      caixa: ref.titulo_caixa === 'alta' ? 'uppercase' : 'none', ft: ctx.ft || `"${fo.titulo}",sans-serif`, fx: ctx.fx || `"${fo.texto}",sans-serif`, ...p, ...v};
    if (fmt === 'story') Object.assign(raiz, {t1: '104px', t2: '72px'});
    if (fmt === 'quadrado') Object.assign(raiz, {t1: '80px', t2: '58px', tn: '210px'});
    const escala = {leve: 1.06, media: 1, densa: 0.9}[ref.densidade] || 1;
    const [miolo, centro] = corpo(s, i, n, plano, url);
    const L = s.layout || 'capa'; const just = L === 'capa' && !s.foto ? 'flex-end' : L === 'capa' ? 'flex-start' : 'center';
    const fimg = plano.fundo?.foto; const temFoto = fimg && (i === 0 || plano.fundo?.todas);
    const estilo = Object.entries(raiz).map(([k, x]) => `--${k}:${x}`).join(';') + `;--just:${just};font-size:${escala}em`;
    const html = `<div class="arte ${centro ? 'centro' : ''} ${esc(tipo)}" style="${esc(estilo)}">${temFoto ? `<div class="fundo"><img src="${esc(url(fimg))}" alt=""></div>` : ''}${fimg && i === 0 ? '' : '<div class="decor"></div>'}<div class="conteudo">${miolo}</div>${rodape(plano, i, n, ctx.logo)}</div>`;
    return {w: W, h: H, css: CSS, html, fontes: fo, n};
  }
  /* texto que não cabe encolhe até 72%; devolve os campos que ainda vazam */
  function ajustar(raiz) {
    const vaza = [];
    for (const el of raiz.querySelectorAll('[data-fit]')) {
      el.style.fontSize = ''; const cs = getComputedStyle(el); const base = parseFloat(cs.fontSize); let k = 1;
      const tol = () => parseFloat(getComputedStyle(el).fontSize) * 0.25 + 2;
      const sobra = () => el.scrollHeight > el.clientHeight + tol() || el.scrollWidth > el.clientWidth + 2;
      while (sobra() && k > 0.72) { k -= 0.04; el.style.fontSize = (base * k) + 'px'; }
      if (sobra()) vaza.push(el.dataset.fit);
    }
    return vaza;
  }
  function nSlides(plano) { const n = (plano.slides || []).length; return plano.formato === 'carrossel' ? n : Math.min(1, n); }
  return {TAM, FORMATOS, LAYOUTS, ICONES, PAL, paleta, fontes, pagina, ajustar, nSlides, esc};
})();
if (typeof module !== 'undefined') module.exports = ArteEngine;
