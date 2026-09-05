"""Antigravity Stop hook to verify agentic guardrails before concluding."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent.parent


def main() -> int:
    try:
        stdin_content = sys.stdin.read()
        payload = json.loads(stdin_content) if stdin_content.strip() else {}
    except Exception:
        payload = {}

    script_path = repo_root / "scripts" / "check_agentic_guardrails.py"
    if not script_path.exists():
        sys.stdout.write(json.dumps({}) + "\n")
        sys.stdout.flush()
        return 0

    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        violation_text = result.stdout.strip() or result.stderr.strip() or "Guardrail checks failed."
        output = {
            "decision": "continue",
            "reason": f"Agentic guardrails incomplete: {violation_text}. Please update PLAN.md accordingly.",
        }
    else:
        output = {}

    sys.stdout.write(json.dumps(output) + "\n")
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
