# Demo recording guide

> ⚠️ **On hold (2026-05-10 decision, SCHEDULE.md §9):** video demos are
> deliberately not used — the live `/today` page serves as the demo.
> Kept for reference only.

A 60-second screen capture is the single highest-leverage piece of
marketing content for an MCP product. Marketplaces autoplay it, X
preview-cards play it, the README header gets it. One good demo replaces
ten paragraphs of copy.

## Goal

Watcher should think within the first 15 seconds:
*"That's me asking my AI a question. The answer is real Korean data
translated to English. I want this."*

## Tools

- **Loom** — easiest, free, gives you a hosted MP4 + GIF + auto-captions
- Alternatively **OBS** + render to GIF with `gifski`
- A reasonably clean Claude Desktop window (close other panes)

## Pre-recording checklist

- [ ] `koreanpulse` registered in Claude Desktop config (see `CLAUDE_DESKTOP.md`)
- [ ] DART_API_KEY + OPENAI_API_KEY both set, translation enabled
- [ ] Run `python examples/quickstart.py` once recently — primes the
      caches so the demo is fast (no 5MB corp-code download mid-recording)
- [ ] Close all browser tabs except: a notepad with the prompts below
- [ ] Audio off — captions only. Faster to consume on mute, no accent
      questions, plays inline on every social platform
- [ ] Resolution 1280×720 minimum, 1920×1080 preferred

## Script — 60 seconds

### Beat 1 (0–10s) — the question

Type into Claude Desktop, slowly enough to read:

> Use koreanpulse to show me activist investor filings against Korean
> companies in the last week, with English translation.

The viewer reads the prompt + sees Claude pick up the MCP tool.

### Beat 2 (10–25s) — the answer arriving

Claude calls `monitor_activist_investors`. Pause to let viewer read 1–2
results — ideally a real filing where `is_likely_activist` matched (KCGI
or Align). Show the English title + the Korean original side by side.

### Beat 3 (25–40s) — drilling deeper

Type:

> Pull up DART filings for SK Hynix from the last 14 days, summarize the
> most material one in English.

Shows `track_korean_filings` + the auto-translation step. By now the
viewer believes the product.

### Beat 4 (40–55s) — the "wait, this is real-time" moment

Type:

> What did Korean industry news say about HBM today?

`search_korean_industry_news` returns from etnews / 한국경제 RSS with
classified industry tags. Viewer sees today's date in the metadata — the
"this is live, not a canned demo" beat.

### Beat 5 (55–60s) — the ask

End with a clean cut to a static frame:

```
koreanpulse — Get pinged in English when KRX moves on a stock you care about.
Free public daily snapshot at /today
Cloud Solo $29/mo · Analyst $79/mo · Desk $249/mo
OSS self-host available. AGPL source.
github.com/whdrnr2583-cmd/koreanpulse
```

Hold for 5 seconds. Done.

## Post-production

- **Trim to ≤ 60s** — every second over is conversion drop
- **Burn captions** — Loom does this automatically
- **Export MP4 + GIF** — MP4 for Twitter/X, GIF for README
- **Compress GIF** to ≤ 4MB so GitHub embeds inline:
  ```bash
  gifski --quality 80 --width 800 --fps 12 input.mov -o demo.gif
  ```
- Drop into `docs/assets/demo.mp4` and `docs/assets/demo.gif`
- Reference from README:
  ```markdown
  ![demo](docs/assets/demo.gif)
  ```

## Where to use it

1. **README header** — replaces the current logo placeholder for first
   30 days post-launch (logo can come back after retention is proven)
2. **Smithery / PulseMCP / Glama listings** — drop the URL/file
3. **Show HN post** — embed in the body
4. **Crypto-native channels** (BETA Channel 7) — Twitter quote-reply
   when topic-relevant
5. **Polar checkout pages** — Solo / Analyst / Desk (sole billing path; Lemon Squeezy is not in use, store application declined 2026-05-06)

## What not to do

- ❌ Multiple takes spliced together — looks fake
- ❌ Background music — distracting, fails on auto-mute
- ❌ Shot of you talking — slows the loop
- ❌ Demoing more than 4 tools — viewer attention budget runs out
- ❌ Padding the runtime with "now let me show you another feature"
