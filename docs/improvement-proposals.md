# Cluster Toolkit — Improvement Proposals (Safety, Stability, Performance)

> Generated from a static analysis of this repository on 2026-06-26.
> Each section below is written as a **ready-to-file GitHub issue**: copy the
> heading as the issue title, the suggested labels, and the body.
>
> Scope of the audit: the Go CLI (`cmd/`, `pkg/`), the Terraform modules
> (`modules/`, `community/modules/`), the Slurm-on-GCP runtime Python
> (`community/modules/scheduler/schedmd-slurm-gcp-v6-controller/.../scripts/`),
> and the CI/build/supply-chain configuration (`.github/`, `.pre-commit-config.yaml`,
> `Makefile`).

## How to read this

- **Severity** — `high` = data loss / security / silent failure on production
  paths; `med` = robustness, supply-chain hardening, or developer-facing
  correctness; `low` = polish / consistency.
- **Category** — `safety`, `stability`, `performance`, `supply-chain`.
- Line numbers reflect the state of the repository at audit time and may drift.
- Findings were validated against the source; where a claim is *latent*
  (correct today but fragile) rather than an *active* bug, this is called out
  explicitly so triage isn't misled.

## Summary

| # | Title | Severity | Category | Area |
|---|-------|----------|----------|------|
| 1 | Pin GitHub Actions to commit SHAs | high | supply-chain | CI |
| 2 | Replace `@main`-pinned third-party actions/workflows | high | supply-chain | CI |
| 3 | Add `github-actions` ecosystem to Dependabot | med | supply-chain | CI |
| 4 | Add least-privilege `permissions:` to all workflows | med | safety | CI |
| 5 | Harden `label-external.yml` (`pull_request_target` + injection) | med | safety | CI |
| 6 | Run Go unit tests with `-race` in CI | med | stability | CI |
| 7 | Add SAST (gosec + CodeQL) to CI | med | safety | CI |
| 8 | Generate SLSA provenance + SBOM for released binaries | med | supply-chain | Release |
| 9 | Replace user-reachable `panic`/`OrDie` with errors | med | safety | Go |
| 10 | Synchronize global module caches in `modulereader` | med | stability | Go |
| 11 | Synchronize `globalExpressions` map | med | stability | Go |
| 12 | Add timeouts / context cancellation to Terraform & Packer exec | med | stability | Go |
| 13 | Fix temp-file close + `io.Copy` error handling in `pkg/shell` | med | stability | Go |
| 14 | Remove O(n²) input lookup in `expand.useModule` | low | performance | Go |
| 15 | Stop silently discarding cache read/write errors | low | stability | Go |
| 16 | Add destroy safeguard to Spanner *instance* | high | safety | Terraform |
| 17 | Add destroy safeguard to Redis instance | high | safety | Terraform |
| 18 | Add destroy safeguard to managed-lustre instance | high | safety | Terraform |
| 19 | Add destroy safeguard to parallelstore instance | high | safety | Terraform |
| 20 | Validate `auth_enabled` vs `tier` in redis module | med | stability | Terraform |
| 21 | Add upper-bound validation to `filestore.size_gb` | med | stability | Terraform |
| 22 | Validate GKE node-pool autoscaling min/max | med | stability | Terraform |
| 23 | Reconsider/justify expensive default machine types | med | performance | Terraform |
| 24 | `cloud-storage-bucket` `force_destroy=true` default & docs | low | safety | Terraform |
| 25 | Replace 10 bare `except:` in Slurm runtime scripts | high | safety | Python |
| 26 | Remove `shell=True` string concatenation in Slurm scripts | med | safety | Python |
| 27 | Bound GCP API pagination in `resume.py` | med | stability | Python |
| 28 | Add outer timeout/iteration cap to operation polling | med | stability | Python |
| 29 | Cache repeated nodeset lookups in `conf.py` | med | performance | Python |
| 30 | Atomic writes + locked reads in `repair.py` op file | med | stability | Python |

