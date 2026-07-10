/* plan-html sidebar + interactivity. Copy verbatim to plan/nav.js.
   The ONLY per-project edits live in the CONFIG block below.
   Every page just needs:  <script src="nav.js"></script>  before </body>. */

/* ============================ CONFIG ============================ */
/* Edit these four for your project. Adding a page = one line in PAGES. */

const PROJECT = "Watch Dashboard";
const TAGLINE = "personal Apple Watch health dashboard — plan log";

/* High-level arc. status: "done" | "wip" | "next" | "todo". */
const PHASES = [
  { n: 1, title: "Research",     status: "done" },
  { n: 2, title: "Requirements", status: "done" },
  { n: 3, title: "Build v1",     status: "done" },
  { n: 4, title: "Deploy + v2",  status: "next" },
];

/* One entry per page. n = creation order (stable doc id, also the filename
   prefix). phase = which PHASES.n it belongs to. Newest is rendered first
   automatically — just append. */
const PAGES = [
  { file: "1_requirements-architecture.html", n: 1, phase: 2, title: "Requirements & Architecture" },
  { file: "2_interface-design.html", n: 2, phase: 2, title: "Interface Design" },
  { file: "3_build-plan.html", n: 3, phase: 3, title: "Build Plan v1" },
  { file: "4_v2-build-plan.html", n: 4, phase: 4, title: "v2 Build Plan" },
];

/* ========================== END CONFIG ========================== */

const STATUS_ICON = { done: "✓", wip: "◐", next: "▸", todo: "○" };

/* ---- theme: apply saved choice ASAP to avoid a flash ---- */
(function applyTheme() {
  try {
    const t = localStorage.getItem("plan-theme");
    if (t) document.documentElement.setAttribute("data-theme", t);
  } catch (e) {}
})();

function toggleTheme() {
  const cur = document.documentElement.getAttribute("data-theme") === "light" ? "light" : "dark";
  const next = cur === "light" ? "dark" : "light";
  document.documentElement.setAttribute("data-theme", next);
  try { localStorage.setItem("plan-theme", next); } catch (e) {}
  const btn = document.querySelector(".theme-toggle");
  if (btn) btn.textContent = next === "light" ? "🌙 Dark" : "☀︎ Light";
}

function currentFile() {
  const p = location.pathname.split("/").pop();
  return p && p.length ? p : "index.html";
}

function buildSidebar() {
  const here = currentFile();
  const phaseTitle = {};
  PHASES.forEach(p => { phaseTitle[p.n] = p.title; });

  const roadmap = PHASES.map(p =>
    `<div class="rm-row ${p.status}">
       <span class="rm-ic">${STATUS_ICON[p.status] || "○"}</span>
       <span class="rm-n">${p.n}</span>
       <span class="rm-label">${p.title}</span>
     </div>`).join("");

  const docs = PAGES.slice().sort((a, b) => b.n - a.n).map(pg => {
    const active = pg.file === here ? " active" : "";
    const chip = phaseTitle[pg.phase] ? `<span class="phasechip">P${pg.phase}</span>` : "";
    return `<a class="doc${active}" href="${pg.file}">
              <span class="docnum">${pg.n}</span>
              <span class="doctitle">${pg.title}</span>${chip}
            </a>`;
  }).join("");

  const isLight = document.documentElement.getAttribute("data-theme") === "light";
  const aside = document.createElement("aside");
  aside.className = "sidebar";
  aside.innerHTML = `
    <div class="brand">
      <div class="brand-row">
        <div>
          <div class="brand-name">${PROJECT}</div>
          <div class="brand-tag">${TAGLINE}</div>
        </div>
        <button class="theme-toggle" onclick="toggleTheme()">${isLight ? "🌙 Dark" : "☀︎ Light"}</button>
      </div>
    </div>
    <div class="roadmap">
      <div class="rm-title">Roadmap</div>
      ${roadmap}
    </div>
    <div class="nav-title">Plan log · newest first</div>
    <nav>${docs}</nav>
    <div class="sidebar-foot">${PAGES.length} page${PAGES.length === 1 ? "" : "s"} · plan-html</div>`;
  document.body.prepend(aside);
}

/* ---- interactivity: tabs (<div class="tabs" data-tabs>) ---- */
function wireTabs() {
  document.querySelectorAll(".tabs[data-tabs]").forEach(tabs => {
    const bar = tabs.querySelector(".tabbar");
    const buttons = bar ? Array.from(bar.querySelectorAll("button")) : [];
    const panels = Array.from(tabs.querySelectorAll(".tabpanel"));
    buttons.forEach((btn, i) => {
      btn.addEventListener("click", () => {
        buttons.forEach(b => b.classList.remove("on"));
        panels.forEach(p => p.classList.remove("on"));
        btn.classList.add("on");
        if (panels[i]) panels[i].classList.add("on");
      });
    });
    if (buttons.length && !bar.querySelector("button.on")) buttons[0].classList.add("on");
    if (panels.length && !tabs.querySelector(".tabpanel.on")) panels[0].classList.add("on");
  });
}

/* ---- interactivity: flow nodes (click to expand .detail) ---- */
function wireFlow() {
  document.querySelectorAll(".flow .node").forEach(node => {
    if (!node.querySelector(".detail")) return;
    node.addEventListener("click", () => node.classList.toggle("on"));
  });
}

document.addEventListener("DOMContentLoaded", () => {
  buildSidebar();
  wireTabs();
  wireFlow();
});
