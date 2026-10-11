// Prototype-only helpers. No product logic, no network.
// Each page sets window.PROTO = { states: [[key, label], ...], initial, onState? }.
(() => {
  const cfg = window.PROTO;
  const params = new URLSearchParams(location.search);
  const valid = new Set(cfg.states.map(([key]) => key));
  let current = valid.has(params.get("state")) ? params.get("state") : cfg.initial;

  const panel = document.createElement("details");
  panel.className = "proto-switch glass";
  panel.open = matchMedia("(min-width: 821px)").matches;
  panel.innerHTML = `<summary>Prototype states <span aria-hidden="true">▾</span></summary><ul></ul>
    <div class="proto-links small"><a href="index.html">All prototypes</a></div>`;
  const list = panel.querySelector("ul");
  for (const [key, label] of cfg.states) {
    const li = document.createElement("li");
    li.innerHTML = `<button type="button" data-key="${key}">${label}</button>`;
    list.append(li);
  }
  list.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-key]");
    if (button) apply(button.dataset.key, true);
  });
  // ?clean hides prototype chrome (used for screenshots).
  if (!params.has("clean")) document.body.append(panel);

  function apply(state, fromUser) {
    current = state;
    document.querySelectorAll("[data-state]").forEach((el) => {
      el.hidden = !el.dataset.state.split(" ").includes(state);
    });
    list.querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.key === state)));
    document.body.dataset.view = state;
    if (fromUser) {
      const url = new URL(location.href);
      url.searchParams.set("state", state);
      history.replaceState(null, "", url);
    }
    cfg.onState?.(state);
  }

  // Dialogs: [data-open="id"], [data-close]; state jumps: [data-goto="state"]
  document.addEventListener("click", (event) => {
    const opener = event.target.closest("[data-open]");
    if (opener) document.getElementById(opener.dataset.open)?.showModal();
    const closer = event.target.closest("[data-close]");
    if (closer) closer.closest("dialog")?.close();
    const goto = event.target.closest("[data-goto]");
    if (goto) apply(goto.dataset.goto, true);
  });
  document.querySelectorAll("dialog.sheet").forEach((dialog) => {
    dialog.addEventListener("click", (event) => { if (event.target === dialog) dialog.close(); });
  });

  window.protoApply = apply;
  apply(current, false);
})();
