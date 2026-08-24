// ---------------------------------------------------------------
// leituras.js
// Lógica da página de leituras: gavetas quero_ler/lendo/lido.
// Utilitários compartilhados (apiFetch, escapeHtml, etc.) vêm de common.js.
// ---------------------------------------------------------------

const connectionBanner = document.getElementById("connection-banner");
const listPanel = document.getElementById("list-panel");
const drawerTabs = document.getElementById("drawer-tabs");

let currentStatusFilter = "";

async function loadList() {
  showFeedback(listPanel, "Carregando…", "loading");

  try {
    const url = currentStatusFilter
      ? `/api/list?status=${encodeURIComponent(currentStatusFilter)}`
      : "/api/list";
    const livros = await apiFetch(url);
    renderList(livros);
  } catch (err) {
    showFeedback(listPanel, err.message);
  }
}

function renderList(livros) {
  if (livros.length === 0) {
    listPanel.innerHTML = `<p class="empty-state">Nenhum livro nesta gaveta ainda.</p>`;
    return;
  }

  listPanel.innerHTML = "";
  livros.forEach((livro) => listPanel.appendChild(renderListItem(livro)));
}

function renderListItem(livro) {
  const item = document.createElement("div");
  item.className = "list-item";

  const autores = livro.authors || "";
  const ano = livro.first_publish_year ? ` · ${livro.first_publish_year}` : "";
  const rating = livro.rating || 0;

  const statusOptions = Object.entries(STATUS_LABELS)
    .map(
      ([value, label]) =>
        `<option value="${value}" ${value === livro.status ? "selected" : ""}>${label}</option>`
    )
    .join("");

  const starsHtml = [1, 2, 3, 4, 5]
    .map(
      (n) =>
        `<button type="button" data-value="${n}" class="${n <= rating ? "filled" : ""}" aria-label="Avaliar com ${n} estrela(s)">★</button>`
    )
    .join("");

  item.innerHTML = `
    <span class="stamp stamp-${livro.status}">${STATUS_LABELS[livro.status]}</span>
    <div class="list-item-body">
      <button type="button" class="list-item-title link-title">${escapeHtml(livro.title)}</button>
      <p class="list-item-meta">${escapeHtml(autores)}${ano}</p>
    </div>
    <div class="rating" role="group" aria-label="Avaliação">${starsHtml}</div>
    <select class="status-select" aria-label="Mudar status">${statusOptions}</select>
    <button class="remove-btn" type="button" aria-label="Remover da lista">×</button>
  `;

  // Título leva aos detalhes -- aqui o livro já tem book_id garantido
  // (está na lista), então não precisa salvar de novo antes de navegar.
  item.querySelector(".link-title").addEventListener("click", () => {
    window.location.href = `book.html?id=${livro.book_id}`;
  });

  // Avaliação por estrelas
  item.querySelectorAll(".rating button").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const value = Number(btn.dataset.value);
      try {
        await apiFetch(`/api/list/${livro.book_id}/rating`, {
          method: "POST",
          body: JSON.stringify({ rating: value }),
        });
        await loadList();
      } catch (err) {
        showFeedback(listPanel, err.message);
      }
    });
  });

  // Mudança de status
  item.querySelector(".status-select").addEventListener("change", async (e) => {
    try {
      await apiFetch(`/api/list/${livro.book_id}`, {
        method: "POST",
        body: JSON.stringify({ status: e.target.value }),
      });
      await loadList();
    } catch (err) {
      showFeedback(listPanel, err.message);
    }
  });

  // Remover
  item.querySelector(".remove-btn").addEventListener("click", async () => {
    try {
      await apiFetch(`/api/list/${livro.book_id}`, { method: "DELETE" });
      await loadList();
    } catch (err) {
      showFeedback(listPanel, err.message);
    }
  });

  return item;
}

// ---------------- gavetas (filtro por status) ----------------

drawerTabs.addEventListener("click", (e) => {
  const tab = e.target.closest(".drawer-tab");
  if (!tab) return;

  drawerTabs.querySelectorAll(".drawer-tab").forEach((t) => t.classList.remove("active"));
  tab.classList.add("active");
  currentStatusFilter = tab.dataset.status;
  loadList();
});

// ---------------- inicialização ----------------

checkApiConnection(connectionBanner);
loadList();