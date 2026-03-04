# Legacy toggle cleanup plan (from static tracer hits)

- legacy_templates: 4

## app/templates/_sidebar.html

- HIT L2: `{% block title %} Sidebar{% endblock %}` (context exported L1-L10)
- HIT L5: `/* UI-UNIFY-LAYOUT-01: defensive hide for legacy sidebar/toggle remnants (page-local) */` (context exported L1-L13)
- HIT L6: `button.toggle, button.sidebar-toggle, button.menu-toggle, button.nav-toggle,` (context exported L1-L14)
- HIT L7: `a.toggle, a.sidebar-toggle, a.menu-toggle, a.nav-toggle {` (context exported L1-L15)
- HIT L14: `{# Sidebar: driven by injected `catalog` (modules_catalog.json). #}` (context exported L6-L22)
- context_file: `evidence/UI-LEGACY-TOGGLE-02/contexts/_sidebar.html.ctx.txt`

## app/templates/hub.html

- HIT L4: `/* UI-UNIFY-LAYOUT-01: defensive hide for legacy sidebar/toggle remnants (page-local) */` (context exported L1-L12)
- HIT L5: `button.toggle, button.sidebar-toggle, button.menu-toggle, button.nav-toggle,` (context exported L1-L13)
- HIT L6: `a.toggle, a.sidebar-toggle, a.menu-toggle, a.nav-toggle { display:none !important; }` (context exported L1-L14)
- HIT L14: `// Align hub items with sidebar rules:` (context exported L6-L22)
- HIT L245: `// Align hub items with sidebar rules:` (context exported L237-L253)
- context_file: `evidence/UI-LEGACY-TOGGLE-02/contexts/hub.html.ctx.txt`

## app/templates/layout.html

- HIT L5: `/* UI-UNIFY-LAYOUT-01: defensive hide for legacy sidebar/toggle remnants (page-local) */` (context exported L1-L13)
- HIT L6: `button.toggle, button.sidebar-toggle, button.menu-toggle, button.nav-toggle,` (context exported L1-L14)
- HIT L7: `a.toggle, a.sidebar-toggle, a.menu-toggle, a.nav-toggle {` (context exported L1-L15)
- HIT L15: `<aside id="sidebar" class="sidebar">` (context exported L7-L23)
- HIT L46: `const sb=document.getElementById("sidebar");` (context exported L38-L54)
- HIT L51: `sb.classList.toggle("compact");` (context exported L43-L59)
- HIT L103: `// 3) render recent in sidebar` (context exported L95-L111)
- HIT L133: `/* UI-LAYOUT-04 sidebar search + collapse */` (context exported L125-L141)
- HIT L144: `// 1) group collapse toggle` (context exported L136-L152)
- HIT L172: `// 2) sidebar search filter` (context exported L164-L180)
- context_file: `evidence/UI-LEGACY-TOGGLE-02/contexts/layout.html.ctx.txt`

## app/templates/sys_payroll_vouchers.html

- HIT L5: `/* UI-UNIFY-LAYOUT-01: defensive hide for legacy sidebar/toggle remnants (page-local) */` (context exported L1-L13)
- HIT L6: `button.toggle, button.sidebar-toggle, button.menu-toggle, button.nav-toggle,` (context exported L1-L14)
- HIT L7: `a.toggle, a.sidebar-toggle, a.menu-toggle, a.nav-toggle {` (context exported L1-L15)
- HIT L62: `const a = ev.target.closest('a[data-action="toggle"]');` (context exported L54-L70)
- HIT L68: `// toggle existing detail row` (context exported L60-L76)
- context_file: `evidence/UI-LEGACY-TOGGLE-02/contexts/sys_payroll_vouchers.html.ctx.txt`

