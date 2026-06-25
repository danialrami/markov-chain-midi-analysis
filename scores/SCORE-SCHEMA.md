# Score Schema — v0

> Status: **v0 (minimal)** · Owner: Saariaho (cloud composer) · Audience: the tambora **performer** agent
> The schema grows only as real renders demand it. Resist adding fields before a render needs them.

## What a "score" is

A **score** is an executable performance spec — the contract between the cloud composer
(who designs the generative system) and the local performer (who renders it). It is *not*
prose. The performer must be able to execute it **deterministically** without re-deriving
intent from essays.

Prose — theory, intent, exploration — lives elsewhere (`sagemath-docs`, the shared
`agent-knowledge` base). The score carries only what is needed to **reproduce a render**.

This is LUFS Workchain's own philosophy — declarative, verifiable — pointed at composition.

## The two-audiences rule, restated as fields

Every score separates three concerns that beginners conflate:

| Block | Question it answers | Asserted? |
|---|---|---|
| `generator` + `tuning` + `target` | *How is the artifact produced?* | — (inputs) |
| `expected` | *Is the render structurally what was specified?* | **yes — pass/fail** |
| `provenance` | *Which exact inputs produced this artifact?* | **never** (recorded only) |

### The taste boundary (non-negotiable)

`expected` assertions verify the **renderer**, never the **music**. A failed assertion must
mean *the machine is broken*, not *the music is unsatisfying*. Taste stays with Daniel's ear.

**The litmus** (from Oliveros, 2026-06-25): if a violation would make you open the
renderer's bug tracker, the assertion belongs. If it would make you reach for a different
seed, it's taste in a lab coat — drop it.

- ✅ `all pitch-classes ∈ the specified scale` — quantizer broken if violated
- ✅ `all MIDI pitches ∈ [21, 108]` — range clamp broken if violated
- ✅ `same seed + same models ⇒ identical note events` — determinism is a correctness property
- ❌ `melody spans ≥ one octave` — that's a preference; reach for another seed
- ❌ `contains all 12 pitch-classes` — aggregate completion is an aesthetic, not a correctness, claim

The validator (`validate_score.py`) enforces this mechanically: every `expected` entry must
declare a `kind` drawn from a fixed whitelist of renderer-correctness checks. Free-form
assertions are rejected at lint time, so taste cannot leak into the contract by accident.

## Top-level shape (v0)

```yaml
schema_version: 0
score:        { id, title, description, author, created }
tuning:       { system, reference_hz, scl }     # first-class even at 12-TET
generator:    { repo, ref, entrypoint, algorithm, params, seed }
target:       { kind, writer, requires }         # the deterministic artifact the score commits to
expected:     [ { id, kind, assert, rationale }, ... ]   # structural, pass/fail
provenance:   { seed, model_digest, tool_versions, notes }   # input pins; recorded, never asserted
render_manifest_spec: [ ... ]                    # what the performer stamps onto the rendered artifact
```

### `tuning` — first-class from v0 (a banked call option)

At v0 the only value is `12-TET`, but the field is mandatory now so that the 53-EDO and
just-intonation scores — this lane's actual moat — are a *value change in an existing field*,
not a schema revision later. Free to carry today; painful to retrofit. (Oliveros, 2026-06-25.)

- `system`: `12-TET` | `n-EDO` | `JI`
- `reference_hz`: pitch reference (e.g. 440)
- `scl`: path to a Scala `.scl` file, or `null` for plain equal temperament

### `generator`

- `repo`, `ref`: the source repo and a **pinned** commit/tag (never a moving branch)
- `entrypoint`: the exact command the performer runs
- `algorithm`: human-readable name (e.g. `polyphonic-markov-chain`)
- `params`: a map passed verbatim as CLI flags — must reference **real** flags
- `seed`: the integer that makes the run deterministic

> Verify-by-code applies to the handoff: a score may only reference generator flags that
> actually exist. The v0 generator (`generate_midi.py`) had **no seed flag and seeded
> neither `random` nor `numpy.random`** — caught by reading the source. Without determinism,
> `provenance.seed` is a lie and the `determinism` assertion is un-meetable.
>
> Rather than fork the generator (an unverified hand-edit to an existing repo, and not ours
> to force), determinism is pinned at the **process boundary** by `scores/seeded_run.py`: it
> seeds both global RNGs, then execs the **unmodified** generator via `runpy`. The score's
> `entrypoint` therefore calls the wrapper, not the generator directly. A first-class upstream
> `--seed` flag in `generate_midi.py` is the cleaner long-term fix for direct users and is
> recommended as a follow-up — but that's the generator repo owner's call.
>
> **Wrapper precondition (Oliveros review, 2026-06-25):** process-boundary seeding only works
> for generators that draw from the *global* `random` / `numpy.random` state. A generator that
> builds its own instance (`random.Random()`, `np.random.default_rng()`) would run past the
> wrapper **unseeded** while the score still claimed determinism. Before reusing this wrapper on
> a new generator, confirm it uses global RNG state — and note that the `determinism` assertion
> is the render-time net that catches a violation regardless (defense in depth).

### `target` — the artifact the score commits to

v0 commits to the **MIDI** the generator emits, not rendered audio. Audio rendering
(SuperCollider, a DAW, fluidsynth) is the performer's downstream step and is out of v0 scope.

- `kind`: `midi`
- `writer`: the library that serializes it (e.g. `pretty_midi`)
- `requires`: runtime + library versions the performer must match

### `expected` — structural assertions (pass/fail)

Each entry: `id`, `kind` (from the whitelist below), `assert` (machine-checkable statement),
`rationale` (why a failure means the renderer is broken).

Whitelisted `kind`s in v0:

| kind | meaning |
|---|---|
| `validity` | artifact parses as a well-formed file of `target.kind` |
| `scale_membership` | every pitch-class ∈ the tuning/key the score specified |
| `range` | every pitch within a declared inclusive bound |
| `tempo` | artifact tempo equals the requested `bpm` |
| `determinism` | identical inputs ⇒ identical note-event sequence |

New kinds are added only when a real render needs one — and only if they pass the litmus.

### `provenance` — the reproducibility spine (recorded, never asserted)

Pins the inputs that, together, reproduce a render. The performer also emits a
`render-manifest` sidecar next to the artifact on Drive, stamped with the actuals:

- `seed` (echoed from `generator.seed`)
- `model_digest`: sha256 of each generator model file (`*.pkl`) — **same seed + different
  models ⇒ different music**, so the models are part of the identity, not just the seed
- `tool_versions`: resolved Python + library versions at render time
- `score_commit_sha`: the commit of *this score file* that produced the artifact
- `artifact_backpointer`: Drive path/id of the render, linking audio → score

This is the chain that lets an ear-checked render be traced to the exact score that made it —
the prerequisite for promoting a render to the catalog source-of-truth.

## Failure posture

The SSH link from tambora to klaxon is a hard dependency for rendering. A score must fail
**loudly and unambiguously** — a dropped tunnel or a missing model file is a *render error*,
never silently "the composition is broken." Performers should surface the failing precondition,
not a degraded render.

## Lineage

Companion prose: `[[verifier-philosophy]]` (runtime-correctness vs authoring-trust — the
boundary this schema draws), `[[sagemath-docs]]` (the theory the generators draw on).
