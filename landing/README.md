# koreanpulse landing

Single-page Next.js 15 app — hero, "why crypto natives → Korean equities",
tools, pricing, email capture. Tailwind for styling, no UI library, all
in one `app/page.tsx` so it's trivial to iterate.

## Local dev

```bash
cd landing
npm install
npm run dev
```

Visit `http://localhost:3000`.

## Deploy to Vercel (no domain)

```bash
npm i -g vercel
vercel link        # one-time, creates .vercel/project.json
vercel --prod      # ships to https://koreanpulse-<hash>.vercel.app
```

After deploy you'll have a free `*.vercel.app` URL. Point that as your MCP
marketplace listing homepage until you buy the real domain.

When you're ready for `koreanpulse.dev`:
- Buy the domain from Namecheap / Cloudflare ($12)
- Vercel → Settings → Domains → add `koreanpulse.dev`
- Update DNS A/CNAME per Vercel's instructions
- Update marketplace listings + `smithery.yaml` to point at the apex

## Email capture wiring

`app/api/notify/route.ts` currently logs to stdout. Before launch, pipe to:

| Provider | Why |
|---|---|
| **Buttondown** ($9/mo, free for first 100) | Indie-friendly, simple API |
| ConvertKit free tier (1000 subs) | Bigger catalog later |
| Beehiiv free tier | Newsletter + email-capture combo |
| Just a Google Form | Zero infra, but no double-opt-in |

Set the relevant API token in Vercel → Project → Settings → Environment Variables.

## Brand

- Background `#0E1116` (matches `docs/assets/logo.svg`)
- Accent `#F0B429`
- Inter font (system fallback chain)

When the brand iterates, edit `tailwind.config.ts`.
