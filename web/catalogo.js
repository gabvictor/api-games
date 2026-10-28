montarLayout("catalogo");

const $ = (id) => document.getElementById(id);
const estado = { pagina: 1, paginas: 1, perfilId: null, salvos: new Set(), categorias: [], generos: [] };

// ---------- Perfis ----------
async function carregarPerfis(selecionar) {
  const perfis = await api("/perf");
  const sel = $("perfil");
  sel.innerHTML = perfis.length
    ? perfis.map((p) => `<option value="${p.id}">${esc(p.nome)}</option>`).join("")
    : '<option value="">(crie um perfil)</option>';
  const guardado = Number(localStorage.getItem("perfilId"));
  const desejado = selecionar ?? (perfis.some((p) => p.id === guardado) ? guardado : perfis[0]?.id);
  if (desejado) sel.value = desejado;
  await escolherPerfil(sel.value ? Number(sel.value) : null);
}

async function escolherPerfil(id) {
  estado.perfilId = id;
  if (id) localStorage.setItem("perfilId", id); else localStorage.removeItem("perfilId");
  $("excluir-perfil").disabled = $("renomear-perfil").disabled = !id;
  const perfil = id ? await api(`/perf/${id}`) : { jogos: [] };
  estado.salvos = new Set(perfil.jogos.map((j) => j.id));
  $("qtd-salvos").textContent = perfil.jogos.length;
  desenhar($("salvos"), perfil.jogos);
  $("info-salvos").textContent = !id ? "Crie um perfil para salvar jogos." : perfil.jogos.length ? "" : "Nenhum jogo salvo neste perfil ainda.";
  atualizarBotoes();
}

$("perfil").onchange = (e) => escolherPerfil(e.target.value ? Number(e.target.value) : null);

$("novo-perfil").onclick = async () => {
  const nome = prompt("Nome do novo perfil:");
  if (!nome) return;
  try {
    const p = await api("/perf", { method: "POST", body: JSON.stringify({ nome }) });
    await carregarPerfis(p.id);
  } catch (e) { alert(e.message); }
};

$("renomear-perfil").onclick = async () => {
  const atual = $("perfil").selectedOptions[0].textContent;
  const nome = prompt("Novo nome do perfil:", atual);
  if (!nome || nome === atual) return;
  try {
    await api(`/perf/${estado.perfilId}`, { method: "PUT", body: JSON.stringify({ nome }) });
    await carregarPerfis(estado.perfilId);
  } catch (e) { alert(e.message); }
};

$("excluir-perfil").onclick = async () => {
  const nome = $("perfil").selectedOptions[0].textContent;
  if (!confirm(`Excluir o perfil "${nome}" e todos os jogos salvos nele?`)) return;
  await api(`/perf/${estado.perfilId}`, { method: "DELETE" });
  await carregarPerfis();
};

async function alternarSalvo(jogoId) {
  if (!estado.perfilId) return alert("Crie ou selecione um perfil primeiro.");
  const url = `/perf/${estado.perfilId}/jogos/${jogoId}`;
  await api(url, { method: estado.salvos.has(jogoId) ? "DELETE" : "PUT" });
  await escolherPerfil(estado.perfilId);
}

// ---------- Cartões ----------
function cartao(j) {
  const marcas = [...new Set(j.categorias.map((c) => c.familia))];
  const tags = [
    ...j.categorias.slice(0, 4).map((c) => `<span class="tag">${iconeMarca(c.familia)}${esc(c.nome)}</span>`),
    ...(j.categorias.length > 4 ? [`<span class="tag">+${j.categorias.length - 4}</span>`] : []),
    ...j.generos.map((g) => `<span class="tag">${iconeGenero(g.nome)} ${esc(g.nome)}</span>`),
  ].join("");
  return `<article class="cartao">${capa(j)}
    <div class="corpo">
      <h3 data-detalhe="${j.id}">${esc(j.nome)}</h3>
      <span class="meta">${esc(j.ano ?? "Ano desconhecido")}${j.nota ? " · ⭐ " + Math.round(j.nota) + "/100" : ""}</span>
      <div class="tags">${tags}</div>
      <div class="acoes"><button data-salvar="${j.id}"></button></div>
    </div></article>`;
}

function desenhar(el, jogos) {
  el.innerHTML = jogos.length ? jogos.map(cartao).join("") : '<p class="vazio">Nenhum jogo encontrado.</p>';
}

function atualizarBotoes() {
  document.querySelectorAll("[data-salvar]").forEach((b) => {
    const salvo = estado.salvos.has(Number(b.dataset.salvar));
    b.textContent = salvo ? "✓ Salvo — remover" : "+ Salvar no perfil";
    b.className = "pequeno " + (salvo ? "perigo" : "principal");
  });
}

document.addEventListener("click", (e) => {
  const salvar = e.target.closest("[data-salvar]");
  if (salvar) return alternarSalvo(Number(salvar.dataset.salvar));
  const det = e.target.closest("[data-detalhe]");
  if (det) return mostrarDetalhe(Number(det.dataset.detalhe));
});

