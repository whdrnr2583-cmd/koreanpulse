# Lemon Squeezy setup — step by step

> 🚫 **STATUS: NOT IN USE — Lemon Squeezy store application was declined
> 2026-05-06.** Polar ([polar.sh](https://polar.sh)) is our sole billing
> provider and Merchant of Record. The LS handler code remains in the repo
> only as a historical implementation reference; we do not plan to
> re-apply, and **no LS secrets should be configured in production**
> (doing so would attempt to dispatch licenses against a provider with no
> MoR relationship). For active billing setup see the Billing section of
> the root [`README.md`](../README.md) or
> [`webhook-worker/README.md`](../webhook-worker/README.md). Everything
> below this banner is a snapshot of the LS path as it existed before
> 2026-05-06 — keep for context only.



This is the full path from "no Lemon Squeezy account" to "first paid customer
auto-issued a license key".

> ⚠️ **Updated 2026-05-05** — the webhook receiver no longer runs on
> Render/Railway/Fly/Lightsail. It's now a Cloudflare Worker + D1
> (`webhook-worker/`) with custom domain `api.koreanpulse.dev`. Anywhere
> below this file mentions `koreanpulse-webhook.onrender.com`,
> `koreanpulse-webhook --port 8788`, ngrok tunnels, or `pip install
> 'koreanpulse[billing]'`, treat it as **historical context** for the
> Variant + storefront flow only — the *deploy* path is now in
> [`webhook-worker/README.md`](../webhook-worker/README.md).
>
> The webhook URL you register in LS is **`https://api.koreanpulse.dev/webhook/lemonsqueezy`** once
> the Cloudflare Worker custom domain is wired (see
> `_workspace/checklist_ko_2026-05-05.md` §2-3).

---

## Domain question (short answer)

A custom domain is recommended (`koreanpulse.dev`, ~$12/year — see the
checklist) so the webhook lives at `api.koreanpulse.dev`. Without one,
the worker still works at its `*.workers.dev` URL — paste that into the
LS webhook config.

| What needs HTTPS | Resolution |
|---|---|
| Lemon Squeezy webhook receiver | Cloudflare Worker (custom domain or `*.workers.dev`) — TLS terminated by Cloudflare |
| Customer checkout page | Lemon Squeezy hosts it. Each Variant gets a URL like `https://koreanpulse.lemonsqueezy.com/buy/abc-123` |
| Marketing landing page | Vercel — `koreanpulse.dev` apex, deploys via `vercel --prod` |

For local Worker dev, `wrangler dev` exposes a localhost endpoint; you
can hit it from your laptop only. End-to-end signature verification
testing happens against the deployed Cloudflare Worker, not local.

---

## Account → Store → Product → Variants → Webhook (15 min)

### 1. Sign up

<https://app.lemonsqueezy.com/register>

- Email + password.
- They'll ask basic business info. **Korean residents can use 사업자등록번호** for verified status; without it you can still operate, your store just shows as "personal".
- 선택사항: bank verification (only matters when you want to withdraw).

### 2. Create a Store

After login, **Settings → Stores → New Store**.

- Store name: `koreanpulse` (this is the slug used in customer-facing URLs)
- Currency: USD (Lemon Squeezy converts to KRW on payout)
- Country: Korea, Republic of (their MoR setup handles the rest)

You'll land on `https://app.lemonsqueezy.com/`<store_slug>.

### 3. Create the Product

**Products → New Product → Subscription**.

- Name: `koreanpulse`
- Description: paste from `docs/listings/PULSEMCP.md` (long description section)
- Status: **Draft** at first

The Design Partner Lifetime SKU is **private** — do not create a public LS
product for it. It's a contact-only, 20-seat cap program; if/when a design
partner converts, issue manually via a one-off LS variant or admin-issued
license. Do not surface it on the public store.

### 4. Add the 3 Cloud Variants

Pricing v2 (2026-05-05): three Cloud tiers + an OSS lane (no LS variant).
Inside the Subscription product, **Variants → New Variant** for each tier
(monthly + annual on each):

| Variant name | Price | Interval | Notes |
|---|---|---|---|
| Cloud Solo | $29 | Monthly | Floor tier — 5 watchlists, ~2,000 queries, 1 alert channel |
| Cloud Solo (Annual) | $278 | Yearly | $348 − 20% |
| Cloud Analyst | $79 | Monthly | Real revenue tier — 25 watchlists, ~15,000 queries, multi-channel alerts |
| Cloud Analyst (Annual) | $758 | Yearly | $948 − 20% |
| Cloud Desk | $249 | Monthly | 3 seats, shared watchlists, ~100,000 queries, Slack/webhook alerts |
| Cloud Desk (Annual) | $2,390 | Yearly | $2,988 − 20% |

After saving each variant you'll see a numeric **Variant ID** in the URL or
sidebar. **Copy each one** — you need them for the env vars.

> **Lifetime SKU note** — the **Design Partner Lifetime ($299, 20-seat
> cap, private)** is still active under pricing v2. Create it in LS but
> **hide from the storefront** (Settings → Storefront → Hide variant) so
> casual visitors don't see it; surface it only via direct contact.
> Issued seats are tracked by code (`LIFETIME_DEAL_MAX_SEATS=20` in
> `src/koreanpulse/license.py`).
>
> **Retired variants** — the previous `PRO $19` subscription and the
> `LIFETIME $99` one-time SKU are deprecated. Do not create them. The
> webhook handler still accepts the back-compat
> `LEMONSQUEEZY_VARIANT_PRO` / `_STARTER` / `_INDIE` / `_ENTERPRISE` env
> vars for any pre-pivot grandfathered licenses, but production sets only
> `LEMONSQUEEZY_VARIANT_SOLO` / `_ANALYST` / `_DESK` / `_LIFETIME`.

### 5. Activate the products

For each product: **Edit → Status → Published**. Customer-facing checkout URLs
become live.

### 6. Configure the webhook

**Settings → Webhooks → + Add webhook**

- Callback URL:
  - Local dev: `https://abcd-1234.ngrok-free.app/webhook/lemonsqueezy`
  - Production: `https://koreanpulse-webhook.onrender.com/webhook/lemonsqueezy` (or your Fly/Railway/Vercel URL)
- Signing secret: Lemon Squeezy generates one. **Copy it.**
- Events to subscribe (tick at minimum):
  - `subscription_created`
  - `subscription_updated`
  - `subscription_cancelled`
  - `subscription_resumed`
  - `subscription_expired`
  - `subscription_payment_success`
  - `subscription_payment_failed`
  - `order_created` (needed for the lifetime deal)

### 7. Fill in `.env`

```env
LEMONSQUEEZY_WEBHOOK_SECRET=ls_whsec_AbCdEf...
LEMONSQUEEZY_VARIANT_SOLO=23001
LEMONSQUEEZY_VARIANT_ANALYST=23002
LEMONSQUEEZY_VARIANT_DESK=23003
LEMONSQUEEZY_VARIANT_LIFETIME=23004    # Design Partner $299 (private, 20-seat cap)

# Retired under pricing v2 (2026-05-05) — keep unset for new deployments.
# Only set these if you have grandfathered customers from the previous
# $19 Pro / $99 Lifetime / older Starter / Indie / Enterprise SKUs.
# LEMONSQUEEZY_VARIANT_PRO=
# LEMONSQUEEZY_VARIANT_STARTER=
# LEMONSQUEEZY_VARIANT_INDIE=
# LEMONSQUEEZY_VARIANT_ENTERPRISE=
```

(Numeric IDs only. Don't quote them.)

### 8. Run the webhook receiver locally

```bash
pip install 'koreanpulse[billing]'
koreanpulse-webhook --port 8788
```

It listens on `:8788`. Hit `http://localhost:8788/health` → `{"status":"ok"}`.

### 9. End-to-end test (Test Mode)

Lemon Squeezy has a Test Mode toggle (top-right of dashboard).

- Switch to Test Mode
- Use **Settings → Webhooks → your webhook → Send test event** to fire a `subscription_created`
- Watch your server logs — should see signature verified + `action=issued`
- Or use a real test checkout: each Variant has a "Share link" → open in incognito → use Stripe test card `4242 4242 4242 4242`

If end-to-end works in Test Mode, flip to Live and you're done.

---

## Deploying the webhook receiver (no-domain path)

Pick whichever you're most comfortable with. All give you a free HTTPS subdomain.

### Render (recommended for solo)

1. <https://render.com/> → Sign up
2. New → **Web Service** → connect GitHub repo
3. Build command: `pip install -e '.[billing]'`
4. Start command: `koreanpulse-webhook --host 0.0.0.0 --port $PORT`
5. Environment: paste all `.env` values into Render's UI. Redeploy.
6. URL: `https://koreanpulse-webhook.onrender.com`
7. Update Lemon Squeezy webhook URL to that.

Free tier sleeps after 15min of inactivity. For prod, $7/mo "Starter" plan keeps it warm.

### Railway / Fly.io / Vercel — same pattern

- Railway: similar Web Service flow, $5/mo credit
- Fly.io: `fly launch` from repo, free allowance covers small webhook
- Vercel: works for FastAPI via their Python runtime

---

## Operating notes

### Test webhook locally without deploying

```bash
# Terminal 1: webhook server
koreanpulse-webhook --port 8788

# Terminal 2: ngrok
ngrok http 8788

# Copy the https://...ngrok-free.app URL into Lemon Squeezy webhook config
# Send a test event from LS dashboard → watch terminal 1
```

### License store is in-memory in v0

Webhook updates happen in the running process's memory only. Restart = lost
licenses. **Wire up Postgres before opening the gates** — see
`docs/POSTGRES.md` (next milestone).

### Refund / chargeback handling

Lemon Squeezy fires `subscription_cancelled` on refunds. Our handler marks
the license inactive but **doesn't delete it** — so audit history stays.

### Tax handling

Lemon Squeezy is the Merchant of Record. They collect & remit VAT/GST
(EU/UK/Australia/etc.) on your behalf. **You don't file foreign tax.** You
get a 1099-equivalent from LS at year-end; declare as Korean foreign-source
income. (Talk to a tax accountant before scaling — this is "won't bite at
small scale" not formal advice.)

---

## Quick sanity checklist before going live

- [ ] All 3 Cloud subscription Variants created (Solo / Analyst / Desk), each with monthly + annual
- [ ] All 3 Variant IDs in `.env` (`LEMONSQUEEZY_VARIANT_SOLO/ANALYST/DESK`)
- [ ] Webhook URL configured and reachable (curl `/health` returns ok)
- [ ] `LEMONSQUEEZY_WEBHOOK_SECRET` matches dashboard
- [ ] Sent at least one test webhook from dashboard, server logged `action=issued`
- [ ] Spent ≤ $1 of own money on a real test checkout end-to-end
- [ ] License key arrived in your mailbox / DB
- [ ] Refund processed cleanly (test it)
- [ ] Design Partner Lifetime is **NOT** surfaced on the public store
