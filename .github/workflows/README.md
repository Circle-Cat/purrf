# CI & Release Process

GitHub is the single source of truth for this repo. CI and releases are driven
entirely by GitHub Actions.

## Branch model

```
feature PRs ─► main ─promote─► staging ─promote(by tag)─► prod
                │                │                          │
                │ deploys TEST   │ merge = deploy staging:  │ merge = deploy prod:
                │ (deploy-test)  │ ArgoCD staging ns        │ ArgoCD prod ns
                │                │ CF Pages staging alias   │ CF Pages production
```

- `main` — integration branch. All development lands here first (**squash**
  merge). Merging to `main` deploys the **test** environment (`deploy-test.yml`)
  and otherwise accumulates release candidates for staging/prod.
- `staging` / `prod` — environment branches. ArgoCD (backend) and Cloudflare
  Pages (frontend) watch them directly, so **merging into them is the
  deployment**. Their content arrives exclusively via cherry-pick promotions
  (machine-enforced by `promotion-guard`), except each branch's own
  `values-<env>.yaml` image pin; never push to them directly.

Because promotions are cherry-picks, `staging`/`prod` histories intentionally
diverge from `main`. "What is still unreleased" is computed by patch-id
(`git cherry origin/staging origin/main`), not by branch ancestry.

## Access control

- **`main` PRs** need **2 approvals, at least one from `@Circle-Cat/purrf-maintainers`**
  (CODEOWNERS + ruleset code-owner review).
- **Promote** (`promote.yml`) can only be run by members of
  `purrf-maintainers` — an authorize step checks the triggering actor's team
  membership and fails the run otherwise.

## Day-to-day development

1. Branch off `main`, open a PR to `main` titled `[PUR-123] Capitalized message`.
2. CI runs automatically:
   - **PR Title** (`pr-title.yml`) — validates the title format.
   - **Presubmit** (`presubmit.yml`): `changes` classifies the diff;
     `lint-and-test` lints always, runs backend tests
     (`//tests/backend_test/... //tests/tools_test/...` against a Postgres
     service) when backend/build files changed, and frontend tests
     (`//tests/frontend_test/...`) when frontend/build files changed. Skipped
     for changes outside Bazel-built code (`helm/`, `terraform/`, `script/`, docs).
3. Merge when green (squash).

Pushes to `main` re-run the full suite to backfill the Bazel caches.

## Deploy mechanism: images & frontend

**Backend** ships as a container image, built **from the branch being
deployed** — not built once on `main`. Promotions are selective, so
`staging`/`prod` trees are subsets of `main`; an image built from `main` would
contain un-promoted code.

- `main` → `deploy-test.yml` builds the image and commits the tag into
  `values-test.yaml` on `main` (app token, `main` ruleset bypass) → ArgoCD test.
- `staging` → `deploy-staging.yml` builds from `staging` and opens a **PR**
  pinning `values-staging.yaml` (no bypass; a maintainer merges) → ArgoCD staging.
- `prod` does **not** build — it **reuses the exact image tested on staging**
  (the prod promotion pins `values-prod.yaml` to that same tag). So the prod
  backend binary is byte-identical to what was validated.

**Frontend** is built by Cloudflare Pages directly from the branch code (no
image). It rides the same promotion gating — only cherry-picked frontend code
reaches `staging`/`prod`. Note: prod's frontend is *rebuilt* from the prod
branch (same source as the release tag → functionally equal, not byte-identical
to staging's build).

## Releasing

### 1. Promote to staging

Run **Promote** (Actions → Promote → Run workflow):

- `target`: `staging`
- `commits`: a space/comma-separated list of `main` SHAs for a **selective
  release**, or empty to promote everything pending.

It cherry-picks the code oldest-first with `-x` (appending the
`(cherry picked from commit <sha>)` trailer) onto `promote/staging-<run_id>`,
**skipping env image-pin commits** (a commit touching only some
`values-*.yaml`), and opens a PR. On the PR, `promotion-guard` (every code
commit has a trailer tracing to `main`) and `lint-and-test` run. Review and
merge **with a merge commit** — never squash/rebase (that strips the trailers
the guard depends on).

Merging triggers `deploy-staging.yml`: it builds the image from `staging` and
opens a `values-staging.yaml` pin PR. **Review and merge that pin PR too**;
ArgoCD then syncs the backend. The frontend rebuilds from the `staging` branch.

### 2. Verify on staging

Acceptance-test on staging. Fixes go through `main` as normal PRs, then promote
just the fix SHAs to staging.

### 3. Tag the validated point

When a batch passes, tag the exact staging commit you validated — i.e. the one
whose `values-staging.yaml` holds the tested image (the commit **after** its
image-pin PR merged, which is what ArgoCD deployed):

```bash
git fetch origin
# tag the current validated staging tip (or pass a specific SHA you tested):
git tag -a release/2026.06.16 origin/staging -m "Release: <summary of what's in it>"
git push origin release/2026.06.16
```

Convention: `release/<date-or-version>`. The tag is **immutable**, so staging
can move on to newer batches without affecting this release — the prod
promotion anchors everything to the tag.

### 4. Promote to prod

Run **Promote** with:

- `target`: `prod`
- `release_tag`: the tag from step 3 (e.g. `release/2026.06.16`)

It cherry-picks the code **up to the tag** (skipping staging's env-pin commits),
reads the tested image tag from `values-staging.yaml@<tag>`, and pins
`values-prod.yaml` to it — all in one PR. `promotion-guard` + `lint-and-test` +
maintainer review, then merge with a **merge commit**. ArgoCD prod pulls the
exact staging-tested image; the frontend rebuilds from the `prod` branch.

## Invariants

- Every commit on `prod` traces to `staging`, and every commit on `staging`
  traces to `main` — enforced by `promotion-guard`, except each branch's own
  `values-<env>.yaml` image pin.
- Merging an environment branch **is** the deployment. No separate deploy step.
- Only `purrf-maintainers` can promote.
- `prod` runs the **exact** backend image validated on `staging` (reuse, no
  rebuild). The frontend is rebuilt from the same source.
- The manual actions in a release are: trigger Promote to staging, merge the
  staging promotion + pin PRs, validate and `release/...`-tag, trigger Promote
  to prod, merge the prod PR.
