"""Exporta o catálogo para arquivos JSON estáticos, para o site funcionar SEM backend (ex.: GitHub Pages).

Saída em web/dados/:
  indice.json      lista compacta de todos os jogos (busca, filtros e cartões)
  categorias.json, generos.json, fontes.json
  detalhe/N.json   resumo, história, vídeos etc., em 200 blocos (id % 200), carregados só ao abrir um jogo

Uso: python ferramentas/exportar_estatico.py [catalogo_inicial.db]   (rode depois de etl.py e consolidar.py)
"""
import json
import os
import shutil
import sqlite3
import sys
import tempfile

BANCO = sys.argv[1] if len(sys.argv) > 1 else "catalogo_inicial.db"
SAIDA = os.path.join("web", "dados")
BLOCOS = 200
PREFIXO_IMG = "https://media.rawg.io/media/games/"

shutil.rmtree(SAIDA, ignore_errors=True)
os.makedirs(os.path.join(SAIDA, "detalhe"))
db = sqlite3.connect(BANCO)
db.row_factory = sqlite3.Row


def salvar(nome, dados):
    with open(os.path.join(SAIDA, nome), "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, separators=(",", ":"))


cats, gens = {}, {}
for r in db.execute("SELECT jogo_id, categoria_id FROM jogo_categoria ORDER BY categoria_id"):
    cats.setdefault(r[0], []).append(r[1])
for r in db.execute("SELECT jogo_id, genero_id FROM jogo_genero ORDER BY genero_id"):
    gens.setdefault(r[0], []).append(r[1])
videos = {}
for r in db.execute("SELECT jogo_id, youtube_id, titulo FROM videos"):
    videos.setdefault(r[0], []).append([r[1], r[2]])

indice, blocos = [], {}
for j in db.execute("SELECT * FROM jogos ORDER BY id"):
    img = j["imagem_url"] or ""
    if img.startswith(PREFIXO_IMG):
        img = img[len(PREFIXO_IMG):]
    nota = int(round(j["nota"])) if j["nota"] is not None else -1
    # [id, nome, nome_pt, ano, nota(0-100 ou -1), imagem, [categorias], [gêneros]]
    indice.append([j["id"], j["nome"], j["nome_pt"] or "", j["ano"] or 0, nota, img,
                   cats.get(j["id"], []), gens.get(j["id"], [])])
    det = {k: j[k] for k in ("data_lancamento", "resumo", "historia", "descricao_pt", "desenvolvedora", "editora",
                             "fontes", "nota", "tempo_principal", "tempo_extra", "tempo_completo")}
    det = {k: v for k, v in det.items() if v is not None}
    if j["id"] in videos:
        det["videos"] = videos[j["id"]]
    blocos.setdefault(j["id"] % BLOCOS, {})[str(j["id"])] = det

salvar("indice.json", indice)
for n, dados in blocos.items():
    salvar(f"detalhe/{n}.json", dados)
salvar("categorias.json", [dict(r) for r in db.execute("SELECT id, nome, familia FROM categorias ORDER BY familia, nome")])
salvar("generos.json", [dict(r) for r in db.execute("SELECT id, nome FROM generos ORDER BY nome")])

# /fontes: pede para a própria API (assim o texto fica em um lugar só)
os.environ["DATA_DIR"] = tempfile.mkdtemp()
os.environ["SEED_DB"] = os.path.abspath(BANCO)
sys.path.insert(0, ".")
from app import app  # noqa: E402

fontes = app.test_client().get("/fontes").json
for a in fontes["arquivos_usados"]:
    a["download"] = a["download"].lstrip("/")  # relativo: funciona em github.io/repositorio/
salvar("fontes.json", fontes)

tam = sum(os.path.getsize(os.path.join(p, f)) for p, _, fs in os.walk(SAIDA) for f in fs) / 1e6
print(f"{len(indice)} jogos exportados para {SAIDA}/ ({tam:.1f} MB, {len(blocos)} blocos de detalhe)")
