
## P1-UX-LAYOUT-03 (20260303_185326)
- Goal: Force desktop layout under 90%-125% zoom; fix stale-page issue via cache-busting + selector-hit proof.
- Files: templates/main_layout.html, static/css/force_desktop.css
- Evidence: snapshots/uat/P1-UX-LAYOUT-03_20260303_185326.txt
- DoD: /system/books HTML includes force_desktop.css?v=... and force-desktop class; manual zoom check checklist recorded.
