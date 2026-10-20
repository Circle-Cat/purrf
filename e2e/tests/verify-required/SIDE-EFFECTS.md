# Email verification wall (`/verify-required`) e2e: side effects audit

What the wall's actions do outside their own rows on test, who they reach,
how a test account can be put in front of the wall, and what the suite lets
out. Read from main at `527c833c` (2026-10-17); none of the files below has
changed since `228ab6c4` (PUR-762). Backend paths are under `backend/`,
frontend paths under `frontend/src/`.

## When the wall shows

- Backend: `GET /api/permissions/me` answers `has_verified_email`, which is
  `user_emails_repository.has_confirmed` (`authentication/authentication_controller.py:61-66`,
  `repository/user_emails_repository.py:281-294`): does the caller have
  **any** `user_emails` row with `otp_confirmed = true`.
- Frontend: `context/auth/AuthProvider.jsx:44` stores it; `components/common/HardWallGate.jsx:54-60`
  sends every path except `/verify-required` to the wall while it is false,
  and sends `/verify-required` to `/profile` while it is true. A 403 from
  `/permissions/me` shows Access denied (`:39`), a 401, 400, 5xx or network
  error shows the load-error card (`:44-52`, `components/common/AuthLoadError.jsx`),
  never the wall.
- The gate wraps only `<Routes>` inside `<main>` (`App.jsx:78`); the header
  and sidebar stay drawn on the wall, with the full menu the account's
  permissions give. A click there lands back on the wall.
- Nothing on the server holds an unverified caller back: `authenticate()`
  only checks that a user is resolved (`utils/permission_decorators.py:118-134`).
  The wall is the frontend alone.

## Why a test account cannot really be unverified

Every test account signs in by Auth0 passwordless (`email|…` sub). Such a
login is row-less (`common/identity_type.py:23-34`): no `user_identities`
row, and every request re-resolves the account through the **confirmed**
`user_emails` row of the login address
(`user_identity/user_identity_service.py:281-344`, step 2.5). So while the
session resolves, its login address is confirmed and `has_confirmed` is true.
On test each account has exactly one address, its sign-in address, confirmed
and primary (email ids 290, 590, 591, 593, 990 for 267, 276, 277, 279, 280).
e2e-admin also holds a `google-oauth2|…` identity, but the suite signs it in
by code, not Google.

What flipping the login row (`otp_confirmed = false`; `is_primary` must go
false too, `ck_user_emails_user_emails_primary_must_be_confirmed`) would do
to the next request of that account:

1. Step 2.5 finds no confirmed row, so it falls to step 3
   (`user_identity_service.py:351-359`).
2. Token `iat` (the Auth0 login time, `authentication/authentication_service.py:250`)
   older than 30 minutes: `ValueError("Session expired; sign in again")`,
   every API call answers 400, and the app shows "Sign-in was refused", not
   the wall. Global setup then sees the cookie fail and signs the account in
   again, which lands in case 3.
3. Token younger than 30 minutes: **first-login insert**. A new `users` row
   is created, `delete_unconfirmed_on_other_users` deletes the flipped row
   from the real account (`:535-537`), and the address is inserted confirmed
   and primary on the new user (`:538-551`). The account is forked: the
   alias now signs into an empty user with no permissions, and the old user
   id (whose id every layer reads from `.state/accounts.json`) has no
   address. Undoing it is hand SQL on `users`, `user_emails` and anything the
   new user touched.

No cache delays any of this: there is no Redis or JWT claim for the
verified state; `has_confirmed` is read on every `/permissions/me`. The CF
Access cookie in `.state/logins.json` stays valid at Cloudflare, but the
backend resolves it as above. A sixth passwordless account would behave the
same. Only a Google (sub-routed) login with no confirmed address can stand
at the wall for real (`user_identity_service.py:85-123` resolves it without
looking at addresses), and the suite cannot sign in through Google.

