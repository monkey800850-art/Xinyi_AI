/* P1-UX-SIDEBAR-COLLAPSE-03: Shadow DOM injected controller (always visible) */
(function () {
  const KEY = "xinyi.sidebar.mode";
  const CLS = "xinyi-sidebar-collapsed";

  function safeGet(k) { try { return localStorage.getItem(k); } catch(e){ return null; } }
  function safeSet(k,v){ try { localStorage.setItem(k,v); } catch(e){} }
  function qs(sel, root){ return (root||document).querySelector(sel); }
  function qsa(sel, root){ return Array.from((root||document).querySelectorAll(sel)); }

  function findSidebar(){
    let el = qs("[data-sidebar]"); if (el) return el;
    const candidates = ["#sidebar",".shell-sidebar","aside.sidebar","nav.sidebar",".sidebar",".side-nav","#leftNav","#left-nav",".layout-sidebar"];
    for (const s of candidates){ el = qs(s); if (el) return el; }
    const navs = qsa("aside, nav");
    navs.sort((a,b)=> qsa("a",b).length - qsa("a",a).length);
    if (navs[0] && qsa("a", navs[0]).length >= 3) return navs[0];
    return null;
  }

  function ensureSidebarMarker(){
    const sb = findSidebar();
    if (sb && !sb.hasAttribute("data-sidebar")) sb.setAttribute("data-sidebar","1");
  }

  function apply(mode){
    const root = document.documentElement;
    if (mode === "collapsed") root.classList.add(CLS);
    else root.classList.remove(CLS);
    safeSet(KEY, mode);
  }
  function getMode(){ return safeGet(KEY) || "expanded"; }

  function ensureCollapseCss(){
    if (document.getElementById("xinyiCollapseStyle")) return;
    const style = document.createElement("style");
    style.id = "xinyiCollapseStyle";
    style.textContent = `
      :root { --xinyi-sidebar-width: 280px; --xinyi-sidebar-collapsed-width: 56px; }
      [data-sidebar] { width: var(--xinyi-sidebar-width); min-width: var(--xinyi-sidebar-width); max-width: var(--xinyi-sidebar-width); }
      .${CLS} [data-sidebar] { width: var(--xinyi-sidebar-collapsed-width) !important; min-width: var(--xinyi-sidebar-collapsed-width) !important; max-width: var(--xinyi-sidebar-collapsed-width) !important; overflow:hidden !important; }
      .${CLS} .shell, .${CLS} .layout-root, .${CLS} .layout-container, .${CLS} .app-container, .${CLS} .main-container { display:flex !important; flex-direction:row !important; align-items:stretch !important; }
      .${CLS} .shell-main, .${CLS} #content, .${CLS} .main-content, .${CLS} .content, .${CLS} main { flex: 1 1 auto !important; min-width: 0 !important; }
    `;
    document.head.appendChild(style);
  }

  function injectShadowUI(){
    if (document.getElementById("xinyiShadowRoot")) return;

    const host = document.createElement("div");
    host.id = "xinyiShadowRoot";
    host.style.position = "fixed";
    host.style.top = "0";
    host.style.left = "0";
    host.style.width = "0";
    host.style.height = "0";
    host.style.zIndex = "2147483647";
    host.style.pointerEvents = "none";
    document.documentElement.appendChild(host);

    const shadow = host.attachShadow({ mode: "open" });
    const style = document.createElement("style");
    style.textContent = `
      .btn, .handle { all: unset; pointer-events:auto; z-index:2147483647 !important;
        font: 800 14px/1 system-ui, -apple-system, Segoe UI, Roboto, Arial;
        color:#111; background:rgba(255,255,255,.92); border:1px solid rgba(0,0,0,.22);
        box-shadow:0 8px 30px rgba(0,0,0,.22); cursor:pointer; user-select:none;
      }
      .btn { position:fixed; top:10px; left:10px; border-radius:10px; padding:8px 10px; }
      .handle { position:fixed; top:50%; left:0; transform:translateY(-50%); border-left:none; border-radius:0 10px 10px 0; padding:12px 10px; display:none; }
    `;
    const btn = document.createElement("button");
    btn.className = "btn";
    btn.type = "button";
    const handle = document.createElement("button");
    handle.className = "handle";
    handle.type = "button";
    handle.textContent = "⟩";

    function update(){
      const collapsed = document.documentElement.classList.contains(CLS);
      btn.textContent = collapsed ? "⟩" : "⟨⟨";
      handle.style.display = collapsed ? "block" : "none";
    }

    btn.addEventListener("click", ()=>{ apply(document.documentElement.classList.contains(CLS) ? "expanded":"collapsed"); update(); });
    handle.addEventListener("click", ()=>{ apply("expanded"); update(); });

    shadow.appendChild(style);
    shadow.appendChild(btn);
    shadow.appendChild(handle);
    apply(getMode());
    update();
  }

  function init(){
    ensureSidebarMarker();
    ensureCollapseCss();
    injectShadowUI();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
