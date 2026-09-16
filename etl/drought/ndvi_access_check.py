"""Minimal, non-download access check for the configured CDSE NDVI collection.

This is deliberately a collection-metadata request, rather than an imagery
request: it validates both OAuth client credentials and access to the exact
configured Copernicus Land Monitoring Service NDVI collection without pulling
pixels or creating any remote resource.
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


CATALOG_BASE = "https://sh.dataspace.copernicus.eu/catalog/v1/collections/"


def fail(stage: str, detail: str, expiry: str | None = None) -> int:
    # Never surface response bodies: OAuth and service responses can contain
    # sensitive diagnostic context.  Status-only errors remain actionable.
    print(json.dumps({
        "authentication": "failed" if stage == "authentication" else "passed",
        "ndvi_collection_access": "failed",
        "client_expiry_utc": expiry,
        "error": detail,
    }))
    return 1


def normalized_collection_id(value: str) -> str:
    value = value.strip()
    return value if value.startswith("byoc-") else f"byoc-{value}"


def main() -> int:
    client_id = os.environ.get("CDSE_OAUTH_CLIENT_ID")
    client_secret = os.environ.get("CDSE_OAUTH_CLIENT_SECRET")
    token_url = os.environ.get("CDSE_OAUTH_TOKEN_URL")
    collection = os.environ.get("CDSE_NDVI_COLLECTION")
    if not all((client_id, client_secret, token_url, collection)):
        return fail("authentication", "CDSE configuration is incomplete")

    try:
        body = urlencode({
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        }).encode("utf-8")
        token_request = Request(token_url, data=body, method="POST", headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        })
        with urlopen(token_request, timeout=30) as response:
            token_payload = json.loads(response.read().decode("utf-8"))
        token = token_payload.get("access_token")
        expires_in = token_payload.get("expires_in")
        if not isinstance(token, str) or not token:
            return fail("authentication", "OAuth response did not include an access token")
        expiry = None
        if isinstance(expires_in, (int, float)):
            expiry = (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat()
    except HTTPError as exc:
        return fail("authentication", f"OAuth request failed (HTTP {exc.code})")
    except (URLError, TimeoutError):
        return fail("authentication", "OAuth request could not reach CDSE")
    except (ValueError, OSError):
        return fail("authentication", "OAuth response was invalid")

    collection_id = normalized_collection_id(collection)
    try:
        request = Request(
            f"{CATALOG_BASE}{collection_id}", method="GET", headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            },
        )
        with urlopen(request, timeout=30) as response:
            metadata = json.loads(response.read().decode("utf-8"))
        if metadata.get("id") != collection_id:
            return fail("collection", "NDVI catalog returned an unexpected collection", expiry)
    except HTTPError as exc:
        return fail("collection", f"NDVI catalog request failed (HTTP {exc.code})", expiry)
    except (URLError, TimeoutError):
        return fail("collection", "NDVI catalog request could not reach CDSE", expiry)
    except (ValueError, OSError):
        return fail("collection", "NDVI catalog response was invalid", expiry)

    print(json.dumps({
        "authentication": "passed",
        "ndvi_collection_access": "passed",
        "client_expiry_utc": expiry,
        "error": None,
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
