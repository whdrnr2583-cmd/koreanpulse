# koreanpulse-cache

Cloudflare Worker that hosts the global translation cache + license gate for
`koreanpulse`. Lives on the Cloudflare free tier in production:

| Service | Free quota |
|---|---|
| Workers | 100,000 req/day |
| KV | 100,000 reads + 1,000 writes/day |
| Cache API | unmetered |

The Worker is the only piece of infra that has to scale with paid traffic.
The Python MCP server runs on the user's machine, so we eat zero per-user
compute cost.

## Architecture

```
  user machine                       Cloudflare                Lightsail
┌────────────┐  POST /v1/translate ┌────────────┐ POST /v1/  ┌──────────┐
│ koreanpulse│ ─────────────────▶  │ cache-     │ validate   │ webhook  │
│ MCP (py)   │ {license_key, text}│ worker     │ ──────────▶│ (FastAPI)│
└────────────┘                     │            │            └─────┬────┘
                                   │   KV       │                  │
                                   │   cache    │                  ▼
                                   └─────┬──────┘            ┌──────────┐
                                         │                   │ Postgres │
                                  miss ▼ │                   │ licenses │
                                ┌────────────┐               └──────────┘
                                │  OpenAI    │
                                │  /v1/chat/ │
                                │  completions│
                                └────────────┘
```

License validation is HMAC-signed and cached for 60s in the per-colocation
Cache API, so each license generates at most ~1 validate/min/colo of
Postgres pressure no matter how many translation calls fly through.

## Local dev

```bash
cd cache-worker
npm install
# One-time KV namespace creation
npx wrangler kv:namespace create TRANSLATIONS
npx wrangler kv:namespace create TRANSLATIONS --preview
# Paste both IDs into wrangler.toml.
# Set the secrets:
npx wrangler secret put OPENAI_API_KEY
npx wrangler secret put WEBHOOK_SHARED_SECRET
# Run:
npm run dev   # http://localhost:8787
```

For local end-to-end tests with the Python webhook, set the same
`WEBHOOK_SHARED_SECRET` on the webhook process and point
`WEBHOOK_VALIDATE_URL` at `http://host.docker.internal:8788/v1/validate`
(or whichever URL serves your dev webhook).

## Deploy

```bash
npx wrangler deploy
```

The Worker is exposed at `https://koreanpulse-cache.<account>.workers.dev`
by default; map a custom domain (`cache.koreanpulse.dev`) via the
Cloudflare dashboard once the apex domain is registered.

## Endpoints

### `GET /health`

```json
{ "status": "ok" }
```

### `POST /v1/translate`

Request body:

```json
{
  "kind": "translate",        // or "summarize"
  "text": "삼성전자 연결 영업이익 ...",
  "attribution": "DART (...)", // required only for "summarize"
  "license_key": "kp_..."
}
```

Successful response:

```json
{
  "output": "Samsung Electronics consolidated operating profit ...",
  "cached": true,
  "provider": "openai",
  "model": "gpt-5-mini"
}
```

Error responses use `{ "error": "..." }` shape with these statuses:

| Status | Cause |
|---|---|
| 400 | bad / missing fields |
| 401 | missing license_key |
| 402 | license invalid / inactive / quota exceeded |
| 502 | OpenAI failure (transient — retry with backoff) |
| 503 | webhook unreachable (license backend) |

## Security model

- License keys never sit in a URL. They live in the request body and we
  hash them before using them as a Cache API key.
- Worker → webhook calls are HMAC-SHA256 signed with `WEBHOOK_SHARED_SECRET`
  in `X-Cache-Signature`. Webhook rejects anything else with 401.
- OpenAI key never leaves the Worker. Clients only see translated output.
- Failed validations are not cached — a cancelled subscription stops
  serving cache hits within seconds.
