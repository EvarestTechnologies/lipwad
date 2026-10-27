# Lipwad — Design

The approved screens live on the Lipwad Screens design canvas. The `.dc.html` files in `screens/` are exported copies of those artboards. They are **reference specs, not production code**: they need the canvas runtime to render, but their markup and inline styles are plain HTML and CSS, so they show exact layout, spacing, colours, copy and interaction states.

| File | Screen | Notes |
|---|---|---|
| `screens/Today.dc.html` | Today · desktop | Sidebar, at-risk hero, "Needs you" tasks with one action each, "Lipwad is working" feed |
| `screens/Review.dc.html` | Claim review · desktop | Evidence panel (photo with SAM highlight / audio segment / rule) and field list with citation chips, plus "Ask about this claim" (stretch) |
| `screens/MobileToday.dc.html` | Today · PWA | Bottom tab bar with raised camera button |
| `screens/MobileCapture.dc.html` | Capture · PWA | Camera with document edges, captured-docs strip, shutter, mic, Build claim |
| `screens/MobileReview.dc.html` | Claim review · PWA | Field list, proof in bottom sheet, fix action |
| `screens/Tokens.dc.html` | Visual system | Palette, alert system, type, rules |

`tokens.css` holds the same values as CSS variables. Import it once and never hard-code colours in components.

Money and Rescue screens are described in `docs/DESIGN_PROMPT.md` and `docs/PRD.md`. Build them in the same system; Rescue is a state of Today and Claim review, not its own page.

All names, amounts and the facility shown are synthetic. Rule IDs show `v[YYYY-MM]` and clause text is a placeholder until `docs/SOURCES.md` is filled.
