"""ETL: converte os CSVs do dataset PlayMyData (IGDB) em um banco SQLite em português.

Uso: python etl.py [pasta_do_dataset] [arquivo_de_saida]
"""
import ast
import csv
import math
import sqlite3
import sys
import unicodedata
from datetime import datetime, timezone

csv.field_size_limit(sys.maxsize)

PASTA = sys.argv[1] if len(sys.argv) > 1 else "dataset"
SAIDA = sys.argv[2] if len(sys.argv) > 2 else "catalogo_inicial.db"

# Categorias = plataformas. Mapa: id da plataforma no IGDB -> marca (família)
FAMILIAS = {
    "PlayStation": [7, 8, 9, 48, 167, 38, 46],
    "Xbox": [11, 12, 49, 169],
    "Nintendo": [18, 19, 58, 4, 416, 21, 5, 41, 130, 33, 22, 24, 87, 20, 159, 37, 137, 47],
}
FAMILIA_DA_PLATAFORMA = {p: f for f, ids in FAMILIAS.items() for p in ids}
ARQUIVOS = ["all_games_PlayStation.csv", "all_games_Xbox.csv", "all_games_Nintendo.csv"]

# Nomes dos gêneros em português (o IGDB original está em inglês)
GENEROS_PT = {
    "Fighting": "Luta", "Shooter": "Tiro", "Music": "Música", "Platform": "Plataforma",
    "Puzzle": "Quebra-cabeça", "Racing": "Corrida", "Real Time Strategy (RTS)": "Estratégia em tempo real (RTS)",
    "Role-playing (RPG)": "RPG", "Simulator": "Simulador", "Sport": "Esportes", "Strategy": "Estratégia",
    "Turn-based strategy (TBS)": "Estratégia por turnos", "Tactical": "Tático", "Quiz": "Quiz/Trivia",
    "Hack and slash": "Hack and slash", "Pinball": "Pinball", "Adventure": "Aventura", "Arcade": "Arcade",
    "Visual Novel": "Visual novel", "Indie": "Indie", "Card & Board Game": "Cartas e tabuleiro",
    "MOBA": "MOBA", "Point-and-click": "Point-and-click",
}


def numero(v, tipo=float):
    if v is None or v in ("", "nan", "Missing"):
        return None
    try:
        x = tipo(float(v))
    except ValueError:
        return None
    return None if isinstance(x, float) and math.isnan(x) else x


def texto(v):
    return None if v in (None, "", "nan", "Missing") else v.strip()