// ---------- Detalhe, edição e exclusão ----------
const horas = (s) => (s ? `${Math.round(s / 3600)} h` : "—");

async function mostrarDetalhe(id) {
  const j = await api(`/cat/jogos/${id}`);
  $("detalhe").innerHTML = `${capa(j)}<div class="miolo">
    <h2>${esc(j.nome)}</h2>
    ${j.nome_pt ? `<p class="meta">Em português: <b>${esc(j.nome_pt)}</b></p>` : ""}
    <p class="meta">Lançamento: ${esc(j.data_lancamento ?? j.ano ?? "desconhecido")} · ID no catálogo: ${j.id}</p>
    ${j.desenvolvedora || j.editora ? `<p class="meta">${j.desenvolvedora ? "Desenvolvedora: " + esc(j.desenvolvedora) : ""}${j.desenvolvedora && j.editora ? " · " : ""}${j.editora ? "Editora: " + esc(j.editora) : ""}</p>` : ""}
    <div class="tags">${j.categorias.map((c) => `<span class="tag">${iconeMarca(c.familia)}${esc(c.nome)}</span>`).join("")}
      ${j.generos.map((g) => `<span class="tag">${iconeGenero(g.nome)} ${esc(g.nome)}</span>`).join("")}</div>
    <p>${esc(j.descricao_pt ?? j.resumo ?? "Sem descrição disponível.")}</p>
    ${j.historia ? `<p><b>História:</b> ${esc(j.historia)}</p>` : ""}
    <div class="detalhes">
      <div><b>${j.nota ? Math.round(j.nota) + "/100" : "—"}</b>Nota dos usuários (IGDB)</div>
      <div><b>${horas(j.tempo_principal)}</b>Tempo da história</div>
      <div><b>${horas(j.tempo_completo)}</b>Tempo 100%</div>
    </div>
    ${j.videos?.length ? `<p class="meta">Vídeo no YouTube (precisa de internet):</p>` + j.videos.map((v) =>
      `<a class="video" href="${esc(v.url)}" target="_blank" rel="noopener">
        <img loading="lazy" alt="" src="https://img.youtube.com/vi/${esc(v.youtube_id)}/hqdefault.jpg" onerror="this.remove()">
        <span>▶ ${esc(v.titulo ?? "Vídeo")}</span></a>`).join("") : ""}
    <p class="meta">Fontes dos dados deste jogo: ${esc(j.fontes ?? "IGDB")}</p>
    <div class="botoes">
      <button data-salvar="${j.id}"></button>
      <button id="editar">✏️ Editar</button>
      <button id="excluir" class="perigo">🗑️ Excluir do catálogo</button>
      <button id="fechar">Fechar</button>
    </div></div>`;
  $("fechar").onclick = () => $("detalhe").close();
  $("editar").onclick = () => { $("detalhe").close(); formularioJogo(j); };
  $("excluir").onclick = async () => {
    if (!confirm(`Excluir "${j.nome}" do catálogo? (também sai dos perfis)`)) return;
    await api(`/cat/jogos/${j.id}`, { method: "DELETE" });
    $("detalhe").close();
    await escolherPerfil(estado.perfilId);
    await buscar();
  };
  atualizarBotoes();
  $("detalhe").showModal();
}

function formularioJogo(jogo) {
  const edicao = !!jogo;
  const opcoes = (lista, marcados) => lista.map((i) =>
    `<option value="${i.id}" ${marcados.includes(i.id) ? "selected" : ""}>${esc(i.nome)}</option>`).join("");
  $("cadastro").innerHTML = `<div class="miolo"><h2>${edicao ? "Editar jogo" : "Cadastrar novo jogo"}</h2>
    <form id="form-jogo" class="formulario">
      <label>Nome *<input name="nome" required maxlength="120" value="${esc(jogo?.nome)}"></label>
      <label>Data de lançamento<input name="data_lancamento" type="date" value="${esc(jogo?.data_lancamento)}"></label>
      <label>Plataformas (categorias) * — Ctrl/Cmd para escolher várias
        <select name="categorias" multiple required>${opcoes(estado.categorias, jogo?.categorias.map((c) => c.id) ?? [])}</select></label>
      <label>Gêneros — Ctrl/Cmd para escolher vários
        <select name="generos" multiple>${opcoes(estado.generos, jogo?.generos.map((g) => g.id) ?? [])}</select></label>
      <label>Resumo<textarea name="resumo" rows="3">${esc(jogo?.resumo)}</textarea></label>
      <p class="erro-form" id="erro-form"></p>
      <div class="botoes"><button class="principal">${edicao ? "Salvar alterações" : "Cadastrar"}</button>
        <button type="button" id="cancelar">Cancelar</button></div>
    </form></div>`;
  $("cancelar").onclick = () => $("cadastro").close();
  $("form-jogo").onsubmit = async (ev) => {
    ev.preventDefault();
    const f = ev.target;
    const ids = (nome) => [...f[nome].selectedOptions].map((o) => Number(o.value));
    const corpo = { nome: f.nome.value, categorias: ids("categorias"), generos: ids("generos"), resumo: f.resumo.value || null };
    if (f.data_lancamento.value || edicao) corpo.data_lancamento = f.data_lancamento.value || null;
    try {
      const salvo = await api(edicao ? `/cat/jogos/${jogo.id}` : "/cat/jogos",
        { method: edicao ? "PUT" : "POST", body: JSON.stringify(corpo) });
      $("cadastro").close();
      await buscar();
      await escolherPerfil(estado.perfilId);
      mostrarDetalhe(salvo.id);
    } catch (e) { $("erro-form").textContent = e.message; }
  };
  $("cadastro").showModal();
}
$("novo-jogo").onclick = () => formularioJogo(null);

