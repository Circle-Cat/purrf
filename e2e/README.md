# End-to-end regression suite

Playwright tests that click through a deployed Purrf as real accounts. They run
by hand against test (or, read-only, staging) after a deploy; they are not part
of CI or `bazel test`.

## Accounts

Four dedicated accounts on personal addresses (not `@circlecat.org`, which
would get the employee permission bundle on first login). By default they are
plus aliases of one mailbox, so every sign-in code lands in one inbox:

| Role      | Signs in as                 | Holds                                                       |
| --------- | --------------------------- | ----------------------------------------------------------- |
| admin     | `<mailbox>+e2e-admin@…`     | every admin permission except approving                     |
| reviewer  | `<mailbox>+e2e-reviewer@…`  | `mentorship.admin.read`, `mentorship.approve`, `user.admin` |
| reviewer2 | `<mailbox>+e2e-reviewer2@…` | the same as reviewer, so a request can really be reassigned |
| member    | `<mailbox>+e2e-member@…`    | nothing                                                     |

The exact lists live in `lib/accounts.js`. `logins` in the settings file
overrides an address. Global setup refuses an account that is a super admin,
a company address, or holds more than its list; a role without a way to sign
in skips the tests that need it.

## Settings file

Copy `e2e.local.example.json` to `e2e.local.json` (gitignored) and fill in:

- `mailbox.address`: the mailbox the aliases belong to.
- `databaseUrl`: the test database (seeding, cleanup, and topping up the
  accounts' permissions).
- `flags`: the flags you set in LaunchDarkly for these accounts (optional).
- `logins`: per-role addresses that differ from the alias (optional).
- `tokens`: per-role Access cookies handed over by hand instead of signing in
  (optional; `.tokens/<role>.txt` still works too).

## Signing in

Global setup signs each account in the way a person does, by emailed code,
and caches the Access cookie in `.state/logins.json` for its 24 hours. When a
cached cookie is missing or no longer accepted, it sends a code to every such
account at once and waits for them: run from a terminal, it asks for each
code; run otherwise, it waits up to 5 minutes for `.state/codes/<role>.txt`.
A code is good for 3 minutes. It never signs out, because signing out ends the
Access session a cookie belongs to.

Missing permissions are written straight into the test database, as the
permission console would, so no super admin is needed. On staging there is no
database URL; grant the accounts their permissions there once by hand.

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

Before any test, `global-setup.js` signs the accounts in, tops up their
permissions, checks them, and refuses to run unless the page shows the banner
of the chosen environment. Set `E2E_ANY_ACCOUNT=1` to skip the account checks
when trying the suite with your own login.

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
- A round may be created only when it is named `E2E …` with every date at
  least 30 days ago, and edited only when the suite created it in the same run.
- Anything that sends mail (Kit, single sends, replies) is always aborted.
- Any API response of 400 or above fails the test unless it is listed in
  `KNOWN_API_ERRORS` with the reason.

Reports and traces contain the session cookies; do not share them outside the
team.
