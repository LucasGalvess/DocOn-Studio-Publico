"""DocOn Cinema · voz da DocOn (gratuita, roda local): Kokoro 82M (Apache 2.0), voz feminina pt-BR "pf_dora",
pronúncia brasileira (espeak pt-br), com o tratamento "assistente de IA" da DocOn.

uso: python3 voz.py "texto" SAIDA.mp3 [--perfil assistente|clara|serena] [--voz pf_dora]
     echo "texto" | python3 voz.py - SAIDA.wav
Modelo em ~/.docon/models/kokoro/ (o setup.sh baixa: kokoro-v1.0.onnx + voices-v1.0.bin; pip install kokoro-onnx).
Perfis (a equipe escolheu um no Studio; padrão "assistente"):
  clara       ritmo 0,97 · tom natural · tratamento leve
  assistente  ritmo 0,93 · tom -1 semitom (formantes preservados) · brilho, chorus sutil e eco curto
  serena      ritmo 0,90 · tom -2 semitons · mesmo tratamento, mais grave e pausada
"""
import os, sys, subprocess, tempfile, argparse
import soundfile as sf

M = os.path.expanduser('~/.docon/models/kokoro/')
CADEIAS = {     # mesmas cadeias de web/voz.mjs
    'docon': 'highpass=f=90,equalizer=f=250:t=q:w=1:g=-2,equalizer=f=3200:t=q:w=1.2:g=2,equalizer=f=9500:t=h:w=3000:g=3.5,'
             'chorus=0.7:0.9:24|37:0.16|0.11:0.30|0.25:1.4|2.1,aecho=0.85:0.7:32|61:0.13|0.07,loudnorm=I=-18:TP=-2:LRA=7',
    'leve': 'highpass=f=90,equalizer=f=9500:t=h:w=3000:g=2.5,aecho=0.85:0.7:30:0.08,loudnorm=I=-18:TP=-2:LRA=7',
    'nenhum': 'highpass=f=80,loudnorm=I=-18:TP=-2:LRA=7',
}
PERFIS = {'clara': (0.97, 0, 'leve'), 'assistente': (0.93, -1, 'docon'), 'serena': (0.90, -2, 'docon')}

# pronúncia de termos da casa e do inglês (a voz lê em português; escrevemos como se fala)
PRONUNCIA = [(r'\bDocOn\b', 'Dóc Ón'), (r'\bStudio\b', 'Stúdio'), (r'\blight leaks?\b', 'láit líik'), (r'\bB-?rolls?\b', 'bí rôl'),
             (r'\blower thirds?\b', 'lôuer férd'), (r'\bCTA\b', 'cê tê á'), (r'\bzoom\b', 'zum'), (r'\bwhip pan\b', 'uíp pén'),
             (r'\bglow\b', 'glôu'), (r'\bbokeh\b', 'bokê'), (r'\breels?\b', 'ríls'), (r'\bkicker\b', 'kíquer'), (r'\bflash\b', 'fléch'),
             (r'\bpunch\b', 'pântch'), (r'\bInstagram\b', 'Instagrã'), (r'\bdesign\b', 'dizáin'), (r'\bplay\b', 'plêi')]
def pronunciar(t):
    import re
    for a, b in PRONUNCIA: t = re.sub(a, b, t, flags=re.I)
    return t

_k = None
def kokoro():
    global _k
    if _k is None:
        from kokoro_onnx import Kokoro
        _k = Kokoro(M + 'kokoro-v1.0.onnx', M + 'voices-v1.0.bin')
    return _k

def falar(texto, saida, perfil='assistente', voz='pf_dora'):
    vel, semis, cadeia = PERFIS.get(perfil, PERFIS['assistente'])
    a, sr = kokoro().create(pronunciar(texto), voice=voz, speed=vel, lang='pt-br')
    with tempfile.NamedTemporaryFile(suffix='.wav') as t:
        sf.write(t.name, a, sr)
        af = (f'rubberband=pitch={2 ** (semis / 12):.5f}:formant=preserved,' if semis else '') + CADEIAS[cadeia]
        cod = ['-c:a', 'libmp3lame', '-b:a', '128k'] if saida.endswith('.mp3') else ['-c:a', 'pcm_s16le']
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', t.name, '-af', af, '-ar', '48000', '-ac', '1', *cod, saida], check=True)
    return saida

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('texto'); ap.add_argument('saida')
    ap.add_argument('--perfil', default=os.environ.get('VOZ_PERFIL', 'assistente')); ap.add_argument('--voz', default='pf_dora')
    A = ap.parse_args(); txt = sys.stdin.read() if A.texto == '-' else A.texto
    print(falar(txt.strip(), A.saida, A.perfil, A.voz))
