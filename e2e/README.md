# End-to-end regression suite

Playwright tests that click through a deployed Purrf as real accounts. They run
by hand against test (or, read-only, staging) after a deploy; they are not part
of CI or `bazel test`.

## Accounts

Three dedicated accounts on personal addresses (not `@circlecat.org`, which
would get the employee permission bundle on first login), plus an account holding
`permission.manage` (any admin who can grant permissions; it need not be a
super admin) that only tops up their permissions:

| Token file               | Account      | Holds                                         |
| ------------------------ | ------------ | --------------------------------------------- |
| `.tokens/superadmin.txt` | super admin  | used by the pre-run check only                |
| `.tokens/admin.txt`      | e2e-admin    | every admin permission except approving       |
| `.tokens/reviewer.txt`   | e2e-reviewer | `mentorship.admin.read`, `mentorship.approve` |
| `.tokens/member.txt`     | e2e-member   | nothing                                       |

The exact lists live in `lib/accounts.js`. A missing token skips the tests
that need that account.

## Settings file

Copy `e2e.local.example.json` to `e2e.local.json` (gitignored) and fill it in:
the four tokens, the test database URL (needed for the write tests), and the
flags you set in LaunchDarkly (optional). Empty values count as not given.
The per-file forms below (`.tokens/<role>.txt`, `E2E_DATABASE_URL`,
`.flags.json`, `E2E_FLAGS`) still work.

## Getting a token

Log in to the environment in a browser, open DevTools → Application → Cookies,
and copy the value of `CF_Authorization`. It is good for 24 hours.

```sh
printf '%s' '<value>' > e2e/.tokens/admin.txt
```

## Running

```sh
cd e2e
npm ci
npx playwright install chromium
npx playwright test                     # test, everything
E2E_ENV=staging npx playwright test     # staging, @smoke only
npx playwright test --grep @smoke       # just the read-only pass
npx playwright show-report              # screenshots and traces of failures
```

Before any test, `global-setup.js` checks every token, grants missing
permissions with the super admin's token, refuses accounts that are super
admins or company addresses, and refuses to run unless the page shows the
banner of the chosen environment. Set `E2E_ANY_ACCOUNT=1` to skip the account
checks when trying the suite with your own login.

## Seeding the write tests

The `@mentorship` tests write, so they only run on test and only after global
setup has seeded fake people (user ids from 990001, addresses
`@e2e.purrf.test`) into the round in progress. That needs `psql` on the
machine, the admin and member tokens, and the test database's URL:

```sh
printf '%s' 'postgresql://…' > e2e/.tokens/database-url.txt   # or export E2E_DATABASE_URL; the backend's asyncpg form works too
```

Setup cleans up leftovers, seeds, and writes `.state/seed.json`; teardown
removes the seeded people and everything the tests did to them, and takes back
a publish request the suite left pending. Set `E2E_KEEP_SEED=1` to keep the
data for a look after a failure, then run `seed/cleanup.sql` by hand with the
`round_id` and `member_id` from `.state/seed.json`. Without the URL or the
tokens, setup skips seeding and the write tests skip.

If someone has a matching draft, an edit lock or a pending publish request on
the round, the matching tests skip rather than overwrite it. When a leftover
draft may be thrown away, set `E2E_TAKE_MATCHING=1`: the suite's run then
replaces it. A held lock, a running run or a pending publish request still
makes the matching tests skip.

## Feature flags

Set the test accounts' flags in LaunchDarkly first, then declare them in
`.flags.json` (or `E2E_FLAGS` with the same JSON):

```json
{ "matching-run": true, "mentorship-kit-email": false }
```

Tests tagged `@flag:<key>` assert the declared state and skip when the flag is
not declared. Setup compares the declaration with what each account's browser
gets from LaunchDarkly (and, for backend-only flags such as
`view-personal-summary`, with how the endpoint answers) and stops on any
mismatch. To cover both states, run twice and flip the flag in between.

## Guardrails

`lib/guard.js` sits in front of every API call the browser makes:

- `@smoke` tests, and every test on staging, may not write. Writes are aborted
  and fail the test.
- Other tests may write only about seeded people and e2e-member, may decide
  only requests the suite raised itself, and may save or publish a matching
  result only in a round where the suite started the run.
- Anything that sends mail (Kit, single sends, replies) is always aborted.
- Any API response of 400 or above fails the test unless it is listed in
  `KNOWN_API_ERRORS` with the reason.

Reports and traces contain the session cookies; do not share them outside the
team.
