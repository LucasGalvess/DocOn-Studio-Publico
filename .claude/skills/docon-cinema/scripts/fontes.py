"""DocOn Cinema · fontes universais gratuitas (Google Fonts) para o render, iguais às da prévia do Studio.

baixar(família, peso) devolve o caminho de um TTF estático em ~/.docon/fonts/gf/ (baixa na primeira vez pela
API de CSS do Google Fonts, que entrega TTF a clientes simples). Sem rede, devolve None e o gfx usa a
fonte padrão (Montserrat / Inter Display).
uso: python3 fontes.py "Playfair Display" 800
"""
import os, re, sys, urllib.request
DIR = os.path.expanduser('~/.docon/fonts/gf'); os.makedirs(DIR, exist_ok=True)
UA = 'curl/8'      # agente simples recebe TTF (navegadores recebem WOFF2)
def baixar(familia, peso=700):
    nome = re.sub(r'[^A-Za-z0-9]+', '', familia) + f'-{peso}.ttf'; p = os.path.join(DIR, nome)
    if os.path.exists(p): return p
    for w in [peso, 800, 700, 900, 600, 400]:
        try:
            q = urllib.request.Request(f'https://fonts.googleapis.com/css2?family={familia.replace(" ", "+")}:wght@{w}', headers={'User-Agent': UA})
            css = urllib.request.urlopen(q, timeout=20).read().decode()
            url = re.search(r'url\((https://[^)]+)\)', css)
            if not url: continue
            data = urllib.request.urlopen(url.group(1), timeout=30).read()
            if data[:4] not in (b'\x00\x01\x00\x00', b'true', b'OTTO'): continue
            open(p, 'wb').write(data); return p
        except Exception:
            continue
    return None
if __name__ == '__main__':
    print(baixar(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 700))
