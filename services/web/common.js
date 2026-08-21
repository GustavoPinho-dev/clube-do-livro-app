// ---------------------------------------------------------------
// common.js
// Utilitários compartilhados entre as páginas do serviço web.
// Depende de API_BASE_URL, definido em config.js (incluído antes
// deste arquivo em cada página HTML).
// ---------------------------------------------------------------

const STATUS_LABELS = {
  quero_ler: "Quero ler",
  lendo: "Lendo",
  lido: "Lido",
};

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}

function showFeedback(container, message, type = "error") {
  container.innerHTML = `<div class="${type === "error" ? "error-banner" : "loading"}">${escapeHtml(message)}</div>`;
}

function clearFeedback(container) {
  container.innerHTML = "";
}

async function apiFetch(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.error || `Erro ${response.status}`);
  }
  return data;
}

async function checkApiConnection(bannerEl) {
  try {
    await apiFetch("/health");
    bannerEl.innerHTML = "";
  } catch (err) {
    bannerEl.innerHTML = `<div class="error-banner">Não foi possível conectar à API em ${API_BASE_URL}. Verifique se o serviço está rodando.</div>`;
  }
}