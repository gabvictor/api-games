"""Testes automáticos dos 12 endpoints da especificação (usa uma cópia temporária do banco).

Rodar:  python -m unittest discover -s tests -v
"""
import os
import sys
import tempfile
import unittest

os.environ["DATA_DIR"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app  # noqa: E402


class TesteApi(unittest.TestCase):
    def setUp(self):
        self.c = app.test_client()

    # --- /cat/jogos ---
    def test_get_jogos_lista(self):
        r = self.c.get("/cat/jogos?q=zelda&por_pagina=3")
        self.assertEqual(r.status_code, 200)
        self.assertLessEqual(len(r.json["resultados"]), 3)
        self.assertGreater(r.json["total"], 0)

    def test_get_jogo_200_e_404(self):
        jid = self.c.get("/cat/jogos").json["resultados"][0]["id"]
        self.assertEqual(self.c.get(f"/cat/jogos/{jid}").status_code, 200)
        self.assertEqual(self.c.get("/cat/jogos/999999999").status_code, 404)

    def test_post_put_delete_jogo(self):
        r = self.c.post("/cat/jogos", json={"nome": "Jogo de Teste", "categorias": [7], "generos": [31]})
        self.assertEqual(r.status_code, 201)
        jid = r.json["id"]
        self.assertEqual(r.json["categorias"][0]["nome"], "PlayStation")
        r = self.c.put(f"/cat/jogos/{jid}", json={"nome": "Jogo Editado", "ano": 2001})
        self.assertEqual((r.status_code, r.json["nome"], r.json["ano"]), (200, "Jogo Editado", 2001))
        self.assertEqual(self.c.put("/cat/jogos/999999999", json={"nome": "x"}).status_code, 404)
        self.assertEqual(self.c.delete(f"/cat/jogos/{jid}").status_code, 204)
        self.assertEqual(self.c.delete(f"/cat/jogos/{jid}").status_code, 404)

    def test_post_jogo_invalido_400(self):
        self.assertEqual(self.c.post("/cat/jogos", json={"categorias": [7]}).status_code, 400)  # sem nome
        self.assertEqual(self.c.post("/cat/jogos", json={"nome": "X"}).status_code, 400)  # sem categoria
        self.assertEqual(self.c.post("/cat/jogos", json={"nome": "X", "categorias": [99999]}).status_code, 400)
        self.assertEqual(self.c.post("/cat/jogos", data="isso nao e json").status_code, 400)

    # --- /cat/{id} ---
    def test_categoria(self):
        r = self.c.get("/cat/167")
        self.assertEqual((r.status_code, r.json["nome"]), (200, "PlayStation 5"))
        self.assertEqual(self.c.get("/cat/999999").status_code, 404)
        self.assertEqual(self.c.post("/cat/900", json={"nome": "Plataforma Nova", "familia": "Outras"}).status_code, 201)
        self.assertEqual(self.c.post("/cat/900", json={"nome": "Repetida"}).status_code, 400)
        self.assertEqual(self.c.post("/cat/901", json={}).status_code, 400)
        self.assertEqual(self.c.delete("/cat/900").status_code, 204)
        self.assertEqual(self.c.delete("/cat/900").status_code, 404)

    # --- /perf ---
    def test_perfil_completo(self):
        r = self.c.post("/perf", json={"nome": "Perfil Teste"})
        self.assertEqual(r.status_code, 201)
        pid = r.json["id"]
        self.assertEqual(self.c.post("/perf", json={"nome": "perfil teste"}).status_code, 400)  # duplicado
        self.assertEqual(self.c.post("/perf", json={}).status_code, 400)
        jid = self.c.get("/cat/jogos").json["resultados"][0]["id"]
        r = self.c.put(f"/perf/{pid}", json={"nome": "Renomeado", "jogos": [jid]})
        self.assertEqual((r.status_code, r.json["nome"], len(r.json["jogos"])), (200, "Renomeado", 1))
        self.assertEqual(self.c.put(f"/perf/{pid}", json={"jogos": [999999999]}).status_code, 400)
        self.assertEqual(self.c.get(f"/perf/{pid}").status_code, 200)
        self.assertEqual(self.c.delete(f"/perf/{pid}/jogos/{jid}").status_code, 204)
        self.assertEqual(self.c.put(f"/perf/{pid}/jogos/{jid}").status_code, 200)
        self.assertEqual(self.c.delete(f"/perf/{pid}").status_code, 204)
        self.assertEqual(self.c.get(f"/perf/{pid}").status_code, 404)
        self.assertEqual(self.c.put(f"/perf/{pid}", json={"nome": "x"}).status_code, 404)
        self.assertEqual(self.c.delete(f"/perf/{pid}").status_code, 404)

    def test_fontes_e_dataset(self):
        r = self.c.get("/fontes")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(all(a["tamanho_bytes"] for a in r.json["arquivos_usados"]))
        self.assertEqual(self.c.get("/dataset/genres.csv").status_code, 200)


if __name__ == "__main__":
    unittest.main()
