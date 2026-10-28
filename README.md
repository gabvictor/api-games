# Catálogo de Jogos — API em Python

**Equipe:** Gabriel Victor, Matheus Salomão e Lucas Lima
**Conceito:** catálogo de jogos de diversas plataformas, separados por categoria (cada plataforma é uma categoria).
**Linguagem:** Python 3 (Flask) · **Banco:** SQLite · **Site:** HTML/CSS/JS · **Container:** Docker

API REST com ~41 mil jogos de **PlayStation (PS1 a PS5, PSP e Vita)**, **Xbox (original, 360, One e Series X|S)** e **todos os consoles Nintendo**, funcionando **100% offline**. Cada pessoa pode criar um **perfil** e salvar/excluir jogos nele.

---

## 1. Onde está cada coisa (caminhos)

| O quê | Caminho |
|---|---|
| **Dataset baixado (CSVs originais)** | `dataset/` |
| Imagens: lista de URLs gerada | `dataset/capas.csv` · scripts em `ferramentas/` |
| Script que trata os dados (ETL) | `etl.py` |
| Banco gerado a partir do dataset | `catalogo_inicial.db` (gerado pelo `etl.py`) |
| API (todos os endpoints) | `app.py` |
| Site (catálogo, documentação da API, fontes) | `web/` |
| Testes automáticos | `tests/test_api.py` |
| Docker | `Dockerfile`, `docker-compose.yml` |

O site também mostra tudo isso para o professor: página **Sobre e fontes dos dados** (`/sobre.html`) e **Documentação da API** (`/api.html`).

## 2. Dataset: de onde veio

