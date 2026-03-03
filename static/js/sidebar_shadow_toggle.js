/* P1-UX-SIDEBAR-COLLAPSE-02: Shadow DOM injected controller (always visible) */
(function () {
  const KEY = "xinyi.sidebar.mode";
  const CLS = "xinyi-sidebar-collapsed";

  function safeGet(k) { try { return localStorage.getItem(k); } catch(e){ return null; } }
  function safeSet(k,v){ try { localStorage.setItem(k,v); } catch(e){} }

  function qs(sel, root){ return (root||document).querySelector(sel); }
  function qsa(sel, root){ return Array.from((root||document).querySelectorAll(sel)); }

  function findSidebar(){
    let el = qs("[data-sidebar]");
    if (el) return el;

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
    for (const s of candidates){
      el = qs(s);
      if (el) return el;
    }

    // heuristic: aside/nav with most links
    const navs = qsa("aside, nav");
    navs.sort((a,b)=> qsa("a",b).length - qsa("a",a).length);
    if (navs[0] && qsa("a", navs[0]).length >= 3) return navs[0];
    return null;
  }

  function apply(mode){
    const root = document.documentElement;
    if (mode === "collapsed") root.classList.add(CLS);
    else root.classList.remove(CLS);
    safeSet(KEY, mode);
  }

  function getMode(){
    return safeGet(KEY) || "expanded";
  }

  function ensureSidebarMarker(){
    const sb = findSidebar();
    if (sb && !sb.hasAttribute("data-sidebar")){
      sb.setAttribute("data-sidebar","1");
    }
  }

  function injectRoot(){
    if (document.getElementById("xinyiShadowRoot")) return;

    const host = document.createElement("div");
    host.id = "xinyiShadowRoot";
    // host must be visible even if body is styled oddly
    host.style.position = "fixed";
    host.style.top = "0";
    host.style.left = "0";
    host.style.width = "0";
    host.style.height = "0";
    host.style.zIndex = "2147483647"; // max-ish
    host.style.pointerEvents = "none"; // only buttons inside receive events
    document.documentElement.appendChild(host);

    const shadow = host.attachShadow({ mode: "open" });

    const style = document.createElement("style");
    style.textContent = `
      :host { all: initial; }
      .btn {
        all: unset;
        pointer-events: auto;
        position: fixed;
        top: 10px;
        left: 10px;
        z-index: 2147483647 !important;
        font: 700 14px/1 system-ui, -apple-system, Segoe UI, Roboto, Arial;
        color: #111;
        background: rgba(255,255,255,0.92);
        border: 1px solid rgba(0,0,0,0.22);
        border-radius: 10px;
        padding: 8px 10px;
        cursor: pointer;
        box-shadow: 0 8px 30px rgba(0,0,0,0.22);
        user-select: none;
      }
      .btn:hover { background: rgba(255,255,255,0.98); }
      .handle {
        all: unset;
        pointer-events: auto;
        position: fixed;
        top: 50%;
        left: 0;
        transform: translateY(-50%);
        z-index: 2147483647 !important;
        font: 900 16px/1 system-ui, -apple-system, Segoe UI, Roboto, Arial;
        color: #111;
        background: rgba(255,255,255,0.92);
        border: 1px solid rgba(0,0,0,0.22);
        border-left: none;
        border-radius: 0 10px 10px 0;
        padding: 12px 10px;
        cursor: pointer;
        box-shadow: 0 8px 30px rgba(0,0,0,0.22);
        display: none;
        user-select: none;
      }
      .hint {
        all: unset;
        pointer-events: none;
        position: fixed;
        top: 52px;
        left: 10px;
        z-index: 2147483647 !important;
        font: 12px/1.4 system-ui, -apple-system, Segoe UI, Roboto, Arial;
        color: rgba(0,0,0,0.75);
        background: rgba(255,255,255,0.85);
        border: 1px solid rgba(0,0,0,0.12);
        border-radius: 10px;
        padding: 6px 8px;
        display: none;
      }
    `;

    const btn = document.createElement("button");
    btn.className = "btn";
    btn.id = "xinyiSidebarToggleBtn";
    btn.type = "button";
    btn.title = "折叠/展开侧边栏";
    btn.textContent = "⟨⟨";

    const handle = document.createElement("button");
    handle.className = "handle";
    handle.id = "xinyiSidebarToggleHandle";
    handle.type = "button";
    handle.title = "展开侧边栏";
    handle.textContent = "⟩";

    const hint = document.createElement("div");
    hint.className = "hint";
    hint.textContent = "侧边栏折叠/展开（状态已记忆）";

    function update(){
      const collapsed = document.documentElement.classList.contains(CLS);
      btn.textContent = collapsed ? "⟩" : "⟨⟨";
      handle.style.display = collapsed ? "block" : "none";
      hint.style.display = "block";
      clearTimeout(update._t);
      update._t = setTimeout(()=>{ hint.style.display="none"; }, 1800);
    }

    btn.addEventListener("click", () => {
      const collapsed = document.documentElement.classList.contains(CLS);
      apply(collapsed ? "expanded" : "collapsed");
      update();
    });

    handle.addEventListener("click", () => {
      apply("expanded");
      update();
    });

    shadow.appendChild(style);
    shadow.appendChild(btn);
    shadow.appendChild(handle);
    shadow.appendChild(hint);

    // initial
    update();
  }

  function ensureCollapseCss(){
    // Inject global CSS once (outside shadow), to actually collapse sidebar/content.
    if (document.getElementById("xinyiCollapseStyle")) return;
    const style = document.createElement("style");
    style.id = "xinyiCollapseStyle";
    style.textContent = `
      /* global collapse effect (must affect page DOM) */
      :root { --xinyi-sidebar-width: 280px; --xinyi-sidebar-collapsed-width: 56px; }

      /* mark sidebar width baseline */
      [data-sidebar] {
        width: var(--xinyi-sidebar-width);
        min-width: var(--xinyi-sidebar-width);
        max-width: var(--xinyi-sidebar-width);
      }

      /* collapsed: shrink sidebar, keep left edge */
      .${CLS} [data-sidebar] {
        width: var(--xinyi-sidebar-collapsed-width) !important;
        min-width: var(--xinyi-sidebar-collapsed-width) !important;
        max-width: var(--xinyi-sidebar-collapsed-width) !important;
        overflow: hidden !important;
      }

      /* keep two-column layout */
      .${CLS} .shell,
      .${CLS} .layout-root,
      .${CLS} .layout-container,
      .${CLS} .app-container,
      .${CLS} .main-container {
        display: flex !important;
        flex-direction: row !important;
        align-items: stretch !important;
      }

      .${CLS} .shell-main,
      .${CLS} #content,
      .${CLS} .main-content,
      .${CLS} .content,
      .${CLS} main {
        flex: 1 1 auto !important;
        min-width: 0 !important;
      }
    `;
    document.head.appendChild(style);
  }

  function init(){
    ensureSidebarMarker();
    ensureCollapseCss();
    injectRoot();
    apply(getMode());
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
