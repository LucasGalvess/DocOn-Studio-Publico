// DocOn · modelos Remotion (React). Renderizados por motion.py com fundo transparente (PNG), 1080x1920, 30 fps.
import React from 'react';
import {registerRoot, Composition, AbsoluteFill, useCurrentFrame, useVideoConfig, interpolate, spring, Easing, staticFile} from 'remotion';
const fontes = `@font-face{font-family:DocOnTitulo;src:url(${staticFile('titulo.ttf')})}@font-face{font-family:DocOnTexto;src:url(${staticFile('texto.ttf')})}`;
const cores = (p) => ({glass: p.glass || '#34241e', texto: p.texto || '#f8f3ea', destaque: p.destaque || '#f2d6a6', acento: p.acento || '#e9c48c'});
const saida = (f, total, fps) => interpolate(f, [total - 0.32 * fps, total], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.in(Easing.cubic)});
export const Titulo = (p) => {
  const f = useCurrentFrame(); const {fps, durationInFrames} = useVideoConfig(); const c = cores(p); const ws = String(p.titulo || '').split(/\s+/);
  const kw = String(p.destaque || '').toLowerCase().split(/[,\s]+/).filter(Boolean);
  return <AbsoluteFill style={{opacity: saida(f, durationInFrames, fps)}}><style>{fontes}</style>
    <div style={{position: 'absolute', left: 80, right: 80, top: `${p.y ?? 38}%`, textAlign: 'center', font: '800 96px/1.08 DocOnTitulo, Montserrat, sans-serif', color: c.texto, textShadow: '0 6px 22px rgba(0,0,0,.45)'}}>
      {ws.map((w, i) => { const s = spring({frame: f - 2 - i * 2.4, fps, config: {damping: 200}}); const k = kw.includes(w.toLowerCase().replace(/[.,!?:;]/g, ''));
        return <span key={i} style={{display: 'inline-block', margin: '0 .12em', opacity: s, filter: `blur(${(1 - s) * 8}px)`, transform: `translateY(${(1 - s) * 14}px) scale(${k ? 0.82 + 0.18 * spring({frame: f - 8, fps, config: {damping: 9}}) : 1})`, color: k ? c.destaque : c.texto}}>{w}</span>; })}
    </div></AbsoluteFill>;
};
export const Contador = (p) => {
  const f = useCurrentFrame(); const {fps, durationInFrames} = useVideoConfig(); const c = cores(p); const alvo = Number(p.valor) || 0; const dec = (String(p.valor).split(/[.,]/)[1] || '').length;
  const v = interpolate(f, [6, 6 + Math.min(1.6 * fps, durationInFrames * 0.45)], [0, alvo], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic)});
  const ent = spring({frame: f, fps, config: {damping: 200}});
  return <AbsoluteFill style={{opacity: saida(f, durationInFrames, fps)}}><style>{fontes}</style>
    <div style={{position: 'absolute', left: 90, right: 90, top: `${p.y ?? 36}%`, padding: '44px 40px', borderRadius: 40, textAlign: 'center', background: `color-mix(in srgb, ${c.glass} 66%, transparent)`, opacity: ent, transform: `translateY(${(1 - ent) * 40}px)`}}>
      <div style={{font: '900 190px/1 DocOnTitulo, Montserrat, sans-serif', color: c.destaque, fontVariantNumeric: 'tabular-nums'}}>{(p.prefixo || '') + v.toLocaleString('pt-BR', {minimumFractionDigits: dec, maximumFractionDigits: dec}) + (p.sufixo || '')}</div>
      <div style={{marginTop: 18, font: '600 44px/1.2 DocOnTexto, Inter, sans-serif', color: c.texto}}>{p.rotulo}</div>
    </div></AbsoluteFill>;
};
const comp = (id, C) => <Composition id={id} component={C} fps={30} width={1080} height={1920} durationInFrames={90} defaultProps={{}} calculateMetadata={({props}) => ({durationInFrames: Math.max(15, Math.round((Number(props.duracao) || 3) * 30))})} />;
registerRoot(() => <>{comp('titulo-cinetico', Titulo)}{comp('numero', Contador)}</>);
