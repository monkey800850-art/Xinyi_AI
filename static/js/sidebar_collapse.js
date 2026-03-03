/* P1-UX-SIDEBAR-COLLAPSE-01 */
(function () {
  const KEY = "xinyi.sidebar.mode"; // "collapsed" | "expanded"
  const CLS = "xinyi-sidebar-collapsed";

  function qs(sel, root) { return (root || document).querySelector(sel); }
  function qsa(sel, root) { return Array.from((root || document).querySelectorAll(sel)); }

  function findSidebar() {
    // 1) explicit marker preferred
    let el = qs("[data-sidebar]");
    if (el) return el;

    // 2) common ids/classes
    const candidates = [
      "#sidebar",
      ".shell-sidebar",
      "aside.sidebar",
      "nav.sidebar",
      ".sidebar",
      ".side-nav",
      "#leftNav",
      "#left-nav",
      ".layout-sidebar"
    ];
    for (const s of candidates) {
      el = qs(s);
      if (el) return el;
    }

    // 3) heuristic: first <aside> or <nav> that contains many links
    const navs = qsa("aside, nav");
    navs.sort((a,b)=> (qsa("a",b).length - qsa("a",a).length));
    if (navs[0] && qsa("a", navs[0]).length >= 3) return navs[0];

    return null;
  }

  function apply(mode) {
    const root = document.documentElement;
    if (mode === "collapsed") root.classList.add(CLS);
    else root.classList.remove(CLS);

    try { localStorage.setItem(KEY, mode); } catch (e) {}
  }

  function getMode() {
    try { return localStorage.getItem(KEY) || "expanded"; } catch (e) { return "expanded"; }
  }

  function ensureControls() {
    // Floating toggle button (always visible)
    let btn = qs("#xinyiSidebarToggle");
    if (!btn) {
      btn = document.createElement("button");
      btn.id = "xinyiSidebarToggle";
      btn.type = "button";
      btn.textContent = "⟨⟨";
      btn.title = "折叠/展开侧边栏";
      document.body.appendChild(btn);
    }

    // Edge handle shown when collapsed
    let handle = qs("#xinyiSidebarHandle");
    if (!handle) {
      handle = document.createElement("button");
      handle.id = "xinyiSidebarHandle";
      handle.type = "button";
      handle.textContent = "⟩";
      handle.title = "展开侧边栏";
      document.body.appendChild(handle);
    }

    const update = () => {
      const collapsed = document.documentElement.classList.contains(CLS);
      btn.textContent = collapsed ? "⟩" : "⟨⟨";
      handle.style.display = collapsed ? "block" : "none";
    };

    btn.addEventListener("click", () => {
      const collapsed = document.documentElement.classList.contains(CLS);
      apply(collapsed ? "expanded" : "collapsed");
      update();
    });
    handle.addEventListener("click", () => {
      apply("expanded");
      update();
    });

    update();
  }

  function init() {
    // mark sidebar with data-sidebar if found (for CSS selector stability)
    const sidebar = findSidebar();
    if (sidebar && !sidebar.hasAttribute("data-sidebar")) {
      sidebar.setAttribute("data-sidebar", "1");
    }

    ensureControls();
    apply(getMode());
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
