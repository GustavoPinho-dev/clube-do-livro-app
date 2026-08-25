// ---------------------------------------------------------------
// nav.js
// Cabeçalho/menu compartilhado entre todas as páginas do serviço web.
//
// Cada página define <body data-page="busca|leituras|listas|clube"> para
// que o item correspondente do menu apareça destacado. Páginas que não são
// nenhum desses (ex: detalhe de um livro ou de uma lista) simplesmente não
// têm data-page, e nenhum item fica ativo.
// ---------------------------------------------------------------

const NAV_ITEMS = [
  { page: "listas", label: "Listas", href: "lists.html" },
  { page: "busca", label: "Busca", href: "index.html" },
  { page: "leituras", label: "Leituras", href: "leituras.html" },
  { page: "clube", label: "Clube do Livro", href: "clube.html" },
];

(function renderSiteNav() {
  const container = document.getElementById("site-nav");
  if (!container) return;

  const activePage = document.body.dataset.page;

  container.innerHTML = `
    <nav class="site-nav" aria-label="Navegação principal">
      <a class="site-nav-brand" href="index.html">Catálogo de Leituras</a>
      <div class="site-nav-links">
        ${NAV_ITEMS.map(
          (item) =>
            `<a href="${item.href}" class="site-nav-link${item.page === activePage ? " active" : ""}">${item.label}</a>`
        ).join("")}
      </div>
    </nav>
  `;
})();