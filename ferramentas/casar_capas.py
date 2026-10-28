"""Associa cada jogo do catálogo (IGDB) a uma imagem do RAWG, comparando o nome (e o ano, quando existe).

Entrada : dataset/all_games_*.csv  +  dataset/rawg_imagens.csv (gerado por baixar_capas.py)
Saída   : dataset/capas.csv  (id_jogo, nome, url_imagem, nome_rawg)  <- pequeno, usado pelo etl.py

Uso: python ferramentas/casar_capas.py
"""
import csv
import re
import sys
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone

csv.field_size_limit(sys.maxsize)
PASTA = "dataset"
ARQUIVOS = ["all_games_PlayStation.csv", "all_games_Xbox.csv", "all_games_Nintendo.csv"]


def normalizar(nome):
    s = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\(.*?\)|\[.*?\]", " ", s)          # tira "(2010)", "[PS4]"
    s = s.replace("&", " and ")
    s = re.sub(r"\bthe\b", " ", s)
    return re.sub(r"[^a-z0-9]+", "", s)


# Sufixos que indicam só outra versão do mesmo jogo ("Minecraft: Xbox 360 Edition" -> "Minecraft")
SUFIXO = re.compile(
    r"\s*[:\-–]\s*[^:\-–]*\b(edition|version|remaster(ed)?|remake|definitive|deluxe|premium|special|goty|"
    r"game of the year|complete|anniversary|collection)\b.*$", re.I)
TOLERANCIA_ANOS = 15


def escolher(candidatos, ano):
    """Entre os jogos do RAWG com o mesmo nome, devolve (url, nome) do ano mais próximo.

    O IGDB cria uma entrada por plataforma/relançamento (ex.: GTA V de 2013 e de 2022), enquanto o RAWG tem
    uma só por jogo; por isso aceitamos uma diferença grande de anos, mas sempre preferimos o ano mais próximo.
    """
    if not candidatos:
        return None
    if ano is None:
        return (candidatos[0][1], candidatos[0][2]) if len(candidatos) == 1 else None
    com_ano = [c for c in candidatos if c[0]]
    if not com_ano:
        return (candidatos[0][1], candidatos[0][2]) if len(candidatos) == 1 else None
    a, url, nome = min(com_ano, key=lambda c: abs(c[0] - ano))
    return (url, nome) if abs(a - ano) <= TOLERANCIA_ANOS else None


# 1) índice do RAWG: nome normalizado -> [(ano, url, nome)]
indice = defaultdict(list)
with open(f"{PASTA}/rawg_imagens.csv", encoding="utf-8", newline="") as f:
    for r in csv.DictReader(f):
        chave = normalizar(r["name"])
        if chave:
            ano = int(r["released"][:4]) if r["released"][:4].isdigit() else None
            indice[chave].append((ano, r["background_image"], r["name"]))

# 2) jogos do catálogo
vistos, casados, total = set(), 0, 0
with open(f"{PASTA}/capas.csv", "w", encoding="utf-8", newline="") as saida:
    w = csv.writer(saida)
    w.writerow(["id_jogo", "nome", "url_imagem", "nome_rawg"])
    for arquivo in ARQUIVOS:
        with open(f"{PASTA}/{arquivo}", encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                if r["id"] in vistos or not r["name"]:
                    continue
                vistos.add(r["id"])
                total += 1
                ano = None
                if r["first_release_date"] not in ("", "nan"):
                    ano = datetime.fromtimestamp(int(float(r["first_release_date"])), timezone.utc).year
                # 1ª tentativa: nome igual; 2ª: nome sem o sufixo "Edition/Remastered/..." (mesmo jogo, outra versão)
                melhor = None
                for chave in (normalizar(r["name"]), normalizar(SUFIXO.sub("", r["name"]))):
                    melhor = escolher(indice.get(chave), ano)
                    if melhor:
                        break
                if melhor:
                    w.writerow([r["id"], r["name"], melhor[0], melhor[1]])
                    casados += 1
print(f"{casados} de {total} jogos receberam imagem ({casados / total:.0%})")
