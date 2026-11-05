# End-to-end regression suite

Playwright tests that click through a deployed Purrf as real accounts. They run
by hand against test (or, read-only, staging) after a deploy; they are not part
of CI or `bazel test`.

## Accounts

Five dedicated accounts on personal addresses (not `@circlecat.org`, which
would get the employee permission bundle on first login). By default they are
plus aliases of one mailbox, so every sign-in code lands in one inbox:

| Role      | Signs in as                 | Holds                                                                                                                  |
| --------- | --------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| admin     | `<mailbox>+e2e-admin@…`     | every admin permission except approving                                                                                |
| reviewer  | `<mailbox>+e2e-reviewer@…`  | `mentorship.admin.read`, `mentorship.approve`, `user.admin`, `recruiting.job.approve`, `recruiting.interview.evaluate` |
| reviewer2 | `<mailbox>+e2e-reviewer2@…` | `mentorship.admin.read`, `mentorship.admin.write`, `mentorship.approve`, `user.admin`, `recruiting.job.approve`        |
| readonly  | `<mailbox>+e2e-readonly@…`  | `mentorship.admin.read` only                                                                                           |
| member    | `<mailbox>+e2e-member@…`    | nothing                                                                                                                |

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
setup has seeded rounds of the suite's own and fake people in them (user ids
from 990001, addresses `@e2e.purrf.test`), with e2e-member registered too. No
real round's participants, pairs or matching result are touched:

| Round                         | Phase                                             | Used for                                 |
| ----------------------------- | ------------------------------------------------- | ---------------------------------------- |
| `E2E seed live round`         | in progress, past matching, meetings under way    | every console spec (`page.seed.roundId`) |
| `E2E seed registration round` | registration open, closing after every real round | the member registering                   |
| `E2E seed feedback round`     | meetings over, feedback open                      | the member's feedback                    |
| `E2E seed previous round`     | ended                                             | participation history, exemptions        |

The registration round closes after every real round open for registration,
so the Personal Dashboard and the admission email (both take the open round
closing first) keep pointing at the real one. While no real round is open
for registration it is not created, and its test skips. While a run lasts
(about half an hour), everyone on test sees these rounds; the live round is
also the dashboard's default round then.

That needs `psql` on the machine, the admin and member tokens, and the test
database's URL:

```sh
printf '%s' 'postgresql://…' > e2e/.tokens/database-url.txt   # or export E2E_DATABASE_URL; the backend's asyncpg form works too
```

Setup cleans up leftovers, seeds, and writes `.state/seed.json` (the round
ids, the people, and a fingerprint of every real round in progress: its
registrations, pairs, notes, approval requests and latest matching run).
Teardown removes the seeded rounds, the seeded people and everything in or
about them, including any real person's registration in a seeded round, then
takes the fingerprint again and prints a warning if a real round changed.
Set `E2E_KEEP_SEED=1` to keep the data for a look after a failure, then run
the six cleanup scripts by hand, in the order teardown runs them (values
from `.state/seed.json`):

1. `seed/inbox-admin-cleanup.sql` (first: it puts back real threads filed to
   seeded people, which the others would delete with those people)
2. `seed/profile-cleanup.sql`
3. `seed/leave-cleanup.sql` with `-v accounts=<testAccounts, comma-separated>`
4. `seed/cleanup.sql` with `-v member_id=<memberId>`
5. `seed/recruiting-cleanup.sql` with `-v admin_id=<adminId>`, after
   cancelling any interview still booked on a suite application
6. `seed/training-cleanup.sql`

Without the URL or the tokens, setup skips seeding and the write tests skip.

## Seeding the recruiting tests

The `@recruiting` tests run on postings and candidates of the suite's own,
seeded by global setup next to the rounds (`seed/recruiting-seed.sql`):
three published employment postings named `E2E seed …` whose only recruiter
is e2e-admin, and 31 candidates (user ids 990101-990134) whose only address
is a confirmed `<mailbox>+e2e-cand-<n>@…` alias. The postings the specs
create are named `E2E posting …`, also recruited by e2e-admin alone. Every
account's addresses must be the mailbox or an `+e2e-…` alias of it, or setup
refuses to run.

