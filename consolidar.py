"""Junta várias fontes de dados no catálogo (rodar depois do etl.py).

Fontes (todas em dataset/):
  - IGDB/PlayMyData ........ já carregado pelo etl.py (base do catálogo)
  - Libretro (No-Intro) .... dataset/libretro/  -> acrescenta jogos que faltam nos consoles Nintendo antigos
                              (Game Boy, GBC, GBA, NES, SNES, N64, Virtual Boy) e preenche desenvolvedora/ano/gênero
  - Wikidata ............... dataset/wikidata.csv -> nome em português, descrição em português, desenvolvedora, editora

Cada jogo guarda de onde vieram os dados na coluna `fontes` (ex.: "IGDB; Wikidata").
Uso: python consolidar.py [catalogo_inicial.db]
"""
import csv
import glob
import os
import re
import sqlite3
import sys
import unicodedata

BANCO = sys.argv[1] if len(sys.argv) > 1 else "catalogo_inicial.db"
ID_BASE_NOVOS = 10_000_000  # ids dos jogos que vieram só do Libretro (não colidem com ids do IGDB)

# Sistema do Libretro -> id da categoria (plataforma do IGDB)
SISTEMAS_LIBRETRO = {
    "Nintendo - Game Boy": 33,
    "Nintendo - Game Boy Color": 22,
    "Nintendo - Game Boy Advance": 24,
    "Nintendo - Nintendo Entertainment System": 18,
    "Nintendo - Super Nintendo Entertainment System": 19,
    "Nintendo - Nintendo 64": 4,
    "Nintendo - Virtual Boy": 87,
}
# Nome da plataforma no Wikidata -> id da categoria
PLATAFORMAS_WIKIDATA = {
    "PlayStation": 7, "PlayStation 2": 8, "PlayStation 3": 9, "PlayStation 4": 48, "PlayStation 5": 167,
    "PlayStation Portable": 38, "PlayStation Vita": 46, "Xbox": 11, "Xbox 360": 12, "Xbox One": 49,
    "Xbox Series X and Series S": 169, "Nintendo Entertainment System": 18, "Super Nintendo Entertainment System": 19,
    "Nintendo 64": 4, "GameCube": 21, "Wii": 5, "Wii U": 41, "Nintendo Switch": 130, "Game Boy": 33,
    "Game Boy Color": 22, "Game Boy Advance": 24, "Nintendo DS": 20, "Nintendo 3DS": 37, "Virtual Boy": 87,
}
# Gêneros do Libretro -> nome (em português) na tabela generos
GENEROS = [("platform", "Plataforma"), ("shoot", "Tiro"), ("racing", "Corrida"), ("puzzle", "Quebra-cabeça"),
           ("role", "RPG"), ("rpg", "RPG"), ("sport", "Esportes"), ("fight", "Luta"), ("beat", "Luta"),
           ("adventure", "Aventura"), ("strategy", "Estratégia"), ("simulation", "Simulador"),
           ("pinball", "Pinball"), ("board", "Cartas e tabuleiro"), ("card", "Cartas e tabuleiro"),
           ("music", "Música"), ("rhythm", "Música"), ("arcade", "Arcade"), ("quiz", "Quiz/Trivia")]
IGNORAR = re.compile(r"\((Beta|Proto|Demo|Sample|Unl|Aftermarket|Pirate|Kiosk|Debug|Possible Proto|Not for Resale|"
                     r"Promo|Program|Test)", re.I)


def normalizar(nome):
    s = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\(.*?\)|\[.*?\]", " ", s).replace("&", " and ")
    s = re.sub(r"\bthe\b", " ", s)
    return re.sub(r"[^a-z0-9]+", "", s)


