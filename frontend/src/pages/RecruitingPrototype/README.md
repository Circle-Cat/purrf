# Recruiting v2 Prototype

A self-contained, **mock-data** prototype of the Recruiting v2 design, built for
stakeholder demos. No backend, no auth, no env vars — everything renders from
[`mockData.js`](./mockData.js).

> ⚠️ This is a **demo prototype**, not the real implementation. The production
> recruiting feature ships separately via its own slices/PRs.

## 🔗 Live demo

**https://circle-cat.github.io/purrf/**

Open it in a browser — nothing to install. (Public repo → the page is publicly
visible on the internet. It only contains mock data.)

## What's in it

A left sidebar navigates four sections:

| Section | Component | What it shows |
|---|---|---|
| Screening Board | `ScreeningBoardPrototype.jsx` | Swimlane board with Hired/Rejected terminal lanes; detail drawer with Advance / Reject / Blacklist |
| Apply Form | `ApplyPrototype.jsx` | Candidate apply shell: Personal / Profile / Details |
| Create Posting | `JobModalPrototype.jsx` | Posting editor with templates, per-field required toggles, and a full preview |
| Blacklist | `BlacklistPrototype.jsx` | Org-wide blacklist page |

The form builder (`vendor/FormBuilder.jsx`, `JsonSchemaForm.jsx`,
`formBuilderUtils.js`) is vendored in so the prototype only depends on the shared
`@/components/ui/*` primitives plus `react` and `lucide-react`.

## Run locally

Inside the full app — route `/recruiting/prototype` (no auth gate):

```bash
bazel run //frontend:dev_server     # or: ibazel run //frontend:dev_server
# open http://localhost:5173/recruiting/prototype
```

Or build/preview just the standalone static bundle (what GitHub Pages serves):

```bash
# node 18 locally needs a pinned pnpm:
corepack prepare pnpm@10.27.0 --activate
corepack pnpm install --frozen-lockfile
corepack pnpm exec vite build   --config frontend/vite.config.pages.mjs
corepack pnpm exec vite preview --config frontend/vite.config.pages.mjs
```

## How the GitHub Pages deploy works

Pushing to the `recruiting-v2-prototype-standalone` branch triggers
[`.github/workflows/deploy-pages.yml`](../../../../.github/workflows/deploy-pages.yml):
pnpm install → `vite build` → rename `prototype.html` → `index.html` →
`actions/deploy-pages`. Manual trigger:

```bash
gh workflow run deploy-pages.yml --ref recruiting-v2-prototype-standalone
```

Files involved:

- `frontend/src/prototype-main.jsx` — bare entry, mounts only `<RecruitingPrototype/>` (no Auth0/LaunchDarkly/router)
- `frontend/prototype.html` — entry document
- `frontend/vite.config.pages.mjs` — `base: "./"` (relative paths for the `/purrf/` subpath), outputs to `dist-pages/` (kept out of the Bazel build graph)
- `.github/workflows/deploy-pages.yml` — build + deploy

### One-time repo setup (already done)

These were configured once and don't need redoing for normal updates:

1. **Settings → Pages → Source = "GitHub Actions"**
   (or `gh api -X POST repos/Circle-Cat/purrf/pages -f build_type=workflow`).
2. **Allow this branch in the `github-pages` environment** — the default branch
   policy only permits the default branch, so deploys from this branch are
   otherwise rejected with *"not allowed to deploy … due to environment
   protection rules"*:
   ```bash
   gh api -X POST repos/Circle-Cat/purrf/environments/github-pages/deployment-branch-policies \
     -f name='recruiting-v2-prototype-standalone'
   ```
