// ---------------------------------------------------------------
// clube.js
// Lógica da página do Clube do Livro: ciclo atual, ideias de
// discussão e histórico de ciclos já concluídos.
// Utilitários compartilhados (apiFetch, escapeHtml, etc.) vêm de common.js.
// ---------------------------------------------------------------

const connectionBanner = document.getElementById("connection-banner");
const clubFeedback = document.getElementById("club-feedback");
const currentContainer = document.getElementById("current-session-container");
const historyContainer = document.getElementById("club-history-container");

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

async function loadAll() {
  await loadCurrentSession();
  await loadHistory();
}

// ---------------- ciclo atual / escolher livro ----------------

async function loadCurrentSession() {
  showFeedback(clubFeedback, "Carregando…", "loading");

  try {
    const sessao = await apiFetch("/api/club/current");
    clearFeedback(clubFeedback);
    if (sessao) {
      renderCurrentSession(sessao);
    } else {
      renderBookPicker();
    }
  } catch (err) {
    clearFeedback(clubFeedback);
    showFeedback(clubFeedback, err.message);
  }
}

function renderCurrentSession(sessao) {
  const autores = sessao.authors || "Autor desconhecido";
  const ano = sessao.first_publish_year ? ` · ${sessao.first_publish_year}` : "";

  const coverHtml = sessao.cover_url
    ? `<img class="detail-cover" src="${escapeHtml(sessao.cover_url)}" alt="Capa de ${escapeHtml(sessao.title)}">`
    : `<div class="detail-cover-placeholder">?</div>`;

  const ideasHtml = renderIdeasHtml(sessao.ideas, true);

  currentContainer.innerHTML = `
    <article class="detail-card">
      <p class="detail-section-title">Leitura atual do clube</p>
      <div class="detail-hero">
        ${coverHtml}
        <div class="detail-info">
          <h2 class="detail-title">${escapeHtml(sessao.title)}</h2>
          <p class="detail-authors">${escapeHtml(autores)}${ano}</p>
          <ul class="detail-meta-list">
            <li><strong>Início</strong> ${escapeHtml(sessao.start_date || "—")}</li>
          </ul>
          <div class="detail-actions">
            <button type="button" class="link-title" id="view-book-link">Ver detalhes do livro</button>
          </div>
        </div>
      </div>

      <div class="detail-section">
        <div class="review-actions" style="justify-content: space-between; align-items: center;">
          <p class="detail-section-title" style="margin: 0;">Ideias para discussão</p>
        </div>
        <div class="idea-list" id="idea-list">${ideasHtml}</div>
        <form class="idea-form-row" id="idea-form">
          <textarea class="quote-textarea" id="idea-input" placeholder="Uma pergunta ou tópico para discutir…" rows="2"></textarea>
          <button class="btn btn-small" type="submit">Adicionar ideia</button>
        </form>
      </div>

      <div class="detail-section" id="conclude-section">
        <button class="btn" type="button" id="conclude-btn">Concluir leitura</button>
        <div id="conclude-form-area"></div>
      </div>
    </article>
  `;

  document.getElementById("view-book-link").addEventListener("click", () => {
    window.location.href = `book.html?id=${sessao.book_id}`;
  });

  wireIdeaRemoveButtons();

  document.getElementById("idea-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const input = document.getElementById("idea-input");
    const idea = input.value.trim();
    if (!idea) return;

    try {
      await apiFetch(`/api/club/sessions/${sessao.id}/ideas`, {
        method: "POST",
        body: JSON.stringify({ idea }),
      });
      await loadCurrentSession();
    } catch (err) {
      showFeedback(clubFeedback, err.message);
    }
  });

  document.getElementById("conclude-btn").addEventListener("click", () => {
    renderConcludeForm(sessao);
  });
}

function renderConcludeForm(sessao) {
  const areaEl = document.getElementById("conclude-form-area");

  areaEl.innerHTML = `
    <form id="conclude-form">
      <div class="dates-row">
        <div class="field-group">
          <label for="end-date-input">Data de término</label>
          <input type="date" id="end-date-input" value="${todayIso()}">
        </div>
      </div>
      <label for="conclusions-input" class="search-slip-label">Conclusões da leitura</label>
      <textarea class="review-textarea" id="conclusions-input" placeholder="O que o clube achou? Principais pontos da discussão…"></textarea>
      <div class="review-actions">
        <button class="btn btn-small btn-ghost" type="button" id="cancel-conclude-btn">Cancelar</button>
        <button class="btn btn-small" type="submit">Salvar e concluir</button>
      </div>
    </form>
  `;

  document.getElementById("cancel-conclude-btn").addEventListener("click", () => {
    areaEl.innerHTML = "";
  });

  document.getElementById("conclude-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const endDate = document.getElementById("end-date-input").value;
    const conclusions = document.getElementById("conclusions-input").value;

    try {
      await apiFetch(`/api/club/sessions/${sessao.id}/conclude`, {
        method: "POST",
        body: JSON.stringify({ end_date: endDate, conclusions }),
      });
      await loadAll();
    } catch (err) {
      showFeedback(clubFeedback, err.message);
    }
  });
}