- **Nome:** PlayMyData — *a curated dataset of multi-platform video games*
- **Link:** https://zenodo.org/records/10797761 (artigo: https://arxiv.org/abs/2401.08561)
- **Origem das informações:** IGDB (Internet Game Database, https://www.igdb.com)
- **Autores:** Riccardo Rubei, Claudio Di Sipio, Davide Di Ruscio e colegas (Universidade de L'Aquila), publicado no MSR 2024
- **Licença:** CC BY 4.0 — pode usar e redistribuir citando a fonte (o site já cita)

Arquivos baixados (pasta `dataset/`), 36 MB no total:

| Arquivo | Conteúdo | Tamanho |
|---|---|---|
| `all_games_PlayStation.csv` | jogos de PlayStation | 15,3 MB |
| `all_games_Xbox.csv` | jogos de Xbox | 9,1 MB |
| `all_games_Nintendo.csv` | jogos de Nintendo | 11,4 MB |
| `platforms.csv` | lista de plataformas (id, nome) | 3,5 kB |
| `genres.csv` | lista de gêneros (id, nome) | 331 B |

Não baixamos o `screenshots.zip` (2,8 GB).

### Imagens dos jogos (segunda fonte)

O dataset do IGDB não tem capas. Para ter imagem, usamos um segundo dataset:

- **Nome:** Video Games Dataset (dados do RAWG) — https://huggingface.co/datasets/atalaydenknalbant/video-games-dataset · licença **CC0** · origem: https://rawg.io
- **`ferramentas/baixar_capas.py`** lê só 4 colunas (nome, ano, URL da imagem) do arquivo de 1 GB → `dataset/rawg_imagens.csv` (~100 MB, não vai para o Git/Docker).
- **`ferramentas/casar_capas.py`** liga cada jogo do catálogo à imagem pelo nome + ano → **`dataset/capas.csv`** (21.302 dos 41.226 jogos, cerca de 52%).
- ⚠️ As imagens **não ficam salvas no projeto**: o navegador as carrega do servidor do RAWG (precisa de internet). Sem internet, ou nos jogos sem imagem, o site mostra uma **capa gerada** com a cor e o ícone da marca e um emoji do gênero (ícones desenhados para o trabalho, não são logos oficiais).

**Tratamento (`etl.py`):** filtra as plataformas pedidas → remove jogos duplicados → converte datas (Unix → AAAA-MM-DD) → troca `Missing`/`nan` por vazio → traduz os gêneros para português → grava no SQLite.

**Resultado:** 41.226 jogos — PlayStation 23.642 · Nintendo 22.960 · Xbox 14.335 (um jogo pode estar em mais de uma marca).

**Limitações:** o IGDB tem pouca cobertura dos consoles mais antigos (ex.: poucos jogos de Game Boy; Virtual Boy sem registros); descrições em inglês; dados coletados em 2023/2024.

## 3. Como rodar

### Opção A — Docker (recomendado)

```bash
docker compose up -d --build
```

Abra http://localhost:8000. Os dados cadastrados (jogos novos e perfis) ficam no volume `dados-catalogo`. Para parar: `docker compose down` (e `docker compose down -v` para apagar os dados).

### Opção B — Python direto (sem Docker)

```bash
python -m venv .venv
.venv\Scripts\activate          # Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt
python etl.py dataset catalogo_inicial.db    # gera o banco a partir dos CSVs (uma vez)
python app.py                                # sobe em http://localhost:8000
```

## 4. Como testar

```bash
python -m unittest discover -s tests -v
```

Os testes usam uma cópia temporária do banco e cobrem os 12 endpoints, incluindo os códigos 200/201/204/400/404. Também dá para testar ao vivo pela página `/api.html` ou com `curl`.

## 5. Endpoints (conforme a especificação do trabalho)

| Método | Endpoint | O que faz | Resposta |
|---|---|---|---|
| GET | `/cat/jogos` | Mostrar todos os jogos | 200 + lista |
| GET | `/cat/jogos/{id}` | Mostrar um jogo | 200 ou 404 |
| GET | `/cat/{id}` | Mostrar uma categoria | 200 ou 404 |
| GET | `/perf/{id}` | Mostrar um perfil | 200 ou 404 |
| POST | `/cat/{id}` | Cadastrar uma categoria | 201 ou 400 |
| POST | `/cat/jogos` | Cadastrar um jogo | 201 ou 400 |
| POST | `/perf` | Cadastrar um perfil | 201 ou 400 |
| PUT | `/cat/jogos/{id}` | Atualizar um jogo | 200 ou 404 (400 se inválido) |
| PUT | `/perf/{id}` | Atualizar um perfil | 200 ou 404 (400 se inválido) |
| DELETE | `/cat/jogos/{id}` | Apagar um jogo | 204 ou 404 |
| DELETE | `/cat/{id}` | Apagar uma categoria | 204 ou 404 |
| DELETE | `/perf/{id}` | Apagar um perfil | 204 ou 404 |

**Extras** (usados pelo site): `GET /cat` (lista categorias), `GET /perf` (lista perfis), `PUT`/`DELETE /perf/{id}/jogos/{jogoId}` (salvar/remover jogo do perfil), `GET /generos`, `GET /estatisticas`, `GET /fontes`, `GET /dataset/{arquivo}` (baixar os CSVs).

**Detalhes:**
- `GET /cat/jogos` é paginado e aceita `q` (nome), `categoria`, `familia` (PlayStation/Xbox/Nintendo), `genero`, `ano`, `ordem` (nome/ano/nota), `pagina`, `por_pagina`. Resposta: `{"pagina", "por_pagina", "total", "resultados": [...]}`.
- Corpo do `POST /cat/jogos`: `{"nome": "...", "categorias": [7], "generos": [31], "data_lancamento": "2001-05-20", "resumo": "..."}` (`nome` e `categorias` obrigatórios).
- `POST /cat/{id}`: o id da nova categoria vai na URL; corpo `{"nome": "Dreamcast", "familia": "Outras"}`. Id repetido → 400.
- `PUT /perf/{id}`: corpo `{"nome": "...", "jogos": [ids]}` — a lista `jogos` **substitui** os jogos salvos (é assim que se salva/exclui jogos do perfil).
- Erros: `{"erro": "mensagem em português"}`.
- Apagar jogo também o remove dos perfis; apagar categoria remove só o vínculo (os jogos continuam).

Exemplos:

```bash
curl "http://localhost:8000/cat/jogos?q=zelda&familia=Nintendo&por_pagina=5"
curl -X POST localhost:8000/perf -H "Content-Type: application/json" -d '{"nome":"Ana"}'
curl -X PUT  localhost:8000/perf/1 -H "Content-Type: application/json" -d '{"jogos":[150080]}'
curl -X DELETE localhost:8000/perf/1
```

## 6. Arquitetura

```
Navegador ── site (web/) ──► Flask (app.py) ──► SQLite: catalogo.db
                                                 ▲
dataset/*.csv ──► etl.py ──► catalogo_inicial.db ┘ (copiado para o volume na 1ª execução)
```

Tabelas: `jogos`, `categorias`, `generos`, `jogo_categoria` e `jogo_genero` (ligações N:N), `perfis`, `perfil_jogos`. As chaves estrangeiras usam `ON DELETE CASCADE`.

## 7. Roteiro sugerido para a apresentação

1. Mostrar o conceito e a equipe (`/sobre.html`).
2. Mostrar de onde vieram os dados: dataset, licença, arquivos em `dataset/` (`/sobre.html`).
3. Explicar o `etl.py` e as tabelas do banco.
4. Demonstrar o site: pesquisa e filtros → criar perfil → salvar/remover jogo → cadastrar, editar e excluir um jogo.
5. Abrir `/api.html` e testar ao vivo um GET, um POST com erro 400 e um DELETE 204/404.
6. Rodar os testes (`python -m unittest discover -s tests -v`) e mostrar o `docker compose up`.

## 8. Baixar as imagens para rodar 100% offline

As imagens dos jogos (~21 mil, cerca de 0,5 GB com Pillow (sem ele chega a ~6 GB)) não vêm no projeto. Para guardá-las no computador, instale o Pillow e rode **uma vez** na pasta do projeto (pode interromper com Ctrl+C e rodar de novo; ele continua de onde parou):

```bash
pip install pillow
python ferramentas/baixar_imagens.py
```

Elas ficam em `web/capas/<id>.jpg` e o site passa a usá-las sozinho. Ordem de exibição: imagem local → imagem online → capa gerada com ícones. Depois, para colocá-las no Docker: `docker compose up -d --build`.



## 9. Catálogo consolidado (várias fontes) e publicação

O banco é montado em duas etapas: `etl.py` (IGDB + imagens RAWG + vídeos YouTube) e `consolidar.py` (Libretro + Wikidata). O resultado, com **51.643 jogos**, também é exportado em `dataset/catalogo_consolidado.csv`. Todas as fontes, licenças e como citar estão em [`DATASETS.md`](DATASETS.md).

```bash
python etl.py dataset catalogo_inicial.db
python consolidar.py catalogo_inicial.db
python ferramentas/conferir_banco.py      # resumo dos números
```

Para baixar de novo as fontes: `ferramentas/baixar_wikidata.py` (Wikidata) e `ferramentas/baixar_capas_igdb.py` (capas oficiais do IGDB/Twitch — exige chave gratuita; instruções no topo do arquivo).

**Publicação no GitHub:** o `.gitignore` já deixa de fora `.venv/`, o banco do volume e o `dataset/rawg_imagens.csv` (100 MB, recriável). A pasta `web/capas/` (imagens) vai junto: se passar de ~1 GB ou o GitHub reclamar, use [Git LFS](https://git-lfs.com) para ela ou publique as imagens num ZIP em "Releases". Leia os avisos de licença em `DATASETS.md`.

## 10. Publicar no GitHub Pages (sem backend)

O GitHub Pages só serve arquivos estáticos (não roda Python). Por isso o site tem um **modo estático**: quando a API Flask não responde, `web/estatico.js` implementa **os mesmos endpoints no navegador**, lendo JSONs gerados pelo `ferramentas/exportar_estatico.py`. Perfis e jogos cadastrados ficam salvos no navegador (localStorage). Um aviso amarelo no topo informa que está nesse modo. O backend Python continua no repositório (`app.py`, Docker, testes) e é o que vale para a entrega da API.

Passo a passo:
1. Crie um repositório no GitHub e envie todo o projeto (branch `main`).
2. No repositório: **Settings → Pages → Build and deployment → Source: GitHub Actions**.
3. A cada push, o workflow `.github/workflows/pages.yml` gera o banco, **roda os testes**, exporta os dados e publica. O link fica em `https://SEU-USUARIO.github.io/NOME-DO-REPO/`.

Para testar localmente sem a API: `python ferramentas/exportar_estatico.py` e depois `python -m http.server 8090 --directory web`.