// ---------- Busca ----------
async function buscar() {
  const p = new URLSearchParams({ pagina: estado.pagina, por_pagina: 24, ordem: $("ordem").value });
  for (const k of ["q", "familia", "categoria", "genero", "ano"]) if ($(k).value) p.set(k, $(k).value);
  if ($("so-imagem").checked) p.set("com_imagem", "1");
  $("resultados").classList.add("carregando");
  const d = await api("/cat/jogos?" + p);
  $("resultados").classList.remove("carregando");
  estado.paginas = Math.max(1, Math.ceil(d.total / d.por_pagina));
  $("info").textContent = `${d.total.toLocaleString("pt-BR")} jogos encontrados`;
  $("rotulo-pagina").textContent = `Página ${estado.pagina} de ${estado.paginas}`;
  $("anterior").disabled = estado.pagina <= 1;
  $("proxima").disabled = estado.pagina >= estado.paginas;
  desenhar($("resultados"), d.resultados);
  atualizarBotoes();
}

let temporizador;
const novaBusca = () => { estado.pagina = 1; buscar(); };
$("q").oninput = () => { clearTimeout(temporizador); temporizador = setTimeout(novaBusca, 300); };
["familia", "categoria", "genero", "ano", "ordem", "so-imagem"].forEach((k) => ($(k).onchange = novaBusca));

// Botões grandes de marca (PlayStation / Xbox / Nintendo)
document.querySelectorAll(".marca").forEach((b) => {
  if (b.dataset.familia) b.innerHTML = `${iconeMarca(b.dataset.familia)} ${b.dataset.familia}`;
  b.onclick = () => {
    document.querySelectorAll(".marca").forEach((x) => x.classList.toggle("ativa", x === b));
    $("familia").value = b.dataset.familia;
    $("categoria").value = "";
    $("familia").dispatchEvent(new Event("change"));
  };
});

$("limpar").onclick = () => {
  $("filtros").reset();
  $("familia").value = "";
  document.querySelectorAll(".marca").forEach((x) => x.classList.toggle("ativa", !x.dataset.familia));
  $("familia").dispatchEvent(new Event("change"));
};
$("familia").addEventListener("change", () => {
  const fam = $("familia").value;
  $("categoria").innerHTML = '<option value="">Todas as plataformas</option>' + estado.categorias
    .filter((c) => !fam || c.familia === fam)
    .map((c) => `<option value="${c.id}">${esc(c.nome)} (${c.total_jogos})</option>`).join("");
});
$("filtros").onsubmit = (e) => e.preventDefault();
$("anterior").onclick = () => { estado.pagina--; buscar(); window.scrollTo(0, 0); };
$("proxima").onclick = () => { estado.pagina++; buscar(); window.scrollTo(0, 0); };

// ---------- Abas ----------
function aba(nome) {
  $("vista-busca").hidden = nome !== "busca";
  $("vista-salvos").hidden = nome !== "salvos";
  $("aba-busca").classList.toggle("ativa", nome === "busca");
  $("aba-salvos").classList.toggle("ativa", nome === "salvos");
}
$("aba-busca").onclick = () => aba("busca");
$("aba-salvos").onclick = () => aba("salvos");

// ---------- Início ----------
(async () => {
  [estado.categorias, estado.generos] = await Promise.all([api("/cat"), api("/generos")]);
  $("familia").dispatchEvent(new Event("change"));
  $("genero").innerHTML += estado.generos.map((g) => `<option value="${g.id}">${iconeGenero(g.nome)} ${esc(g.nome)}</option>`).join("");
  api("/estatisticas").then((e) => {
    $("numeros").innerHTML = [
      [e.total_jogos.toLocaleString("pt-BR"), "jogos"], [e.total_categorias, "plataformas"],
      [Object.keys(e.por_familia).length, "marcas"],
    ].map(([n, t]) => `<div><b>${n}</b><span>${t}</span></div>`).join("");
  });
  await carregarPerfis();
  await buscar();
})();