---

## CI / Build / Supply chain

### Issue 1 — Pin GitHub Actions to full commit SHAs

**Labels:** `security`, `supply-chain`, `ci`
**Severity:** high · **Category:** supply-chain

**Problem.** Every workflow references third-party actions by mutable tag, e.g.
`actions/checkout@v6`, `actions/setup-python@v6`, `actions/setup-go@v6`,
`hashicorp/setup-terraform@v4`, `terraform-linters/setup-tflint@v6`,
`pre-commit/action@v3.0.1`, `actions/dependency-review-action@v4`. A tag is not
immutable — if an action's repo or a maintainer account is compromised, the tag
can be re-pointed at malicious code that then runs with the workflow's
`GITHUB_TOKEN`.

**Impact.** Supply-chain compromise of CI, including potential exfiltration of
the repo token and write access on `pull_request`-triggered jobs.

**Where.** All files in `.github/workflows/`.

**Proposed fix.**
- Pin every external action to a full 40-char commit SHA with a trailing
  `# vX.Y.Z` comment, e.g.
  `uses: actions/checkout@<sha> # v6.0.0`.
- Let Dependabot (`github-actions` ecosystem — see Issue 3) keep the SHAs
  current.

**Acceptance criteria.** No `uses:` line in `.github/workflows/` references a
floating tag or branch; CI still green.

---

### Issue 2 — Replace `@main`-pinned third-party actions and reusable workflows

**Labels:** `security`, `supply-chain`, `ci`
**Severity:** high · **Category:** supply-chain

**Problem.** Two references track an upstream **branch**, so their behavior can
change without any commit to this repo:
- `.github/workflows/pr-precommit.yml` — `uses: jlumbroso/free-disk-space@main`
  (twice, lines ~37 and ~74).
- `.github/workflows/multi-approvers.yml` — `uses: abcxyz/pkg/.github/workflows/multi-approvers.yml@main` (line ~43). This is the **approval-gate** workflow, so a silent upstream change directly affects merge governance.

**Impact.** Non-reproducible CI and a moving target for the approval policy;
worst case, an upstream change runs arbitrary code in CI.

**Proposed fix.** Pin both to a release tag or commit SHA. For the approval
workflow especially, pin to a SHA and bump deliberately.

**Acceptance criteria.** No `@main` (or other branch) refs remain in
`.github/workflows/`.

---

### Issue 3 — Add the `github-actions` ecosystem to Dependabot

**Labels:** `supply-chain`, `ci`, `dependencies`
**Severity:** med · **Category:** supply-chain

**Problem.** `.github/dependabot.yml` only configures `gomod` (root) and `pip`
(`/community/front-end/ofe/`). GitHub Actions versions are not tracked, which is
what makes SHA-pinning (Issue 1) sustainable. The Slurm runtime
`requirements.txt` and other `pip` manifests outside the OFE directory are also
unmonitored.

**Proposed fix.** Add at least:
```yaml
- package-ecosystem: github-actions
  directory: /
  schedule: { interval: weekly }
  target-branch: develop
```
and evaluate adding `pip` entries for the other Python requirement files.

**Acceptance criteria.** Dependabot opens PRs for outdated actions.

---

### Issue 4 — Add explicit least-privilege `permissions:` blocks to all workflows

**Labels:** `security`, `ci`
**Severity:** med · **Category:** safety

**Problem.** `pr-precommit.yml` and `pr-description-check.yml` declare no
top-level `permissions:`, so they inherit the repository/organization default
`GITHUB_TOKEN` scope, which is frequently broader than needed.
`label-external.yml` requests `actions: write` and `issues: write` for what is
fundamentally a PR-labeling job. (`dependency-review.yml` already does this
correctly with `permissions: { contents: read }` — use it as the template.)

**Proposed fix.** Add a minimal `permissions:` block to each workflow
(`contents: read` by default; widen per-job only where required, e.g.
`pull-requests: write` for the labeler).

