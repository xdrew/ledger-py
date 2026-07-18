"""Run domain mutation testing and enforce a kill-rate floor.

Runs `mutmut run`, parses its final summary, and fails if too many mutants
survive — so a weakened domain test suite breaks CI. Message-only survivors
(mutating an error string to None) are expected tail noise, so the floor is set
below 100% deliberately. Surviving mutants are listed for triage.

Usage: python scripts/mutation_gate.py [floor]   # floor defaults to 0.75
"""

import re
import subprocess
import sys

FLOOR = float(sys.argv[1]) if len(sys.argv) > 1 else 0.75


def _last_count(emoji: str, text: str) -> int:
    matches = re.findall(rf"{emoji}\s*(\d+)", text)
    return int(matches[-1]) if matches else 0


def main() -> int:
    run = subprocess.run(["mutmut", "run"], capture_output=True, text=True, check=False)
    summary = run.stdout + run.stderr

    killed = _last_count("🎉", summary)
    no_tests = _last_count("🫥", summary)
    timeout = _last_count("⏰", summary)
    suspicious = _last_count("🤔", summary)
    survived = _last_count("🙁", summary)

    caught = killed + timeout
    not_caught = survived + suspicious
    total = caught + not_caught
    rate = caught / total if total else 0.0

    print(f"mutation: {caught}/{total} caught ({rate:.1%}); floor {FLOOR:.0%}")
    print(
        f"  killed={killed} survived={survived} timeout={timeout} "
        f"suspicious={suspicious} no-tests={no_tests}"
    )

    listing = subprocess.run(["mutmut", "results"], capture_output=True, text=True, check=False)
    survivors = [
        ln.strip() for ln in listing.stdout.splitlines() if ln.strip().endswith("survived")
    ]
    if survivors:
        print("surviving mutants (triage):")
        for survivor in survivors:
            print(f"  {survivor}")

    if total == 0:
        print("FAIL: no mutants were tested — check the mutmut config / run")
        return 1
    if rate < FLOOR:
        print(f"FAIL: kill-rate {rate:.1%} is below the floor {FLOOR:.0%}")
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