**So the suite never edits a test account's address rows to reach the wall.**
It answers `GET /api/permissions/me` in the browser with the real response
and `has_verified_email: false` (`page.route`, which wins over the guard's
context route), keeping `sub`, `user_id` and `email` as they are, so the
LaunchDarkly context (`context/flags/ldContext.js:10`, keyed by `sub`) does
not change. Everything the wall then calls goes to the real backend.

## The wall's actions

Routes: `authentication/email_management_controller.py:267-311`; service:
`authentication/email_management_service.py`; Auth0: `common/auth0_client.py`.
Both routes only need a signed-in caller.

| Action (UI)  | Call                                                | Mail                                       | Auth0                                                                                                      | Database                                                                                                                                                                                                                                    |
| ------------ | --------------------------------------------------- | ------------------------------------------ | ---------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Send code    | `POST /api/auth/emails/initiate {email}`            | a code to the typed address, sent by Auth0 | `passwordless/start` (`auth0_client.py:73-96`)                                                             | none (`email_management_service.py:170-209`); returns a signed state (10 min)                                                                                                                                                               |
| Resend code  | the same initiate again                             | one more code each click                   | one more `passwordless/start`                                                                              | none                                                                                                                                                                                                                                        |
| Change email | none                                                | none                                       | none                                                                                                       | none; clears code and state, keeps the typed address (`components/common/OtpVerifyForm.jsx:73-77`)                                                                                                                                          |
| Verify       | `POST /api/auth/emails/verify {state, otp}`         | none                                       | `oauth/token` passwordless grant; a right code creates (or reuses) an Auth0 `email\|` user for the address | right code only: releases the address from any other account holding it unconfirmed, drops a never-used `manual\|` identity claiming it, then confirms the caller's row or inserts one (primary only when the caller has none) (`:549-602`) |
| Log out      | navigation to Auth0 `/v2/logout` → CF Access logout | none                                       | ends the Auth0 session                                                                                     | none; **ends the Access session the cached cookie belongs to** (`utils/auth.js:146-188`)                                                                                                                                                    |

- Who gets mail: only the typed address, and only from Auth0. Purrf sends
  nothing itself; no notification, Pub/Sub, Kit, Gmail or `record_event`
  call is on these paths.
- Rate limits: none in Purrf and no cooldown in the UI; every Send or
  Resend is one more mail. Auth0's own limits answer 429 ("Too many
  requests. Please try again later." on initiate, "Too many verification
  attempts…" on verify). Wrong codes count against that address at Auth0.
- Refusals, all before Auth0 is called unless noted:
  - malformed address: 400 "Please enter a valid email address." (`:194-195`);
    empty field and empty code are stopped in the browser with a toast;
  - address **confirmed** on another account: 409 "This email is already in
    use by another account. If it's yours, sign in with a code sent to that
    address instead." (`:196-199`, re-checked at verify `:251-254`). An
    address another account holds **unconfirmed** is not refused: the code
    goes out, and a right code takes the address away from that account;
  - wrong or expired code: 400 "Incorrect or expired verification code.
    Please request a new one." (Auth0 `invalid_grant`, `auth0_client.py:145-148`);
  - state from another user, another flow, tampered or older than 10 min:
    400 "Verification session expired. Please request a new code." (`:241-246`);
  - the Auth0 `email|` sub already tied to another account's identity row:
    409 "This sign-in method is already linked to another account." (`:271-277`).
- A company address (`@circlecat.org`, `@u.circlecat.org`) verified here
  also runs `absorb_internal_identity`: the employee permission bundle, the
  internal flag and the address made primary (`:280-281`). The suite never
  types one into Send.
- After a right code the wall calls `refreshAuth()` and goes to `/profile`
  (`pages/VerifyRequired.jsx:46-49`). With the mock still answering false
  the gate would bounce it back, so the mock must pass through once the
  verify call has succeeded.

## What the suite lets out

- Reaching the wall: the browser-side answer above, nothing in the
  database. The account's rows are never touched for it.
