"""Baixa para o computador as imagens de todos os jogos listados em dataset/capas.csv.

As imagens vão para web/capas/<id_do_jogo>.jpg e o site passa a usá-las (funciona sem internet).
Pode ser interrompido (Ctrl+C) e rodado de novo: pula o que já foi baixado.

Uso:   python ferramentas/baixar_imagens.py [--limite N] [--threads 16]
Recomendado antes: pip install pillow  (reduz cada imagem para uma miniatura; sem isso a pasta chega a ~6 GB)
"""
import argparse
import csv
import io
import os
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from PIL import Image  # opcional: pip install pillow (reduz as imagens e economiza disco)
except ImportError:
    Image = None
    print("Aviso: sem Pillow as imagens ficam em tamanho original (~6 GB no total). Recomendado: pip install pillow")

DESTINO = os.path.join("web", "capas")
LARGURA, ALTURA = 420, 280  # tamanho reduzido pelo próprio servidor do RAWG (cada imagem fica com ~20-40 KB)

ap = argparse.ArgumentParser()
ap.add_argument("--limite", type=int, default=0, help="baixa só as N primeiras (para testar)")
ap.add_argument("--threads", type=int, default=32)
args = ap.parse_args()

os.makedirs(DESTINO, exist_ok=True)
with open("dataset/capas.csv", encoding="utf-8", newline="") as f:
    itens = [(r["id_jogo"], r["url_imagem"]) for r in csv.DictReader(f) if r["url_imagem"].startswith("http")]
if args.limite:
    itens = itens[: args.limite]


def baixar(item):
    jogo_id, url = item
    caminho = os.path.join(DESTINO, f"{jogo_id}.jpg")
    if os.path.exists(caminho) and os.path.getsize(caminho) > 0:
        return "ja_existia"
    if not url.startswith("http"):
        return "falhou"
    reduzida = url.replace("/media/games/", f"/media/crop/{LARGURA}/{ALTURA}/games/")
    # tenta a versão reduzida; se o servidor não tiver (404), usa a imagem original
    for tentativa, endereco in enumerate([reduzida, reduzida, url, url]):
        try:
            req = urllib.request.Request(endereco, headers={"User-Agent": "Mozilla/5.0 (trabalho-faculdade)"})
            with urllib.request.urlopen(req, timeout=30) as r:
                dados = r.read()
            if Image is not None:  # reduz para miniatura (de ~300 KB para ~25 KB)
                im = Image.open(io.BytesIO(dados)).convert("RGB")
                im.thumbnail((LARGURA, ALTURA))
                buf = io.BytesIO()
                im.save(buf, "JPEG", quality=80, optimize=True)
                dados = buf.getvalue()
            with open(caminho + ".tmp", "wb") as out:
                out.write(dados)
            os.replace(caminho + ".tmp", caminho)
            return "baixada"
        except Exception:
            time.sleep(0.5 + tentativa)
    return "falhou"


cont = {"baixada": 0, "ja_existia": 0, "falhou": 0}
inicio = time.time()
with ThreadPoolExecutor(args.threads) as pool:
    futuros = [pool.submit(baixar, i) for i in itens]
    for n, fut in enumerate(as_completed(futuros), 1):
        cont[fut.result()] += 1
        if n % 200 == 0 or n == len(itens):
            vel = n / (time.time() - inicio)
            print(f"{n}/{len(itens)}  baixadas={cont['baixada']} já existiam={cont['ja_existia']} falhas={cont['falhou']}  ({vel:.1f} img/s)", flush=True)

tam = sum(os.path.getsize(os.path.join(DESTINO, a)) for a in os.listdir(DESTINO)) / 1e6
print(f"Pronto. Pasta {DESTINO}: {tam:.0f} MB. Falhas: {cont['falhou']} (rode de novo para tentar outra vez).")
if cont["falhou"]:
    sys.exit(1)
