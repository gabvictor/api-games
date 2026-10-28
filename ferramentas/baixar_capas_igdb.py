"""Baixa a CAPA OFICIAL (box art) de cada jogo direto do IGDB, que pertence à Twitch.

Como o catálogo já usa os ids do IGDB, o casamento é exato (sem adivinhar pelo nome).
As capas vão para web/capas/<id_do_jogo>.jpg (substituem as do RAWG, se existirem).

PRECISA de uma chave gratuita da Twitch (cada pessoa cria a sua; não coloque no código nem no Git):
  1. Entre em https://dev.twitch.tv/console  (precisa de conta Twitch com verificação em 2 etapas)
  2. "Register Your Application": nome qualquer, URL de redirecionamento http://localhost, categoria "Other"
  3. Copie o "Client ID" e gere um "Client Secret"
  4. No terminal (PowerShell):
        $env:TWITCH_CLIENT_ID="seu_client_id"
        $env:TWITCH_CLIENT_SECRET="seu_client_secret"
        python ferramentas/baixar_capas_igdb.py

Uso: python ferramentas/baixar_capas_igdb.py [--limite N] [--threads 16]
Recomendado: pip install pillow  (reduz o tamanho dos arquivos)
Pode ser interrompido e rodado de novo: pula o que já foi baixado do IGDB (controle em dataset/capas_igdb.csv).
"""
import argparse
import csv
import io
import json
import os
import sqlite3
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

try:
    from PIL import Image
except ImportError:
    Image = None

ap = argparse.ArgumentParser()
ap.add_argument("--limite", type=int, default=0)
ap.add_argument("--threads", type=int, default=16)
args = ap.parse_args()

cid, segredo = os.environ.get("TWITCH_CLIENT_ID"), os.environ.get("TWITCH_CLIENT_SECRET")
if not cid or not segredo:
    sys.exit("Defina TWITCH_CLIENT_ID e TWITCH_CLIENT_SECRET (veja as instruções no topo deste arquivo).")

DESTINO = os.path.join("web", "capas")
CONTROLE = "dataset/capas_igdb.csv"
os.makedirs(DESTINO, exist_ok=True)

# 1) token de acesso (válido ~60 dias; usado só nesta execução)
req = urllib.request.Request(
    "https://id.twitch.tv/oauth2/token?" + urllib.parse.urlencode(
        {"client_id": cid, "client_secret": segredo, "grant_type": "client_credentials"}), method="POST")
token = json.load(urllib.request.urlopen(req, timeout=30))["access_token"]

# 2) ids dos jogos do nosso banco
banco = "catalogo_inicial.db"
ids = [r[0] for r in sqlite3.connect(banco).execute("SELECT id FROM jogos ORDER BY id")]
feitos = {}
if os.path.exists(CONTROLE):
    with open(CONTROLE, encoding="utf-8", newline="") as f:
        feitos = {int(r["id_jogo"]): r["image_id"] for r in csv.DictReader(f)}
pendentes = [i for i in ids if i not in feitos]
if args.limite:
    pendentes = pendentes[: args.limite]
print(f"{len(ids)} jogos no catálogo; {len(feitos)} já consultados; consultando {len(pendentes)} agora.")


def consultar_igdb(lote):
    corpo = f"fields id,cover.image_id; where id = ({','.join(map(str, lote))}); limit 500;"
    r = urllib.request.Request("https://api.igdb.com/v4/games", data=corpo.encode(), method="POST",
                               headers={"Client-ID": cid, "Authorization": f"Bearer {token}"})
    for tentativa in range(4):
        try:
            return json.load(urllib.request.urlopen(r, timeout=60))
        except Exception:
            time.sleep(2 + tentativa * 2)
    raise SystemExit("Falha ao consultar a API do IGDB (verifique as chaves e a internet).")


def baixar(item):
    jogo_id, image_id = item
    url = f"https://images.igdb.com/igdb/image/upload/t_cover_big/{image_id}.jpg"  # 264x374
    for tentativa in range(3):
        try:
            dados = urllib.request.urlopen(url, timeout=30).read()
            if Image is not None:
                im = Image.open(io.BytesIO(dados)).convert("RGB")
                buf = io.BytesIO()
                im.save(buf, "JPEG", quality=82, optimize=True)
                dados = buf.getvalue()
            with open(os.path.join(DESTINO, f"{jogo_id}.jpg"), "wb") as out:
                out.write(dados)
            return True
        except Exception:
            time.sleep(1 + tentativa)
    return False


novo = not os.path.exists(CONTROLE)
with open(CONTROLE, "a", encoding="utf-8", newline="") as controle:
    w = csv.writer(controle)
    if novo:
        w.writerow(["id_jogo", "image_id"])
    ok = falhas = sem_capa = 0
    for i in range(0, len(pendentes), 500):
        lote = pendentes[i : i + 500]
        resposta = consultar_igdb(lote)  # limite do IGDB: 4 consultas por segundo
        com_capa = {g["id"]: g["cover"]["image_id"] for g in resposta if g.get("cover")}
        with ThreadPoolExecutor(args.threads) as pool:
            resultados = list(pool.map(baixar, com_capa.items()))
        for (jid, imagem), deu_certo in zip(com_capa.items(), resultados):
            if deu_certo:
                w.writerow([jid, imagem]); ok += 1
            else:
                falhas += 1
        for jid in lote:  # jogos sem capa no IGDB também são anotados, para não consultar de novo
            if jid not in com_capa:
                w.writerow([jid, ""]); sem_capa += 1
        controle.flush()
        print(f"{min(i + 500, len(pendentes))}/{len(pendentes)}  capas baixadas={ok} sem capa no IGDB={sem_capa} falhas={falhas}", flush=True)
        time.sleep(0.3)

print("Pronto. Se houve falhas, apague as linhas correspondentes de dataset/capas_igdb.csv ou rode de novo.")
