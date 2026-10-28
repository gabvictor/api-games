"""API do Catálogo de Jogos (PlayStation, Xbox e Nintendo) com perfis de usuário.

Endpoints principais (conforme a especificação do trabalho):
  GET/POST /cat/jogos · GET/PUT/DELETE /cat/jogos/{id}
  GET/POST/DELETE /cat/{id} · POST/GET/PUT/DELETE /perf[/{id}]
"""
import os
import shutil
import sqlite3
import unicodedata
from datetime import datetime, timezone

from flask import Flask, abort, g, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(BASE, "dados"))
SEED_DB = os.environ.get("SEED_DB", os.path.join(BASE, "catalogo_inicial.db"))
DATASET_DIR = os.environ.get("DATASET_DIR", os.path.join(BASE, "dataset"))
DB_PATH = os.path.join(DATA_DIR, "catalogo.db")

app = Flask(__name__, static_folder="web", static_url_path="")
app.json.ensure_ascii = False
app.json.sort_keys = False


# ---------- Banco ----------
def banco():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def fechar_banco(_):
    conn = g.pop("db", None)
    if conn:
        conn.close()


def preparar_banco():
    """Na primeira execução copia o catálogo pronto para a pasta de dados (que é um volume)."""
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(DB_PATH):
        if not os.path.exists(SEED_DB):
            raise SystemExit("catalogo_inicial.db não encontrado. Rode: python etl.py")
        shutil.copy(SEED_DB, DB_PATH)


# ---------- Erros em JSON ----------
def erro(msg, codigo):
    return jsonify({"erro": msg}), codigo


@app.errorhandler(HTTPException)
def erro_http(e):
    msgs = {404: "Recurso não encontrado", 405: "Método não permitido"}
    return erro(msgs.get(e.code, e.description), e.code)


def corpo_json():
    dados = request.get_json(silent=True)
    if not isinstance(dados, dict):
        abort(400, "Envie um corpo JSON (objeto) válido")
    return dados


