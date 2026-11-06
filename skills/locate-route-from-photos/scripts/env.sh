#!/usr/bin/env bash
# Source this once per working directory/session, before any fetch_dem/rasterio call:
#   . "${CLAUDE_SKILL_DIR}/scripts/env.sh"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="$SCRIPT_DIR${PYTHONPATH:+:$PYTHONPATH}"

export GDAL_DISABLE_READDIR_ON_OPEN=EMPTY_DIR
export CPL_VSIL_CURL_ALLOWED_EXTENSIONS=.tif
export GDAL_HTTP_MAX_RETRY=4
export GDAL_HTTP_RETRY_DELAY=2

# Some sandboxes (claude.ai) intercept TLS at an egress proxy. Plain curl
# trusts it via the system CA store, but GDAL's own curl build does not —
# vsicurl reads fail with an SSL error even though the host is allow-listed.
# Point GDAL at the proxy's CA if one is present; harmless elsewhere.
for ca in /root/.ccr/ca-bundle.crt /etc/ssl/certs/ca-certificates.crt; do
    if [ -f "$ca" ]; then
        export GDAL_CURL_CA_BUNDLE="$ca"
        export CURL_CA_BUNDLE="$ca"
        break
    fi
done
