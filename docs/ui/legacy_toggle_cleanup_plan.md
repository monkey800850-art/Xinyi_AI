# Legacy toggle cleanup plan (from static tracer hits)

- legacy_templates: 5

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

- HIT L6: `/* UI-UNIFY-LAYOUT-01: defensive hide for legacy sidebar/toggle remnants (page-local) */` (context exported L1-L14)
- HIT L7: `button.toggle, button.sidebar-toggle, button.menu-toggle, button.nav-toggle,` (context exported L1-L15)
- HIT L8: `a.toggle, a.sidebar-toggle, a.menu-toggle, a.nav-toggle {` (context exported L1-L16)
- HIT L17: `<aside id="sidebar" class="sidebar">` (context exported L9-L25)
- HIT L45: `const sb=document.getElementById("sidebar");` (context exported L37-L53)
- HIT L50: `sb.classList.toggle("compact");` (context exported L42-L58)
- HIT L102: `// 3) render recent in sidebar` (context exported L94-L110)
- HIT L132: `/* UI-LAYOUT-04 sidebar search + collapse */` (context exported L124-L140)
- HIT L143: `// 1) group collapse toggle` (context exported L135-L151)
- HIT L171: `// 2) sidebar search filter` (context exported L163-L179)
- HIT L203: `/* UI-SIDEBAR-TOGGLE-01: robust sidebar collapse toggle */` (context exported L195-L211)
- HIT L207: `document.body.classList.toggle("sidebar-collapsed", collapsed);` (context exported L199-L215)
- HIT L214: `var sidebar = qs("sidebar");` (context exported L206-L222)
- HIT L215: `// if layout uses different structure, still allow toggle by body class` (context exported L207-L223)
- HIT L220: `var collapsed = document.body.classList.contains("sidebar-collapsed");` (context exported L212-L228)
- context_file: `evidence/UI-LEGACY-TOGGLE-02/contexts/layout.html.ctx.txt`

## app/templates/modules/tax.html

- HIT L16: `<table id="tax-forms-table" border="1" cellpadding="6" style="border-collapse:collapse;width:100%;display:none;">` (context exported L8-L24)
- context_file: `evidence/UI-LEGACY-TOGGLE-02/contexts/tax.html.ctx.txt`

## app/templates/sys_payroll_vouchers.html

- HIT L5: `/* UI-UNIFY-LAYOUT-01: defensive hide for legacy sidebar/toggle remnants (page-local) */` (context exported L1-L13)
- HIT L6: `button.toggle, button.sidebar-toggle, button.menu-toggle, button.nav-toggle,` (context exported L1-L14)
- HIT L7: `a.toggle, a.sidebar-toggle, a.menu-toggle, a.nav-toggle {` (context exported L1-L15)
- HIT L62: `const a = ev.target.closest('a[data-action="toggle"]');` (context exported L54-L70)
- HIT L68: `// toggle existing detail row` (context exported L60-L76)
- context_file: `evidence/UI-LEGACY-TOGGLE-02/contexts/sys_payroll_vouchers.html.ctx.txt`

