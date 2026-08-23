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
      <div id="detail-extra"></div>
    </article>
  `;

  renderActions(livro);
  renderPersonalSections(livro);
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

function renderPersonalSections(livro) {
  const extraEl = document.getElementById("detail-extra");

  // Listas personalizadas não dependem de status de leitura -- só do livro
  // já estar salvo (o que sempre é verdade nesta página). Datas/resenha/
  // citações, por outro lado, vivem em user_lists e só existem se o livro
  // estiver em alguma gaveta (quero_ler/lendo/lido).
  const readingSectionsHtml = livro.status
    ? `
    <div class="detail-section">
      <p class="detail-section-title">Datas de leitura</p>
      <div class="dates-row">
        <div class="field-group">
          <label for="started-at">Início</label>
          <input type="date" id="started-at" value="${livro.started_at || ""}">
        </div>
        <div class="field-group">
          <label for="finished-at">Término</label>
          <input type="date" id="finished-at" value="${livro.finished_at || ""}">
        </div>
        <button class="btn btn-small" type="button" id="save-dates-btn">Salvar datas</button>
      </div>
    </div>

    <div class="detail-section">
      <p class="detail-section-title">Resenha</p>
      <textarea class="review-textarea" id="review-input" placeholder="O que você achou do livro?">${escapeHtml(livro.review || "")}</textarea>
      <div class="review-actions">
        <button class="btn btn-small" type="button" id="save-review-btn">Salvar resenha</button>
      </div>
    </div>

    <div class="detail-section">
      <p class="detail-section-title">Principais citações</p>
      <div class="quote-list" id="quote-list"></div>
      <div class="quote-form-row">
        <textarea class="quote-textarea" id="quote-input" placeholder="Digite uma citação marcante…"></textarea>
        <div class="field-group">
          <label for="quote-page">Página</label>
          <input type="number" id="quote-page" min="1">
        </div>
      </div>
      <div class="quote-form-actions">
        <button class="btn btn-small" type="button" id="add-quote-btn">Adicionar citação</button>
      </div>
    </div>
  `
    : `<p class="empty-note detail-section">Adicione este livro à sua lista para registrar datas de leitura, resenha e citações.</p>`;

  extraEl.innerHTML = `
    <div class="detail-section" id="custom-lists-section">
      <p class="detail-section-title">Listas personalizadas</p>
      <div id="custom-lists-checkboxes"><p class="loading">Carregando…</p></div>
      <a class="section-link" href="lists.html">+ criar nova lista</a>
    </div>
    ${readingSectionsHtml}
  `;

  renderCustomListsCheckboxes(livro);

  if (!livro.status) {
    return;
  }

  renderQuoteList(livro.quotes || [], livro.book_id);

  // --- datas ---
  document.getElementById("save-dates-btn").addEventListener("click", async (e) => {
    const btn = e.target;
    const startedAt = document.getElementById("started-at").value;
    const finishedAt = document.getElementById("finished-at").value;

    btn.disabled = true;
    try {
      await apiFetch(`/api/list/${livro.book_id}/dates`, {
        method: "POST",
        body: JSON.stringify({ started_at: startedAt, finished_at: finishedAt }),
      });
      btn.textContent = "Salvo ✓";
      setTimeout(() => {
        btn.textContent = "Salvar datas";
        btn.disabled = false;
      }, 1500);
    } catch (err) {
      btn.disabled = false;
      showFeedback(detailFeedback, err.message);
    }
  });

  // --- resenha ---
  document.getElementById("save-review-btn").addEventListener("click", async (e) => {
    const btn = e.target;
    const review = document.getElementById("review-input").value;

    btn.disabled = true;
    try {
      await apiFetch(`/api/list/${livro.book_id}/review`, {
        method: "POST",
        body: JSON.stringify({ review }),
      });
      btn.textContent = "Salvo ✓";
      setTimeout(() => {
        btn.textContent = "Salvar resenha";
        btn.disabled = false;
      }, 1500);
    } catch (err) {
      btn.disabled = false;
      showFeedback(detailFeedback, err.message);
    }
  });

  // --- adicionar citação ---
  document.getElementById("add-quote-btn").addEventListener("click", async (e) => {
    const btn = e.target;
    const quoteInput = document.getElementById("quote-input");
    const pageInput = document.getElementById("quote-page");

    const quote = quoteInput.value.trim();
    if (!quote) {
      showFeedback(detailFeedback, "Digite o texto da citação antes de adicionar.");
      return;
    }

    const page = pageInput.value ? Number(pageInput.value) : null;

    btn.disabled = true;
    btn.textContent = "Adicionando…";
    try {
      await apiFetch(`/api/books/${livro.book_id}/quotes`, {
        method: "POST",
        body: JSON.stringify({ quote, page }),
      });
      quoteInput.value = "";
      pageInput.value = "";
      await loadDetail(); // recarrega para trazer a citação já com id
    } catch (err) {
      showFeedback(detailFeedback, err.message);
    } finally {
      btn.disabled = false;
      btn.textContent = "Adicionar citação";
    }
  });
}

async function renderCustomListsCheckboxes(livro) {
  const containerEl = document.getElementById("custom-lists-checkboxes");

  let todasAsListas;
  try {
    todasAsListas = await apiFetch("/api/custom-lists");
  } catch (err) {
    containerEl.innerHTML = `<p class="loading">Não foi possível carregar as listas.</p>`;
    return;
  }

  if (todasAsListas.length === 0) {
    containerEl.innerHTML = `<p class="empty-note">Você ainda não criou nenhuma lista.</p>`;
    return;
  }

  const idsAtuais = new Set((livro.custom_lists || []).map((l) => l.id));

  containerEl.innerHTML = todasAsListas
    .map(
      (lista) => `
        <div class="list-checkbox-row">
          <input type="checkbox" id="clist-${lista.id}" data-list-id="${lista.id}" ${idsAtuais.has(lista.id) ? "checked" : ""}>
          <label for="clist-${lista.id}">${escapeHtml(lista.name)}</label>
        </div>
      `
    )
    .join("");

  containerEl.querySelectorAll('input[type="checkbox"]').forEach((checkbox) => {
    checkbox.addEventListener("change", async () => {
      const listId = checkbox.dataset.listId;
      checkbox.disabled = true;

      try {
        if (checkbox.checked) {
          await apiFetch(`/api/custom-lists/${listId}/books`, {
            method: "POST",
            body: JSON.stringify({ book_id: livro.book_id }),
          });
        } else {
          await apiFetch(`/api/custom-lists/${listId}/books/${livro.book_id}`, {
            method: "DELETE",
          });
        }
      } catch (err) {
        checkbox.checked = !checkbox.checked; // desfaz visualmente se der erro
        showFeedback(detailFeedback, err.message);
      } finally {
        checkbox.disabled = false;
      }
    });
  });
}

function renderQuoteList(quotes, bookId) {
  const listEl = document.getElementById("quote-list");

  if (quotes.length === 0) {
    listEl.innerHTML = `<p class="empty-note">Nenhuma citação registrada ainda.</p>`;
    return;
  }

  listEl.innerHTML = quotes
    .map(
      (q) => `
        <div class="quote-card" data-quote-id="${q.id}">
          “${escapeHtml(q.quote)}”
          ${q.page ? `<span class="quote-card-page">p. ${escapeHtml(String(q.page))}</span>` : ""}
          <button class="quote-remove-btn" type="button" data-quote-id="${q.id}" aria-label="Remover citação">×</button>
        </div>
      `
    )
    .join("");

  listEl.querySelectorAll(".quote-remove-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      try {
        await apiFetch(`/api/quotes/${btn.dataset.quoteId}`, { method: "DELETE" });
        await loadDetail();
      } catch (err) {
        showFeedback(detailFeedback, err.message);
      }
    });
  });
}

checkApiConnection(connectionBanner);
loadDetail();