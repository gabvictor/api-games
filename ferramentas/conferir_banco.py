"""Mostra um resumo do banco consolidado (para conferir os números na apresentação).
Uso: python ferramentas/conferir_banco.py [catalogo_inicial.db]
"""
import sqlite3
import sys

d = sqlite3.connect(sys.argv[1] if len(sys.argv) > 1 else "catalogo_inicial.db")
print("jogos por plataforma:")
for nome, n in d.execute("SELECT c.nome, COUNT(*) FROM jogo_categoria jc JOIN categorias c ON c.id=jc.categoria_id "
                         "GROUP BY 1 ORDER BY 2 DESC"):
    print(f"  {nome:40} {n}")
print("total:", d.execute("SELECT COUNT(*) FROM jogos").fetchone()[0])
print("com nome em português:", d.execute("SELECT COUNT(*) FROM jogos WHERE nome_pt IS NOT NULL").fetchone()[0])
print("com desenvolvedora:", d.execute("SELECT COUNT(*) FROM jogos WHERE desenvolvedora IS NOT NULL").fetchone()[0])
print("exemplos que vieram só do Libretro:")
for r in d.execute("SELECT nome, ano, desenvolvedora FROM jogos WHERE fontes LIKE 'Libretro%' ORDER BY RANDOM() LIMIT 8"):
    print("  ", r)