Teardown cancels any interview still booked on a suite application (through
the API, which deletes the Calendar event), then `seed/recruiting-cleanup.sql`
removes the suite's postings, every application to them (e2e-member's
included), the candidates and everything about them. A fingerprint of every
real posting and its applications is taken before and after, with a warning
when anything changed. `tests/recruiting/SIDE-EFFECTS.md` lists what each
recruiting write sends and to whom.

## Seeding the training tests

The `@training` tests create their own courses through the API, named
`E2E … <timestamp>` (there is no create button), and assign them only to
four seeded trainees (user ids 990201-990204, addresses
`<mailbox>+e2e-trainee-<n>@…`, `seed/training-seed.sql`) and the test
accounts. Global setup also writes the SCORM fixtures they upload
(`lib/scorm-fixtures.js`, a few KB each) into `.state/scorm/`; run
`node lib/scorm-fixtures.js <dir>` to get them elsewhere. Teardown runs
`seed/training-cleanup.sql`, which removes every `E2E …` course without a
category with its packages, assignments and progress, and the trainees, and
compares a fingerprint of the real courses. Package files stay in the
training bucket; teardown prints their prefixes.
`tests/training/SIDE-EFFECTS.md` lists what the training writes do.

## Seeding the Inbox and account console tests

The `@inbox` and `@accounts` tests (`tests/inbox-admin/`) work on nine ops
people seeded by global setup (`seed/inbox-admin-seed.sql`, user ids
990301-990309, addresses `<mailbox>+e2e-ops-<n>@…`), on Inbox threads they
insert into the database (`gmail_thread_id` `e2e-…`), and on four real
threads sent from the test mailbox to the test aliases with subjects
starting `E2E inbox`, which are kept and reused. `seed/inbox-thread-reset.sql`
puts the real threads back and drops the inserted ones between tests;
`seed/inbox-admin-cleanup.sql` runs it and removes the ops people, before
the other cleanups in setup and teardown. Teardown compares a fingerprint
of real accounts, grants, block requests and mail threads.
`tests/inbox-admin/SIDE-EFFECTS.md` lists what each write does.

## Seeding the profile tests

The `@profile` tests (`tests/profile/`) edit the test accounts' own profile,
education and work history, and add and remove extra addresses on Sign in &
security. Global setup snapshots every test account (profile fields,
experience, addresses, training status) and seeds E2E Profile Owner
(user id 990401, `seed/profile-seed.sql`), whose addresses are the "already
in use" and "someone else's" cases. Each profile test snapshots the accounts
again and puts them back when it ends; teardown restores the run's snapshot,
prints every account's name and addresses, and runs
`seed/profile-cleanup.sql`. The résumé tests create two `E2E profile …`
postings of their own and upload two generated PDFs
(`lib/resume-fixtures.js`) to the résumé bucket, where they stay.
`tests/profile/SIDE-EFFECTS.md` lists what each write does.

The Add email test that completes verification runs only with
`E2E_EMAIL_OTP=1`: it sends a code to `<mailbox>+e2e-member-otp@…` and
waits up to 5 minutes for it, typed at the terminal or written to
`.state/codes/member-email.txt`.

## Seeding the leave tests

The `@leave` tests (`tests/leave/`) work on requests seeded by SQL
(`seed/leave-seed.sql`), all filed against e2e-reviewer: ten seed employees
(user ids 990501-990510, addresses `<mailbox>+e2e-leave-<n>@…`) and
e2e-member, whose ledger rows make it covered. Global setup also enters
`E2E …` company holidays for 2019 (edited by the Yearly setup spec) and 2099
(the seeded requests are dated there so approving can recount them); while a
run lasts both years show in everyone's Company holidays picker. Nothing is
filed through the API: a test account has no company address, so the server
refuses every request it files. Teardown runs `seed/leave-cleanup.sql` and
compares a fingerprint of the real requests, ledger rows, holidays, approval
rows and events. `tests/leave/SIDE-EFFECTS.md` lists what each write does.

