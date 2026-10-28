// Funções compartilhadas pelas três páginas: chamadas à API, ícones, cabeçalho e rodapé.

async function api(caminho, opcoes = {}) {
  // caminho relativo ("cat/jogos"): funciona na raiz (Flask) e em subpasta (github.io/repositorio/)
  const res = await fetch(caminho.replace(/^\//, ""), { headers: { "Content-Type": "application/json" }, ...opcoes });
  if (!res.ok) {
    const corpo = await res.json().catch(() => ({}));
    throw new Error(corpo.erro || res.statusText);
  }
  return res.status === 204 ? null : res.json();
}

const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

// ---------- Ícones (SVGs próprios, desenhados com formas simples) ----------
const CORES = { PlayStation: "#2f6fe4", Xbox: "#2a9d4b", Nintendo: "#e4352f", Outras: "#8a63d2" };

const ICONES_MARCA = {
  PlayStation: `<svg viewBox="0 0 32 32" aria-hidden="true"><circle cx="9" cy="9" r="4" fill="none" stroke="currentColor" stroke-width="2.4"/><path d="M20 5l5 8.7h-10z" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linejoin="round"/><path d="M5 20l8 8M13 20l-8 8" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/><rect x="18" y="20" width="8" height="8" rx="1" fill="none" stroke="currentColor" stroke-width="2.4"/></svg>`,
  Xbox: `<svg viewBox="0 0 32 32" aria-hidden="true"><circle cx="16" cy="16" r="12.5" fill="none" stroke="currentColor" stroke-width="2.4"/><path d="M9.5 9.5c3 2.5 4.5 4.5 6.5 6.5s3.5 4 6.5 6.5M22.5 9.5c-3 2.5-4.5 4.5-6.5 6.5s-3.5 4-6.5 6.5" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/></svg>`,
  Nintendo: `<svg viewBox="0 0 32 32" aria-hidden="true"><rect x="3" y="6" width="26" height="20" rx="10" fill="none" stroke="currentColor" stroke-width="2.4"/><circle cx="11" cy="16" r="3" fill="currentColor"/><circle cx="21" cy="16" r="3" fill="none" stroke="currentColor" stroke-width="2.4"/><path d="M16 6v20" stroke="currentColor" stroke-width="2.4"/></svg>`,
  Outras: `<svg viewBox="0 0 32 32" aria-hidden="true"><rect x="4" y="9" width="24" height="14" rx="5" fill="none" stroke="currentColor" stroke-width="2.4"/><path d="M10 16h5M12.5 13.5v5" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/></svg>`,
};

function iconeMarca(familia, classe = "") {
  const f = ICONES_MARCA[familia] ? familia : "Outras";
  return `<span class="icone-marca ${classe}" style="--cor:${CORES[f]}" title="${esc(familia)}">${ICONES_MARCA[f]}</span>`;
}

const ICONES_GENERO = {
  "Luta": "🥊", "Tiro": "🔫", "Música": "🎵", "Plataforma": "🍄", "Quebra-cabeça": "🧩", "Corrida": "🏎️",
  "Estratégia em tempo real (RTS)": "♟️", "RPG": "⚔️", "Simulador": "🛠️", "Esportes": "⚽", "Estratégia": "♟️",
  "Estratégia por turnos": "♟️", "Tático": "🎯", "Quiz/Trivia": "❓", "Hack and slash": "🗡️", "Pinball": "🎱",
  "Aventura": "🗺️", "Arcade": "🕹️", "Visual novel": "📖", "Indie": "💡", "Cartas e tabuleiro": "🃏",
  "MOBA": "🛡️", "Point-and-click": "🖱️",
};
const iconeGenero = (nome) => ICONES_GENERO[nome] || "🎮";

// Como o dataset não traz capas, cada jogo ganha uma "capa" gerada: cor da marca + ícone do gênero.
// Quando o jogo tem imagem (RAWG), ela cobre a capa gerada; se não carregar (sem internet), a capa gerada aparece.
function capa(jogo) {
  const familia = jogo.categorias?.[0]?.familia || "Outras";
  const emoji = iconeGenero(jogo.generos?.[0]?.nome);
  const url = jogo.imagem_url ? jogo.imagem_url.replace("/media/games/", "/media/crop/600/400/games/") : null;
  // 1º imagem local (web/capas/ID.jpg), 2º imagem online do RAWG, 3º capa gerada
  // (a imagem aparece duas vezes: uma borrada de fundo e outra inteira por cima)
  const tag = (classe, alt) => `<img class="${classe}" loading="lazy" referrerpolicy="no-referrer" alt="${alt}" src="capas/${jogo.id}.jpg" data-remota="${esc(url)}"
    onerror="if(this.dataset.remota){this.src=this.dataset.remota;delete this.dataset.remota}else{this.remove()}">`;
  const img = url ? tag("capa-fundo", "") + tag("capa-img", `Imagem de ${esc(jogo.nome)}`) : "";
  return `<div class="capa" style="--cor:${CORES[familia] || CORES.Outras}">
    <span class="capa-emoji">${emoji}</span>${img}${iconeMarca(familia, "capa-marca")}
    ${jogo.nota ? `<span class="capa-nota">⭐ ${Math.round(jogo.nota)}</span>` : ""}</div>`;
}

// ---------- Tema claro/escuro (lembra a escolha) ----------
try { const t = localStorage.getItem("tema"); if (t) document.documentElement.dataset.tema = t; } catch {}
function alternarTema() {
  const atual = document.documentElement.dataset.tema
    || (matchMedia("(prefers-color-scheme: light)").matches ? "claro" : "escuro");
  const novo = atual === "claro" ? "escuro" : "claro";
  document.documentElement.dataset.tema = novo;
  try { localStorage.setItem("tema", novo); } catch {}
}

// ---------- Cabeçalho e rodapé ----------
function montarLayout(paginaAtual) {
  const links = [["index.html", "Catálogo", "catalogo"], ["api.html", "Documentação da API", "api"], ["sobre.html", "Sobre e fontes dos dados", "sobre"]];
  document.body.insertAdjacentHTML("afterbegin", `
    <header class="topo"><div class="conteudo topo-in">
      <a class="logo" href="index.html"><span class="logo-ico">🎮</span><span>Catálogo de Jogos</span></a>
      <nav>${links.map(([h, t, id]) => `<a href="${h}" class="${id === paginaAtual ? "ativo" : ""}">${t}</a>`).join("")}
        <button class="tema" id="tema" title="Alternar tema claro/escuro" aria-label="Alternar tema">🌓</button></nav>
    </div></header>`);
  document.getElementById("tema").onclick = alternarTema;
  document.body.insertAdjacentHTML("beforeend", `
    <footer class="rodape"><div class="conteudo">
      <p><b>Trabalho de faculdade — API em Python (Flask).</b> Equipe: Gabriel Victor, Matheus Salomão e Lucas Lima.</p>
      <p>Fonte dos dados: dataset <a href="https://zenodo.org/records/10797761" target="_blank" rel="noopener">PlayMyData</a>
      (informações do <a href="https://www.igdb.com" target="_blank" rel="noopener">IGDB</a>), licença
      <a href="https://creativecommons.org/licenses/by/4.0/deed.pt-br" target="_blank" rel="noopener">CC BY 4.0</a>.
      <a href="sobre.html">Ver detalhes e arquivos baixados</a>.</p>
    </div></footer>`);
}
