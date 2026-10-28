"""Baixa do dataset RAWG (Hugging Face) só as colunas necessárias para ter a URL da imagem de cada jogo.

Fonte: https://huggingface.co/datasets/atalaydenknalbant/video-games-dataset (licença CC0-1.0, dados do RAWG)
O arquivo parquet completo tem ~1 GB (com descrições e tags); lemos só 4 colunas usando requisições HTTP parciais,
então o download real fica na casa de dezenas de MB.

Uso: python ferramentas/baixar_capas.py [saida.csv]
Requer: pip install pyarrow fsspec aiohttp requests
"""
import csv
import sys

import fsspec
import pyarrow.parquet as pq

URL = "https://huggingface.co/api/datasets/atalaydenknalbant/video-games-dataset/parquet/default/train/0.parquet"
SAIDA = sys.argv[1] if len(sys.argv) > 1 else "dataset/rawg_imagens.csv"
COLUNAS = ["id", "name", "released", "background_image"]

fs = fsspec.filesystem("https")
with fs.open(URL, "rb", block_size=8 * 1024 * 1024) as f:
    arquivo = pq.ParquetFile(f)
    print("linhas no arquivo:", arquivo.metadata.num_rows)
    n = 0
    with open(SAIDA, "w", encoding="utf-8", newline="") as out:
        w = csv.writer(out)
        w.writerow(COLUNAS)
        for lote in arquivo.iter_batches(batch_size=50_000, columns=COLUNAS):
            for linha in zip(*(lote.column(c).to_pylist() for c in COLUNAS)):
                if linha[1] and linha[3]:
                    w.writerow(linha)
                    n += 1
            print("gravadas:", n, flush=True)
print("pronto:", SAIDA)
