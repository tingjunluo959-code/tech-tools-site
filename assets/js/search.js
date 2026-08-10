"use strict";

document.addEventListener("DOMContentLoaded", () => {
  const input = document.getElementById("siteSearchInput");
  const clearButton = document.getElementById("siteSearchClear");
  const count = document.getElementById("siteSearchCount");
  const empty = document.getElementById("siteSearchEmpty");
  const items = Array.from(document.querySelectorAll(".search-result-item"));

  if (!input || !clearButton || !count || !empty) {
    return;
  }

  const normalize = (value) => value.normalize("NFKC").trim().toLocaleLowerCase();

  const render = () => {
    const query = normalize(input.value);
    let visible = 0;

    items.forEach((item) => {
      const matches = !query || normalize(item.dataset.searchText || "").includes(query);
      item.hidden = !matches;
      visible += matches ? 1 : 0;
    });

    count.textContent = `${visible} ${count.dataset.label || ""}`.trim();
    empty.classList.toggle("hidden", visible !== 0);
  };

  input.addEventListener("input", render);
  input.addEventListener("search", render);
  clearButton.addEventListener("click", () => {
    input.value = "";
    input.focus();
    render();
  });

  const initialQuery = new URLSearchParams(window.location.search).get("q") || "";
  input.value = initialQuery;
  render();
});