**Acceptance criteria.** Every workflow declares an explicit `permissions:`
block scoped to what it actually uses.

---

### Issue 5 — Harden `label-external.yml` against `pull_request_target` script injection

**Labels:** `security`, `ci`
**Severity:** med · **Category:** safety

**Problem.** `label-external.yml` runs on `pull_request_target` (privileged
context) and interpolates attacker-influenced fields such as
`${{ github.event.pull_request.user.login }}` directly into `run:` shell steps.
Even with the existing `grep -qx` guard, interpolating event data into a shell
line is the canonical script-injection pattern.

**Proposed fix.** Pass event fields through `env:` variables (which are not
re-evaluated by the shell) instead of inlining `${{ … }}` into `run:`; keep the
job's `permissions:` minimal (see Issue 4); avoid checking out PR head code in
the privileged job.

**Acceptance criteria.** No `${{ github.event.* }}` value is interpolated
directly into a `run:` block; values arrive via `env:`.

---

### Issue 6 — Run Go unit tests with the race detector in CI

**Labels:** `stability`, `ci`, `go`
**Severity:** med · **Category:** stability

**Problem.** Neither the `Makefile` test targets nor the pre-commit
`go-unit-tests` hook pass `-race`. Given the project uses goroutines and global
caches (see Issues 10 and 11), data races can land undetected.

**Proposed fix.** Add a CI step / make target that runs `go test -race ./...`
(it can be a separate job to keep runtime acceptable).

**Acceptance criteria.** A required check runs the suite with `-race`.

---

### Issue 7 — Add static application security testing (gosec + CodeQL)

**Labels:** `security`, `ci`
**Severity:** med · **Category:** safety

**Problem.** CI runs `golangci-lint`, `tflint`, `yamllint`, etc. via pre-commit,
plus `dependency-review` (which is additionally gated to the upstream repo via
`if: github.repository == 'GoogleCloudPlatform/cluster-toolkit'`), but there is
no dedicated SAST scanning of the Go/Python source for security issues (command
injection, weak crypto, tainted exec, etc.).

**Proposed fix.** Add a CodeQL workflow (Go + Python) and/or a `gosec` step.
Start in non-blocking mode, then promote to a required check.

**Acceptance criteria.** SAST results appear in the Security tab / PR checks.

---

### Issue 8 — Generate SLSA provenance and an SBOM for released binaries

**Labels:** `supply-chain`, `release`
**Severity:** med · **Category:** supply-chain

**Problem.** Released `gcluster` bundles (per README) ship without verifiable
build provenance, an SBOM, or signatures, so downstream consumers cannot verify
how/where a binary was built.

**Proposed fix.** Adopt the SLSA Go builder for tagged releases and attach an
SBOM (e.g. `syft`) + signed checksums to release assets.

**Acceptance criteria.** Release assets include provenance, an SBOM, and a
documented verification command.

---

## Go CLI (`gcluster`)

### Issue 9 — Replace user-reachable `panic` / `…OrDie` paths with returned errors

**Labels:** `stability`, `go`, `ux`
**Severity:** med · **Category:** safety

**Problem.** Several code paths `panic` (often with a “should never happen”
comment) on conditions that depend on blueprint/module state rather than pure
program invariants. A panic prints a Go stack trace instead of a clean,
actionable CLI error. Representative sites:
- `pkg/config/expand.go:327` — `applyUseModules` panics if `bp.Module(u)` fails.
- `pkg/config/config.go` — `Module.InfoOrDie()` (~L286) and
  `ModuleGroupOrDie()` (~L178).
- `pkg/config/expression.go` — `MustParseExpression()` (~L214).
- `pkg/shell/terraform.go:327` — `panic("Unknown output format requested")`.

**Impact.** A malformed/edge-case blueprint or corrupted intermediate state
crashes the CLI ungracefully rather than reporting a diagnosable error.

