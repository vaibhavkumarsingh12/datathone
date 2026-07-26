# Mobile support

The dashboard is responsive below 820px (phones). Added 2026-07-26, tested on a
real device at 375–390px.

Three changes, all additive — desktop is untouched:

1. **`static/css/spear.css`** — a `@media (max-width:820px)` block at the end.
   Turns off the desktop `body{display:flex}` two-column layout (the sidebar was
   pinning `main` to ~88px on a phone), converts the sidebar into an off-canvas
   drawer, makes the 9-tab bar a horizontal scroll strip, and caps the network
   graph height.

2. **`static/js/spear.js`** — a small IIFE at the end that injects the `☰`
   hamburger button + backdrop and toggles `.sidebar.open`.

3. **`templates/index.html`** — `defer` on all three `<script>` tags
   (`plotly.min.js`, `vis-network.min.js`, `spear.js`) so the ~4 MB of JS no
   longer blocks first paint. All three must keep `defer` together — deferring
   Plotly but not spear.js would run spear.js first → "Plotly is not defined".

Rollback: `git checkout pre-mobile-patch -- deploy/spear-catalyst`
