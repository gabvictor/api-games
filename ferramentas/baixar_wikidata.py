"""Baixa do Wikidata (licença CC0) nome em português, descrição, desenvolvedora, editora e data de lançamento
dos jogos de cada plataforma do catálogo.

Saída: dataset/wikidata.csv  (plataforma, qid, nome_en, nome_pt, descricao_pt, desenvolvedora, editora, data)
Uso:   python ferramentas/baixar_wikidata.py
Fonte: https://www.wikidata.org  ·  consultas SPARQL em https://query.wikidata.org
"""
import csv
import io
import time
import urllib.parse
import urllib.request

# nome -> QID do Wikidata (None = procurar pelo nome em inglês). Plataformas com vários itens de mesmo nome
# (ex.: "Xbox One") precisam do QID para a consulta não estourar o tempo limite.
PLATAFORMAS = {
    "PlayStation": "Q10677", "PlayStation 2": "Q10680", "PlayStation 3": "Q10683", "PlayStation 4": "Q5014725",
    "PlayStation 5": "Q63184502", "PlayStation Portable": "Q170325", "PlayStation Vita": "Q188808",
    "Xbox": "Q132020", "Xbox 360": "Q48263", "Xbox One": "Q13361286", "Xbox Series X and Series S": "Q98973368",
    "Nintendo Entertainment System": None, "Super Nintendo Entertainment System": None, "Nintendo 64": None,
    "GameCube": "Q182172", "Wii": None, "Wii U": None, "Nintendo Switch": "Q19610114", "Game Boy": None,
    "Game Boy Color": None, "Game Boy Advance": "Q188642", "Nintendo DS": None, "Nintendo 3DS": None,
    "Virtual Boy": None, "Family Computer Disk System": None,
}

CONSULTA = """
SELECT ?item (SAMPLE(?n) AS ?nome) (SAMPLE(?npt) AS ?nome_pt) (SAMPLE(?dpt) AS ?desc_pt)
       (SAMPLE(?dv) AS ?dev) (SAMPLE(?pb) AS ?pub) (MIN(?dt) AS ?data) WHERE {
  %s
  ?item wdt:P400 ?plat ; wdt:P31 wd:Q7889 ; rdfs:label ?n . FILTER(LANG(?n)="en")
  OPTIONAL { ?item rdfs:label ?npt . FILTER(LANG(?npt)="pt") }
  OPTIONAL { ?item schema:description ?dpt . FILTER(LANG(?dpt)="pt") }
  OPTIONAL { ?item wdt:P178 ?d . ?d rdfs:label ?dv . FILTER(LANG(?dv)="en") }
  OPTIONAL { ?item wdt:P123 ?p . ?p rdfs:label ?pb . FILTER(LANG(?pb)="en") }
  OPTIONAL { ?item wdt:P577 ?dt }
  %s
} GROUP BY ?item LIMIT 50000
"""

# Plataformas grandes estouram o tempo limite do Wikidata; nesse caso consultamos por faixas de ano.
FAIXAS = [(1970, 1999), (2000, 2005), (2006, 2009), (2010, 2012), (2013, 2015), (2016, 2017), (2018, 2019),
          (2020, 2021), (2022, 2023), (2024, 2026)]


def filtro_ano(a, b):
    return f"?item wdt:P577 ?dtf . FILTER(YEAR(?dtf) >= {a} && YEAR(?dtf) <= {b})"


def consultar(plat, filtro=""):
    qid = PLATAFORMAS[plat]
    plataforma = f"VALUES ?plat {{ wd:{qid} }}" if qid else f'?plat rdfs:label "{plat}"@en .'
    url = "https://query.wikidata.org/sparql?" + urllib.parse.urlencode({"query": CONSULTA % (plataforma, filtro)})
    req = urllib.request.Request(url, headers={
        "Accept": "text/csv", "User-Agent": "trabalho-faculdade-catalogo-jogos/1.0 (projeto academico)"})
    for tentativa in range(2):
        try:
            texto = urllib.request.urlopen(req, timeout=75).read().decode("utf-8")
            return list(csv.DictReader(io.StringIO(texto)))
        except Exception as e:
            print(f"  tentativa {tentativa + 1} falhou ({plat} {filtro[-28:]}): {e}", flush=True)
            time.sleep(5 * (tentativa + 1))
    return None


with open("dataset/wikidata.csv", "w", encoding="utf-8", newline="", buffering=1) as saida:
    w = csv.writer(saida)
    w.writerow(["plataforma", "qid", "nome_en", "nome_pt", "descricao_pt", "desenvolvedora", "editora", "data"])
    total = 0
    for plat in PLATAFORMAS:
        linhas = consultar(plat)
        if not linhas:  # vazio ou estourou o tempo: tenta por faixas de ano
            linhas = []
            for a, b in FAIXAS:
                linhas += consultar(plat, filtro_ano(a, b)) or []
                time.sleep(1)
        vistos = set()
        for r in linhas:
            if r["item"] in vistos:
                continue
            vistos.add(r["item"])
            w.writerow([plat, r["item"].rsplit("/", 1)[-1], r["nome"], r["nome_pt"], r["desc_pt"],
                        r["dev"], r["pub"], r["data"][:10]])
        total += len(vistos)
        print(f"{plat}: {len(vistos)} jogos", flush=True)
        time.sleep(2)  # gentileza com o servidor público
print("Pronto: dataset/wikidata.csv,", total, "linhas", flush=True)