**Proposed fix.** Audit each `panic`/`*OrDie` on a user-input-dependent path and
convert to an `error` return wrapped with context
(`fmt.Errorf("...: %w", err)`). Reserve panics for genuine invariants only.

**Acceptance criteria.** No `panic` reachable from blueprint parsing/expansion;
malformed input yields a non-zero exit with a readable message.

---

### Issue 10 — Synchronize the global module caches in `modulereader`

**Labels:** `stability`, `go`, `concurrency`
**Severity:** med · **Category:** stability

**Problem.** `pkg/modulereader/resreader.go` keeps package-global maps
`modInfoCache` (L121) and `modDownloadCache` (L122) that are read and written by
`GetModuleInfo` without any lock. Today all callers appear to be serial, so this
is *latent* rather than an active race — but it is a footgun the moment any
concurrent module read is introduced (and `-race`, Issue 6, would then flag it).

**Proposed fix.** Guard both maps with a `sync.RWMutex` (or use `sync.Map`).
Keep the change small and behavior-preserving.

**Acceptance criteria.** Cache access is synchronized; `go test -race` clean.

---

### Issue 11 — Synchronize the `globalExpressions` map

**Labels:** `stability`, `go`, `concurrency`
**Severity:** med · **Category:** stability

**Problem.** `pkg/config/expression.go` uses a package-global
`globalExpressions` map accessed without synchronization (~L309–311). Same
latent-race rationale as Issue 10.

**Proposed fix.** Protect with a mutex, or restructure so the map is not global
mutable state.

**Acceptance criteria.** No unsynchronized access; `-race` clean.

---

### Issue 12 — Add timeouts / context cancellation to Terraform & Packer execution

**Labels:** `stability`, `go`
**Severity:** med · **Category:** stability

**Problem.** `pkg/shell/terraform.go` drives terraform via `context.Background()`
with no timeout or signal-based cancellation (multiple call sites, e.g. Init /
Plan / Apply). If terraform blocks (e.g. waiting on stdin), `gcluster` hangs
indefinitely with no way to interrupt cleanly.

**Proposed fix.** Thread a cancellable context (wired to SIGINT/SIGTERM) through
the exec wrappers, with an optional configurable timeout. Mirror the good
pattern already used in `config.go`'s GitHub-fetch worker
(`context.WithTimeout`).

**Acceptance criteria.** Long-running exec calls honor Ctrl-C and an optional
timeout.

---

### Issue 13 — Fix temp-file close and `io.Copy` error handling in `pkg/shell`

**Labels:** `stability`, `go`, `resource-leak`
**Severity:** med · **Category:** stability

**Problem.** Two related issues:
- `pkg/shell/terraform.go` (~L295) creates a temp file via `os.CreateTemp` and
  defers `os.Remove`, but never `Close()`s the handle.
- `pkg/shell/packer.go` (~L70–77) copies stdout/stderr in goroutines and
  discards the `io.Copy` error, so a failed copy (e.g. disk full) is silent.

**Proposed fix.** Add `defer f.Close()` before the `defer os.Remove`; capture
and surface (or at least log) `io.Copy` errors from the streaming goroutines.

**Acceptance criteria.** No open temp handle at remove time; copy errors are not
silently dropped.

---

### Issue 14 — Remove O(n²) input lookup in `expand.useModule`

**Labels:** `performance`, `go`
**Severity:** low · **Category:** performance

**Problem.** `pkg/config/expand.go` (`useModule`, ~L286–294) iterates a module's
outputs and, for each, linearly scans the input list. For modules with many
inputs/outputs this is quadratic.

**Proposed fix.** Build a `map[string]struct{}` of input names once and do O(1)
membership checks.

**Acceptance criteria.** Lookup is linear; behavior unchanged (add/extend a unit
test).

---

### Issue 15 — Stop silently discarding cache read/write errors

**Labels:** `stability`, `go`
**Severity:** low · **Category:** stability

