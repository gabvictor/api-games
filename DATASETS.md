# Fontes de dados, licenças e créditos

O catálogo junta várias bases públicas. Esta página lista **de onde veio cada dado, a licença e o que é obrigatório citar** ao publicar.

| # | Fonte | O que traz | Licença | Arquivo no projeto |
|---|---|---|---|---|
| 1 | **PlayMyData** (IGDB) — https://zenodo.org/records/10797761 | Base de jogos PlayStation/Xbox/Nintendo, gêneros, notas, resumos, vídeos do YouTube | CC BY 4.0 | `dataset/all_games_*.csv`, `platforms.csv`, `genres.csv`, `video_ids.csv`, `all_videos.csv` |
| 2 | **Video Games Dataset** (RAWG) — https://huggingface.co/datasets/atalaydenknalbant/video-games-dataset | URL de imagem de cada jogo | CC0 | `dataset/capas.csv` (gerado por `ferramentas/casar_capas.py`) |
| 3 | **Wikidata** — https://www.wikidata.org | Nome e descrição em português, desenvolvedora, editora | CC0 | `dataset/wikidata.csv` (`ferramentas/baixar_wikidata.py`) |
| 4 | **Libretro database** (listas No-Intro) — https://github.com/libretro/libretro-database | Jogos que faltavam em Game Boy, GBC, GBA, NES, SNES, N64 e Virtual Boy; desenvolvedora, ano, gênero | CC BY-SA 4.0 | `dataset/libretro/` |
| 5 | **IGDB / Twitch** (capas oficiais, opcional) — https://api-docs.igdb.com | Capa (box art) de cada jogo | Termos da API do IGDB (uso gratuito não comercial) | `dataset/capas_igdb.csv` (`ferramentas/baixar_capas_igdb.py`) |

Resultado: **`dataset/catalogo_consolidado.csv`** (51.643 jogos) e o banco `catalogo_inicial.db`. A coluna `fontes` de cada jogo diz quais bases contribuíram.

## Como citar (para a apresentação / repositório)

- Rubei, R. et al. *PlayMyData: a curated dataset of multi-platform video games*. MSR 2024. Zenodo, 2024. CC BY 4.0.
- RAWG.io (https://rawg.io) — dados via dataset `atalaydenknalbant/video-games-dataset` (CC0).
- Wikidata contributors. *Wikidata*. CC0.
- Libretro Team. *libretro-database* (No-Intro DAT files). CC BY-SA 4.0.
- IGDB.com, uma empresa da Twitch (quando as capas oficiais forem usadas).

## Pontos de atenção ao publicar

1. **Licença do conjunto:** como o catálogo consolidado contém dados do Libretro (CC BY-SA 4.0, “compartilhar igual”), o arquivo `catalogo_consolidado.csv` e o banco devem ser publicados também sob **CC BY-SA 4.0**. O código (`app.py`, `etl.py` etc.) pode ter outra licença.
2. **Imagens de capa:** são arte protegida por direitos autorais das empresas dos jogos; elas **não** vêm de uma licença livre. Para um trabalho acadêmico, mostrar capas em um site de catálogo (sem vender nada) é um uso comum, mas ao publicar na internet deixe claro o crédito (RAWG / IGDB) e retire as imagens se algum titular pedir.
3. **Termos do RAWG e do IGDB** pedem citar a fonte e não usar a base como produto comercial concorrente.
4. **Wikidata** limita a 1 consulta por vez e pede um `User-Agent` identificado (já feito no script).
