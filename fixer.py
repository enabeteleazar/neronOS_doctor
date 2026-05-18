# doctor/fixer.py
# Autocorrection systemd bornee et auditable.

from __future__ import annotations

import subprocess
import time
from typing import Any

from doctor.config import cfg


# Mapping strict test runtime -> services systemd autorises.
# Chaque tuple est ordonne par preference; le service retenu doit aussi etre
# present dans cfg.SYSTEMD_SERVICES.
_ALLOWED_RESTARTS: dict[str, tuple[str, ...]] = {
    "server_health": ("neron-core", "neron-server"),
    "server_status": ("neron-core", "neron-server"),
    "llm_health": ("neron-llm",),
}

_RESTARTABLE_HTTP_MIN = 500
_RESTART_TIMEOUT_SECONDS = 20
_OUTPUT_MAX_CHARS = 500


def _is_restartable_failure(value: Any) -> bool:
    """Return True only for failures a restart can plausibly fix."""
    if isinstance(value, str):
        return True
    if isinstance(value, int):
        return value >= _RESTARTABLE_HTTP_MIN
    return False


def _failure_reason(value: Any) -> str:
    if isinstance(value, str):
        return "request_error"
    if isinstance(value, int):
        return f"http_{value}"
    return f"unsupported_result_{type(value).__name__}"


def _select_service(test_key: str) -> str | None:
    configured = set(cfg.SYSTEMD_SERVICES)
    for service in _ALLOWED_RESTARTS.get(test_key, ()):
        if service in configured:
            return service
    return None


def _restart_service(service: str) -> dict[str, Any]:
    try:
        result = subprocess.run(
            ["systemctl", "restart", service],
            capture_output=True,
            text=True,
            timeout=_RESTART_TIMEOUT_SECONDS,
        )
        return {
            "service": service,
            "action": "restart",
            "ok": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout[-_OUTPUT_MAX_CHARS:],
            "stderr": result.stderr[-_OUTPUT_MAX_CHARS:],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "service": service,
            "action": "restart",
            "ok": False,
            "returncode": None,
            "stdout": (exc.stdout or "")[-_OUTPUT_MAX_CHARS:],
            "stderr": (exc.stderr or "systemctl restart timed out")[-_OUTPUT_MAX_CHARS:],
        }
    except FileNotFoundError:
        return {
            "service": service,
            "action": "restart",
            "ok": False,
            "returncode": None,
            "stdout": "",
            "stderr": "systemctl not found",
        }


def _validate_services() -> dict[str, Any]:
    from doctor.tester import test_services

    return test_services()


def apply_fixes(report: dict[str, Any]) -> list[dict[str, Any]]:
    """Apply bounded fixes for failed runtime checks.

    The function is intentionally conservative:
    - only known test keys can trigger a restart;
    - the chosen service must be present in doctor.SYSTEMD_SERVICES;
    - client-side HTTP errors such as 401/403/404 do not trigger a restart;
    - every attempted restart is followed by a runtime validation pass.
    """
    tests = report.get("tests", {})
    fixes: list[dict[str, Any]] = []

    for test_key, value in tests.items():
        if test_key not in _ALLOWED_RESTARTS:
            continue

        if not _is_restartable_failure(value):
            if isinstance(value, int) and value >= 400:
                fixes.append({
                    "test": test_key,
                    "action": "skip",
                    "ok": True,
                    "reason": f"http_{value}_not_restartable",
                })
            continue

        service = _select_service(test_key)
        if not service:
            fixes.append({
                "test": test_key,
                "action": "skip",
                "ok": False,
                "reason": "no_allowed_configured_service",
                "configured_services": cfg.SYSTEMD_SERVICES,
                "allowed_services": list(_ALLOWED_RESTARTS[test_key]),
            })
            continue

        fix = _restart_service(service)
        fix.update({
            "test": test_key,
            "reason": _failure_reason(value),
        })
        fixes.append(fix)

    attempted = [fix for fix in fixes if fix.get("action") == "restart"]
    if not attempted:
        return fixes

    time.sleep(max(0, cfg.FIX_RETRY_DELAY))
    post_tests = _validate_services()

    for fix in attempted:
        test_key = str(fix.get("test", ""))
        post_value = post_tests.get(test_key)
        fix["validation"] = {
            "test": test_key,
            "result": post_value,
            "ok": not _is_restartable_failure(post_value),
        }

    return fixes
