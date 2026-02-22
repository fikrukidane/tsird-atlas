# WMS Proxy Fix - 2026-02-20

## Problem

MapServer was unable to load the mapfile when requests came through the nginx reverse proxy at port 18080:

```
msLoadMap(): Unable to access file. (/etc/mapserver/tsird.map)
```

The error occurred even though:
- The file exists at `/etc/mapserver/tsird.map`
- The file is readable (644 permissions)
- Direct requests to MapServer inside the container worked with `?map=/etc/mapserver/tsird.map`

## Root Cause

The **`ms.config`** file in `/infra/mapserver/mapfiles/ms.config` had a restrictive pattern validation:

```
MS_MAP_PATTERN "^/mapfiles/.*\.map$"
MS_MAPFILE "/mapfiles/tsird.map"
```

This regex only allowed mapfiles under `/mapfiles/`, but the actual mapfile was mounted at `/etc/mapserver/` per the docker-compose volume configuration:

```yaml
volumes:
  - ./infra/mapserver/mapfiles:/etc/mapserver
```

When MapServer received a request with `?map=/etc/mapserver/tsird.map`, it rejected it because the path didn't match the hardcoded pattern.

## Solution

Updated **`infra/mapserver/mapfiles/ms.config`** to:

1. Accept mapfiles from both `/mapfiles/` and `/etc/mapserver/` directories
2. Correctly reference the actual mapfile location

```diff
CONFIG
  ENV
-   MS_MAP_PATTERN "^/mapfiles/.*\.map$"
-   MS_MAPFILE "/mapfiles/tsird.map"
+   MS_MAP_PATTERN "^(/mapfiles/|/etc/mapserver/).*\.map$"
+   MS_MAPFILE "/etc/mapserver/tsird.map"
  END
END
```

## Impact

- ✅ HTTP requests to `http://127.0.0.1:18080/map/ogc?SERVICE=WMS&REQUEST=GetCapabilities` now succeed
- ✅ GetCapabilities returns valid XML with `Content-Type: text/xml`
- ✅ No more `msLoadMap()` errors
- ✅ WMS service fully functional through nginx proxy
- ✅ Security maintained: pattern still restricts mapfiles to specific directories

## Verification

A new verification script was added: **`scripts/tsird-verify-wms-proxy.sh`**

This script tests:
1. HTTP response code is 200
2. Response contains valid WMS XML (`<WMS_Capabilities>`)
3. Content-Type header contains "xml"

Run with:
```bash
./scripts/tsird-verify-wms-proxy.sh
```

Or test specific endpoint:
```bash
./scripts/tsird-verify-wms-proxy.sh "http://lab.example.com"
```

## Testing

After the fix:

```bash
$ curl -sS "http://127.0.0.1:18080/map/ogc?service=WMS&request=GetCapabilities&version=1.3.0" | head -3
<?xml version='1.0' encoding="UTF-8" standalone="no" ?>
<WMS_Capabilities version="1.3.0" xmlns="http://www.opengis.net/wms" ...>
```

All acceptance tests pass ✓

## Files Changed

- `infra/mapserver/mapfiles/ms.config` - Updated MS_MAP_PATTERN and MS_MAPFILE
- `scripts/tsird-verify-wms-proxy.sh` - New verification script (executable)
