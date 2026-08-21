// ---------------------------------------------------------------
// book.js
// Lógica da página de detalhes de um livro (book.html).
// Utilitários compartilhados (apiFetch, escapeHtml, etc.) vêm de common.js.
// ---------------------------------------------------------------

const connectionBanner = document.getElementById("connection-banner");
const detailFeedback = document.getElementById("detail-feedback");
const detailContainer = document.getElementById("detail-container");

function getBookIdFromUrl() {
  const params = new URLSearchParams(window.location.search);
  const id = params.get("id");
  return id ? Number(id) : null;
}

// Remove eventuais tags HTML simples que a Google Books às vezes inclui
// na descrição (ex: <b>, <br>), mantendo só o texto.
function stripHtml(str) {
  const div = document.createElement("div");
  div.innerHTML = str ?? "";
  return div.textContent || "";
}

async function loadDetail() {
  const bookId = getBookIdFromUrl();

  if (!bookId) {
    showFeedback(detailFeedback, "Nenhum livro informado na URL.");
    return;
  }

  showFeedback(detailFeedback, "Carregando…", "loading");

  try {
    const livro = await apiFetch(`/api/books/${bookId}`);
    clearFeedback(detailFeedback);
    renderDetail(livro);
  } catch (err) {
    clearFeedback(detailFeedback);
    showFeedback(detailFeedback, err.message);
  }
}

function renderDetail(livro) {
  const autores = livro.authors || "Autor desconhecido";
  const ano = livro.first_publish_year || "—";

  const coverHtml = livro.cover_url
    ? `<img class="detail-cover" src="${escapeHtml(livro.cover_url)}" alt="Capa de ${escapeHtml(livro.title)}">`
    : `<div class="detail-cover-placeholder">?</div>`;

  const metaItems = [];
  metaItems.push(`<li><strong>Ano</strong> ${escapeHtml(String(ano))}</li>`);
  if (livro.publisher) metaItems.push(`<li><strong>Editora</strong> ${escapeHtml(livro.publisher)}</li>`);
  if (livro.page_count) metaItems.push(`<li><strong>Páginas</strong> ${escapeHtml(String(livro.page_count))}</li>`);
  if (livro.isbn) metaItems.push(`<li><strong>ISBN</strong> ${escapeHtml(livro.isbn)}</li>`);

  const googleRatingHtml = livro.average_rating
    ? `<p class="google-rating">★ ${livro.average_rating.toFixed(1)} — avaliação pública na Google Books</p>`
    : "";

  const categories = livro.categories || [];
  const chipsHtml = categories.length
    ? `<div class="chip-row">${categories.map((c) => `<span class="chip">${escapeHtml(c)}</span>`).join("")}</div>`
    : "";

  const descricaoHtml = livro.description
    ? `<p class="detail-description">${escapeHtml(stripHtml(livro.description))}</p>`
    : "";

  detailContainer.innerHTML = `
    <article class="detail-card">
      <div class="detail-hero">
        ${coverHtml}
        <div class="detail-info">
          <h1 class="detail-title">${escapeHtml(livro.title)}</h1>
          <p class="detail-authors">${escapeHtml(autores)}</p>
          <ul class="detail-meta-list">${metaItems.join("")}</ul>
          ${googleRatingHtml}
          ${chipsHtml}
          <div class="detail-actions" id="detail-actions"></div>
        </div>
      </div>
      ${descricaoHtml}
    </article>
  `;

  renderActions(livro);
}

function renderActions(livro) {
  const actionsEl = document.getElementById("detail-actions");

  // Livro ainda não está em nenhuma gaveta -> oferece adicionar
  if (!livro.status) {
    actionsEl.innerHTML = `<button class="btn" type="button" id="add-list-btn">Adicionar à lista</button>`;
    document.getElementById("add-list-btn").addEventListener("click", async (e) => {
      const btn = e.target;
      btn.disabled = true;
      btn.textContent = "Adicionando…";
      try {
        await apiFetch(`/api/list/${livro.book_id}`, {
          method: "POST",
          body: JSON.stringify({ status: "quero_ler" }),
        });
        await loadDetail(); // recarrega já com os controles de status/rating
      } catch (err) {
        btn.disabled = false;
        btn.textContent = "Adicionar à lista";
        showFeedback(detailFeedback, err.message);
      }
    });
    return;
  }

  // Livro já está na lista -> mostra carimbo, seletor de status, nota e remover
  const statusOptions = Object.entries(STATUS_LABELS)
    .map(
      ([value, label]) =>
        `<option value="${value}" ${value === livro.status ? "selected" : ""}>${label}</option>`
    )
    .join("");

  const rating = livro.rating || 0;
  const starsHtml = [1, 2, 3, 4, 5]
    .map(
      (n) =>
        `<button type="button" data-value="${n}" class="${n <= rating ? "filled" : ""}" aria-label="Avaliar com ${n} estrela(s)">★</button>`
    )
    .join("");

  actionsEl.innerHTML = `
    <span class="stamp stamp-${livro.status}">${STATUS_LABELS[livro.status]}</span>
    <div class="rating" role="group" aria-label="Avaliação">${starsHtml}</div>
    <select class="status-select" aria-label="Mudar status">${statusOptions}</select>
    <button class="remove-btn" type="button" aria-label="Remover da lista">×</button>
  `;

  actionsEl.querySelectorAll(".rating button").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const value = Number(btn.dataset.value);
      try {
        await apiFetch(`/api/list/${livro.book_id}/rating`, {
          method: "POST",
          body: JSON.stringify({ rating: value }),
        });
        await loadDetail();
      } catch (err) {
        showFeedback(detailFeedback, err.message);
      }
    });
  });

  actionsEl.querySelector(".status-select").addEventListener("change", async (e) => {
    try {
      await apiFetch(`/api/list/${livro.book_id}`, {
        method: "POST",
        body: JSON.stringify({ status: e.target.value }),
      });
      await loadDetail();
    } catch (err) {
      showFeedback(detailFeedback, err.message);
    }
  });

  actionsEl.querySelector(".remove-btn").addEventListener("click", async () => {
    try {
      await apiFetch(`/api/list/${livro.book_id}`, { method: "DELETE" });
      await loadDetail(); // volta para o estado "adicionar à lista"
    } catch (err) {
      showFeedback(detailFeedback, err.message);
    }
  });
}

checkApiConnection(connectionBanner);
loadDetail();