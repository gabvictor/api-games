FROM python:3.12-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Dataset offline: os CSVs ficam na imagem e o etl.py gera o banco SQLite no build
COPY dataset/ dataset/
COPY etl.py consolidar.py ./
RUN python etl.py dataset catalogo_inicial.db && python consolidar.py catalogo_inicial.db

COPY app.py .
COPY web/ web/
COPY tests/ tests/

ENV DATA_DIR=/data
VOLUME /data
EXPOSE 8000
CMD ["gunicorn", "-b", "0.0.0.0:8000", "-w", "2", "app:app"]
