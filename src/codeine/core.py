"""CODEINE v0 session storage and the single persistence detector."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
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


def _stable_output(value: bytes) -> str:
    """Remove only local temporary-path residue from a test-output digest."""
    text = value.decode("utf-8", errors="replace")
    temp_root = str(Path(tempfile.gettempdir()))
    text = text.replace(temp_root, "<TEMP>").replace(temp_root.replace("\\", "/"), "<TEMP>")
    text = re.sub(r"(?i)tmp[a-z0-9_-]{4,}", "<TMP>", text)
    return re.sub(r"Ran (\d+) tests in [0-9.]+s", r"Ran \1 tests in <DURATION>s", text)


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
        "stable_stdout_digest": _digest(_stable_output(result.stdout)),
        "stable_stderr_digest": _digest(_stable_output(result.stderr)),
        "duration_ms": elapsed_ms,
    }
    stable = {
        key: value
        for key, value in snapshot.items()
        if key not in {"duration_ms", "stdout_digest", "stderr_digest"}
    }
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
        "test": {
            key: value
            for key, value in test.items()
            if key not in {"duration_ms", "stdout_digest", "stderr_digest"}
        },
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


def decide(diagnostics: list[dict[str, Any]]) -> dict[str, Any]:
    """Apply the single persistence rule to a list of attempt diagnostics.

    This is the only place the rule exists.  ``assess`` calls it while a session
    runs and ``replay`` calls it afterwards over the recorded raw observations,
    so a recommendation can be recomputed instead of trusted.
    """
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
    elif len(trailing_unchanged) == 1:
        decision = "CONTINUE"
        strength = "weak_repetition"
        reason = "one unchanged observable boundary; the intervention threshold has not been reached"
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
    return {
        "decision": decision,
        "evidence_strength": strength,
        "reason": reason,
        "evidence_for": evidence_for,
        "evidence_against": evidence_against,
        "evaluation": evaluation,
        "fingerprint": fingerprint,
    }


def assess(session: Path | str | None = None) -> dict[str, Any]:
    path = _session_path(session)
    data = _read(path)
    diagnostics = _attempt_diagnostics(data)
    verdict = decide(diagnostics)
    decision = verdict["decision"]
    strength = verdict["evidence_strength"]
    reason = verdict["reason"]
    evidence_for = verdict["evidence_for"]
    evidence_against = verdict["evidence_against"]
    evaluation = verdict["evaluation"]
    fingerprint = verdict["fingerprint"]
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


_ABSOLUTE_PATH = re.compile(r"(?:^|[\s=:\"'])(?:/|~/|[A-Za-z]:[\\/])")
FORBIDDEN_RAW_LABELS = ("progress", "stuck", "success", "failure", "productive", "bad_strategy")


def _sanitize_command(command: str | None) -> tuple[str | None, str]:
    """Keep a test command only when it carries no absolute local path."""
    if not command:
        return None, "absent"
    if _ABSOLUTE_PATH.search(command):
        return None, "withheld_absolute_path_present"
    return command, "included"


def _export_snapshot(snapshot: dict[str, Any] | None) -> dict[str, Any] | None:
    """Project one raw snapshot to committable evidence: digests, never payloads."""
    if not snapshot:
        return None
    git = snapshot.get("git", {})
    test = snapshot.get("test", {})
    return {
        "state_digest": snapshot["state_digest"],
        "captured_at": snapshot["captured_at"],
        "scope": snapshot["scope"],
        "git": {
            "head": git.get("head"),
            "status_digest": git.get("status_digest"),
            "unstaged_diff_digest": git.get("unstaged_diff_digest"),
            "staged_diff_digest": git.get("staged_diff_digest"),
            "working_tree_digest": git.get("working_tree_digest"),
            "diff_bytes": git.get("diff_bytes"),
            "status_line_count": len(git.get("status", [])),
            "untracked_file_count": len(git.get("untracked_files", [])),
            "payload_withheld": ["status lines", "untracked file paths", "diff payloads"],
        },
        "test": {
            key: test.get(key)
            for key in (
                "availability",
                "command_digest",
                "exit_code",
                "stdout_digest",
                "stderr_digest",
                "stable_stdout_digest",
                "stable_stderr_digest",
            )
        },
    }


def _raw_label_audit(data: dict[str, Any]) -> dict[str, Any]:
    """Machine check that no semantic conclusion was stored in a raw record."""
    payload = _canonical([attempt["record"] for attempt in data["attempts"]]).lower()
    found = sorted({label for label in FORBIDDEN_RAW_LABELS if f'"{label}"' in payload})
    return {
        "forbidden_keys_checked": list(FORBIDDEN_RAW_LABELS),
        "forbidden_keys_present": found,
        "raw_records_carry_no_conclusion": not found,
    }


def export_session(session: Path | str | None = None) -> dict[str, Any]:
    """Build the deterministic, committable projection of one raw session."""
    path = _session_path(session)
    data = _read(path)
    command, command_disclosure = _sanitize_command(data.get("test_command"))
    attempts = []
    for ordinal, attempt in enumerate(data["attempts"], start=1):
        record = attempt["record"]
        attempts.append(
            {
                "attempt_id": attempt["attempt_id"],
                "ordinal": ordinal,
                "intervention": dict(record["intervention"]),
                "before": _export_snapshot(record["before"]),
                "after": _export_snapshot(record["after"]),
                "derived": {
                    "state_changed": attempt["derived"]["state_changed"],
                    "resources_observed": attempt["derived"]["resources_observed"],
                    "semantic_claim": attempt["derived"]["semantic_claim"],
                },
                "resources": record["resources"],
                "provenance": {
                    "source_ref": record["provenance"]["source_ref"],
                    "captured_at": record["provenance"]["captured_at"],
                    "source_system": record["provenance"]["source_system"],
                    "field_audit_keys": sorted(record["provenance"]["field_audit"]),
                    "residue": {
                        "test_command_digest": record["provenance"]["residue"]["test_command_digest"],
                        "raw_snapshots_retained": record["provenance"]["residue"]["raw_snapshots_retained"],
                        "repository_root": "withheld_local_path",
                    },
                },
            }
        )
    decisions: dict[str, int] = {}
    for recommendation in data["recommendations"]:
        decisions[recommendation["decision"]] = decisions.get(recommendation["decision"], 0) + 1
    final = data.get("final_observation")
    export = {
        "protocol": "codeine-v0-session-export",
        "schema_version": SCHEMA_VERSION,
        "generated_by": "codeine.core.export_session",
        "manually_authored": False,
        "session_id": data["session_id"],
        "task": data.get("task"),
        "hypothesis": data["hypothesis"],
        "test_command": command,
        "test_command_disclosure": command_disclosure,
        "test_command_digest": data.get("test_command_digest"),
        "started_at": data["started_at"],
        "finished_at": data.get("finished_at"),
        "baseline_before": _export_snapshot(
            data["attempts"][0]["record"]["before"] if data["attempts"] else data.get("current_before")
        ),
        "attempts": attempts,
        "recommendations": [
            {
                "recommendation_id": item["recommendation_id"],
                "decision": item["decision"],
                "hypothesis_id": item["hypothesis_id"],
                "reason": item["reason"],
                "evidence_for": item["evidence_for"],
                "evidence_against": item["evidence_against"],
                "evidence_strength": item["evidence_strength"],
                "evaluation": item["evaluation"],
                "fingerprint": item["fingerprint"],
                "issued_at": item["issued_at"],
                "consequence": item["consequence"],
                "provenance": item["provenance"],
            }
            for item in data["recommendations"]
        ],
        "final_observation": {
            "recorded": final is not None,
            "test_exit_code": (final or {}).get("test", {}).get("exit_code"),
            "snapshot": _export_snapshot(final),
        },
        "gate_inputs": {
            "attempt_count": len(attempts),
            "unchanged_boundary_count": sum(
                1 for item in attempts if not item["derived"]["state_changed"]
            ),
            "decisions_emitted": decisions,
            "intervention_recommended": any(
                item["decision"] in {"SWITCH", "STOP"} for item in data["recommendations"]
            ),
            "causal_help_claimed": False,
            "derivation": "counted from the machine-generated records in this export",
        },
        "raw_record_label_audit": _raw_label_audit(data),
        "privacy": {
            "committed": [
                "observation order",
                "opaque intervention token digests",
                "before/after state digests",
                "raw and stable test output digests",
                "measured resource dimensions",
                "detector inputs",
                "recommendations and provenance",
            ],
            "withheld": [
                "repository root path",
                "git status lines",
                "untracked file paths",
                "diff and test output payloads",
            ],
            "withheld_payloads_are_represented_by": "their digests and provenance only",
        },
    }
    export["determinism"] = {
        "export_digest": _digest(export),
        "digest_scope": "every field of this export except determinism itself",
        "replay_entry_point": "codeine.core.replay_export",
    }
    return export


def _export_diagnostics(export: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        attempt["attempt_id"]: {
            "attempt_id": attempt["attempt_id"],
            "state_changed": attempt["derived"]["state_changed"],
            "resources_observed": attempt["derived"]["resources_observed"],
            "before_state_digest": attempt["before"]["state_digest"],
            "after_state_digest": attempt["after"]["state_digest"],
        }
        for attempt in export["attempts"]
    }


def _replay(diagnostics: dict[str, dict[str, Any]], recommendations: list[dict[str, Any]], source: str) -> dict[str, Any]:
    compared = 0
    mismatches: list[dict[str, Any]] = []
    for recommendation in recommendations:
        attempt_ids = recommendation["provenance"]["attempt_ids"]
        subset = [diagnostics[item] for item in attempt_ids if item in diagnostics]
        if len(subset) != len(attempt_ids):
            mismatches.append(
                {
                    "recommendation_id": recommendation["recommendation_id"],
                    "field": "provenance.attempt_ids",
                    "reason": "a referenced raw observation is absent from this record",
                }
            )
            continue
        verdict = decide(subset)
        compared += 1
        for field in ("decision", "evidence_strength", "reason", "evidence_for", "evidence_against", "fingerprint"):
            if verdict[field] != recommendation[field]:
                mismatches.append(
                    {
                        "recommendation_id": recommendation["recommendation_id"],
                        "field": field,
                        "recorded": recommendation[field],
                        "recomputed": verdict[field],
                    }
                )
    return {
        "source": source,
        "rule_id": HYPOTHESIS_ID,
        "recommendations_compared": compared,
        "recommendations_total": len(recommendations),
        "mismatches": mismatches,
        "deterministic": not mismatches and compared == len(recommendations),
        "provenance": {
            "derivation": "decide() re-applied to the raw diagnostics named by each recommendation",
            "recomputed_from": "machine-generated observation records only",
            "semantic_claim": "none; replay checks reproducibility, not usefulness",
        },
    }


def replay_export(export: Path | str) -> dict[str, Any]:
    """Recompute every recommendation from an exported record alone."""
    path = Path(export).expanduser().resolve()
    if not path.exists():
        raise CodeineError(f"session export not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CodeineError(f"invalid session export JSON: {path}") from exc
    stated = payload.get("determinism", {}).get("export_digest")
    recomputed = _digest({key: value for key, value in payload.items() if key != "determinism"})
    result = _replay(_export_diagnostics(payload), payload["recommendations"], path.name)
    result["export_digest_stated"] = stated
    result["export_digest_recomputed"] = recomputed
    result["export_digest_verified"] = stated == recomputed
    result["deterministic"] = result["deterministic"] and result["export_digest_verified"]
    return result


def replay_session(session: Path | str | None = None, export: Path | str | None = None) -> dict[str, Any]:
    """Recompute recommendations from the raw session, and check the export matches."""
    path = _session_path(session)
    data = _read(path)
    diagnostics = {item["attempt_id"]: item for item in _attempt_diagnostics(data)}
    result = _replay(diagnostics, data["recommendations"], path.name)
    if export is not None:
        export_path = Path(export).expanduser().resolve()
        rebuilt = serialize_export(export_session(path))
        stored = export_path.read_text(encoding="utf-8") if export_path.exists() else None
        result["export_reproducible_byte_for_byte"] = stored == rebuilt
        result["export_path"] = export_path.name
        result["deterministic"] = result["deterministic"] and stored == rebuilt
    return result


def serialize_export(export: dict[str, Any]) -> str:
    return json.dumps(export, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def write_export(session: Path | str | None = None, out: Path | str | None = None) -> dict[str, Any]:
    export = export_session(session)
    target = Path(out) if out else Path("results") / "codeine-session-export.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(serialize_export(export), encoding="utf-8")
    return {
        "export_path": str(target),
        "session_id": export["session_id"],
        "attempt_count": export["gate_inputs"]["attempt_count"],
        "recommendation_count": len(export["recommendations"]),
        "export_digest": export["determinism"]["export_digest"],
        "manually_authored": False,
    }


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