async function renderBookPicker() {
  currentContainer.innerHTML = `
    <section class="search-slip" aria-label="Escolher livro atual do clube">
      <p class="detail-section-title">Nenhuma leitura em andamento no clube</p>
      <div class="dates-row">
        <div class="field-group">
          <label for="picker-start-date">Data de início</label>
          <input type="date" id="picker-start-date" value="${todayIso()}">
        </div>
      </div>
      <label for="picker-search" class="search-slip-label">Escolha um livro já salvo no catálogo</label>
      <div class="search-row">
        <input type="text" id="picker-search" placeholder="Filtrar por título ou autor…" autocomplete="off">
      </div>
    </section>
    <div id="picker-results" class="results"></div>
  `;

  let todosOsLivros;
  try {
    todosOsLivros = await apiFetch("/api/books");
  } catch (err) {
    showFeedback(clubFeedback, err.message);
    return;
  }

  const resultsEl = document.getElementById("picker-results");

  function renderPickerResults(filtro) {
    const termo = filtro.trim().toLowerCase();
    const filtrados = termo
      ? todosOsLivros.filter(
          (l) =>
            l.title.toLowerCase().includes(termo) ||
            (l.authors || "").toLowerCase().includes(termo)
        )
      : todosOsLivros;

    if (filtrados.length === 0) {
      resultsEl.innerHTML = `<p class="empty-state">Nenhum livro encontrado. Salve livros pela página de Busca primeiro.</p>`;
      return;
    }

    resultsEl.innerHTML = filtrados.map(renderPickerCard).join("");

    resultsEl.querySelectorAll("[data-start-book]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const bookId = Number(btn.dataset.startBook);
        const startDate = document.getElementById("picker-start-date").value;

        btn.disabled = true;
        btn.textContent = "Iniciando…";
        try {
          await apiFetch("/api/club/sessions", {
            method: "POST",
            body: JSON.stringify({ book_id: bookId, start_date: startDate }),
          });
          await loadCurrentSession();
        } catch (err) {
          btn.disabled = false;
          btn.textContent = "Definir como leitura atual";
          showFeedback(clubFeedback, err.message);
        }
      });
    });
  }

  function renderPickerCard(livro) {
    const autores = livro.authors || "Autor desconhecido";
    const ano = livro.first_publish_year ? ` · ${livro.first_publish_year}` : "";
    const coverHtml = livro.cover_url
      ? `<img class="card-cover" src="${escapeHtml(livro.cover_url)}" alt="">`
      : `<div class="card-cover-placeholder">?</div>`;

    return `
      <article class="card">
        ${coverHtml}
        <div class="card-body">
          <p class="card-title">${escapeHtml(livro.title)}</p>
          <p class="card-meta">${escapeHtml(autores)}${ano}</p>
        </div>
        <div class="card-actions">
          <button class="btn btn-small" type="button" data-start-book="${livro.book_id}">Definir como leitura atual</button>
        </div>
      </article>
    `;
  }

  renderPickerResults("");

  document.getElementById("picker-search").addEventListener("input", (e) => {
    renderPickerResults(e.target.value);
  });
}

// ---------------- ideias (compartilhado entre ciclo atual e histórico) ----------------

function renderIdeasHtml(ideas, removable) {
  if (!ideas || ideas.length === 0) {
    return `<p class="empty-note">Nenhuma ideia registrada ainda.</p>`;
  }

  return ideas
    .map(
      (i) => `
        <div class="idea-item" data-idea-id="${i.id}">
          <span>${escapeHtml(i.idea)}</span>
          ${removable ? `<button class="idea-remove-btn" type="button" data-remove-idea="${i.id}" aria-label="Remover ideia">×</button>` : ""}
        </div>
      `
    )
    .join("");
}

function wireIdeaRemoveButtons() {
  document.querySelectorAll("[data-remove-idea]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      try {
        await apiFetch(`/api/club/ideas/${btn.dataset.removeIdea}`, { method: "DELETE" });
        await loadCurrentSession();
      } catch (err) {
        showFeedback(clubFeedback, err.message);
      }
    });
  });
}

