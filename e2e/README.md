# End-to-end regression suite

Playwright tests that click through a deployed Purrf as real accounts. They run
by hand against test (or, read-only, staging) after a deploy; they are not part
of CI or `bazel test`.

## Accounts

Three dedicated accounts on personal addresses (not `@circlecat.org`, which
would get the employee permission bundle on first login), plus a super admin
that only tops up their permissions:

| Token file               | Account      | Holds                                         |
| ------------------------ | ------------ | --------------------------------------------- |
| `.tokens/superadmin.txt` | super admin  | used by the pre-run check only                |
| `.tokens/admin.txt`      | e2e-admin    | every admin permission except approving       |
| `.tokens/reviewer.txt`   | e2e-reviewer | `mentorship.admin.read`, `mentorship.approve` |
| `.tokens/member.txt`     | e2e-member   | nothing                                       |

The exact lists live in `lib/accounts.js`. A missing token skips the tests
that need that account.

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

## Guardrails

`lib/guard.js` sits in front of every API call the browser makes:

- `@smoke` tests, and every test on staging, may not write. Writes are aborted
  and fail the test.
- Any API response of 400 or above fails the test unless it is listed in
  `KNOWN_API_ERRORS` with the reason.

Reports and traces contain the session cookies; do not share them outside the
team.
