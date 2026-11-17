#!/usr/bin/env python3
"""
Shared durable state for SIGG Hub across phones / PCs / Render restarts.

Priority:
1) GitHub Gist  (SIGG_STATE_GIST_ID + SIGG_GITHUB_TOKEN)  — recommended
2) Local disk fallback (dev/tests only; NOT multi-device)

All devices hit the same Render URL; Render reads/writes the same Gist so
portfolio holdings, contest cURL, and settings survive spin-downs and redeploys.
"""

from __future__ import annotations

import json
import os
import threading
import time
from typing import Any, Dict, Optional

import requests

_LOCK = threading.RLock()
_CACHE: Dict[str, Any] = {
    "payload": None,
    "fetched_at": 0.0,
    "gist_files_sha": None,
}
_CACHE_TTL_SEC = 5.0


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def cloud_enabled() -> bool:
    return bool(_env("SIGG_STATE_GIST_ID") and _env("SIGG_GITHUB_TOKEN"))


def _gist_headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {_env('SIGG_GITHUB_TOKEN')}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "sigg-hub-remote-store",
    }


def _default_payload() -> Dict[str, Any]:
    return {
        "portfolio": None,
        "contest_curl": None,
        "settings": None,
        "notifications": [],
        "updated_at": None,
    }


def _fetch_gist_payload(force: bool = False) -> Dict[str, Any]:
    if not cloud_enabled():
        return _default_payload()

    now = time.time()
    with _LOCK:
        if (
            not force
            and _CACHE["payload"] is not None
            and (now - float(_CACHE["fetched_at"])) < _CACHE_TTL_SEC
        ):
            return dict(_CACHE["payload"])

    gist_id = _env("SIGG_STATE_GIST_ID")
    url = f"https://api.github.com/gists/{gist_id}"
    try:
        resp = requests.get(url, headers=_gist_headers(), timeout=15)
        if resp.status_code != 200:
            print(f"[remote_store] gist fetch HTTP {resp.status_code}: {resp.text[:200]}")
            with _LOCK:
                if _CACHE["payload"] is not None:
                    return dict(_CACHE["payload"])
            return _default_payload()

        data = resp.json()
        files = data.get("files") or {}
        # Prefer single bundle file; fall back to legacy split files
        bundle = files.get("sigg_hub_state.json") or files.get("state.json")
        payload = _default_payload()
        if bundle and bundle.get("content"):
            try:
                loaded = json.loads(bundle["content"])
                if isinstance(loaded, dict):
                    payload.update(loaded)
            except Exception as e:
                print(f"[remote_store] bad gist JSON: {e}")
        else:
            # Split-file compatibility
            for key, fname in (
                ("portfolio", "portfolio_state.json"),
                ("contest_curl", "contest_curl.json"),
                ("settings", "settings.json"),
                ("notifications", "recent_notifications.json"),
            ):
                fobj = files.get(fname)
                if fobj and fobj.get("content"):
                    try:
                        payload[key] = json.loads(fobj["content"])
                    except Exception:
                        pass

        with _LOCK:
            _CACHE["payload"] = payload
            _CACHE["fetched_at"] = time.time()
        return dict(payload)
    except Exception as e:
        print(f"[remote_store] gist fetch error: {e}")
        with _LOCK:
            if _CACHE["payload"] is not None:
                return dict(_CACHE["payload"])
        return _default_payload()


def _push_gist_payload(payload: Dict[str, Any]) -> bool:
    if not cloud_enabled():
        return False

    gist_id = _env("SIGG_STATE_GIST_ID")
    url = f"https://api.github.com/gists/{gist_id}"
    body = {
        "files": {
            "sigg_hub_state.json": {
                "content": json.dumps(payload, indent=2, ensure_ascii=False)
            }
        }
    }
    try:
        resp = requests.patch(url, headers=_gist_headers(), json=body, timeout=20)
        if resp.status_code not in (200, 201):
            print(f"[remote_store] gist push HTTP {resp.status_code}: {resp.text[:300]}")
            return False
        with _LOCK:
            _CACHE["payload"] = dict(payload)
            _CACHE["fetched_at"] = time.time()
        return True
    except Exception as e:
        print(f"[remote_store] gist push error: {e}")
        return False


def load_section(section: str) -> Optional[Any]:
    """Load one section (portfolio | contest_curl | settings | notifications)."""
    payload = _fetch_gist_payload()
    return payload.get(section)


def save_section(section: str, value: Any) -> bool:
    """Merge-save one section into the shared cloud bundle."""
    if not cloud_enabled():
        return False
    with _LOCK:
        payload = _fetch_gist_payload(force=True)
        payload[section] = value
        from datetime import datetime
        payload["updated_at"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        return _push_gist_payload(payload)


def load_json_file(local_path: str, section: str, default: Any) -> Any:
    """
    Cloud-first loader. Falls back to local file for tests/dev.
    """
    if cloud_enabled():
        remote = load_section(section)
        if remote is not None:
            return remote

    if os.path.exists(local_path):
        try:
            with open(local_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default


def save_json_file(local_path: str, section: str, value: Any) -> None:
    """
    Always write local mirror (for Actions/debug), and push to cloud when configured.
    """
    os.makedirs(os.path.dirname(local_path) if os.path.dirname(local_path) else ".", exist_ok=True)
    with open(local_path, "w", encoding="utf-8") as f:
        json.dump(value, f, indent=2, ensure_ascii=False)

    if cloud_enabled():
        ok = save_section(section, value)
        if not ok:
            print(f"[remote_store] WARNING: failed to persist section '{section}' to cloud")


def cloud_status() -> Dict[str, Any]:
    enabled = cloud_enabled()
    info: Dict[str, Any] = {
        "enabled": enabled,
        "backend": "github_gist" if enabled else "local_disk_only",
        "gist_id": _env("SIGG_STATE_GIST_ID")[:8] + "…" if enabled else None,
        "multi_device_safe": enabled,
    }
    if enabled:
        payload = _fetch_gist_payload()
        info["updated_at"] = payload.get("updated_at")
        port = payload.get("portfolio") or {}
        info["positions_count"] = len(port.get("positions") or []) if isinstance(port, dict) else 0
    return info