## The Dashboard and DataSearch tests

The `@dashboard` tests (`tests/dashboard/`) only read: the activity data on
test is real (synced from Jira, Gerrit, Calendar, Chat and the Azure
directory into Redis), so they seed nothing and compare the pages with the
API responses they got, never with fixed numbers. Their POSTs are queries
and sit on the guard's read-style list. The permission spec gives
e2e-readonly `dashboard.activity_summary.read` or `internal_activity.read`
for one test through a `user_permissions` row it deletes afterwards.
Every query costs Redis commands per member on test's metered Redis, so
the layer sends one whole-group summary, over a week, and answers the
Dashboard's other summaries from it in the browser; DataSearch queries
name two people over at most seven days. `tests/dashboard/SIDE-EFFECTS.md` lists every call
and the budget.

## The email verification wall tests

The `@verify` tests (`tests/verify-required/`) stand e2e-member at
`/verify-required` without touching its addresses: the browser is handed
the real `GET /api/permissions/me` with `has_verified_email` turned false
(a test account made unverified in the database would be forked on its next
sign-in). Everything the wall then calls is real. A run mails two codes to
`<mailbox>+e2e-member-wall@…`; Log out is stopped before it reaches Auth0.
The test that completes verification runs only with `E2E_EMAIL_OTP=1`, with
its code typed at the terminal or written to `.state/codes/member-verify.txt`.
`tests/verify-required/SIDE-EFFECTS.md` lists what each action does.

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
- Other tests may write only about seeded people and e2e-member, and only in
  a seeded round; may decide only requests the suite raised itself; may start
  a matching run only in a seeded round, and lock, save or publish a result
  only there (or where the suite started the run); e2e-member may register
  and send feedback only in a seeded round. A participant page's Refresh
  emails pulls Gmail into the database, so it counts as a write too: only
  for a seeded person in a seeded round.
- A round may be created only when it is named `E2E …` with every date at
  least 30 days ago, and edited only when the suite created it in the same run.
- Anything mentorship sends (Kit, single sends, replies) is always aborted.
- Recruiting writes must be about a suite posting or an application to one,
  and every person they name (owner, reviewer, interviewer, mention, block
  reviewer) must be a test account. Mail to a candidate goes out only to an
  `+e2e-…` alias and never as a reply; interview invites go out only for
  suite applications. Résumé uploads are aborted unless the test allows
  them (below).
- Training writes must be about an `E2E …` course without a category (never
  one of the real courses), assign only seed trainees and test accounts, and
  run only on an assignment of such a course. `page.expectBlocked(regex)`
  names a write a test expects the guard to abort.
- Deactivating, reactivating, blocking, unblocking, granting or revoking
  permissions and raising a block request are allowed only about seeded
  people (user ids from 990001 that setup created); super-admin never.
- Inbox writes are allowed only on the suite's threads (inserted, or the real
  `E2E inbox …` ones from the test mailbox): a reply only on a real one whose
  reply goes to the test mailbox, a transfer only while the thread needs no
  reply, filing only to a seeded person in a seeded round or to a seeded
  application.
- A profile is saved only by a role the test allows
  (`page.allowProfileWrites()`) and restores. Addresses are added and
  removed only when they are an extra alias `<mailbox>+e2e-<role>-<suffix>@…`
  of the caller, never a sign-in address. Two adds go out only so the API can
  refuse them before sending a code: exactly the address of a seeded profile
  person (`.state/seed.json`, `profile.people`; "already in use"), and
  something that is not an address at all. Making an address primary may be
  started but never confirmed, and sign-in identities are never removed.
  Résumé uploads go out only in a test that calls `page.allowResumeUploads()`.
- Any API response of 400 or above fails the test unless it is listed in
  `KNOWN_API_ERRORS` with the reason, or the test provoked it on purpose with
  `page.expectApiError({method, path, status})`, which holds for that test
  only. An entry with a `message` must match the response's message; when
  the page closed before the body could be read, the error is not taken as
  known.

Reports and traces contain the session cookies; do not share them outside the
team.
