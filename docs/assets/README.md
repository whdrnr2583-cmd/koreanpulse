# Brand assets

Placeholder marks. Good enough to clear marketplace requirements; replace
with proper brand work after first paying customer feedback.

## Files

| File | Use |
|---|---|
| `logo.svg` | 256×256 with wordmark — README header, marketplace square tile |
| `icon.svg` | 64×64 mark only — favicon, app launcher, browser tab |

## Generating PNG variants

Most marketplaces ask for PNG. Render with `rsvg-convert` or any SVG tool:

```bash
# Logo variants
rsvg-convert -w 256 -h 256 docs/assets/logo.svg -o docs/assets/logo-256.png
rsvg-convert -w 512 -h 512 docs/assets/logo.svg -o docs/assets/logo-512.png

# Favicon
rsvg-convert -w 32  -h 32  docs/assets/icon.svg -o docs/assets/favicon-32.png
rsvg-convert -w 64  -h 64  docs/assets/icon.svg -o docs/assets/favicon-64.png
rsvg-convert -w 192 -h 192 docs/assets/icon.svg -o docs/assets/icon-192.png
```

Or just open the SVG in any browser, screenshot at desired size.

## Hosting

When the domain goes up, upload to:

- `https://koreanpulse.dev/icon.png` (referenced in `smithery.yaml`)
- `https://koreanpulse.dev/logo.png` (referenced in marketplace listings)
- `https://koreanpulse.dev/favicon.ico` (browser default)

Until then, link to GitHub raw:
- `https://raw.githubusercontent.com/whdrnr2583-cmd/koreanpulse/main/docs/assets/logo.svg`

GitHub serves SVGs with the right MIME type for embedding.

## Brand notes (placeholder, iterate later)

- Background `#0E1116` — near-black, signals "professional finance tool"
- Accent `#F0B429` — Korean traditional gold/saffron, hints at the Korean theme without being on-the-nose
- Sharp pulse line evokes both EKG and stock chart — intentional double meaning
- Wordmark in Inter to match the rest of the indie SaaS dev tooling visual language

When real brand work happens: keep the pulse motif, evolve the colors.