// ---------------- histórico ----------------

async function loadHistory() {
  try {
    const historico = await apiFetch("/api/club/history");
    renderHistory(historico);
  } catch (err) {
    historyContainer.innerHTML = "";
    showFeedback(clubFeedback, err.message);
  }
}

function renderHistory(historico) {
  if (historico.length === 0) {
    historyContainer.innerHTML = `<p class="empty-state">O clube ainda não concluiu nenhuma leitura.</p>`;
    return;
  }

  historyContainer.innerHTML = historico.map(renderHistoryCard).join("");

  historico.forEach((sessao) => {
    const cardEl = historyContainer.querySelector(`[data-session-id="${sessao.id}"]`);

    cardEl.querySelector(".link-title").addEventListener("click", () => {
      window.location.href = `book.html?id=${sessao.book_id}`;
    });

    cardEl.querySelector("[data-edit-session]").addEventListener("click", () => {
      renderHistoryEditForm(cardEl, sessao);
    });

    cardEl.querySelector("[data-delete-session]").addEventListener("click", async () => {
      const confirmado = window.confirm(
        `Apagar o registro de "${sessao.title}" do histórico do clube? Essa ação não pode ser desfeita.`
      );
      if (!confirmado) return;

      try {
        await apiFetch(`/api/club/sessions/${sessao.id}`, { method: "DELETE" });
        await loadHistory();
      } catch (err) {
        showFeedback(clubFeedback, err.message);
      }
    });
  });
}

function renderHistoryCard(sessao) {
  const autores = sessao.authors || "Autor desconhecido";
  const coverHtml = sessao.cover_url
    ? `<img class="card-cover" src="${escapeHtml(sessao.cover_url)}" alt="">`
    : `<div class="card-cover-placeholder">?</div>`;

  const conclusionsHtml = sessao.conclusions
    ? `<p class="club-history-conclusions">${escapeHtml(sessao.conclusions)}</p>`
    : `<p class="empty-note">Sem conclusões registradas.</p>`;

  return `
    <article class="club-history-card" data-session-id="${sessao.id}">
      ${coverHtml}
      <div class="card-body">
        <button type="button" class="list-item-title link-title">${escapeHtml(sessao.title)}</button>
        <p class="club-history-meta">${escapeHtml(autores)} · ${escapeHtml(sessao.start_date || "—")} a ${escapeHtml(sessao.end_date || "—")}</p>
        <div class="idea-list">${renderIdeasHtml(sessao.ideas, false)}</div>
        ${conclusionsHtml}
        <div class="review-actions">
          <button class="btn btn-small btn-ghost" type="button" data-edit-session="${sessao.id}">Editar</button>
          <button class="btn btn-small btn-ghost" type="button" data-delete-session="${sessao.id}">Apagar</button>
        </div>
        <div data-edit-area="${sessao.id}"></div>
      </div>
    </article>
  `;
}

function renderHistoryEditForm(cardEl, sessao) {
  const areaEl = cardEl.querySelector(`[data-edit-area="${sessao.id}"]`);

  areaEl.innerHTML = `
    <form class="edit-list-form">
      <div class="dates-row">
        <div class="field-group">
          <label>Início</label>
          <input type="date" id="edit-start-${sessao.id}" value="${sessao.start_date || ""}">
        </div>
        <div class="field-group">
          <label>Término</label>
          <input type="date" id="edit-end-${sessao.id}" value="${sessao.end_date || ""}">
        </div>
      </div>
      <textarea class="review-textarea" id="edit-conclusions-${sessao.id}">${escapeHtml(sessao.conclusions || "")}</textarea>
      <div>
        <button class="btn btn-small" type="submit">Salvar</button>
        <button class="btn btn-small btn-ghost" type="button" data-cancel-edit>Cancelar</button>
      </div>
    </form>
  `;

  areaEl.querySelector("[data-cancel-edit]").addEventListener("click", () => {
    areaEl.innerHTML = "";
  });

  areaEl.querySelector("form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const startDate = document.getElementById(`edit-start-${sessao.id}`).value;
    const endDate = document.getElementById(`edit-end-${sessao.id}`).value;
    const conclusions = document.getElementById(`edit-conclusions-${sessao.id}`).value;

    try {
      await apiFetch(`/api/club/sessions/${sessao.id}`, {
        method: "PATCH",
        body: JSON.stringify({ start_date: startDate, end_date: endDate, conclusions }),
      });
      await loadHistory();
    } catch (err) {
      showFeedback(clubFeedback, err.message);
    }
  });
}

checkApiConnection(connectionBanner);
loadAll();