"""zeemap-audit Tier 1 — flag and report. Never modifies zees.

Checks per zee:
  1. parse_error            — YAML frontmatter fails to parse
  2. missing_required_field — schema-version-dispatched required-field check
  3. malformed_created      — `created:` (or `date:` for v0) not ISO 8601
  4. unknown_field          — frontmatter key not in v1 schema
  5. non_canonical_filename — filename doesn't match YYYY-MM-DD-HHMM-slug.md

Writes a dated markdown report and appends an `audit_run` event to the
zeemap log. Prints a short summary to stdout for the caller (Claude/cron)
to relay to Slack.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import uuid as uuid_mod
from pathlib import Path

import yaml

# Make the sibling zeemap skill's lib importable for log.py.
ZEEMAP_LIB = Path.home() / ".hermes" / "skills" / "productivity" / "zeemap"
sys.path.insert(0, str(ZEEMAP_LIB))
from lib import log  # type: ignore  # noqa: E402

DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "data" / "config.json"
ZEE_FILENAME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-\d{4}-[a-z0-9-]+\.md$")
ISO_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}(:\d{2})?(\.\d+)?(Z|[+-]\d{2}:?\d{2})?)?$"
)

SEVERITY_ORDER = ("critical", "warn", "info")

# Load v1 schema once per run; used for required-field + unknown-field checks.
def load_schema(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _expand(p: str) -> Path:
    return Path(p).expanduser()


def parse_frontmatter(raw: str) -> tuple[dict | None, str | None]:
    """Return (frontmatter_dict or None, error_message or None).

    None frontmatter with an error indicates a parse failure worth flagging.
    Missing frontmatter entirely (no `---` delimiters) counts as a parse error
    so the audit surfaces it.
    """
    if not raw.startswith("---"):
        return None, "no frontmatter delimiter"
    parts = raw.split("\n---", 2)
    if len(parts) < 2:
        return None, "no closing frontmatter delimiter"
    body = parts[0].lstrip("-").lstrip("\n")
    try:
        data = yaml.safe_load(body)
    except yaml.YAMLError as e:
        return None, str(e).splitlines()[0]
    if not isinstance(data, dict):
        return None, f"frontmatter is not a mapping (got {type(data).__name__})"
    return data, None


def get_schema_version(fm: dict) -> int:
    v = fm.get("schema_version")
    if isinstance(v, int) and v >= 0 and not isinstance(v, bool):
        return v
    return 0


def iso_ok(value) -> bool:
    if isinstance(value, str):
        return bool(ISO_RE.match(value))
    if isinstance(value, dt.date):
        return True
    return False


def check_zee(filename: str, raw: str, schema: dict) -> list[dict]:
    """Return a list of finding dicts for this zee. Each finding:
    {check, severity_code, detail}.
    """
    findings: list[dict] = []

    # Non-canonical filenames are not treated as zees for field-level checks.
    # We flag them once (info) and move on — matches the viewer's behavior of
    # ignoring non-zee .md files like README.md in the data dir.
    if not ZEE_FILENAME_RE.match(filename):
        findings.append({
            "check": "non_canonical_filename",
            "detail": f"{filename} does not match YYYY-MM-DD-HHMM-slug.md",
        })
        return findings

    fm, err = parse_frontmatter(raw)
    if fm is None:
        findings.append({
            "check": "parse_error",
            "detail": err or "unknown parse error",
        })
        return findings  # No point running field-level checks on unparseable fm.

    sv = get_schema_version(fm)

    # Required-field check
    if sv >= 1:
        required = schema["required"]
        missing = [f for f in required if f not in fm or fm.get(f) in (None, "")]
        if missing:
            findings.append({
                "check": "missing_required_field",
                "detail": f"v{sv} zee missing: {', '.join(sorted(missing))}",
            })
    else:
        # v0 grandfathered: require only title + some date hint
        v0_missing = []
        if not fm.get("title"):
            v0_missing.append("title")
        if "created" not in fm and "date" not in fm:
            # Filename date prefix is accepted as a date fallback
            if not re.match(r"^\d{4}-\d{2}-\d{2}-\d{4}-", filename):
                v0_missing.append("created-or-date")
        if v0_missing:
            findings.append({
                "check": "missing_required_field",
                "detail": f"v0 zee missing: {', '.join(v0_missing)}",
            })

    # Malformed created / date
    created_raw = fm.get("created") if "created" in fm else fm.get("date")
    if created_raw is not None and not iso_ok(created_raw):
        findings.append({
            "check": "malformed_created",
            "detail": f"created/date not ISO 8601: {created_raw!r}",
        })

    # Unknown fields (only meaningful for v1; v0 zees predate the schema)
    if sv >= 1:
        known = set(schema["required"]) | set(schema["optional"])
        unknown = [k for k in fm.keys() if k not in known]
        if unknown:
            findings.append({
                "check": "unknown_field",
                "detail": f"not in v1 schema: {', '.join(sorted(unknown))}",
            })

    return findings


def run_audit(config: dict) -> dict:
    """Execute all checks. Returns {zees: int, findings: [...], by_severity: {...}}."""
    data_dir = _expand(config["data_dir"])
    schema = load_schema(_expand(config["schema_path"]))
    severity_map = config["severity"]
    ignore = set(config.get("ignore_uuids", []))

    all_findings: list[dict] = []
    n_zees = 0
    for path in sorted(data_dir.glob("*.md")):
        n_zees += 1
        raw = path.read_text(encoding="utf-8")
        findings = check_zee(path.name, raw, schema)
        if not findings:
            continue
        # Try to extract uuid for ignore-list support; best-effort.
        fm, _ = parse_frontmatter(raw)
        uuid_val = (fm or {}).get("uuid")
        if uuid_val in ignore:
            continue
        for f in findings:
            f["filename"] = path.name
            f["uuid"] = uuid_val
            f["severity"] = severity_map.get(f["check"], "info")
        all_findings.extend(findings)

    by_severity = {s: [f for f in all_findings if f["severity"] == s]
                   for s in SEVERITY_ORDER}

    return {
        "zees": n_zees,
        "findings": all_findings,
        "by_severity": by_severity,
    }


def render_report(result: dict, *, ts: str) -> str:
    lines = [
        f"# Zeemap audit — {ts[:10]}",
        "",
        f"Scanned **{result['zees']}** zees. "
        f"{len(result['findings'])} findings total.",
        "",
        "| Severity | Count |",
        "|---|---|",
    ]
    for sev in SEVERITY_ORDER:
        lines.append(f"| {sev} | {len(result['by_severity'][sev])} |")
    lines.append("")

    for sev in SEVERITY_ORDER:
        items = result["by_severity"][sev]
        if not items:
            continue
        lines.append(f"## {sev} ({len(items)})")
        lines.append("")
        for f in items:
            uuid_part = f" · `{f['uuid']}`" if f.get("uuid") else ""
            lines.append(f"- **{f['check']}** — `{f['filename']}`{uuid_part}")
            lines.append(f"    - {f['detail']}")
        lines.append("")

    if not result["findings"]:
        lines.append("_No findings. All zees look clean._")
        lines.append("")

    return "\n".join(lines)


def render_summary(result: dict) -> str:
    """One-line summary suitable for Slack / chat relay."""
    by = result["by_severity"]
    parts = [
        f"{result['zees']} scanned",
        f"{len(by['critical'])} critical",
        f"{len(by['warn'])} warn",
        f"{len(by['info'])} info",
    ]
    return "zeemap audit: " + ", ".join(parts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--json", action="store_true",
                        help="Print JSON result to stdout instead of writing report.")
    parser.add_argument("--no-log", action="store_true",
                        help="Skip writing the audit_run log event.")
    parser.add_argument("--model", default=None,
                        help="Actor model id (stamped on the audit_run log event).")
    args = parser.parse_args(argv)

    config_path = _expand(args.config)
    config = json.loads(config_path.read_text(encoding="utf-8"))

    result = run_audit(config)
    ts = dt.datetime.now().replace(microsecond=0).isoformat(timespec="seconds")

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
        return 0

    # Write dated report
    reports_dir = _expand(config["reports_dir"])
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / f"audit-{ts[:10]}.md"
    report_path.write_text(render_report(result, ts=ts), encoding="utf-8")

    # Append audit_run log event — unless suppressed
    if not args.no_log:
        log_path = _expand(config["log_path"])
        event = {
            "uuid": f"audit-run-{uuid_mod.uuid4()}",
            "ts": ts,
            "action": "audit_run",
            "actor_model": args.model,
            "skill": "zeemap-audit",
            "note": render_summary(result),
        }
        try:
            log.append(event, path=log_path)
        except Exception as e:
            print(f"warning: log append failed: {e}", file=sys.stderr)

    # Short chat/Slack summary to stdout
    print(render_summary(result))
    print(f"report: {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
