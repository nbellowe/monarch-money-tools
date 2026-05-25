function renderMermaidDiagrams() {
  document.querySelectorAll("pre.mermaid").forEach((block) => {
    const code = block.querySelector("code");
    if (!code) {
      return;
    }
    const diagram = document.createElement("div");
    diagram.className = "mermaid";
    diagram.textContent = code.textContent;
    block.replaceWith(diagram);
  });

  if (!window.mermaid) {
    window.setTimeout(renderMermaidDiagrams, 100);
    return;
  }

  window.mermaid.initialize({
    startOnLoad: false,
    theme: document.body.getAttribute("data-md-color-scheme") === "slate" ? "dark" : "default",
  });
  window.mermaid.run({ querySelector: ".mermaid" });
}

if (typeof document$ !== "undefined") {
  document$.subscribe(renderMermaidDiagrams);
} else {
  document.addEventListener("DOMContentLoaded", renderMermaidDiagrams);
}