**Problem.** In `pkg/config/config.go` (~L1027–1043) the blueprint-name cache
read/write ignores errors (`os.WriteFile` result discarded; corrupt cache falls
through silently). A corrupted or unwritable cache becomes a confusing failure
later instead of a clear log line.

**Proposed fix.** Log (at warn/debug) on cache read corruption and write
failure; keep the graceful fallback.

**Acceptance criteria.** Cache failures are observable in logs.

---

## Terraform modules

> **Common note for Issues 16–19.** The `filestore` module already exposes a
> `deletion_protection` object and is the pattern to follow. For resources whose
> provider exposes a native `deletion_protection` argument, wire it to a
> module variable (default protective). Where the provider has no native flag,
> add a `lifecycle { prevent_destroy = true }` guard (gated so users can opt
> out), and/or document the persistence/backup story. Pick the mechanism per
> resource based on provider support.

### Issue 16 — Add a destroy safeguard to the Spanner *instance*

**Labels:** `safety`, `terraform`, `data-loss`
**Severity:** high · **Category:** safety

**Problem.** `modules/database/spanner` protects each **database**
(`deletion_protection = optional(bool, true)` in `variables.tf:61`, applied at
`main.tf:33`), but the **`google_spanner_instance`** itself has no guard.
Destroying the instance takes every database with it regardless of the
per-database setting.

**Proposed fix.** Add an instance-level `deletion_protection`/`prevent_destroy`
guard (default protective) exposed via a variable.

**Acceptance criteria.** `terraform destroy` on a default deployment refuses to
delete the instance without an explicit opt-out.

---

### Issue 17 — Add a destroy safeguard to the Redis instance

**Labels:** `safety`, `terraform`, `data-loss`
**Severity:** high · **Category:** safety

**Problem.** `modules/database/redis/main.tf` (`google_redis_instance.default`,
~L29) has no deletion/destroy protection. Redis instances are stateful and a
mistaken `destroy` is unrecoverable.

**Proposed fix.** Add a `lifecycle { prevent_destroy }`-style guard wired to a
variable (default protective). Confirm whether the installed provider version
exposes a native flag; if not, use `prevent_destroy` plus a documented backup
recommendation.

**Acceptance criteria.** Default deployment is protected from accidental
destroy.

---

### Issue 18 — Add a destroy safeguard to the managed-lustre instance

**Labels:** `safety`, `terraform`, `data-loss`
**Severity:** high · **Category:** safety

**Problem.** `modules/file-system/managed-lustre/main.tf`
(`google_lustre_instance`, ~L61) has no destroy protection. These are large,
expensive, persistent filesystems backing live workloads.

**Proposed fix.** Same approach as Issue 16/17, defaulting to protected.

**Acceptance criteria.** Default deployment is protected.

---

### Issue 19 — Add a destroy safeguard to the parallelstore instance

**Labels:** `safety`, `terraform`, `data-loss`
**Severity:** high · **Category:** safety

**Problem.** `modules/file-system/parallelstore/main.tf`
(`google_parallelstore_instance`, ~L53) has no destroy protection.

**Proposed fix.** Same approach as Issue 16/17, defaulting to protected;
document any import/export-before-destroy workflow.

**Acceptance criteria.** Default deployment is protected.

---

### Issue 20 — Validate `auth_enabled` against `tier` in the redis module

**Labels:** `stability`, `terraform`, `validation`
**Severity:** med · **Category:** stability

**Problem.** `modules/database/redis` accepts `auth_enabled` and `tier`
independently. Invalid combinations surface only at `apply` time (late failure)
rather than at `plan`/validate.

**Proposed fix.** Add a `validation` block expressing the supported
combinations, with a clear error message.

**Acceptance criteria.** Invalid combos fail at `validate`/`plan`.

---

### Issue 21 — Add an upper-bound validation to `filestore.size_gb`

**Labels:** `stability`, `terraform`, `validation`
**Severity:** med · **Category:** stability

