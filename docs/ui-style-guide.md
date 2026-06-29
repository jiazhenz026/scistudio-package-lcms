# UI Style Guide — making your package UI look like SciStudio

Most packages never touch the frontend. But if your package ships a
**previewer** or an **interactive-block panel**, it ships a small frontend asset
(e.g. `assets/viewer.js` and its CSS) that the app mounts **into the same page**
as the rest of SciStudio. That asset is the one place where your package can look
like a different app — cold stock greys and blues, square corners, the wrong
font. This guide is how to avoid that with almost no effort.

If your package has no previewer or panel, you can skip this page.

## The design language in one paragraph

SciStudio is warm and calm — a "macaron" palette on a soft off-white canvas, with
near-black ink text, gently rounded corners, comfortable padding, and **one** warm
accent (ember). It is not a dashboard: avoid stock cold greys/blues, hard
shadows, and rainbow color. When in doubt, open a core viewer (a DataFrame or
Array preview) next to your panel and make yours feel like a quiet sibling.

## Use the brand tokens — don't hardcode colors

The app publishes its palette as CSS custom properties on the page root. Because
your module mounts in the **same document**, your CSS inherits them for free —
just reference `var(--ss-*)`. This is the single most important rule: pull color
from the tokens instead of pasting hex codes, and your UI tracks the app
automatically.

| Token | Use it for | Full-opacity value |
| --- | --- | --- |
| `--ss-canvas` | app/background surfaces | `#f5f1e8` |
| `--ss-ink` | primary text, dark surfaces, borders | `#1c211b` |
| `--ss-ember` | primary action / accent (use sparingly) | `#f06a44` |
| `--ss-pine` | success | `#2e5d50` |
| `--ss-sea` | links / informational | `#2d7891` |
| `--ss-sand` | warm neutral / muted fills | `#ddc49d` |

The tokens are **space-separated RGB channels**, so wrap them in `rgb()` and you
get opacity for free:

```css
color: rgb(var(--ss-ink));            /* solid ink text            */
color: rgb(var(--ss-ink) / 0.6);      /* muted/secondary text      */
border-color: rgb(var(--ss-ink) / 0.1); /* hairline divider        */
background: rgb(var(--ss-ember));      /* accent fill               */
```

> **Status.** These `--ss-*` tokens ship with recent core. The formal,
> frozen cross-boundary theming contract (guaranteed token names exposed on the
> panel host element, plus an optional shared control stylesheet) is being
> finalized in core — track **SciStudio#1849**. Until then, treat `--ss-*` as
> provisional but available, and degrade gracefully: always pair a token with a
> sensible literal fallback if you need to support older core, e.g.
> `color: #1c211b; color: rgb(var(--ss-ink));`.

## Quick rules

- **Text**: `rgb(var(--ss-ink))`; secondary text `rgb(var(--ss-ink) / 0.6)`.
- **Borders / dividers**: `rgb(var(--ss-ink) / 0.1)` — soft, never harsh black.
- **Surfaces**: white or `rgb(var(--ss-canvas))`; subtle fills
  `rgb(var(--ss-ink) / 0.05)`.
- **Actions**: primary button in ink or ember; **success** uses pine; reserve a
  red strictly for **errors**.
- **One accent.** Ember is a seasoning, not a base coat. Don't rainbow.
- **Rounded corners** (~8–12px) and generous padding.
- **Font**: `font: inherit;` so you pick up the app's typeface — don't import a
  different one.
- **Don't** hardcode stock blues (`#3b82f6`), slate/stone greys (`#64748b`,
  `#e2e8f0`), or heavy drop shadows. Those are exactly what read as "a different
  app."

## Before / after

```css
/* ❌ Before — cold, off-brand: stock blue + slate, square, hardcoded. */
.mypkg-btn   { background: #3b82f6; color: #fff; border-radius: 4px; }
.mypkg-panel { border: 1px solid #e2e8f0; background: #f8fafc; color: #334155; }
```

```css
/* ✅ After — on-brand: tokens, rounded, inherits the app font. */
.mypkg-btn {
  background: rgb(var(--ss-ember));
  color: #fff;
  border-radius: 10px;
  padding: 6px 14px;
  font: inherit;
  border: 0;
}
.mypkg-panel {
  border: 1px solid rgb(var(--ss-ink) / 0.1);
  background: #fff;
  color: rgb(var(--ss-ink));
  border-radius: 12px;
  padding: 16px;
}
```

## Keep your CSS scoped

Your stylesheet is injected into the shared document `<head>`, so unprefixed
selectors can collide with the app or with another package. Prefix every class
with your package (e.g. `.mypkg-…`) or nest your styles under a single root
class on your mount element. Never style bare element selectors (`button`,
`table`, `div`) globally.

## A 60-second checklist

- [ ] Colors come from `--ss-*` (or match the palette) — no stock cold
      grey/blue, no random hex.
- [ ] Rounded corners + comfortable padding; `font: inherit`.
- [ ] One accent color; red is reserved for errors.
- [ ] Class names are package-prefixed or scoped under a root class.
- [ ] Opened a core viewer beside your panel — yours looks like it belongs.

## See also

- `docs/DOCUMENTATION-STANDARD.md` — the docs every package must ship.
- Core guide `docs/block-development/previewers-and-plots.md` — how to wire a
  previewer (backend provider + frontend asset).
- `scistudio-blocks-spectroscopy` — the reference package to model on.
