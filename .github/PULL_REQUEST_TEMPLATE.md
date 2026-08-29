<!-- Thank you for contributing! Please run the release gate before submitting:
     python scripts/release_gate.py   (validate + unit tests)
     python -m ruff check .           (pinned version in CI: 0.13.2) -->

## What does this PR change?

<!-- One paragraph: the problem, the fix, and which gate/tool is affected. -->

## Checklist

- [ ] `python scripts/release_gate.py` passes locally
- [ ] `python -m ruff check .` passes with ruff **0.13.2** (the version pinned in CI)
- [ ] New rules/checkers come with regression tests (same input → same report)
- [ ] Threshold-affecting changes reference the corpus benchmark discipline (see docs/CORPUS-BENCHMARK.md)
- [ ] README (en/zh) tool tables and tool counts updated if tools were added
- [ ] CHANGELOG.md has an entry under the appropriate version
- [ ] Findings stay hints, not verdicts (no single "AI %" style judgments)
