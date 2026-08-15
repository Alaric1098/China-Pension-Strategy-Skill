"""webget — HTTPS fetch primitive that works inside the DSH Windows sandbox.

Why this exists: the DSH Windows sandbox runs commands under an ACL
restricted token (CreateRestrictedToken). Under that token Schannel-based
clients (pwsh Invoke-WebRequest, curl.exe, .NET HttpClient) fail TLS
handshakes with SEC_E_NO_CREDENTIALS (0x8009030e) at
AcquireCredentialsHandle, because Schannel cannot open the user's crypto
credential context with the restricted token. OpenSSL-based clients
(Python, Node) do not depend on the Windows crypto context for the basic
handshake, so they work.

This script is the portable HTTPS primitive for pwsh workflows: call it
from PowerShell instead of Invoke-WebRequest when the sandbox blocks
Schannel.

Usage:
    python scripts/webget.py URL [--output FILE] [--timeout N]
            [--jina]           # prefix https://r.jina.ai/ for markdown
            [--status-only]    # print HTTP status and exit
    Exit codes: 0 success, 1 fetch/network error, 2 usage error.
"""

import argparse
import pathlib
import sys
import urllib.error
import urllib.request


def _force_utf8_stdio() -> None:
    """Windows console/pipe default to cp1252/OEM; force UTF-8 so Chinese output survives."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def main() -> int:
    _force_utf8_stdio()
    parser = argparse.ArgumentParser(prog="webget")
    parser.add_argument("url", help="https:// URL to fetch")
    parser.add_argument("--output", help="write body to this file instead of stdout")
    parser.add_argument("--timeout", type=float, default=30.0, help="timeout seconds")
    parser.add_argument("--jina", action="store_true", help="fetch via r.jina.ai reader (markdown)")
    parser.add_argument("--status-only", action="store_true", help="print status code only")
    args = parser.parse_args()

    target = args.url
    if args.jina:
        target = f"https://r.jina.ai/{target}"

    req = urllib.request.Request(
        target,
        headers={"User-Agent": "china-pension-webget/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=args.timeout) as resp:
            body = resp.read().decode("utf-8", "replace")
            if args.status_only:
                print(resp.status)
                return 0
            if args.output:
                pathlib.Path(args.output).write_text(body, encoding="utf-8")
                print(f"wrote {args.output} ({len(body)} chars)")
            else:
                sys.stdout.write(body)
            return 0
    except urllib.error.HTTPError as error:
        print(f"webget: HTTP {error.code} for {target}", file=sys.stderr)
        return 1
    except Exception as error:  # network / TLS / timeout
        print(f"webget: {type(error).__name__}: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