def sem_acento(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()


# ---------- Serialização ----------
def jogos_completos(linhas):
    """Transforma linhas de `jogos` em dicts, anexando categorias e gêneros."""
    jogos = [dict(l) for l in linhas]
    for j in jogos:
        j.pop("nome_busca", None)
    if not jogos:
        return jogos
    ids = [j["id"] for j in jogos]
    marcas = ",".join("?" * len(ids))
    por_id = {j["id"]: j for j in jogos}
    for j in jogos:
        j["categorias"], j["generos"] = [], []
    if len(jogos) == 1:  # vídeos só na consulta de um jogo (GET /cat/jogos/{id})
        jogos[0]["videos"] = [
            {"youtube_id": r["youtube_id"], "titulo": r["titulo"], "url": f"https://www.youtube.com/watch?v={r['youtube_id']}"}
            for r in banco().execute("SELECT youtube_id, titulo FROM videos WHERE jogo_id=?", (ids[0],))]
    for r in banco().execute(
        f"SELECT jc.jogo_id, c.id, c.nome, c.familia FROM jogo_categoria jc "
        f"JOIN categorias c ON c.id=jc.categoria_id WHERE jc.jogo_id IN ({marcas}) ORDER BY c.nome", ids):
        por_id[r["jogo_id"]]["categorias"].append({"id": r["id"], "nome": r["nome"], "familia": r["familia"]})
    for r in banco().execute(
        f"SELECT jg.jogo_id, g.id, g.nome FROM jogo_genero jg "
        f"JOIN generos g ON g.id=jg.genero_id WHERE jg.jogo_id IN ({marcas}) ORDER BY g.nome", ids):
        por_id[r["jogo_id"]]["generos"].append({"id": r["id"], "nome": r["nome"]})
    return jogos


COLUNAS_LISTA = "j.id, j.nome, j.nome_pt, j.data_lancamento, j.ano, j.nota, j.resumo, j.imagem_url, j.desenvolvedora, j.fontes"


def buscar_jogo(jid):
    linha = banco().execute("SELECT * FROM jogos WHERE id=?", (jid,)).fetchone()
    return jogos_completos([linha])[0] if linha else None


def perfil_completo(pid):
    p = banco().execute("SELECT id, nome, criado_em FROM perfis WHERE id=?", (pid,)).fetchone()
    if not p:
        return None
    linhas = banco().execute(
        f"SELECT {COLUNAS_LISTA} FROM perfil_jogos pj JOIN jogos j ON j.id=pj.jogo_id "
        "WHERE pj.perfil_id=? ORDER BY pj.salvo_em DESC, j.nome", (pid,)).fetchall()
    d = dict(p)
    d["jogos"] = jogos_completos(linhas)
    return d


# ---------- Validação ----------
def lista_de_ids(valor, campo, tabela, obrigatoria=False):
    if not isinstance(valor, list) or not all(isinstance(i, int) and not isinstance(i, bool) for i in valor):
        abort(400, f"'{campo}' deve ser uma lista de números inteiros")
    valor = list(dict.fromkeys(valor))
    if obrigatoria and not valor:
        abort(400, f"Informe ao menos um item em '{campo}'")
    if valor:
        marcas = ",".join("?" * len(valor))
        achados = {r[0] for r in banco().execute(f"SELECT id FROM {tabela} WHERE id IN ({marcas})", valor)}
        faltando = [i for i in valor if i not in achados]
        if faltando:
            abort(400, f"'{campo}' contém ids inexistentes: {faltando}")
    return valor


def nome_valido(dados, obrigatorio=True, limite=120):
    nome = dados.get("nome")
    if nome is None and not obrigatorio:
        return None
    if not isinstance(nome, str) or not nome.strip() or len(nome.strip()) > limite:
        abort(400, f"'nome' é obrigatório (texto de 1 a {limite} caracteres)")
    return nome.strip()


def campos_jogo(dados, parcial):
    """Valida o corpo de POST/PUT de jogo; devolve (campos_simples, categorias, generos)."""
    campos = {}
    if not parcial or "nome" in dados:
        campos["nome"] = nome_valido(dados)
    if "data_lancamento" in dados:
        d = dados["data_lancamento"]
        if d is not None:
            try:
                ano = datetime.strptime(d, "%Y-%m-%d").year
            except (TypeError, ValueError):
                abort(400, "'data_lancamento' deve estar no formato AAAA-MM-DD")
            campos["data_lancamento"], campos["ano"] = d, ano
        else:
            campos["data_lancamento"] = campos["ano"] = None
    if "ano" in dados and "data_lancamento" not in dados:
        a = dados["ano"]
        if a is not None and (not isinstance(a, int) or isinstance(a, bool) or not 1950 <= a <= 2100):
            abort(400, "'ano' deve ser um inteiro entre 1950 e 2100")
        campos["ano"] = a
    for k in ("resumo", "historia"):
        if k in dados:
            if dados[k] is not None and not isinstance(dados[k], str):
                abort(400, f"'{k}' deve ser texto")
            campos[k] = dados[k]
    if "nota" in dados:
        n = dados["nota"]
        if n is not None and (isinstance(n, bool) or not isinstance(n, (int, float)) or not 0 <= n <= 100):
            abort(400, "'nota' deve ser um número de 0 a 100")
        campos["nota"] = n
    cats = lista_de_ids(dados["categorias"], "categorias", "categorias", True) if "categorias" in dados else None
    gens = lista_de_ids(dados["generos"], "generos", "generos") if "generos" in dados else None
    if not parcial and cats is None:
        abort(400, "'categorias' é obrigatório (lista com ids de categorias/plataformas)")
    return campos, cats, gens


def gravar_vinculos(jid, cats, gens):
    if cats is not None:
        banco().execute("DELETE FROM jogo_categoria WHERE jogo_id=?", (jid,))
        banco().executemany("INSERT INTO jogo_categoria VALUES (?,?)", [(jid, c) for c in cats])
    if gens is not None:
        banco().execute("DELETE FROM jogo_genero WHERE jogo_id=?", (jid,))
        banco().executemany("INSERT INTO jogo_genero VALUES (?,?)", [(jid, x) for x in gens])


# ---------- /cat/jogos ----------
@app.get("/cat/jogos")
def listar_jogos():
    a = request.args
    onde, params = [], []
    if a.get("q"):
        onde.append("j.nome_busca LIKE ?")
        params.append(f"%{sem_acento(a['q'])}%")
    if a.get("categoria"):
        onde.append("EXISTS (SELECT 1 FROM jogo_categoria jc WHERE jc.jogo_id=j.id AND jc.categoria_id=?)")
        params.append(a["categoria"])
    if a.get("familia"):
        onde.append("EXISTS (SELECT 1 FROM jogo_categoria jc JOIN categorias c ON c.id=jc.categoria_id "
                    "WHERE jc.jogo_id=j.id AND c.familia=? COLLATE NOCASE)")
        params.append(a["familia"])
    if a.get("genero"):
        onde.append("EXISTS (SELECT 1 FROM jogo_genero jg WHERE jg.jogo_id=j.id AND jg.genero_id=?)")
        params.append(a["genero"])
    if a.get("ano"):
        onde.append("j.ano=?")
        params.append(a["ano"])
    if a.get("com_imagem") == "1":
        onde.append("j.imagem_url IS NOT NULL")
    ordem = {
        "nome": "j.nome COLLATE NOCASE",
        "ano": "j.ano IS NULL, j.ano DESC",
        "nota": "j.nota IS NULL, j.nota DESC",
        "destaques": "j.imagem_url IS NULL, j.nota IS NULL, j.nota DESC",  # com capa e bem avaliados primeiro
    }.get(a.get("ordem", "nome"), "j.nome COLLATE NOCASE")
    try:
        pagina = max(1, int(a.get("pagina", 1)))
        por_pagina = min(100, max(1, int(a.get("por_pagina", 24))))
    except ValueError:
        abort(400, "'pagina' e 'por_pagina' devem ser números inteiros")
    clausula = ("WHERE " + " AND ".join(onde)) if onde else ""
    total = banco().execute(f"SELECT COUNT(*) FROM jogos j {clausula}", params).fetchone()[0]
    linhas = banco().execute(
        f"SELECT {COLUNAS_LISTA} FROM jogos j {clausula} ORDER BY {ordem}, j.id LIMIT ? OFFSET ?",
        params + [por_pagina, (pagina - 1) * por_pagina]).fetchall()
    return jsonify({"pagina": pagina, "por_pagina": por_pagina, "total": total, "resultados": jogos_completos(linhas)})


@app.post("/cat/jogos")
def cadastrar_jogo():
    campos, cats, gens = campos_jogo(corpo_json(), parcial=False)
    campos["nome_busca"] = sem_acento(campos["nome"])
    campos["fontes"] = "Cadastro manual"
    cur = banco().execute(
        f"INSERT INTO jogos ({','.join(campos)}) VALUES ({','.join('?' * len(campos))})", list(campos.values()))
    jid = cur.lastrowid
    gravar_vinculos(jid, cats, gens or [])
    banco().commit()
    resp = jsonify(buscar_jogo(jid))
    resp.status_code = 201
    resp.headers["Location"] = f"/cat/jogos/{jid}"
    return resp


@app.get("/cat/jogos/<int:jid>")
def mostrar_jogo(jid):
    jogo = buscar_jogo(jid)
    return jsonify(jogo) if jogo else erro("Jogo não encontrado", 404)


@app.put("/cat/jogos/<int:jid>")
def atualizar_jogo(jid):
    if not banco().execute("SELECT 1 FROM jogos WHERE id=?", (jid,)).fetchone():
        return erro("Jogo não encontrado", 404)
    campos, cats, gens = campos_jogo(corpo_json(), parcial=True)
    if "nome" in campos:
        campos["nome_busca"] = sem_acento(campos["nome"])
    if campos:
        sets = ",".join(f"{k}=?" for k in campos)
        banco().execute(f"UPDATE jogos SET {sets} WHERE id=?", list(campos.values()) + [jid])
    gravar_vinculos(jid, cats, gens)
    banco().commit()
    return jsonify(buscar_jogo(jid))


@app.delete("/cat/jogos/<int:jid>")
def apagar_jogo(jid):
    cur = banco().execute("DELETE FROM jogos WHERE id=?", (jid,))
    banco().commit()
    return ("", 204) if cur.rowcount else erro("Jogo não encontrado", 404)


# ---------- /cat (categorias = plataformas) ----------
CONSULTA_CATEGORIA = (
    "SELECT c.id, c.nome, c.familia, COUNT(jc.jogo_id) AS total_jogos FROM categorias c "
    "LEFT JOIN jogo_categoria jc ON jc.categoria_id=c.id {} GROUP BY c.id ORDER BY c.familia, c.nome")


@app.get("/cat")
def listar_categorias():
    return jsonify([dict(r) for r in banco().execute(CONSULTA_CATEGORIA.format("")).fetchall()])


@app.get("/cat/<int:cid>")
def mostrar_categoria(cid):
    r = banco().execute(CONSULTA_CATEGORIA.format("WHERE c.id=?"), (cid,)).fetchone()
    return jsonify(dict(r)) if r else erro("Categoria não encontrada", 404)


@app.post("/cat/<int:cid>")
def cadastrar_categoria(cid):
    dados = corpo_json()
    nome = nome_valido(dados, limite=60)
    familia = dados.get("familia")
    if familia is not None and (not isinstance(familia, str) or len(familia) > 40):
        abort(400, "'familia' deve ser texto de até 40 caracteres")
    try:
        banco().execute("INSERT INTO categorias VALUES (?,?,?)", (cid, nome, familia))
        banco().commit()
    except sqlite3.IntegrityError:
        return erro(f"Já existe uma categoria com o id {cid}", 400)
    resp = jsonify({"id": cid, "nome": nome, "familia": familia, "total_jogos": 0})
    resp.status_code = 201
    resp.headers["Location"] = f"/cat/{cid}"
    return resp


@app.delete("/cat/<int:cid>")
def apagar_categoria(cid):
    cur = banco().execute("DELETE FROM categorias WHERE id=?", (cid,))
    banco().commit()
    return ("", 204) if cur.rowcount else erro("Categoria não encontrada", 404)


# ---------- /perf (perfis) ----------
@app.get("/perf")
def listar_perfis():
    linhas = banco().execute(
        "SELECT p.id, p.nome, p.criado_em, COUNT(pj.jogo_id) AS total_jogos FROM perfis p "
        "LEFT JOIN perfil_jogos pj ON pj.perfil_id=p.id GROUP BY p.id ORDER BY p.nome").fetchall()
    return jsonify([dict(r) for r in linhas])


@app.post("/perf")
def cadastrar_perfil():
    nome = nome_valido(corpo_json(), limite=40)
    try:
        cur = banco().execute("INSERT INTO perfis(nome) VALUES (?)", (nome,))
        banco().commit()
    except sqlite3.IntegrityError:
        return erro("Já existe um perfil com esse nome", 400)
    resp = jsonify(perfil_completo(cur.lastrowid))
    resp.status_code = 201
    resp.headers["Location"] = f"/perf/{cur.lastrowid}"
    return resp


@app.get("/perf/<int:pid>")
def mostrar_perfil(pid):
    p = perfil_completo(pid)
    return jsonify(p) if p else erro("Perfil não encontrado", 404)


@app.put("/perf/<int:pid>")
def atualizar_perfil(pid):
    if not banco().execute("SELECT 1 FROM perfis WHERE id=?", (pid,)).fetchone():
        return erro("Perfil não encontrado", 404)
    dados = corpo_json()
    nome = nome_valido(dados, obrigatorio=False, limite=40) if "nome" in dados else None
    jogos = lista_de_ids(dados["jogos"], "jogos", "jogos") if "jogos" in dados else None
    if nome is None and jogos is None:
        abort(400, "Envie 'nome' e/ou 'jogos' (lista de ids) para atualizar")
    try:
        if nome is not None:
            banco().execute("UPDATE perfis SET nome=? WHERE id=?", (nome, pid))
        if jogos is not None:
            banco().execute("DELETE FROM perfil_jogos WHERE perfil_id=?", (pid,))
            banco().executemany("INSERT INTO perfil_jogos(perfil_id, jogo_id) VALUES (?,?)", [(pid, j) for j in jogos])
        banco().commit()
    except sqlite3.IntegrityError:
        banco().rollback()
        return erro("Já existe um perfil com esse nome", 400)
    return jsonify(perfil_completo(pid))


@app.delete("/perf/<int:pid>")
def apagar_perfil(pid):
    cur = banco().execute("DELETE FROM perfis WHERE id=?", (pid,))
    banco().commit()
    return ("", 204) if cur.rowcount else erro("Perfil não encontrado", 404)


# Atalhos extras usados pelo site (equivalentes a um PUT /perf/{id} com a lista de jogos)
@app.put("/perf/<int:pid>/jogos/<int:jid>")
def salvar_jogo_no_perfil(pid, jid):
    if not banco().execute("SELECT 1 FROM perfis WHERE id=?", (pid,)).fetchone():
        return erro("Perfil não encontrado", 404)
    if not banco().execute("SELECT 1 FROM jogos WHERE id=?", (jid,)).fetchone():
        return erro("Jogo não encontrado", 404)
    banco().execute("INSERT OR IGNORE INTO perfil_jogos(perfil_id, jogo_id) VALUES (?,?)", (pid, jid))
    banco().commit()
    return jsonify(perfil_completo(pid))


@app.delete("/perf/<int:pid>/jogos/<int:jid>")
def remover_jogo_do_perfil(pid, jid):
    cur = banco().execute("DELETE FROM perfil_jogos WHERE perfil_id=? AND jogo_id=?", (pid, jid))
    banco().commit()
    return ("", 204) if cur.rowcount else erro("Esse jogo não está salvo neste perfil", 404)


# ---------- Extras de consulta ----------
@app.get("/generos")
def listar_generos():
    return jsonify([dict(r) for r in banco().execute("SELECT id, nome FROM generos ORDER BY nome")])


@app.get("/estatisticas")
def estatisticas():
    b = banco()
    por_familia = b.execute(
        "SELECT c.familia, COUNT(DISTINCT jc.jogo_id) AS jogos FROM jogo_categoria jc "
        "JOIN categorias c ON c.id=jc.categoria_id GROUP BY c.familia").fetchall()
    return jsonify({
        "total_jogos": b.execute("SELECT COUNT(*) FROM jogos").fetchone()[0],
        "total_categorias": b.execute("SELECT COUNT(*) FROM categorias").fetchone()[0],
        "total_perfis": b.execute("SELECT COUNT(*) FROM perfis").fetchone()[0],
        "por_familia": {r["familia"]: r["jogos"] for r in por_familia},
    })


FONTE = {
    "nome": "PlayMyData: a curated dataset of multi-platform video games",
    "descricao": ("Conjunto de dados acadêmico com ~100 mil jogos de PlayStation, Xbox, Nintendo e PC, "
                  "coletado do IGDB (Internet Game Database) e publicado para pesquisa em Engenharia de Software."),
    "autores": "Riccardo Rubei, Claudio Di Sipio, Davide Di Ruscio e colegas (Universidade de L'Aquila)",
    "publicacao": "MSR 2024 – Mining Software Repositories (Data and Tool Showcase)",
    "licenca": "Creative Commons Atribuição 4.0 Internacional (CC BY 4.0)",
    "licenca_url": "https://creativecommons.org/licenses/by/4.0/deed.pt-br",
    "pagina_dataset": "https://zenodo.org/records/10797761",
    "artigo": "https://arxiv.org/abs/2401.08561",
    "origem_original": "https://www.igdb.com",
    "fonte_imagens": {
        "nome": "Video Games Dataset (dados do RAWG) — Hugging Face",
        "descricao": ("Base com ~900 mil jogos que traz o endereço (URL) de uma imagem de cada jogo. "
                      "Usamos só o nome, o ano e a URL da imagem, e ligamos aos jogos do catálogo pelo nome e ano de lançamento."),
        "autor": "atalaydenknalbant (dados originais do RAWG.io)",
        "licenca": "CC0 1.0 (domínio público)",
        "pagina": "https://huggingface.co/datasets/atalaydenknalbant/video-games-dataset",
        "origem_original": "https://rawg.io",
        "observacao": ("As imagens NÃO ficam salvas no projeto: o navegador as carrega do servidor do RAWG (precisa de internet). "
                       "Sem internet, ou para jogos sem imagem, o site mostra uma capa gerada com ícones."),
    },
    "fontes_extras": [
        {"nome": "Wikidata", "uso": "Nome e descrição em português, desenvolvedora e editora",
         "licenca": "CC0 1.0 (domínio público)", "pagina": "https://www.wikidata.org",
         "arquivo": "wikidata.csv", "como": "ferramentas/baixar_wikidata.py (consultas SPARQL)"},
        {"nome": "Libretro database (listas No-Intro)", "uso": "Jogos que faltavam nos consoles Nintendo antigos, além de desenvolvedora, ano e gênero",
         "licenca": "CC BY-SA 4.0 (exige citar a fonte e manter a mesma licença)",
         "pagina": "https://github.com/libretro/libretro-database", "arquivo": "libretro/",
         "como": "arquivos .dat baixados do GitHub (metadat/no-intro, developer, releaseyear, genre)"},
        {"nome": "IGDB (Twitch) — capas oficiais", "uso": "Capa (box art) de cada jogo, casada pelo id",
         "licenca": "Termos da API do IGDB/Twitch (uso gratuito não comercial, citar a fonte)",
         "pagina": "https://api-docs.igdb.com", "arquivo": "capas_igdb.csv",
         "como": "ferramentas/baixar_capas_igdb.py (exige chave gratuita da Twitch)"},
    ],
    "arquivos_usados": [
        {"arquivo": "all_games_PlayStation.csv", "conteudo": "Jogos de PlayStation (PS1 a PS5, PSP e Vita)"},
        {"arquivo": "all_games_Xbox.csv", "conteudo": "Jogos de Xbox (original, 360, One e Series X|S)"},
        {"arquivo": "all_games_Nintendo.csv", "conteudo": "Jogos de todos os consoles Nintendo"},
        {"arquivo": "platforms.csv", "conteudo": "Lista de plataformas do IGDB (id e nome)"},
        {"arquivo": "genres.csv", "conteudo": "Lista de gêneros do IGDB (id e nome)"},
        {"arquivo": "video_ids.csv", "conteudo": "Ligação entre cada jogo e o vídeo do YouTube cadastrado no IGDB"},
        {"arquivo": "all_videos.csv", "conteudo": "Endereço e título (Trailer, Gameplay...) de cada vídeo do YouTube"},
        {"arquivo": "capas.csv", "conteudo": "Endereço da imagem de cada jogo (gerado por ferramentas/casar_capas.py)"},
    ],
}


@app.get("/fontes")
def fontes():
    arquivos = []
    for a in FONTE["arquivos_usados"]:
        caminho = os.path.join(DATASET_DIR, a["arquivo"])
        tamanho = os.path.getsize(caminho) if os.path.exists(caminho) else None
        arquivos.append({**a, "tamanho_bytes": tamanho, "download": f"/dataset/{a['arquivo']}"})
    return jsonify({**FONTE, "arquivos_usados": arquivos})


@app.get("/dataset/<path:nome>")
def baixar_dataset(nome):
    return send_from_directory(DATASET_DIR, nome, as_attachment=True)


@app.get("/")
def inicio():
    return send_from_directory(app.static_folder, "index.html")


preparar_banco()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), debug=False)
