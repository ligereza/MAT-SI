"""CODEINE v0 session storage and the single persistence detector."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import time
from typing import Any
from uuid import uuid4


SCHEMA_VERSION = 1
PROTOCOL = "codeine-v0"
DEFAULT_SESSION = Path("artifacts") / "codeine-v0" / "session.json"
HYPOTHESIS_ID = "persistence_without_observable_change"


class CodeineError(RuntimeError):
    """Expected user-facing CODEINE failure."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: Any) -> str:
    if isinstance(value, bytes):
        payload = value
    else:
        payload = _canonical(value).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _session_path(path: Path | str | None) -> Path:
    return Path(path or DEFAULT_SESSION).expanduser().resolve()


def _repo_root(repo: Path | str) -> Path:
    candidate = Path(repo).expanduser().resolve()
    result = subprocess.run(
        ["git", "-C", str(candidate), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise CodeineError(f"not a Git repository: {candidate}")
    return Path(result.stdout.strip()).resolve()


def _git(repo: Path, *args: str, binary: bool = False) -> str | bytes:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=not binary,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace") if binary else result.stderr
        raise CodeineError(f"git {' '.join(args)} failed: {detail.strip()}")
    return result.stdout


def _untracked_files(repo: Path) -> list[dict[str, Any]]:
    raw = _git(repo, "ls-files", "--others", "--exclude-standard", "-z", binary=True)
    paths = [item for item in raw.decode("utf-8", errors="surrogateescape").split("\0") if item]
    files = []
    for relative in paths:
        path = repo / relative
        if not path.is_file():
            continue
        data = path.read_bytes()
        files.append({"path": relative, "bytes": len(data), "sha256": _digest(data)})
    return files


def _test_snapshot(repo: Path, command: str | None) -> tuple[dict[str, Any], dict[str, Any]]:
    if not command:
        return (
            {"availability": "UNKNOWN", "reason": "no test command configured"},
            {},
        )
    started = time.perf_counter()
    result = subprocess.run(
        command,
        cwd=repo,
        shell=True,
        capture_output=True,
        text=False,
        timeout=300,
        check=False,
    )
    elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
    snapshot = {
        "availability": "OBSERVED",
        "command_digest": _digest(command),
        "exit_code": result.returncode,
        "stdout_digest": _digest(result.stdout),
        "stderr_digest": _digest(result.stderr),
        "duration_ms": elapsed_ms,
    }
    stable = {key: value for key, value in snapshot.items() if key != "duration_ms"}
    return snapshot, {"elapsed_ms": elapsed_ms, "test_state_digest": _digest(stable)}


def capture_snapshot(repo: Path, test_command: str | None) -> dict[str, Any]:
    status = _git(repo, "status", "--porcelain=v1", "--untracked-files=all")
    unstaged = _git(repo, "diff", "--binary", "--no-ext-diff", "--no-renames", binary=True)
    staged = _git(repo, "diff", "--cached", "--binary", "--no-ext-diff", "--no-renames", binary=True)
    untracked = _untracked_files(repo)
    head = _git(repo, "rev-parse", "HEAD").strip()
    test, test_resource = _test_snapshot(repo, test_command)
    git_state = {
        "head": head,
        "status": status.splitlines(),
        "status_digest": _digest(status),
        "unstaged_diff_digest": _digest(unstaged),
        "staged_diff_digest": _digest(staged),
        "untracked_files": untracked,
        "working_tree_digest": _digest(
            {
                "head": head,
                "status": status,
                "unstaged_diff": _digest(unstaged),
                "staged_diff": _digest(staged),
                "untracked": untracked,
            }
        ),
        "diff_bytes": len(unstaged) + len(staged),
    }
    stable = {
        "git": git_state,
        "test": {key: value for key, value in test.items() if key != "duration_ms"},
    }
    return {
        "captured_at": _now(),
        "scope": "local_git_worktree",
        "state_digest": _digest(stable),
        "git": git_state,
        "test": test,
        "resources": {
            "dimensions": {
                "diff_bytes": {
                    "value": git_state["diff_bytes"],
                    "status": "MEASURED",
                    "source_ref": "git diff --binary",
                },
                **(
                    {
                        "elapsed_ms": {
                            "value": test_resource["elapsed_ms"],
                            "status": "MEASURED",
                            "source_ref": "configured test command",
                        }
                    }
                    if "elapsed_ms" in test_resource
                    else {}
                ),
            },
            "scalar_collapsed": False,
        },
    }


def _audit(raw_source: str, derivation: str, loss: str, residue: Any, provenance: str) -> dict[str, Any]:
    return {
        "RAW_SOURCE": raw_source,
        "DERIVATION": derivation,
        "LOSS": loss,
        "RESIDUE": residue,
        "PROVENANCE": provenance,
    }


def _record(session: dict[str, Any], before: dict[str, Any], after: dict[str, Any], token: str, ordinal: int) -> dict[str, Any]:
    source_ref = f"session:{session['session_id']}/attempts[{ordinal}]"
    token_digest = _digest(token)[:16]
    return {
        "before": before,
        "intervention": {"token_digest": token_digest, "kind": "opaque_attempt_token"},
        "after": after,
        "provenance": {
            "source_system": "local Git workflow",
            "source_ref": source_ref,
            "captured_at": after["captured_at"],
            "field_audit": {
                "before": _audit(
                    "git HEAD/status/diff + configured test snapshot before checkpoint",
                    "capture_snapshot before the opaque checkpoint boundary",
                    "human intent and domain interpretation are not recorded",
                    {"state_digest": before["state_digest"]},
                    source_ref,
                ),
                "intervention": _audit(
                    "checkpoint invocation",
                    "hash supplied token; default token is generated locally",
                    "token wording is not retained as action semantics",
                    {"token_digest": token_digest},
                    source_ref,
                ),
                "after": _audit(
                    "git HEAD/status/diff + configured test snapshot after checkpoint",
                    "capture_snapshot after the opaque checkpoint boundary",
                    "human interpretation of change is not inferred",
                    {"state_digest": after["state_digest"]},
                    source_ref,
                ),
                "provenance": _audit(
                    "local session file and Git repository",
                    "attach session id, repository root, source refs, and capture times",
                    "external context is not available to the CLI",
                    {"session_id": session["session_id"]},
                    source_ref,
                ),
            },
            "residue": {
                "repository_root": session["repo_root"],
                "test_command_digest": session.get("test_command_digest"),
                "raw_snapshots_retained": True,
            },
        },
        "resources": after["resources"],
    }


def _derived_transition(record: dict[str, Any], attempt_id: str) -> dict[str, Any]:
    before_digest = record["before"]["state_digest"]
    after_digest = record["after"]["state_digest"]
    elapsed = record["resources"]["dimensions"].get("elapsed_ms")
    return {
        "state_changed": before_digest != after_digest,
        "resources_observed": bool(elapsed and elapsed.get("status") == "MEASURED"),
        "derived_from": {
            "attempt_id": attempt_id,
            "before_state_digest": before_digest,
            "after_state_digest": after_digest,
            "resource_dimensions": sorted(record["resources"]["dimensions"]),
        },
        "semantic_claim": "none; state_changed is only digest inequality",
    }


def _read(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise CodeineError(f"session not found: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CodeineError(f"invalid session JSON: {path}") from exc


def _write(path: Path, session: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(session, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def start(repo: Path | str = ".", session: Path | str | None = None, test_command: str | None = None, task: str | None = None, force: bool = False) -> dict[str, Any]:
    repo_root = _repo_root(repo)
    path = _session_path(session)
    if path.exists() and not force:
        existing = _read(path)
        if not existing.get("finished_at"):
            raise CodeineError(f"active session exists: {path}; use --force to replace it")
    before = capture_snapshot(repo_root, test_command)
    session_data = {
        "protocol": PROTOCOL,
        "schema_version": SCHEMA_VERSION,
        "session_id": uuid4().hex,
        "repo_root": str(repo_root),
        "task": task,
        "test_command": test_command,
        "test_command_digest": _digest(test_command) if test_command else None,
        "hypothesis": {
            "id": HYPOTHESIS_ID,
            "statement": "repeated similar boundaries with no observable state change while measured resources continue",
            "not_universal_truth": True,
            "required_observables": ["before", "intervention", "after", "resources when available", "provenance"],
        },
        "started_at": _now(),
        "current_before": before,
        "attempts": [],
        "recommendations": [],
        "finished_at": None,
        "final_observation": None,
    }
    _write(path, session_data)
    return {"session_path": str(path), "session_id": session_data["session_id"], "before": before, "hypothesis": session_data["hypothesis"]}


def checkpoint(session: Path | str | None = None, token: str | None = None) -> dict[str, Any]:
    path = _session_path(session)
    data = _read(path)
    if data.get("finished_at"):
        raise CodeineError("session is already finished")
    repo = Path(data["repo_root"])
    before = data["current_before"]
    after = capture_snapshot(repo, data.get("test_command"))
    ordinal = len(data["attempts"])
    attempt_id = f"attempt-{ordinal + 1:04d}"
    record = _record(data, before, after, token or uuid4().hex, ordinal)
    derived = _derived_transition(record, attempt_id)
    attempt = {"attempt_id": attempt_id, "record": record, "derived": derived}
    data["attempts"].append(attempt)
    data["current_before"] = after
    for recommendation in reversed(data["recommendations"]):
        if recommendation.get("awaiting_consequence"):
            recommendation["awaiting_consequence"] = False
            recommendation["consequence"] = {
                "observed_in_attempt": attempt_id,
                "state_changed": derived["state_changed"],
                "causal_effect_claimed": False,
                "note": "next boundary observed; recommendation benefit is not inferred",
            }
            break
    _write(path, data)
    return {
        "session_path": str(path),
        "attempt_id": attempt_id,
        "record": record,
        "derived": derived,
    }


def _attempt_diagnostics(data: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "attempt_id": attempt["attempt_id"],
            "state_changed": attempt["derived"]["state_changed"],
            "resources_observed": attempt["derived"]["resources_observed"],
            "before_state_digest": attempt["record"]["before"]["state_digest"],
            "after_state_digest": attempt["record"]["after"]["state_digest"],
        }
        for attempt in data["attempts"]
    ]


def assess(session: Path | str | None = None) -> dict[str, Any]:
    path = _session_path(session)
    data = _read(path)
    diagnostics = _attempt_diagnostics(data)
    changed = [item for item in diagnostics if item["state_changed"]]
    trailing_unchanged = []
    for item in reversed(diagnostics):
        if item["state_changed"]:
            break
        trailing_unchanged.append(item)
    trailing_unchanged.reverse()
    resources_observed = bool(trailing_unchanged) and all(item["resources_observed"] for item in trailing_unchanged)
    missing_resources = [item["attempt_id"] for item in trailing_unchanged if not item["resources_observed"]]

    if not diagnostics:
        decision = "UNKNOWN"
        strength = "none"
        reason = "no completed attempt is available"
    elif trailing_unchanged and not resources_observed:
        decision = "UNKNOWN"
        strength = "insufficient_measurement"
        reason = "state did not change, but continued resource consumption is not measured"
    elif len(trailing_unchanged) >= 3:
        decision = "STOP"
        strength = "strong"
        reason = "three consecutive unchanged observable boundaries with measured resource consumption"
    elif len(trailing_unchanged) >= 2:
        decision = "SWITCH"
        strength = "moderate"
        reason = "two consecutive unchanged observable boundaries with measured resource consumption"
    else:
        decision = "CONTINUE"
        strength = "observed_change"
        reason = "the latest boundary changed observably or repetition remains productive"

    evidence_for = [item["attempt_id"] for item in trailing_unchanged if item["resources_observed"]]
    evidence_against = [item["attempt_id"] for item in changed]
    evaluation = {
        "rule_id": HYPOTHESIS_ID,
        "consecutive_unchanged_attempts": len(trailing_unchanged),
        "evidence_for": evidence_for,
        "evidence_against": evidence_against,
        "resources_observed_for_evidence_for": resources_observed,
        "missing_resource_attempts": missing_resources,
        "no_hidden_score": True,
    }
    fingerprint = _digest({"decision": decision, "evidence_for": evidence_for, "evidence_against": evidence_against})
    existing = next((item for item in reversed(data["recommendations"]) if item["fingerprint"] == fingerprint), None)
    if existing is None:
        recommendation = {
            "recommendation_id": f"recommendation-{len(data['recommendations']) + 1:04d}",
            "decision": decision,
            "hypothesis_id": HYPOTHESIS_ID,
            "reason": reason,
            "evidence_for": evidence_for,
            "evidence_against": evidence_against,
            "evidence_strength": strength,
            "evaluation": evaluation,
            "fingerprint": fingerprint,
            "issued_at": _now(),
            "awaiting_consequence": decision in {"SWITCH", "STOP"},
            "consequence": None,
            "provenance": {
                "source": "CODEINE v0 persistence detector",
                "attempt_ids": [item["attempt_id"] for item in diagnostics],
                "derivation": "explicit count of consecutive digest-equal boundaries and measured elapsed_ms availability",
                "semantic_claim": "recommendation only; no causal claim",
            },
        }
        data["recommendations"].append(recommendation)
        _write(path, data)
    else:
        recommendation = existing
    return {
        "session_path": str(path),
        "decision": recommendation["decision"],
        "recommendation": recommendation,
        "attempt_diagnostics": diagnostics,
    }


def finish(session: Path | str | None = None) -> dict[str, Any]:
    path = _session_path(session)
    data = _read(path)
    if data.get("finished_at"):
        return {"session_path": str(path), "finished_at": data["finished_at"], "summary": _summary(data)}
    repo = Path(data["repo_root"])
    final_observation = capture_snapshot(repo, data.get("test_command"))
    for recommendation in data["recommendations"]:
        if recommendation.get("awaiting_consequence"):
            recommendation["awaiting_consequence"] = False
            recommendation["consequence"] = {
                "observed_in_attempt": None,
                "state_changed": None,
                "causal_effect_claimed": False,
                "note": "session finished before a subsequent checkpoint",
            }
    data["final_observation"] = final_observation
    data["finished_at"] = _now()
    _write(path, data)
    return {"session_path": str(path), "finished_at": data["finished_at"], "summary": _summary(data)}


def _summary(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "session_id": data["session_id"],
        "attempt_count": len(data["attempts"]),
        "recommendations": [
            {
                "recommendation_id": item["recommendation_id"],
                "decision": item["decision"],
                "evidence_for": item["evidence_for"],
                "evidence_against": item["evidence_against"],
                "consequence": item["consequence"],
            }
            for item in data["recommendations"]
        ],
        "final_observation_recorded": data.get("final_observation") is not None,
    }
