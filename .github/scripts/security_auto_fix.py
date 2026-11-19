#!/usr/bin/env python3
"""Apply open Dependabot security alerts by bumping pinned dependency versions.

Reads alerts from GITHUB_ALERTS_JSON (or stdin). Writes a Markdown summary to
SECURITY_FIX_SUMMARY (default: security-fix-summary.md) and prints changed
file paths. Exits 0 even when nothing changed (caller decides whether to PR).
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

try:
    from packaging.version import InvalidVersion, Version
except ImportError:  # pragma: no cover - CI installs packaging
    Version = None  # type: ignore
    InvalidVersion = Exception  # type: ignore


ROOT = Path(os.environ.get("GITHUB_WORKSPACE", ".")).resolve()
SUMMARY_PATH = Path(os.environ.get("SECURITY_FIX_SUMMARY", "security-fix-summary.md"))


def parse_version(value: str):
    if Version is None:
        return None
    try:
        return Version(value.lstrip("vV"))
    except InvalidVersion:
        return None


def needs_bump(current: str, target: str) -> bool:
    cur_v, tgt_v = parse_version(current), parse_version(target)
    if cur_v is not None and tgt_v is not None:
        return cur_v < tgt_v
    return current != target


def load_alerts() -> list[dict]:
    alerts_file = os.environ.get("GITHUB_ALERTS_JSON_FILE")
    raw = os.environ.get("GITHUB_ALERTS_JSON")
    if alerts_file:
        data = json.loads(Path(alerts_file).read_text(encoding="utf-8"))
    elif raw:
        data = json.loads(raw)
    else:
        data = json.load(sys.stdin)
    if not isinstance(data, list):
        raise SystemExit("Expected a JSON list of Dependabot alerts")
    return data


def collect_targets(alerts: list[dict]) -> dict[tuple[str, str], dict]:
    """Map (manifest_path, package) -> best patch target."""
    targets: dict[tuple[str, str], dict] = {}
    for alert in alerts:
        if alert.get("state") != "open":
            continue
        dep = alert.get("dependency") or {}
        pkg = (dep.get("package") or {}).get("name")
        manifest = dep.get("manifest_path")
        vuln = alert.get("security_vulnerability") or {}
        patched = (vuln.get("first_patched_version") or {}).get("identifier")
        if not pkg or not manifest or not patched:
            continue
        key = (manifest, pkg)
        severity = (alert.get("security_advisory") or {}).get("severity") or "unknown"
        existing = targets.get(key)
        if existing is None or needs_bump(existing["patched"], patched):
            targets[key] = {
                "package": pkg,
                "manifest": manifest,
                "patched": patched,
                "severity": severity,
                "alert_numbers": [alert.get("number")],
                "ecosystem": (dep.get("package") or {}).get("ecosystem"),
            }
        else:
            existing["alert_numbers"].append(alert.get("number"))
    return targets


REQ_EQ_RE = re.compile(
    r"^(?P<prefix>\s*)(?P<name>[A-Za-z0-9_.\-]+)(?P<op>==|===)(?P<ver>[^\s#;]+)"
    r"(?P<suffix>\s*(?:#.*)?)$",
    re.IGNORECASE,
)
REQ_PIN_RE = re.compile(
    r"^(?P<prefix>\s*)(?P<name>[A-Za-z0-9_.\-]+)(?P<op>>=|~=)(?P<ver>[^\s#;,]+)"
    r"(?P<rest>[^#]*)(?P<suffix>\s*(?:#.*)?)$",
    re.IGNORECASE,
)


def bump_requirements(path: Path, package: str, patched: str) -> bool:
    if not path.is_file():
        return False
    original = path.read_text(encoding="utf-8")
    lines = original.splitlines(keepends=True)
    changed = False
    out: list[str] = []
    for line in lines:
        ending = "\n" if line.endswith("\n") else ""
        stripped = line[:-1] if ending else line
        if line.endswith("\r\n"):
            ending = "\r\n"
            stripped = line[:-2]
        elif line.endswith("\n"):
            ending = "\n"
            stripped = line[:-1]
        m = REQ_EQ_RE.match(stripped) or REQ_PIN_RE.match(stripped)
        if not m or m.group("name").lower() != package.lower():
            out.append(line)
            continue
        current = m.group("ver")
        if not needs_bump(current, patched):
            out.append(line)
            continue
        # Keep == pins as ==; promote >=/~= lower bounds to the patched floor.
        op = "==" if m.group("op") in ("==", "===") else m.group("op")
        rest = m.groupdict().get("rest") or ""
        suffix = m.group("suffix") or ""
        out.append(
            f"{m.group('prefix')}{m.group('name')}{op}{patched}{rest}{suffix}{ending}"
        )
        changed = True
    if changed:
        path.write_text("".join(out), encoding="utf-8")
    return changed


UV_PKG_BLOCK_RE = re.compile(
    r'(?P<head>\[\[package\]\]\s*\nname\s*=\s*"(?P<name>[^"]+)"\s*\nversion\s*=\s*")'
    r'(?P<ver>[^"]+)(?P<tail>")',
    re.MULTILINE,
)


def bump_uv_lock(path: Path, package: str, patched: str) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")

    def repl(match: re.Match[str]) -> str:
        if match.group("name").lower() != package.lower():
            return match.group(0)
        current = match.group("ver")
        if not needs_bump(current, patched):
            return match.group(0)
        return f"{match.group('head')}{patched}{match.group('tail')}"

    new_text, count = UV_PKG_BLOCK_RE.subn(repl, text)
    # Also bump exact version strings in requirement lines inside the same lock
    # when they pin this package (best-effort; uv lock regen preferred later).
    pin_re = re.compile(
        rf'(^|\n)(\s*(?:requires-dist|dependencies)\s*=\s*\[[^\]]*"{re.escape(package)}==)([^"]+)(")',
        re.IGNORECASE | re.MULTILINE,
    )

    def pin_repl(match: re.Match[str]) -> str:
        current = match.group(3)
        if not needs_bump(current, patched):
            return match.group(0)
        return f"{match.group(1)}{match.group(2)}{patched}{match.group(4)}"

    new_text2, count2 = pin_re.subn(pin_repl, new_text)
    if count or count2:
        path.write_text(new_text2, encoding="utf-8")
        return True
    return False


PKG_JSON_DEP_KEYS = (
    "dependencies",
    "devDependencies",
    "optionalDependencies",
    "peerDependencies",
)


def bump_package_json(path: Path, package: str, patched: str) -> bool:
    if not path.is_file():
        return False
    data = json.loads(path.read_text(encoding="utf-8"))
    changed = False
    for key in PKG_JSON_DEP_KEYS:
        deps = data.get(key)
        if not isinstance(deps, dict) or package not in deps:
            continue
        current_spec = str(deps[package])
        # Preserve caret/tilde range style when present.
        m = re.match(r"^([\^~>=]*)(.+)$", current_spec.strip())
        if not m:
            continue
        prefix, current = m.group(1), m.group(2).lstrip("=")
        # Strip trailing range junk like " || ..."
        current = current.split()[0]
        if not needs_bump(current, patched) and current == patched:
            continue
        if prefix in ("", "=", "=="):
            deps[package] = patched
        else:
            deps[package] = f"{prefix}{patched}"
        changed = True
    if changed:
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return changed


LOCK_VERSION_RE_TMPL = r'("name"\s*:\s*"{pkg}"\s*,\s*"version"\s*:\s*")([^"]+)(")'


def bump_package_lock(path: Path, package: str, patched: str) -> bool:
    """Best-effort version bump inside package-lock.json for a named package."""
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(
        LOCK_VERSION_RE_TMPL.format(pkg=re.escape(package)),
        re.MULTILINE,
    )

    def repl(match: re.Match[str]) -> str:
        current = match.group(2)
        if not needs_bump(current, patched):
            return match.group(0)
        return f"{match.group(1)}{patched}{match.group(3)}"

    new_text, count = pattern.subn(repl, text)
    # packages["node_modules/foo"] style (lockfileVersion 2/3)
    node_re = re.compile(
        rf'("node_modules/{re.escape(package)}"\s*:\s*\{{[^\}}]*?"version"\s*:\s*")([^"]+)(")',
        re.DOTALL,
    )

    def node_repl(match: re.Match[str]) -> str:
        current = match.group(2)
        if not needs_bump(current, patched):
            return match.group(0)
        return f"{match.group(1)}{patched}{match.group(3)}"

    new_text2, count2 = node_re.subn(node_repl, new_text)
    if count or count2:
        path.write_text(new_text2, encoding="utf-8")
        return True
    return False


def apply_fix(manifest: str, package: str, patched: str, ecosystem: str | None) -> bool:
    path = ROOT / manifest
    name = path.name.lower()
    if name == "requirements.txt":
        return bump_requirements(path, package, patched)
    if name == "uv.lock":
        return bump_uv_lock(path, package, patched)
    if name == "package.json":
        return bump_package_json(path, package, patched)
    if name == "package-lock.json":
        # Prefer also bumping sibling package.json when present.
        sibling = path.with_name("package.json")
        changed_json = (
            bump_package_json(sibling, package, patched) if sibling.is_file() else False
        )
        changed_lock = bump_package_lock(path, package, patched)
        return changed_json or changed_lock
    # Fallback by ecosystem
    if ecosystem == "pip" and path.suffix in {".txt", ".in"}:
        return bump_requirements(path, package, patched)
    if ecosystem == "npm" and name.endswith(".json"):
        return bump_package_json(path, package, patched)
    return False


def main() -> int:
    alerts = load_alerts()
    targets = collect_targets(alerts)
    changed_files: set[str] = set()
    applied: list[dict] = []
    skipped: list[dict] = []

    # Prefer highest patched version per (manifest, package) already done.
    for (_manifest, _pkg), info in sorted(
        targets.items(), key=lambda x: (x[0][0], x[0][1].lower())
    ):
        ok = apply_fix(
            info["manifest"], info["package"], info["patched"], info.get("ecosystem")
        )
        if ok:
            changed_files.add(info["manifest"])
            # package.json may also have been updated for lockfile alerts
            if info["manifest"].endswith("package-lock.json"):
                sibling = str(Path(info["manifest"]).with_name("package.json"))
                if (ROOT / sibling).is_file():
                    changed_files.add(sibling)
            applied.append(info)
        else:
            skipped.append(info)

    by_manifest: dict[str, list[dict]] = defaultdict(list)
    for item in applied:
        by_manifest[item["manifest"]].append(item)

    lines = [
        "## Security auto-fix summary",
        "",
        f"- Open alerts considered: **{len(alerts)}**",
        f"- Unique package/manifest targets: **{len(targets)}**",
        f"- Applied bumps: **{len(applied)}**",
        f"- Skipped (no pin found / already patched / no patch version): **{len(skipped)}**",
        "",
    ]
    if applied:
        lines.append("### Applied")
        lines.append("")
        for manifest, items in sorted(by_manifest.items()):
            lines.append(f"- `{manifest}`")
            for item in sorted(items, key=lambda i: i["package"].lower()):
                nums = ", ".join(f"#{n}" for n in item["alert_numbers"] if n)
                lines.append(
                    f"  - `{item['package']}` → `{item['patched']}` "
                    f"({item['severity']}; alerts {nums})"
                )
        lines.append("")
    if skipped:
        lines.append("### Skipped")
        lines.append("")
        for item in skipped[:50]:
            lines.append(
                f"- `{item['manifest']}` / `{item['package']}` → `{item['patched']}`"
            )
        if len(skipped) > 50:
            lines.append(f"- …and {len(skipped) - 50} more")
        lines.append("")

    lines.append("cc @gautammanak1 for review")
    lines.append("")

    SUMMARY_PATH.write_text("\n".join(lines), encoding="utf-8")
    # Machine-readable changed files for the workflow
    changed_list = ROOT / "security-fix-changed.txt"
    changed_list.write_text(
        "\n".join(sorted(changed_files)) + ("\n" if changed_files else ""),
        encoding="utf-8",
    )
    print(f"Applied {len(applied)} bumps across {len(changed_files)} files")
    for path in sorted(changed_files):
        print(f"CHANGED {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