def sem_acento(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()


def lista_ids(v):
    try:
        return [int(i) for i in ast.literal_eval(v)]
    except (ValueError, SyntaxError):
        return []


db = sqlite3.connect(SAIDA)
db.executescript(
    """
    DROP TABLE IF EXISTS videos;
    DROP TABLE IF EXISTS perfil_jogos; DROP TABLE IF EXISTS perfis;
    DROP TABLE IF EXISTS jogo_genero; DROP TABLE IF EXISTS jogo_categoria;
    DROP TABLE IF EXISTS jogos; DROP TABLE IF EXISTS categorias; DROP TABLE IF EXISTS generos;
    CREATE TABLE categorias (id INTEGER PRIMARY KEY, nome TEXT NOT NULL, familia TEXT);
    CREATE TABLE generos (id INTEGER PRIMARY KEY, nome TEXT NOT NULL, nome_original TEXT);
    CREATE TABLE jogos (
        id INTEGER PRIMARY KEY, nome TEXT NOT NULL, data_lancamento TEXT, ano INTEGER,
        resumo TEXT, historia TEXT, nota REAL, nota_critica REAL, qtd_criticas INTEGER,
        tempo_principal REAL, tempo_extra REAL, tempo_completo REAL, imagem_url TEXT,
        nome_busca TEXT  -- nome em minúsculas e sem acento, para pesquisar "pokemon" e achar "Pokémon"
    );
    CREATE TABLE jogo_categoria (
        jogo_id INTEGER NOT NULL REFERENCES jogos(id) ON DELETE CASCADE,
        categoria_id INTEGER NOT NULL REFERENCES categorias(id) ON DELETE CASCADE,
        PRIMARY KEY (jogo_id, categoria_id)
    );
    CREATE TABLE jogo_genero (
        jogo_id INTEGER NOT NULL REFERENCES jogos(id) ON DELETE CASCADE,
        genero_id INTEGER NOT NULL REFERENCES generos(id) ON DELETE CASCADE,
        PRIMARY KEY (jogo_id, genero_id)
    );
    CREATE TABLE videos (
        jogo_id INTEGER NOT NULL REFERENCES jogos(id) ON DELETE CASCADE,
        youtube_id TEXT NOT NULL, titulo TEXT, PRIMARY KEY (jogo_id, youtube_id)
    );
    CREATE TABLE perfis (
        id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL UNIQUE COLLATE NOCASE,
        criado_em TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE perfil_jogos (
        perfil_id INTEGER NOT NULL REFERENCES perfis(id) ON DELETE CASCADE,
        jogo_id INTEGER NOT NULL REFERENCES jogos(id) ON DELETE CASCADE,
        salvo_em TEXT DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (perfil_id, jogo_id)
    );
    """
)

with open(f"{PASTA}/platforms.csv", encoding="utf-8") as f:
    for linha in csv.reader(f):
        if linha and linha[0].isdigit() and int(linha[0]) in FAMILIA_DA_PLATAFORMA:
            db.execute("INSERT INTO categorias VALUES (?,?,?)",
                       (int(linha[0]), linha[1], FAMILIA_DA_PLATAFORMA[int(linha[0])]))

with open(f"{PASTA}/genres.csv", encoding="utf-8") as f:
    for linha in csv.DictReader(f):
        original = linha["genre"]
        db.execute("INSERT INTO generos VALUES (?,?,?)",
                   (int(linha["genre_id"]), GENEROS_PT.get(original, original), original))

# Imagens: dataset/capas.csv (gerado por ferramentas/casar_capas.py a partir do dataset RAWG)
imagens = {}
try:
    with open(f"{PASTA}/capas.csv", encoding="utf-8", newline="") as f:
        imagens = {int(r["id_jogo"]): r["url_imagem"] for r in csv.DictReader(f)}
except FileNotFoundError:
    print("aviso: dataset/capas.csv não encontrado; jogos ficarão sem imagem")

vistos = set()
for arquivo in ARQUIVOS:
    with open(f"{PASTA}/{arquivo}", encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            gid = numero(r["id"], int)
            cats = [p for p in lista_ids(r["platforms"]) if p in FAMILIA_DA_PLATAFORMA]
            if gid is None or gid in vistos or not cats or not texto(r["name"]):
                continue
            vistos.add(gid)
            ts = numero(r["first_release_date"], int)
            data = ano = None
            if ts is not None:
                d = datetime.fromtimestamp(ts, timezone.utc)
                data, ano = d.strftime("%Y-%m-%d"), d.year
            db.execute(
                "INSERT INTO jogos VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (gid, texto(r["name"]), data, ano, texto(r["summary"]), texto(r["storyline"]),
                 numero(r["rating"]), numero(r["review_score"]), numero(r["review_count"], int),
                 numero(r["main"]), numero(r["extra"]), numero(r["completionist"]), imagens.get(gid),
                 sem_acento(texto(r["name"]))),
            )
            db.executemany("INSERT OR IGNORE INTO jogo_categoria VALUES (?,?)", [(gid, c) for c in cats])
            db.executemany("INSERT OR IGNORE INTO jogo_genero VALUES (?,?)",
                           [(gid, g) for g in lista_ids(r["genres"])])

# Vídeos do YouTube (trailers/gameplay) ligados aos jogos pelo id do IGDB
try:
    def youtube_id(url):
        return url.split("v=")[-1] if "youtube.com/watch?v=" in url else None

    titulos = {}
    with open(f"{PASTA}/all_videos.csv", encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            titulos[r["id_video"]] = r["name"]
    with open(f"{PASTA}/video_ids.csv", encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            vid, jogo = youtube_id(r["id_video"]), numero(r["id_game"], int)
            if vid and jogo in vistos:
                db.execute("INSERT OR IGNORE INTO videos VALUES (?,?,?)", (jogo, vid, titulos.get(r["id_video"])))
except FileNotFoundError:
    print("aviso: all_videos.csv/video_ids.csv não encontrados; jogos ficarão sem vídeo")

db.executescript(
    """
    CREATE INDEX idx_jogos_nome ON jogos(nome COLLATE NOCASE);
    CREATE INDEX idx_jogos_ano ON jogos(ano);
    CREATE INDEX idx_jc_categoria ON jogo_categoria(categoria_id, jogo_id);
    CREATE INDEX idx_jg_genero ON jogo_genero(genero_id, jogo_id);
    """
)
db.commit()
print("jogos:", db.execute("SELECT COUNT(*) FROM jogos").fetchone()[0])
print("com vídeo:", db.execute("SELECT COUNT(DISTINCT jogo_id) FROM videos").fetchone()[0])
print("com imagem:", db.execute("SELECT COUNT(*) FROM jogos WHERE imagem_url IS NOT NULL").fetchone()[0])
for fam, n in db.execute(
    "SELECT c.familia, COUNT(DISTINCT jc.jogo_id) FROM jogo_categoria jc "
    "JOIN categorias c ON c.id=jc.categoria_id GROUP BY 1"
):
    print(fam, n)
db.execute("VACUUM")
db.close()
