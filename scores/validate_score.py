#!/usr/bin/env python3
"""
validate_score.py — dry-run a score against the v0 contract.

This does NOT render. It checks that a score is a well-formed, honorable contract
*before* the performer ever touches it:

  1. structure — required blocks/fields are present
  2. taste-litmus lint — every `expected` assertion declares a whitelisted, renderer-
     correctness `kind`. Free-form / taste assertions are rejected (Oliveros's guardrail,
     enforced mechanically so taste cannot leak into the contract by accident).
  3. provenance — the reproducibility spine declares seed + model_digest + tool_versions,
     and a seed is actually pinned on the generator.

Exit code 0 = honorable contract; 1 = rejected. Usage: python validate_score.py SCORE.yaml
"""
import re
import sys
import yaml

# Whitelist of renderer-correctness assertion kinds. A `kind` belongs here only if a
# violation would make you open the renderer's bug tracker — never if it would make you
# reach for a different seed. Grow this list only when a real render needs it.
ALLOWED_EXPECTED_KINDS = {
    "validity",          # artifact parses as a well-formed file of target.kind
    "scale_membership",  # every pitch-class in the specified tuning/key
    "range",             # every pitch within a declared bound
    "tempo",             # artifact tempo equals requested bpm
    "determinism",       # identical inputs => identical note events
}

REQUIRED_TOP = ["schema_version", "score", "tuning", "generator", "target", "expected", "provenance"]
REQUIRED_TUNING = ["system", "reference_hz", "scl"]
REQUIRED_GENERATOR = ["repo", "ref", "algorithm", "entrypoint", "params", "seed"]
REQUIRED_TARGET = ["kind", "writer", "requires"]
REQUIRED_PROVENANCE = ["seed", "model_digest", "tool_versions"]


def fail(errors):
    print("SCORE REJECTED — not an honorable contract:\n")
    for e in errors:
        print(f"  ✗ {e}")
    print(f"\n{len(errors)} problem(s).")
    sys.exit(1)


def main(path):
    with open(path) as f:
        s = yaml.safe_load(f)

    errors = []
    warnings = []

    for k in REQUIRED_TOP:
        if k not in s:
            errors.append(f"missing top-level block: {k}")
    if errors:
        fail(errors)

    if s["schema_version"] != 0:
        errors.append(f"schema_version must be 0 for this validator, got {s['schema_version']!r}")

    for k in REQUIRED_TUNING:
        if k not in s["tuning"]:
            errors.append(f"tuning.{k} missing (tuning is first-class even at 12-TET)")

    for k in REQUIRED_GENERATOR:
        if k not in s["generator"]:
            errors.append(f"generator.{k} missing")
    # the reproducibility promise is only real if a seed is actually pinned
    if s["generator"].get("seed") is None:
        errors.append("generator.seed is null — the score's reproducibility promise would be a lie")
    ref = str(s["generator"].get("ref", "")).strip()
    if not ref:
        errors.append("generator.ref is empty — pin a commit/tag, never a moving target")
    elif not re.fullmatch(r"[0-9a-f]{7,40}", ref) and not (ref.startswith("v") or ref.startswith("refs/tags/")):
        # SCHEMA requires a pinned commit/tag; a branch-shaped ref moves under us. Warn, don't fail —
        # the score is still runnable, but a render is no longer reproducible from the ref alone.
        warnings.append(f"generator.ref={ref!r} looks like a moving branch; SCHEMA requires a pinned commit/tag — repoint to the merge SHA.")

    for k in REQUIRED_TARGET:
        if k not in s["target"]:
            errors.append(f"target.{k} missing")

    # --- the taste-litmus lint ---
    seen_ids = set()
    for i, e in enumerate(s["expected"]):
        where = f"expected[{i}]"
        if "kind" not in e:
            errors.append(f"{where} has no `kind` — every assertion must declare one")
            continue
        if e["kind"] not in ALLOWED_EXPECTED_KINDS:
            errors.append(
                f"{where} kind={e['kind']!r} is not a renderer-correctness kind "
                f"(allowed: {sorted(ALLOWED_EXPECTED_KINDS)}). "
                f"If a violation would make you reach for a different seed, it's taste, not a contract."
            )
        for req in ("id", "assert", "rationale"):
            if not e.get(req):
                errors.append(f"{where} missing `{req}`")
        if e.get("id") in seen_ids:
            errors.append(f"{where} duplicate id {e.get('id')!r}")
        seen_ids.add(e.get("id"))

    for k in REQUIRED_PROVENANCE:
        if k not in s["provenance"]:
            errors.append(f"provenance.{k} missing (the reproducibility spine must be declared, even if null pre-render)")
    if "seed" in s["provenance"] and s["provenance"]["seed"] != s["generator"].get("seed"):
        errors.append("provenance.seed must echo generator.seed")

    if errors:
        fail(errors)

    for w in warnings:
        print(f"  ⚠ {w}")
    if warnings:
        print()

    print(f"SCORE OK — {path}")
    print(f"  score.id            : {s['score']['id']}")
    print(f"  tuning              : {s['tuning']['system']}")
    print(f"  generator           : {s['generator']['algorithm']} @ {s['generator']['repo']}")
    print(f"  seed (pinned)       : {s['generator']['seed']}")
    print(f"  target              : {s['target']['kind']} via {s['target']['writer']}")
    print(f"  expected assertions : {len(s['expected'])} (all renderer-correctness)")
    for e in s["expected"]:
        print(f"      - [{e['kind']}] {e['id']}")
    print("  taste boundary      : intact — no assertion encodes a preference")
    sys.exit(0)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python validate_score.py SCORE.yaml")
        sys.exit(2)
    main(sys.argv[1])