def sem_acento(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()


def limpar_titulo(nome):
    """'Legend of Zelda, The - Link's Awakening (USA) (Rev 1)' -> 'The Legend of Zelda: Link's Awakening'"""
    base = re.sub(r"\s*\(.*?\)|\s*\[.*?\]", "", nome).strip()
    m = re.match(r"^(.*?), (The|A|An)(?= - |:|$)(.*)$", base)
    if m:
        base = f"{m.group(2)} {m.group(1)}{m.group(3)}"
    return base.replace(" - ", ": ")


def ler_dat(caminho):
    """Lê um arquivo .dat (formato clrmamepro) e devolve uma lista de dicts com os campos de cada 'game ( ... )'."""
    with open(caminho, encoding="utf-8", errors="replace") as f:
        texto = f.read()
    jogos = []
    for bloco in re.findall(r"^game \(\n(.*?)^\)", texto, re.S | re.M):
        d = {k: v for k, v in re.findall(r'^\t(\w+) "(.*?)"\s*$', bloco, re.M)}
        crcs = re.findall(r"crc ([0-9A-Fa-f]{8})", bloco)
        d["crc"] = crcs[0].upper() if crcs else None
        jogos.append(d)
    return jogos


db = sqlite3.connect(BANCO)
db.execute("PRAGMA foreign_keys = ON")
colunas = {r[1] for r in db.execute("PRAGMA table_info(jogos)")}
for col in ("desenvolvedora", "editora", "nome_pt", "descricao_pt"):
    if col not in colunas:
        db.execute(f"ALTER TABLE jogos ADD COLUMN {col} TEXT")
if "fontes" not in colunas:
    db.execute("ALTER TABLE jogos ADD COLUMN fontes TEXT DEFAULT 'IGDB'")
db.execute("UPDATE jogos SET fontes='IGDB' WHERE fontes IS NULL")

generos_id = {nome: gid for gid, nome in db.execute("SELECT id, nome FROM generos")}


def indice_da_categoria(cat):
    """nome normalizado -> id do jogo, para os jogos da categoria."""
    idx = {}
    for jid, nome in db.execute(
            "SELECT j.id, j.nome FROM jogos j JOIN jogo_categoria jc ON jc.jogo_id=j.id WHERE jc.categoria_id=?", (cat,)):
        idx.setdefault(normalizar(nome), jid)
    return idx


def marcar_fonte(jid, fonte):
    db.execute("UPDATE jogos SET fontes = fontes || ? WHERE id=? AND fontes NOT LIKE ?",
               (f"; {fonte}", jid, f"%{fonte}%"))


# ---------- Libretro (No-Intro) ----------
estat = {"libretro_novos": 0, "libretro_enriquecidos": 0, "wikidata_enriquecidos": 0}
proximo_id = (db.execute("SELECT MAX(id) FROM jogos WHERE id >= ?", (ID_BASE_NOVOS,)).fetchone()[0] or ID_BASE_NOVOS - 1) + 1

for sistema, cat in SISTEMAS_LIBRETRO.items():
    caminho = f"dataset/libretro/no-intro/{sistema}.dat"
    if not os.path.exists(caminho):
        continue
    meta = {}  # crc -> {developer, releaseyear, genre}
    for tipo in ("developer", "releaseyear", "genre"):
        p = f"dataset/libretro/{tipo}/{sistema}.dat"
        if os.path.exists(p):
            for g in ler_dat(p):
                if g.get("crc") and tipo in g:
                    meta.setdefault(g["crc"], {})[tipo] = g[tipo]

    # agrupa as versões (regiões) do mesmo jogo; prefere USA/World/Europe como "principal"
    grupos = {}
    entradas = [g for g in ler_dat(caminho) if g.get("name") and not IGNORAR.search(g["name"])]
    entradas.sort(key=lambda g: 0 if re.search(r"\((USA|World|Europe)", g["name"]) else 1)
    for g in entradas:
        titulo = limpar_titulo(g["name"])
        chave = normalizar(titulo)
        if not chave:
            continue
        info = meta.get(g["crc"], {})
        grupo = grupos.setdefault(chave, {"titulo": titulo, "dev": None, "ano": None, "genero": None})
        grupo["dev"] = grupo["dev"] or info.get("developer")
        grupo["ano"] = grupo["ano"] or info.get("releaseyear")
        grupo["genero"] = grupo["genero"] or info.get("genre")

    existentes = indice_da_categoria(cat)
    for chave, g in grupos.items():
        ano = int(g["ano"]) if g["ano"] and g["ano"].isdigit() else None
        gen = next((nome for trecho, nome in GENEROS if g["genero"] and trecho in g["genero"].lower()), None)
        if chave in existentes:
            jid = existentes[chave]
            db.execute("UPDATE jogos SET desenvolvedora = COALESCE(desenvolvedora, ?), ano = COALESCE(ano, ?) WHERE id=?",
                       (g["dev"], ano, jid))
            if g["dev"] or ano:
                marcar_fonte(jid, "Libretro")
                estat["libretro_enriquecidos"] += 1
        else:
            jid = proximo_id
            proximo_id += 1
            db.execute(
                "INSERT INTO jogos (id, nome, ano, desenvolvedora, nome_busca, fontes) VALUES (?,?,?,?,?,?)",
                (jid, g["titulo"], ano, g["dev"], sem_acento(g["titulo"]), "Libretro (No-Intro)"))
            db.execute("INSERT INTO jogo_categoria VALUES (?,?)", (jid, cat))
            if gen and gen in generos_id:
                db.execute("INSERT OR IGNORE INTO jogo_genero VALUES (?,?)", (jid, generos_id[gen]))
            estat["libretro_novos"] += 1
    print(f"{sistema}: {len(grupos)} jogos distintos no Libretro")

# ---------- Wikidata ----------
if os.path.exists("dataset/wikidata.csv"):
    indices = {}
    with open("dataset/wikidata.csv", encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            cat = PLATAFORMAS_WIKIDATA.get(r["plataforma"])
            if not cat or not r["nome_en"]:
                continue
            idx = indices.get(cat) or indices.setdefault(cat, indice_da_categoria(cat))
            jid = idx.get(normalizar(r["nome_en"]))
            if not jid:
                continue
            nome_pt = r["nome_pt"] if r["nome_pt"] and r["nome_pt"] != r["nome_en"] else None
            db.execute(
                "UPDATE jogos SET nome_pt = COALESCE(nome_pt, ?), descricao_pt = COALESCE(descricao_pt, ?), "
                "desenvolvedora = COALESCE(desenvolvedora, ?), editora = COALESCE(editora, ?) WHERE id=?",
                (nome_pt, r["descricao_pt"] or None, r["desenvolvedora"] or None, r["editora"] or None, jid))
            marcar_fonte(jid, "Wikidata")
            estat["wikidata_enriquecidos"] += 1
else:
    print("aviso: dataset/wikidata.csv não encontrado (rode ferramentas/baixar_wikidata.py)")

# a busca passa a considerar também o nome em português
for jid, nome, nome_pt in db.execute("SELECT id, nome, nome_pt FROM jogos WHERE nome_pt IS NOT NULL").fetchall():
    db.execute("UPDATE jogos SET nome_busca=? WHERE id=?", (sem_acento(nome) + " " + sem_acento(nome_pt), jid))

db.commit()
print(estat)
for fonte, n in db.execute("SELECT fontes, COUNT(*) FROM jogos GROUP BY fontes ORDER BY 2 DESC LIMIT 8"):
    print(f"  {fonte}: {n}")
print("total de jogos:", db.execute("SELECT COUNT(*) FROM jogos").fetchone()[0])
# ---------- Exporta o catálogo consolidado em CSV (para publicar/conferir) ----------
os.makedirs("dataset", exist_ok=True)
with open("dataset/catalogo_consolidado.csv", "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    w.writerow(["id", "nome", "nome_pt", "ano", "data_lancamento", "plataformas", "marcas", "generos", "desenvolvedora",
                "editora", "nota_igdb", "resumo_en", "descricao_pt", "imagem_url", "fontes"])
    for r in db.execute("""
        SELECT j.id, j.nome, j.nome_pt, j.ano, j.data_lancamento,
          (SELECT GROUP_CONCAT(c.nome, ' | ') FROM jogo_categoria jc JOIN categorias c ON c.id=jc.categoria_id WHERE jc.jogo_id=j.id),
          (SELECT GROUP_CONCAT(DISTINCT c.familia) FROM jogo_categoria jc JOIN categorias c ON c.id=jc.categoria_id WHERE jc.jogo_id=j.id),
          (SELECT GROUP_CONCAT(g.nome, ' | ') FROM jogo_genero jg JOIN generos g ON g.id=jg.genero_id WHERE jg.jogo_id=j.id),
          j.desenvolvedora, j.editora, j.nota, j.resumo, j.descricao_pt, j.imagem_url, j.fontes
        FROM jogos j ORDER BY j.nome COLLATE NOCASE"""):
        w.writerow(r)
print("exportado: dataset/catalogo_consolidado.csv")
db.execute("VACUUM")
db.close()
