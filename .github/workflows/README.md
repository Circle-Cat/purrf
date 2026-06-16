# CI & Release Process

GitHub is the single source of truth for this repo. CI and releases are driven
entirely by GitHub Actions.

## Branch model

```
feature PRs ──► main ──promote──► staging ──promote──► prod
                 │                  │                    │
                 │ accumulates,     │ merge = deploy:    │ merge = deploy:
                 │ deploys nothing  │ ArgoCD staging ns  │ ArgoCD prod ns
                 │                  │ CF Pages branch    │ CF Pages production
                 │                  │ alias              │
```

- `main` — integration branch. All development lands here first. Merging to
  `main` deploys **nothing**; it only accumulates release candidates.
- `staging` / `prod` — environment branches. ArgoCD (backend) and Cloudflare
  Pages (frontend) watch them directly, so **merging into them is the
  deployment**. Their content arrives exclusively via cherry-pick promotions
  (machine-enforced, see below); never push to them directly.

Because promotions are cherry-picks, `staging`/`prod` histories intentionally
diverge from `main`. "What is still unreleased" is computed by patch-id
(`git cherry origin/staging origin/main`), not by branch ancestry.

## Day-to-day development

1. Branch off `main`, open a PR to `main` titled `[PUR-123] Capitalized message`.
2. CI runs automatically:
   - **PR Title** (`pr-title.yml`) — validates the title format. It is the
     only workflow listening to the `edited` event, so fixing a title re-runs
     just this check, not the tests.
   - **Presubmit** (`presubmit.yml`):
     - `changes` — classifies the diff (backend / frontend / build files).
     - `lint-and-test` — lint always; backend tests
       (`//tests/backend_test/... //tests/tools_test/...`, against a Postgres
       service container) only when backend or build files changed; frontend
       tests (`//tests/frontend_test/...`) only when frontend or build files
       changed. Skipped entirely for changes outside Bazel-built code
       (`helm/`, `terraform/`, `script/`, docs).
3. Merge when green. Any merge method is fine on `main`.

Pushes to `main` re-run the full suite to backfill the Bazel disk/repository
caches that PR builds restore from.

## Releasing

Releases are a two-hop promotion:
`main → staging`, verify, then `staging → prod`.

### 1. Promote to staging

Run the **Promote** workflow (Actions tab → Promote → Run workflow):

- `target`: `staging`
- `commits`: empty to promote **everything** pending, or a space/comma-separated
  list of `main` SHAs for a **selective release** (e.g. ship 8 of 10 pending
  commits, leaving unfinished ones behind).

The workflow validates each SHA exists on the upstream branch, cherry-picks
them oldest-first with `-x` (which appends the
`(cherry picked from commit <sha>)` trailer) onto a `promote/staging-<run_id>`
branch, pushes it, and opens a PR listing every commit.

If a cherry-pick conflicts — typically because a skipped commit is a
dependency of a picked one — the run fails and names the offending SHA.
Either include the dependency in the pick list, or build the promotion branch
locally, resolve, and push.

On the promotion PR, CI runs:

- `promotion-guard` — verifies every non-merge commit carries a cherry-pick
  trailer pointing at a commit on `main`. This is what makes "staging content
  only comes from main" a machine guarantee.
- `lint-and-test` — a full re-validation. This is load-bearing for selective
  releases: the picked combination may never have existed on `main`.

Review and merge **with a merge commit** — never squash or rebase, which
rewrite SHAs and strip the trailers that the guard and the pending-commit
calculation depend on.

Merging deploys staging automatically (ArgoCD syncs the staging namespace;
Cloudflare Pages rebuilds the `staging` branch alias).

### 2. Verify on staging

Do acceptance testing on the staging environment. Fixes go through `main` as
normal PRs, then get promoted to staging (pick just the fix SHAs).

### 3. Promote to prod

Run **Promote** again with `target: prod`, normally with `commits` empty so
prod receives exactly what staging validated. Same flow; the guard now
verifies every commit originates from `staging` (trailers accumulate one hop
at a time — the guard checks the most recent one). Merging deploys prod.

## Invariants

- Every commit on `prod` traces to `staging`, and every commit on `staging`
  traces to `main` — enforced by `promotion-guard`, not by convention.
- Merging an environment branch **is** the deployment. There is no separate
  deploy step or button.
- The only manual actions in a release are: trigger Promote, review and merge
  the promotion PR.
