#!/usr/bin/env python3
"""
seeded_run.py — deterministic wrapper for a generator that doesn't seed itself.

Why this exists
---------------
generate_midi.py draws from BOTH `random` and `numpy.random` and seeds neither, with no
--seed flag. Its renders are therefore non-reproducible, which would make the score's
`provenance.seed` a lie and its `determinism` assertion un-meetable.

Rather than fork the generator's code (a hand-edit to an existing repo we can't verify
byte-for-byte, and not our call to make unilaterally), we pin determinism at the *process
boundary*: seed both global RNGs, then exec the UNMODIFIED generator with runpy. Because the
generator uses the module-global RNG state, seeding here propagates into it.

This keeps the score honorable today with zero changes to existing code. A first-class
`--seed` flag upstream in generate_midi.py is the cleaner long-term fix for direct users and
is recommended as a follow-up — but it's the generator repo owner's call, not ours to force.

Usage
-----
    python scores/seeded_run.py --seed 20260625 -- <generator args...>
    python scores/seeded_run.py --seed 7 --generator path/to/gen.py -- --output x.mid

Everything after `--` is passed through verbatim to the generator.
"""
import argparse
import os
import random
import runpy
import sys

try:
    import numpy as np
except ImportError:
    np = None


def main():
    argv = sys.argv[1:]
    if "--" in argv:
        cut = argv.index("--")
        mine, passthrough = argv[:cut], argv[cut + 1:]
    else:
        mine, passthrough = argv, []

    p = argparse.ArgumentParser(description="Seed RNGs, then run an unmodified generator deterministically.")
    p.add_argument("--seed", type=int, required=True, help="integer seed for random + numpy.random")
    p.add_argument("--generator", default=None,
                   help="path to the generator script (default: ../generate_midi.py relative to this file)")
    a = p.parse_args(mine)

    random.seed(a.seed)
    if np is not None:
        np.random.seed(a.seed)
    else:
        print("WARNING: numpy not importable — numpy.random will NOT be seeded; determinism not guaranteed",
              file=sys.stderr)

    gen = a.generator or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "generate_midi.py")
    gen = os.path.abspath(gen)
    if not os.path.exists(gen):
        # Fail loudly and unambiguously — a missing generator is a render error, never "the music broke".
        print(f"RENDER ERROR: generator not found at {gen}", file=sys.stderr)
        sys.exit(3)

    print(f"[seeded_run] seed={a.seed} random+numpy → exec {gen}", file=sys.stderr)
    sys.argv = [gen] + passthrough
    runpy.run_path(gen, run_name="__main__")


if __name__ == "__main__":
    main()