**Problem.** `modules/file-system/filestore/variables.tf` validates a lower
bound on `size_gb` but no maximum, so a typo (e.g. an extra digit) fails late in
`apply` after provisioning attempts.

**Proposed fix.** Add a max-bound `validation` consistent with the service tier
limits, with a message pointing at the relevant range.

**Acceptance criteria.** Out-of-range sizes fail at `validate`/`plan`.

---

### Issue 22 — Validate GKE node-pool autoscaling min/max

**Labels:** `stability`, `terraform`, `validation`
**Severity:** med · **Category:** stability

**Problem.** `modules/compute/gke-node-pool/variables.tf` allows
`autoscaling_total_max_nodes` without a `validation` ensuring
`max >= min` and `> 0` (a `precondition` in `main.tf` catches some cases later).

**Proposed fix.** Add a `validation` block so nonsensical bounds fail early.

**Acceptance criteria.** `max < min` or non-positive values fail at
`validate`/`plan`.

---

### Issue 23 — Reconsider or justify expensive default machine types

**Labels:** `performance`, `cost`, `terraform`
**Severity:** med · **Category:** performance

**Problem.** Compute modules default to large machines (e.g.
`c2-standard-60` in `modules/compute/vm-instance/variables.tf` and
`gke-node-pool/variables.tf`). Users who deploy with defaults incur high cost
without an explicit choice.

**Proposed fix.** Either lower the default to a modest size, or keep it and add
a variable `description` that states the cost implication and when the large
default is appropriate. (Prefer documentation over silently changing behavior if
backwards-compatibility matters.)

**Acceptance criteria.** Cost implication of the default is explicit to the
user.

---

### Issue 24 — `cloud-storage-bucket` `force_destroy=true` default and description

**Labels:** `safety`, `terraform`
**Severity:** low · **Category:** safety

**Problem.** `modules/file-system/cloud-storage-bucket` defaults
`force_destroy = true`, which lets `terraform destroy` delete a bucket and all
objects. The variable description does not warn about data loss.

**Proposed fix.** At minimum, update the description to warn explicitly;
consider defaulting to `false` with explicit opt-in for destructive behavior.

**Acceptance criteria.** Users are warned (and ideally must opt in) before
data-destroying behavior.

---

## Slurm-on-GCP runtime Python

> These scripts run on live controllers and scale to thousands of nodes, so
> silent failures and unbounded operations have outsized impact. Path prefix:
> `community/modules/scheduler/schedmd-slurm-gcp-v6-controller/modules/slurm_files/scripts/`.

### Issue 25 — Replace bare `except:` blocks in the Slurm runtime scripts

**Labels:** `safety`, `stability`, `python`
**Severity:** high · **Category:** safety

**Problem.** There are **10** bare `except:` clauses across the runtime scripts:
`file_cache.py:78`, `local_pubsub.py:127`, `resume.py:570`, `slurmsync.py:665`,
`slurmsync.py:680`, `util.py:400`, `util.py:581`, `util.py:1920`,
`util.py:2313`, `watch_delete_vm_op.py:83`. A bare `except:` also swallows
`KeyboardInterrupt`/`SystemExit` and masks real errors (config problems, API
failures) as benign.

**Proposed fix.** Replace each with the narrowest applicable exception type and
log the caught exception with context. Where a fallback is intended (e.g.
`file_cache.py` → NoCache), catch `(OSError, …)` specifically and log the cause.

**Acceptance criteria.** No bare `except:` remains; each handler logs what it
caught. (mypy/lint clean.)

---

### Issue 26 — Remove `shell=True` string concatenation in Slurm scripts

**Labels:** `safety`, `python`
**Severity:** med · **Category:** safety

**Problem.** Several calls build shell command strings dynamically, notably
`setup.py:216` —
`run("dd if=/dev/urandom bs=32 count=1 > " + str(jwt_key), shell=True)` — and
`slurmsync.py:204` / `util.py:1894`, which use `shell=True` with interpolated
values. Even where inputs are currently internal, this is a fragile pattern that
becomes an injection vector if any interpolated value ever derives from external
config.

