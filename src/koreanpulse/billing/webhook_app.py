"""FastAPI app for Lemon Squeezy webhooks.

Run as a separate process from the MCP server:

    DATABASE_URL=...                       # Postgres later; in-memory now
    LEMONSQUEEZY_WEBHOOK_SECRET=...
    LEMONSQUEEZY_VARIANT_STARTER=12345
    LEMONSQUEEZY_VARIANT_INDIE=12346
    LEMONSQUEEZY_VARIANT_PRO=12347
    LEMONSQUEEZY_VARIANT_ENTERPRISE=12348
    LEMONSQUEEZY_VARIANT_LIFETIME=12349
    koreanpulse-webhook --port 8788

In production sit this behind nginx / Cloudflare with TLS terminated upstream.

The MCP server reads from the same LicenseStore — in v0 that's an in-memory
store local to each process, so for multi-process deployment swap in the
Postgres-backed store via `set_default_store()`.
"""
# NOTE: deliberately NO `from __future__ import annotations` — FastAPI uses
# runtime type introspection on route handlers, and stringified annotations
# break parameter detection (Request gets misread as a query field).

import argparse
import hashlib
import hmac
import json
import logging
import os
from typing import Any, Dict

# Module-level import so FastAPI can introspect the Request annotation.
# Keep optional with a clear error if billing extras aren't installed.
try:
    from fastapi import FastAPI, HTTPException, Request
    _FASTAPI_AVAILABLE = True
except ImportError:  # pragma: no cover
    _FASTAPI_AVAILABLE = False

logger = logging.getLogger(__name__)


def _build_app():
    """Build the FastAPI webhook app. Raises if billing extras absent."""
    if not _FASTAPI_AVAILABLE:
        raise RuntimeError(
            "FastAPI not installed. Run: pip install 'koreanpulse[billing]'"
        )

    from koreanpulse.billing.lemonsqueezy import (
        WebhookVerificationError,
        handle_event,
        verify_signature,
    )
    from koreanpulse.license import (
        LicenseError,
        aget_default_store,
        validate_license_or_raise,
    )

    app = FastAPI(title="koreanpulse-webhook", version="0.0.0")

    @app.get("/health")
    async def health() -> Dict[str, str]:
        return {"status": "ok"}

    @app.post("/webhook/lemonsqueezy")
    async def lemonsqueezy_webhook(request: Request) -> Dict[str, Any]:
        secret = os.environ.get("LEMONSQUEEZY_WEBHOOK_SECRET", "").strip()
        if not secret:
            logger.error("LEMONSQUEEZY_WEBHOOK_SECRET not set; refusing webhook")
            raise HTTPException(status_code=500, detail="server not configured")

        # Pull signature header manually — keeps FastAPI's request-validation
        # layer out of the path for this raw-body endpoint.
        signature = request.headers.get("x-signature") or request.headers.get("X-Signature") or ""

        body = await request.body()
        if not verify_signature(body=body, signature_header=signature, secret=secret):
            logger.warning("rejected webhook with bad signature")
            raise HTTPException(status_code=401, detail="invalid signature")

        try:
            payload = json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise HTTPException(status_code=400, detail=f"invalid JSON: {exc}") from exc

        try:
            result = await handle_event(payload)
        except WebhookVerificationError as exc:  # belt and suspenders
            raise HTTPException(status_code=401, detail=str(exc)) from exc

        # Always return 200 unless we want LS to retry. Surface failures in
        # the body so the dashboard shows them, but don't loop on bad payloads.
        return result.to_dict()

    @app.post("/v1/validate")
    async def validate(request: Request) -> Dict[str, Any]:
        """Internal endpoint for the koreanpulse-cache Worker.

        The Worker calls this once per license-key + ~60s window to confirm
        the key is active and to atomically charge one cost unit. Body is
        HMAC-SHA256 signed with KOREANPULSE_CACHE_SHARED_SECRET so we don't
        have to trust the Worker's network position.

        Response shape (always 200; the `ok` field carries the verdict):
            { "ok": True,  "plan": "indie", "period_calls": 7 }
            { "ok": False, "code": "quota_exceeded", "reason": "..." }
        """
        shared_secret = os.environ.get("KOREANPULSE_CACHE_SHARED_SECRET", "").strip()
        if not shared_secret:
            logger.error("KOREANPULSE_CACHE_SHARED_SECRET not set; refusing validate")
            raise HTTPException(status_code=500, detail="cache validate not configured")

        body = await request.body()
        signature = (
            request.headers.get("x-cache-signature")
            or request.headers.get("X-Cache-Signature")
            or ""
        ).strip()
        expected = hmac.new(
            shared_secret.encode("utf-8"), body, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected, signature):
            logger.warning("rejected validate with bad signature")
            raise HTTPException(status_code=401, detail="invalid signature")

        try:
            payload = json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise HTTPException(status_code=400, detail=f"invalid JSON: {exc}") from exc

        license_key = (payload.get("license_key") or "").strip()
        if not license_key:
            return {"ok": False, "code": "missing", "reason": "missing license_key"}

        store = await aget_default_store()
        try:
            lic = await validate_license_or_raise(
                license_key, store=store, cost_units=1
            )
        except LicenseError as exc:
            return {"ok": False, "code": exc.code, "reason": str(exc)}

        return {
            "ok": True,
            "plan": lic.plan.value,
            "period_calls": lic.period_calls,
        }

    return app


# Importing the module pre-builds the app so uvicorn can find it via
# `koreanpulse.billing.webhook_app:app` when convenient.
if _FASTAPI_AVAILABLE:
    app = _build_app()
else:  # pragma: no cover
    app = None


def main() -> None:
    """Console-script entry. `koreanpulse-webhook --port 8788`."""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s: %(message)s"
    )

    # Production safety: surface missing config at boot rather than at the
    # first webhook arrival. Postgres autoconnect happens lazily inside
    # `aget_default_store()`; here we just refuse to start if the operator
    # asked for license enforcement without wiring Postgres.
    if os.environ.get("KOREANPULSE_REQUIRE_LICENSE", "0").strip() == "1":
        if not os.environ.get("DATABASE_URL", "").strip():
            raise RuntimeError(
                "KOREANPULSE_REQUIRE_LICENSE=1 but DATABASE_URL is not set. "
                "The webhook process and the MCP server must share a Postgres "
                "license store; in-memory state is per-process and the keys "
                "issued here would never reach the MCP server. "
                "See docs/POSTGRES.md."
            )

    parser = argparse.ArgumentParser(prog="koreanpulse-webhook")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8788)
    parser.add_argument("--reload", action="store_true", help="dev only")
    args = parser.parse_args()

    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "uvicorn not installed. Run: pip install 'koreanpulse[billing]'"
        ) from exc

    if args.reload:
        uvicorn.run(
            "koreanpulse.billing.webhook_app:app",
            host=args.host, port=args.port, reload=True,
        )
    else:
        uvicorn.run(_build_app(), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
