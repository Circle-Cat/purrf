# Contributing to Purrf

How a change gets from a ticket to a merged PR. To set up and run the project,
see the [README](README.md).

## Workflow

1. Every change has a Jira ticket in the `PUR` project.
2. Branch from an up-to-date `origin/main`:
   ```bash
   git fetch origin main
   git switch -c <branch> origin/main
   ```
3. Before pushing, rebase onto the latest `main` and run the checks below
   again on the rebased tree:
   ```bash
   git fetch origin main
   git rebase origin/main
   ```
4. Open the PR against `main`. Every PR needs an approval from
   `@Circle-Cat/purrf-maintainers` (see `.github/CODEOWNERS`).

## Pull requests

### Title

CI (`.github/workflows/pr-title.yml`) fails a PR whose title does not match:

```
^\[[a-zA-Z]*-[0-9]*\] [A-Z][a-zA-Z0-9_. -]*$
```

That is the ticket in brackets, one space, then a message starting with a
capital letter, for example `[PUR-828] Ignore whitespace around the account
search text`. The message may contain only letters, digits, spaces and
`_ . -`: commas, colons, slashes and parentheses fail the check.

### Description

Say what changed and why, and how you checked it: the tests you added, and
anything you could not test.

### Size

Keep PRs small enough to review:

- Split by layer: frontend, backend and Terraform each go in their own PR.
  When one depends on another, say in both descriptions which merges first.
- Keep adding and removing apart: a PR either adds the new code, with the old
  code left working beside it, or removes the old code.

## Before pushing

Fix what can be fixed automatically, including formatting:

```bash
bash lint.sh --fix all_files
```

Then check that nothing is left. ESLint errors are not fixed by `--fix`, and CI
fails on them; the summary line has to say `0 failed`:

```bash
bash lint.sh all_files
```

If `lint.sh` fails with checksum verification errors (e.g. "sha256sum: command
not found"), install **jq**.

Run the tests:

```bash
bazel test //...
```

Tests under `tests/backend_test/repository_test` and the other database-backed
tests need a database. Bazel does not pass your shell's environment into
tests, so forward the URL explicitly:

```bash
bazel test //... --test_env=DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@HOST/DATABASE?ssl=require
```

For frontend changes, also build the production bundle and preview it, so
what you checked behaves as it will in production, not just in the dev
server:

```bash
bazel build //frontend:dist
bazel run //frontend:vite_preview
```

## Tests

- Every change comes with tests.
- A Python test file must end with:
  ```python
  if __name__ == "__main__":
      unittest.main()
  ```
  Without it the file runs no tests, and Bazel still reports `PASSED`.
- A new test should fail without the change it covers. Check that once by
  reverting the change locally.

## Database Migrations

Use Alembic migrations to apply schema changes to an existing database **without dropping data**. Migration scripts live in `alembic_setup/versions/` and must be committed alongside the model changes that require them.

### Workflow

**1. Modify your SQLAlchemy model**, then generate a migration. Do not write
migration scripts by hand: generating one from the models is what keeps the
two in step.
```bash
bazel run //tools/migrate_db:make_migration -- "describe your change"
```
This connects to the database, compares the current schema against your models, and writes a new migration script to `alembic_setup/versions/`.

**2. Review the generated file** in `alembic_setup/versions/`. Pay attention to:
- `NOT NULL` columns added to tables with existing data — add `server_default` manually if needed.
- `DROP COLUMN` / `DROP TABLE` statements — confirm they are intentional.

**3. Apply the migration:**

For a local database:
```bash
bazel run //tools/migrate_db:migrate_db
```

Deployed environments (test, staging, prod) do not run this by hand: an ArgoCD
PreSync hook Job runs `alembic upgrade head` from the `purrf-migrate` image
before each Deployment rolls out, so a merged migration lands automatically on
the next sync.

### Enum value changes (PostgreSQL)

`alembic-postgresql-enum` is configured to auto-detect enum changes. Adding a value is detected automatically. Removing a value generates a multi-step migration (rename → recreate → update columns → drop old type) — always test on a non-production database first.

### Summary

| Scenario | Command |
|---|---|
| First-time setup / reset dev database | `bazel run //tools:init_db` |
| Schema changed, generate migration | `bazel run //tools/migrate_db:make_migration -- "description"` |
| Apply migrations to a local database | `bazel run //tools/migrate_db:migrate_db` |
| Deploy schema changes (test/staging/prod) | Automatic: ArgoCD PreSync hook Job, on sync |

## Code conventions

### Backend

- Controllers stay thin: they read the request, open the session, call a
  service and map its result to a response. Business rules and commits belong
  in the service.
- Classes built by `AppDependencyBuilder` take their `logger` through the
  constructor.
- A new environment variable goes in `backend/common/environment_constants.py`
  and in `.env.example`, commented out with what it is for when it is
  optional.

### Frontend

- Exported functions, hooks and components have a JSDoc block and a unit
  test.
- User-facing text is in English.