**Proposed fix.** Prefer the list form of `subprocess` (no shell); where a shell
is genuinely required, wrap interpolated values in `shlex.quote(...)`. The
`dd > file` case can be done with `subprocess` redirecting to an opened file
handle rather than a shell redirect.

**Acceptance criteria.** No `shell=True` call concatenates/interpolates an
unquoted dynamic value.

---

### Issue 27 — Bound GCP API pagination in `resume.py`

**Labels:** `stability`, `performance`, `python`
**Severity:** med · **Category:** stability

**Problem.** `resume.py` `_get_failed_zonal_instance_inserts()` (~L376–392)
pages through *all* matching insert operations with no `maxResults` and no early
termination. On long-lived projects with large operation histories this risks
slow calls and excessive memory.

**Proposed fix.** Set `maxResults`, and stop paging once enough matching
operations are found.

**Acceptance criteria.** Lookup is bounded in time/memory regardless of
operation history size.

---

### Issue 28 — Add an outer timeout / iteration cap to operation polling

**Labels:** `stability`, `python`
**Severity:** med · **Category:** stability

**Problem.** `util.py` `wait_for_operation()` (~L1525) loops on
`ensure_execute(wait_req)` with no overall deadline or iteration cap. If an
operation never reports terminal status or the API is flaky, the poll loop can
hang. `repair.py` `poll_operations()` similarly treats a `None` status as
“retry forever” without a failure budget.

**Proposed fix.** Add an absolute timeout and max-iteration cap to
`wait_for_operation()`; in `repair.py`, track consecutive failures per operation
with a bounded retry/backoff.

**Acceptance criteria.** Polling cannot hang unbounded; a stuck operation is
surfaced and abandoned with a logged error after the cap.

---

### Issue 29 — Cache repeated nodeset lookups in `conf.py`

**Labels:** `performance`, `python`
**Severity:** med · **Category:** performance

**Problem.** `conf.py` (~L764) iterates `lkp.instances().values()` and calls
`lkp.node_nodeset_name(inst.name)` per instance, re-parsing node names for every
instance. At thousands of nodes this is avoidable repeated work on a hot path.

**Proposed fix.** Memoize nodeset resolution (e.g. by node prefix) or compute it
once per distinct nodeset.

**Acceptance criteria.** Per-instance redundant parsing eliminated; output
unchanged.

---

### Issue 30 — Atomic writes and locked reads for the `repair.py` operations file

**Labels:** `stability`, `python`, `concurrency`
**Severity:** med · **Category:** stability

**Problem.** `repair.py` (~L45–65) locks the operations file for writes but
`_get_operations()` reads it without a lock, so a read can observe a partially
written file. Writes are also not atomic.

**Proposed fix.** Acquire the lock for reads as well, and write via
temp-file-plus-`os.rename` for atomicity.

**Acceptance criteria.** No reader can observe a torn write; concurrent
controller processes stay consistent.

---

## Appendix — Verification notes

- **pre-commit *is* a CI gate.** `pr-precommit.yml` runs `pre-commit/action`
  with `--all-files`, so `golangci-lint`, `tflint`, `go-unit-tests`, `yamllint`,
  `mypy`, `shellcheck`, etc. all run on every PR. `git commit --no-verify` only
  skips *local* hooks, not CI. The CI gaps are therefore specifically the
  *missing* checks: `-race` (Issue 6) and SAST (Issue 7) — not "pre-commit can
  be skipped."
- **`dependency-review.yml` exists** and runs on `pull_request`, but is gated to
  the upstream repo (`if: github.repository == 'GoogleCloudPlatform/cluster-toolkit'`),
  so it does not run on forks.
- **Cache races (Issues 10/11) are latent, not active.** Current callers are
  serial; the worker pool in `config.go` does HTTP fetches only and does not
  touch the module caches. The recommendation is defensive hardening, reinforced
  by enabling `-race`.
