/* P1-UX-SIDEBAR-TOGGLE-01 */
(function () {
  const KEY = "xinyi.sidebar.collapsed";

  function apply(collapsed) {
    const root = document.documentElement;
    if (collapsed) {
      root.classList.add("sidebar-collapsed");
    } else {
      root.classList.remove("sidebar-collapsed");
    }
  }

  function getState() {
    try { return localStorage.getItem(KEY) === "1"; } catch (e) { return false; }
  }

  function setState(v) {
    try { localStorage.setItem(KEY, v ? "1" : "0"); } catch (e) {}
  }

  function init() {
    // default: expanded
    apply(getState());

    const btn = document.getElementById("sidebarToggleBtn");
    if (!btn) return;

    const updateText = () => {
      const collapsed = document.documentElement.classList.contains("sidebar-collapsed");
      btn.setAttribute("aria-pressed", collapsed ? "true" : "false");
      btn.textContent = collapsed ? "展开侧边栏" : "收起侧边栏";
    };

    btn.addEventListener("click", function () {
      const collapsed = !document.documentElement.classList.contains("sidebar-collapsed");
      apply(collapsed);
      setState(collapsed);
      updateText();
    });

    updateText();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
