// Modo estático: faz o site funcionar SEM backend (GitHub Pages).
//
// Se a API Python (Flask) responder, nada muda: tudo vai para ela. Se não responder (ex.: no github.io),
// este arquivo implementa os MESMOS endpoints no navegador, lendo os JSONs de web/dados/ (gerados por
// ferramentas/exportar_estatico.py) e guardando perfis e alterações no localStorage deste navegador.
(() => {
  const realFetch = window.fetch.bind(window);
  const BASE = new URL(".", document.baseURI).pathname;            // ex.: "/" ou "/meu-repo/"
  const ROTA = /\/(cat|perf|generos|estatisticas|fontes)(\/.*)?$/;
  const PREFIXO_IMG = "https://media.rawg.io/media/games/";
  const ID_NOVOS = 20_000_000;

  let modo = null;       // "api" | "estatico"
  let dados = null;      // índice carregado
  const blocos = {};     // cache dos arquivos de detalhe

  const semAcento = (s) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  const resposta = (status, corpo, extra = {}) => new Response(
    status === 204 ? null : JSON.stringify(corpo), { status, headers: { "Content-Type": "application/json", ...extra } });
  const erro = (status, msg) => resposta(status, { erro: msg });
  const lerJson = (url) => realFetch(BASE + url).then((r) => r.json());

  async function detectar() {
    if (modo) return modo;
    try {
      const r = await realFetch(BASE + "estatisticas", { headers: { Accept: "application/json" } });
      modo = r.ok && (r.headers.get("content-type") || "").includes("json") ? "api" : "estatico";
    } catch { modo = "estatico"; }
    if (modo === "estatico") mostrarAviso();
    return modo;
  }

  function mostrarAviso() {
    const poe = () => {
      const d = document.createElement("div");
      d.style.cssText = "background:#7c5a00;color:#fff;font-size:.82rem;padding:6px 14px;text-align:center";
      d.innerHTML = "📦 <b>Modo estático</b>: sem servidor Python. A API é simulada no navegador com os mesmos endpoints; "
        + "perfis e alterações ficam salvos só neste navegador. O código da API real está em <code>app.py</code>.";
      document.body.prepend(d);
    };
    document.body ? poe() : addEventListener("DOMContentLoaded", poe);
  }

  // ---------- Dados ----------
  const guardado = (chave, padrao) => { try { return JSON.parse(localStorage.getItem(chave)) ?? padrao; } catch { return padrao; } };
  const gravar = (chave, v) => { try { localStorage.setItem(chave, JSON.stringify(v)); } catch {} };
  let alt = guardado("catalogo_alteracoes", { novos: {}, edicoes: {}, apagados: [], cats: {}, catsApagadas: [], prox: ID_NOVOS });
  let perf = guardado("catalogo_perfis", { prox: 1, itens: [] });
  let cache = null;

  async function carregar() {
    if (dados) return dados;
    const [indice, categorias, generos, fontes] = await Promise.all(
      ["dados/indice.json", "dados/categorias.json", "dados/generos.json", "dados/fontes.json"].map(lerJson));
    dados = { indice, categorias, generos, fontes };
    return dados;
  }

  // Lista efetiva de jogos (base + alterações do usuário), no formato compacto do índice
  function jogos() {
    if (cache) return cache;
    const apagados = new Set(alt.apagados);
    const lista = [];
    for (const j of dados.indice) {
      if (apagados.has(j[0])) continue;
      lista.push({ id: j[0], nome: j[1], nome_pt: j[2] || null, ano: j[3] || null, nota: j[4] >= 0 ? j[4] : null,
        img: j[5] ? (j[5].startsWith("http") ? j[5] : PREFIXO_IMG + j[5]) : null, cats: j[6], gens: j[7], ...alt.edicoes[j[0]] });
    }
    for (const j of Object.values(alt.novos)) if (!apagados.has(j.id)) lista.push({ ...j, ...alt.edicoes[j.id] });
    for (const j of lista) j.busca = semAcento(j.nome + " " + (j.nome_pt || ""));
    cache = lista;
    return lista;
  }
  const invalidar = () => { cache = null; gravar("catalogo_alteracoes", alt); };

  const categoriasAtivas = () => [...dados.categorias.filter((c) => !alt.catsApagadas.includes(c.id)),
    ...Object.values(alt.cats)];
  const catPorId = () => Object.fromEntries(categoriasAtivas().map((c) => [c.id, c]));
  const genPorId = () => Object.fromEntries(dados.generos.map((g) => [g.id, g]));

  function paraApi(j, detalhe = null) {
    const cp = catPorId(), gp = genPorId();
    const o = {
      id: j.id, nome: j.nome, nome_pt: j.nome_pt ?? null, data_lancamento: j.data_lancamento ?? null, ano: j.ano ?? null,
      nota: j.nota ?? null, resumo: j.resumo ?? null, imagem_url: j.img ?? null, desenvolvedora: j.desenvolvedora ?? null,
      fontes: j.fontes ?? "IGDB",
      categorias: j.cats.filter((c) => cp[c]).map((c) => ({ id: c, nome: cp[c].nome, familia: cp[c].familia })),
      generos: j.gens.filter((g) => gp[g]).map((g) => ({ id: g, nome: gp[g].nome })),
    };
    if (detalhe) {
      Object.assign(o, { historia: null, descricao_pt: null, editora: null, nota_critica: null, tempo_principal: null,
        tempo_extra: null, tempo_completo: null }, detalhe);
      o.imagem_url = j.img ?? null; o.nota = j.nota ?? detalhe.nota ?? null;
      o.videos = (detalhe.videos || []).map(([y, t]) => ({ youtube_id: y, titulo: t, url: "https://www.youtube.com/watch?v=" + y }));
      const ed = alt.edicoes[j.id] || {};   // alterações feitas pelo usuário valem mais que o dado original
      for (const k of ["resumo", "historia", "data_lancamento"]) if (k in ed) o[k] = ed[k];
    }
    return o;
  }

  async function detalheBase(id) {
    if (alt.novos[id]) return alt.novos[id].detalhe || {};
    const n = id % 200;
    blocos[n] ??= await lerJson(`dados/detalhe/${n}.json`);
    return blocos[n][String(id)] || {};
  }

  // ---------- Validação (espelha o app.py) ----------
  class Erro400 extends Error {}
  const ruim = (m) => { throw new Erro400(m); };
  function validarListaIds(v, campo, existentes, obrigatoria) {
    if (!Array.isArray(v) || !v.every((i) => Number.isInteger(i))) ruim(`'${campo}' deve ser uma lista de números inteiros`);
    v = [...new Set(v)];
    if (obrigatoria && !v.length) ruim(`Informe ao menos um item em '${campo}'`);
    const faltando = v.filter((i) => !existentes[i]);
    if (faltando.length) ruim(`'${campo}' contém ids inexistentes: [${faltando.join(", ")}]`);
    return v;
  }
  function nomeValido(d, limite, obrig = true) {
    if (d.nome === undefined && !obrig) return undefined;
    if (typeof d.nome !== "string" || !d.nome.trim() || d.nome.trim().length > limite)
      ruim(`'nome' é obrigatório (texto de 1 a ${limite} caracteres)`);
    return d.nome.trim();
  }
  function camposJogo(d, parcial) {
    const c = {};
    if (!parcial || "nome" in d) c.nome = nomeValido(d, 120);
    if ("data_lancamento" in d) {
      if (d.data_lancamento !== null) {
        if (!/^\d{4}-\d{2}-\d{2}$/.test(d.data_lancamento || "") || isNaN(Date.parse(d.data_lancamento)))
          ruim("'data_lancamento' deve estar no formato AAAA-MM-DD");
        c.data_lancamento = d.data_lancamento; c.ano = Number(d.data_lancamento.slice(0, 4));
      } else { c.data_lancamento = null; c.ano = null; }
    }
    if ("ano" in d && !("data_lancamento" in d)) {
      if (d.ano !== null && (!Number.isInteger(d.ano) || d.ano < 1950 || d.ano > 2100)) ruim("'ano' deve ser um inteiro entre 1950 e 2100");
      c.ano = d.ano;
    }
    for (const k of ["resumo", "historia"]) if (k in d) {
      if (d[k] !== null && typeof d[k] !== "string") ruim(`'${k}' deve ser texto`);
      c[k] = d[k];
    }
    if ("nota" in d) {
      if (d.nota !== null && (typeof d.nota !== "number" || d.nota < 0 || d.nota > 100)) ruim("'nota' deve ser um número de 0 a 100");
      c.nota = d.nota;
    }
    const cp = catPorId();
    const cats = "categorias" in d ? validarListaIds(d.categorias, "categorias", cp, true) : undefined;
    const gens = "generos" in d ? validarListaIds(d.generos, "generos", genPorId(), false) : undefined;
    if (!parcial && cats === undefined) ruim("'categorias' é obrigatório (lista com ids de categorias/plataformas)");
    return { c, cats, gens };
  }

  // ---------- Rotas ----------
  async function rotear(metodo, caminho, q, corpo) {
    await carregar();
    const cp = catPorId();
    let m;

    if (caminho === "/estatisticas" && metodo === "GET") {
      const por = {};
      for (const j of jogos()) for (const f of new Set(j.cats.map((c) => cp[c]?.familia).filter(Boolean))) por[f] = (por[f] || 0) + 1;
      return resposta(200, { total_jogos: jogos().length, total_categorias: categoriasAtivas().length, total_perfis: perf.itens.length, por_familia: por });
    }
    if (caminho === "/generos") return resposta(200, dados.generos);
    if (caminho === "/fontes") return resposta(200, dados.fontes);

    // --- jogos ---
    if (caminho === "/cat/jogos" && metodo === "GET") {
      let lista = jogos();
      const qq = q.get("q") ? semAcento(q.get("q")) : null;
      const cat = Number(q.get("categoria")) || null, gen = Number(q.get("genero")) || null, ano = Number(q.get("ano")) || null;
      const fam = q.get("familia")?.toLowerCase();
      lista = lista.filter((j) => (!qq || j.busca.includes(qq)) && (!cat || j.cats.includes(cat)) && (!gen || j.gens.includes(gen))
        && (!ano || j.ano === ano) && (q.get("com_imagem") !== "1" || j.img)
        && (!fam || j.cats.some((c) => cp[c]?.familia.toLowerCase() === fam)));
      const por = (a, b) => a.nome.localeCompare(b.nome, "pt", { sensitivity: "base" });
      const nul = (x) => (x == null ? -1 : x);
      const ordem = q.get("ordem") || "nome";
      lista = [...lista].sort({
        nome: por, ano: (a, b) => nul(b.ano) - nul(a.ano) || por(a, b), nota: (a, b) => nul(b.nota) - nul(a.nota) || por(a, b),
        destaques: (a, b) => (!a.img - !b.img) || nul(b.nota) - nul(a.nota) || por(a, b),
      }[ordem] || por);
      const pagina = Math.max(1, parseInt(q.get("pagina") || "1", 10));
      const pp = Math.min(100, Math.max(1, parseInt(q.get("por_pagina") || "24", 10)));
      if (Number.isNaN(pagina) || Number.isNaN(pp)) return erro(400, "'pagina' e 'por_pagina' devem ser números inteiros");
      return resposta(200, { pagina, por_pagina: pp, total: lista.length, resultados: lista.slice((pagina - 1) * pp, pagina * pp).map((j) => paraApi(j)) });
    }
    if (caminho === "/cat/jogos" && metodo === "POST") {
      const { c, cats, gens } = camposJogo(corpo, false);
      const id = alt.prox++;
      alt.novos[id] = { id, nome: c.nome, ano: c.ano ?? null, nota: c.nota ?? null, nome_pt: null, img: null, cats, gens: gens || [],
        data_lancamento: c.data_lancamento ?? null, resumo: c.resumo ?? null, fontes: "Cadastro manual", detalhe: { resumo: c.resumo ?? undefined, fontes: "Cadastro manual" } };
      invalidar();
      return resposta(201, paraApi(jogos().find((j) => j.id === id), await detalheBase(id)), { Location: `/cat/jogos/${id}` });
    }
    if ((m = caminho.match(/^\/cat\/jogos\/(\d+)$/))) {
      const id = Number(m[1]);
      const j = jogos().find((x) => x.id === id);
      if (!j) return erro(404, "Jogo não encontrado");
      if (metodo === "GET") return resposta(200, paraApi(j, await detalheBase(id)));
      if (metodo === "DELETE") { alt.apagados.push(id); delete alt.novos[id]; invalidar(); return resposta(204); }
      if (metodo === "PUT") {
        const { c, cats, gens } = camposJogo(corpo, true);
        const ed = { ...alt.edicoes[id] };
        const mapa = { nome: "nome", ano: "ano", nota: "nota", resumo: "resumo", historia: "historia", data_lancamento: "data_lancamento" };
        for (const [k, v] of Object.entries(c)) ed[mapa[k]] = v;
        if (cats) ed.cats = cats;
        if (gens) ed.gens = gens;
        alt.edicoes[id] = ed; invalidar();
        return resposta(200, paraApi(jogos().find((x) => x.id === id), await detalheBase(id)));
      }
    }

    // --- categorias ---
    if (caminho === "/cat" && metodo === "GET") {
      const cont = {};
      for (const j of jogos()) for (const c of j.cats) cont[c] = (cont[c] || 0) + 1;
      return resposta(200, categoriasAtivas().map((c) => ({ ...c, total_jogos: cont[c.id] || 0 })));
    }
    if ((m = caminho.match(/^\/cat\/(\d+)$/))) {
      const id = Number(m[1]), c = cp[id];
      if (metodo === "GET") return c ? resposta(200, { ...c, total_jogos: jogos().filter((j) => j.cats.includes(id)).length }) : erro(404, "Categoria não encontrada");
      if (metodo === "POST") {
        const nome = nomeValido(corpo, 60);
        if (c) return erro(400, `Já existe uma categoria com o id ${id}`);
        const fam = corpo.familia ?? null;
        if (fam !== null && (typeof fam !== "string" || fam.length > 40)) ruim("'familia' deve ser texto de até 40 caracteres");
        alt.cats[id] = { id, nome, familia: fam }; alt.catsApagadas = alt.catsApagadas.filter((x) => x !== id); invalidar();
        return resposta(201, { id, nome, familia: fam, total_jogos: 0 }, { Location: `/cat/${id}` });
      }
      if (metodo === "DELETE") {
        if (!c) return erro(404, "Categoria não encontrada");
        delete alt.cats[id]; alt.catsApagadas.push(id); invalidar();
        return resposta(204);
      }
    }

    // --- perfis ---
    const perfilCompleto = (p) => ({ id: p.id, nome: p.nome, criado_em: p.criado_em,
      jogos: p.jogos.map((id) => jogos().find((j) => j.id === id)).filter(Boolean).map((j) => paraApi(j)) });
    const salvarPerf = () => gravar("catalogo_perfis", perf);
    const nomeLivre = (nome, ignorar) => !perf.itens.some((p) => p.id !== ignorar && p.nome.toLowerCase() === nome.toLowerCase());

    if (caminho === "/perf" && metodo === "GET")
      return resposta(200, [...perf.itens].sort((a, b) => a.nome.localeCompare(b.nome, "pt"))
        .map((p) => ({ id: p.id, nome: p.nome, criado_em: p.criado_em, total_jogos: p.jogos.length })));
    if (caminho === "/perf" && metodo === "POST") {
      const nome = nomeValido(corpo, 40);
      if (!nomeLivre(nome)) return erro(400, "Já existe um perfil com esse nome");
      const p = { id: perf.prox++, nome, criado_em: new Date().toISOString().slice(0, 19).replace("T", " "), jogos: [] };
      perf.itens.push(p); salvarPerf();
      return resposta(201, perfilCompleto(p), { Location: `/perf/${p.id}` });
    }
    if ((m = caminho.match(/^\/perf\/(\d+)(?:\/jogos\/(\d+))?$/))) {
      const p = perf.itens.find((x) => x.id === Number(m[1]));
      if (!p) return erro(404, "Perfil não encontrado");
      if (m[2]) {   // atalhos /perf/{id}/jogos/{jogoId}
        const jid = Number(m[2]);
        if (metodo === "PUT") {
          if (!jogos().some((j) => j.id === jid)) return erro(404, "Jogo não encontrado");
          if (!p.jogos.includes(jid)) p.jogos.unshift(jid);
          salvarPerf(); return resposta(200, perfilCompleto(p));
        }
        if (metodo === "DELETE") {
          if (!p.jogos.includes(jid)) return erro(404, "Esse jogo não está salvo neste perfil");
          p.jogos = p.jogos.filter((x) => x !== jid); salvarPerf(); return resposta(204);
        }
      } else {
        if (metodo === "GET") return resposta(200, perfilCompleto(p));
        if (metodo === "DELETE") { perf.itens = perf.itens.filter((x) => x !== p); salvarPerf(); return resposta(204); }
        if (metodo === "PUT") {
          const nome = "nome" in corpo ? nomeValido(corpo, 40) : undefined;
          const ids = "jogos" in corpo ? validarListaIds(corpo.jogos, "jogos", Object.fromEntries(jogos().map((j) => [j.id, 1])), false) : undefined;
          if (nome === undefined && ids === undefined) ruim("Envie 'nome' e/ou 'jogos' (lista de ids) para atualizar");
          if (nome !== undefined) { if (!nomeLivre(nome, p.id)) return erro(400, "Já existe um perfil com esse nome"); p.nome = nome; }
          if (ids !== undefined) p.jogos = ids;
          salvarPerf(); return resposta(200, perfilCompleto(p));
        }
      }
    }
    return erro(404, "Recurso não encontrado");
  }

  // ---------- Intercepta o fetch ----------
  window.fetch = async (entrada, opcoes = {}) => {
    const url = new URL(typeof entrada === "string" ? entrada : entrada.url, document.baseURI);
    const caminhoBruto = url.pathname.startsWith(BASE) && BASE !== "/" ? url.pathname.slice(BASE.length - 1) : url.pathname;
    if (url.origin !== location.origin || !ROTA.test(caminhoBruto) || /\.(js|css|html|json|jpg)$/.test(caminhoBruto)) return realFetch(entrada, opcoes);
    if ((await detectar()) === "api") return realFetch(entrada, opcoes);
    let corpo = {};
    if (opcoes.body) { try { corpo = JSON.parse(opcoes.body); } catch { return erro(400, "Envie um corpo JSON (objeto) válido"); } if (typeof corpo !== "object" || Array.isArray(corpo) || !corpo) return erro(400, "Envie um corpo JSON (objeto) válido"); }
    else if (["POST", "PUT"].includes((opcoes.method || "GET").toUpperCase())) corpo = null;
    try {
      const metodo = (opcoes.method || "GET").toUpperCase();
      if (corpo === null && !/^\/perf\/\d+\/jogos\/\d+$/.test(caminhoBruto)) return erro(400, "Envie um corpo JSON (objeto) válido");
      return await rotear(metodo, caminhoBruto.replace(/\/$/, "") || "/", url.searchParams, corpo || {});
    } catch (e) {
      if (e instanceof Erro400) return erro(400, e.message);
      console.error(e);
      return erro(500, "Erro interno no modo estático");
    }
  };
})();
