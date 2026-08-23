// ---------------------------------------------------------------
// lists.js
// Lógica da página de listas personalizadas (lists.html).
// Utilitários compartilhados (apiFetch, escapeHtml, etc.) vêm de common.js.
// ---------------------------------------------------------------

const connectionBanner = document.getElementById("connection-banner");
const listsFeedback = document.getElementById("lists-feedback");
const listsGrid = document.getElementById("lists-grid");
const createForm = document.getElementById("create-list-form");
const nameInput = document.getElementById("list-name-input");
const descInput = document.getElementById("list-desc-input");

async function loadLists() {
  showFeedback(listsFeedback, "Carregando…", "loading");

  try {
    const listas = await apiFetch("/api/custom-lists");
    clearFeedback(listsFeedback);
    renderLists(listas);
  } catch (err) {
    clearFeedback(listsFeedback);
    showFeedback(listsFeedback, err.message);
  }
}

function renderLists(listas) {
  if (listas.length === 0) {
    listsGrid.innerHTML = `<p class="empty-state">Nenhuma lista personalizada ainda. Crie a primeira acima.</p>`;
    return;
  }

  listsGrid.innerHTML = "";
  listas.forEach((lista) => listsGrid.appendChild(renderListCard(lista)));
}

function renderListCard(lista) {
  const card = document.createElement("article");
  card.className = "list-card";

  const descHtml = lista.description
    ? `<p class="list-card-desc">${escapeHtml(lista.description)}</p>`
    : "";

  const contagem = lista.book_count === 1 ? "1 livro" : `${lista.book_count} livros`;

  card.innerHTML = `
    <div class="list-card-body">
      <p class="list-card-name">${escapeHtml(lista.name)}</p>
      ${descHtml}
      <p class="list-card-count">${contagem}</p>
    </div>
    <div class="list-card-actions">
      <button class="btn btn-small btn-ghost" type="button" data-action="open">Ver lista</button>
      <button class="remove-btn" type="button" data-action="delete" aria-label="Apagar lista">×</button>
    </div>
  `;

  card.querySelector('[data-action="open"]').addEventListener("click", () => {
    window.location.href = `list_detail.html?id=${lista.id}`;
  });

  card.querySelector('[data-action="delete"]').addEventListener("click", async () => {
    const confirmado = window.confirm(`Apagar a lista "${lista.name}"? Os livros continuam salvos, só a lista some.`);
    if (!confirmado) return;

    try {
      await apiFetch(`/api/custom-lists/${lista.id}`, { method: "DELETE" });
      await loadLists();
    } catch (err) {
      showFeedback(listsFeedback, err.message);
    }
  });

  return card;
}

createForm.addEventListener("submit", async (e) => {
  e.preventDefault();

  const name = nameInput.value.trim();
  if (!name) return;

  const submitBtn = createForm.querySelector("button[type=submit]");
  submitBtn.disabled = true;

  try {
    await apiFetch("/api/custom-lists", {
      method: "POST",
      body: JSON.stringify({ name, description: descInput.value.trim() }),
    });
    nameInput.value = "";
    descInput.value = "";
    clearFeedback(listsFeedback);
    await loadLists();
  } catch (err) {
    showFeedback(listsFeedback, err.message);
  } finally {
    submitBtn.disabled = false;
  }
});

checkApiConnection(connectionBanner);
loadLists();