- Send code only to an extra alias of the caller,
  `wangyanpei76+e2e-<role>-<suffix>@gmail.com`, as on Sign in & security
  (`lib/guard.js:refuseProfile`). The wall prefills the **sign-in address**
  (`user.email`), which the guard refuses, as it refuses a company address;
  a test clicks Send with both and expects the block. Two more initiates go
  out because the API refuses them before any mail: something that is not
  an address (`not-an-email`, 400; the guard lets through what fails the
  backend's `^[^@\s]+@[^@\s]+\.[^@\s]+$`), and an extra alias the test
  first inserts **confirmed** on e2e-reviewer (`+e2e-reviewer-wall@…`, 409).
- Verify only with a state for an extra alias. Wrong codes go only against
  an extra alias, never a sign-in address.
- Log out: the navigation to `**/v2/logout**` is aborted in the test and
  only its URL is checked, so neither Auth0 nor Cloudflare logout runs.
- Mail per run: two codes, both to `wangyanpei76+e2e-member-wall@gmail.com`
  (Send, then Resend, in the wrong-code test). With `E2E_EMAIL_OTP=1` one
  more to `wangyanpei76+e2e-member-wall-otp@gmail.com`, whose code is read
  from `.state/codes/member-verify.txt` (or the terminal); completing it
  leaves an Auth0 passwordless user for that alias and a confirmed
  non-primary row on e2e-member, which the test deletes through the API.

## The tests (`01-verify-required.spec.js`, e2e-member)

| Test                                                                                                               | Mock                                    | Mail |
| ------------------------------------------------------------------------------------------------------------------ | --------------------------------------- | ---- |
| Verified at `/verify-required` lands on `/profile` (`@smoke`)                                                      | none                                    | 0    |
| `/profile`, `/dashboard/me`, `/recruiting/jobs` end on the wall; a sidebar link leads back                         | unverified                              | 0    |
| The wall's copy, prefilled editable address, Send code, Log out; the Workspace copy for a `@circlecat.org` sign-in | unverified (+ `email`)                  | 0    |
| 403, 401, 400 from `/permissions/me` show Access denied / session expired / refusal, never the wall                | the status                              | 0    |
| Empty address (toast, no call), malformed address (400)                                                            | unverified                              | 0    |
| Reviewer's confirmed alias (409)                                                                                   | unverified                              | 0    |
| The guard blocks Send to the sign-in address and to a company address                                              | unverified                              | 0    |
| Send to the alias, empty code, wrong code (400, nothing stored), Resend, Change email                              | unverified                              | 2    |
| Log out goes to Auth0 `/v2/logout` → tenant → app Access logout (aborted)                                          | unverified                              | 0    |
| With `E2E_EMAIL_OTP=1`: the real code confirms the alias non-primary and lands on `/profile`; the row is removed   | unverified until the verify answers 200 | 1    |

## Teardown

What can change: e2e-member's `user_emails` (a confirmed
`+e2e-member-wall-otp@…` row from the optional test) and e2e-reviewer's (the
`+e2e-reviewer-wall@…` row the 409 test inserts). The spec runs inside the
profile layer's `restoreAccountsAfterEach()` (`tests/profile/helpers.js`),
which removes every address row added to a test account during a test;
global teardown restores the run's snapshot and `seed/profile-cleanup.sql`
removes every non-primary `+e2e-<role>-…` row of a test account.

The spec also fingerprints, in `beforeAll` and `afterAll`, e2e-member's
address rows (ids, address, `otp_confirmed`, `is_primary`), the number of
users below the seed range, and the number of test-mailbox addresses on a
user below it that is not a test account; all three must be the same, or a
test account was forked.

## Not covered

- A real unverified account (see above). Only a Google-sign-in account with
  no confirmed address reaches the wall for real; the suite has none.
- The internal (`@circlecat.org`) copy beyond the text: no code is ever sent
  to a company address.
- Auth0's 429s, and verifying an address another account holds unconfirmed
  (the right code would take it away from that account).
