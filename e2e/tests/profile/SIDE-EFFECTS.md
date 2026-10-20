# Profile, Sign in & security and Personal Dashboard e2e: side effects audit

What each write on these pages does outside its own rows on test, who it
reaches, and whether the suite lets it out. Read from the backend deployed on
test (main at `5c2dbbed`, 2026-10-15). Paths are under `backend/`.

## Profile (`PATCH /api/profiles/me`)

Route: `profile/profile_controller.py`; writes:
`profile/profile_service.py:update_profile` and
`profile/profile_command_service.py`. The endpoint takes no user id: it
writes the caller's `users` row (names, timezone, LinkedIn, communication
method) and the caller's one `experience` row (`education` and
`work_history` JSON lists, each replaced whole when present, cleared when
`[]`), in one transaction. The DTO (`dto/profile_create_dto.py`) forbids
extra fields, so a body naming someone else is a 400.

- Mail, notifications, events: none. Nothing in `profile/` calls
  `record_event`, Gmail, Kit or Pub/Sub.
- Auth0, Microsoft Graph, LDAP: none. The profile never leaves the database;
  the LDAP and Graph cronjobs only read the directory into Purrf.
- Recruiting: none. An application keeps its own copy of the profile blocks
  in `application_submission.submission`; editing the profile changes no
  submitted application. Only the application form writes the other way
  (its "Update your profile?" write-back), which the profile specs do not use.
- Mentorship: none at write time. Names are read live wherever a person is
  shown, so while a test account carries a name every page shows it; the
  other layers assert the test accounts have none ("User 276"). Kit gets a
  first name only when an admin prepares a broadcast, which the guard always
  aborts.
- Server-side checks (the DTO, since PUR-794 `b0cf6dad`): the timezone must
  be an IANA name; school, field of study, title and company must not be
  blank after trimming; a start month after the current month is refused
  ("Start date cannot be in the future"), and so is an end month before the
  start month. "Now" is taken at UTC+14, so a month any timezone has reached
  is never the future; a job not marked current needs an end date. Names
  (first, last) may still be blank; only the browser checks those
  (`frontend/src/pages/Profile/profileValidation.js`).

### What the suite lets out

Only for a role the test lets edit (`page.allowProfileWrites()`), and every
profile spec snapshots the test accounts before each test and puts them back
after (`restoreAccountsAfterEach`, `lib/seed.js:restoreAccounts`): profile
fields, the experience row (removed when there was none), address rows and
the status of their training rows. Global setup takes the same snapshot for
the whole run and teardown restores and compares it, printing each account's
name and addresses.

## Sign in & security (`/api/auth/emails…`, `/api/auth/identities…`)

Routes: `authentication/email_management_controller.py`; service:
`authentication/email_management_service.py`; Auth0 calls:
`common/auth0_client.py`.

| Write                                                                         | Mail                                                                                                                       | Auth0                                                                               | Database                                                                                                                                  |
| ----------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| Add email: `POST …/initiate`                                                  | Auth0 passwordless code to **the address being added**. None if it is held by someone else (409 first) or malformed (400). | `passwordless/start` only; no user is created yet                                   | none                                                                                                                                      |
| Add email: `POST …/verify`                                                    | none                                                                                                                       | `oauth/token` with the code. A right code creates (or reuses) an inert Auth0 `email | …` user for the address, never deleted afterwards. A wrong one is a 400 and counts against that address in Auth0's brute-force protection | right code: a confirmed, non-primary `user_emails` row (primary only if none). Releases unconfirmed copies of the address on other accounts |
| Remove email: `DELETE …/{id}`                                                 | none                                                                                                                       | none (the Auth0 user stays)                                                         | deletes the row. Refused: the primary, the current passwordless session's address, someone else's row (400)                               |
| Make primary: `POST …/{id}/primary/initiate`                                  | code to **the current primary**                                                                                            | `passwordless/start` for the primary                                                | none                                                                                                                                      |
| Make primary: `POST …/{id}/primary/confirm`                                   | none                                                                                                                       | `oauth/token` against **the current primary** with the code                         | swaps `is_primary`                                                                                                                        |
| Remove sign-in: `POST /api/auth/identities/{id}/unlink/initiate`, `…/confirm` | code to the current primary                                                                                                | confirm **deletes the identity's Auth0 user**                                       | deletes the `user_identities` row                                                                                                         |

- Notifications, events, Graph, LDAP: none for any of these. Verifying a
  company address would also grant the employee permission bundle and make
  it primary (`user_identity/internal_lifecycle.py`); the suite never adds
  one.
- LaunchDarkly evaluates by the account's email, so a moved primary would
  change which flags the account gets.

### What the suite lets out

The test accounts sign in by codes to `wangyanpei76@gmail.com` (e2e-admin)
and `wangyanpei76+e2e-<role>@gmail.com`; losing one locks the suite out. So
(`lib/guard.js:refuseProfile`):

- Adding: only an extra alias `wangyanpei76+e2e-<role>-<suffix>@gmail.com`,
  never a sign-in address, so the code lands in the test mailbox. Starting
  with a profile-seed address (held by E2E Profile Owner) is let through to
  see the 409 that comes before any mail.
- Removing: only the caller's own extra alias, or a profile-seed person's
  row (to see the API refuse it). Never the primary or a sign-in address.
- Make primary: starting only for the caller's extra alias (one code mailed
  to the caller's sign-in address in the test mailbox); confirming never.
  A real switch would move the account off its sign-in address and LD
  targeting with it, and a wrong code would count against the sign-in
  address at Auth0. Whether the API refuses to delete a primary is therefore
  not tried either: the UI offers no button for it, and the guard test pins
  that the suite cannot send it.
- Remove sign-in: never (deletes an Auth0 user). e2e-admin holds a Google
  identity and is offered the button; no test presses it.
- Each run mails two codes, both into the test mailbox: one to
  `wangyanpei76+e2e-member-extra@gmail.com` (the wrong-code attempt) and one
  to e2e-member's sign-in address (the Make primary start). Nothing else. With `E2E_EMAIL_OTP=1`
  one more code goes to `wangyanpei76+e2e-member-otp@gmail.com`; completing
  it leaves an Auth0 passwordless user for that alias.

Extra aliases added in the database by a test are removed by the test, by
`restoreAccounts`, and by `seed/profile-cleanup.sql` (every non-primary
`+e2e-<role>-…` row of a test account).

## Résumé (`POST /api/recruiting/resumes`)

There is no résumé on the Profile page; a résumé belongs to an application.
The application form parses the picked PDF in the browser
(`frontend/src/lib/resume-parser`) and prefills its own fields, not the
profile. When the posting collects a résumé it also uploads the file
(`recruiting/application_controller.py:upload_resume`): stored
content-addressed as `resumes/<sha256>.pdf` in the test résumé bucket
(`terraform/modules/purrf_instance/resumes.tf`), no database row, no mail.
Only a submitted or edited application points at an object, so picking a
new file on a form changes no existing application.

The suite uploads its two generated résumés (`lib/resume-fixtures.js`, a
few hundred bytes each, deterministic), so the bucket keeps two objects
across all runs; nothing deletes them. Uploads are let out only in a test
that calls `page.allowResumeUploads()`, on the two postings
`03-resume.spec.js` creates and deletes itself (`E2E profile …`, recruited
by e2e-admin, also removed by `recruiting-cleanup.sql`). The member never
submits there.

## Personal Dashboard

- `POST /api/summary/me` reads (behind `view-personal-summary`); it is on
  the guard's read-style list. Since PUR-804 it answers every test account
  403 (no confirmed CircleCat address) before reading Redis.
- The onboarding reminder test sets e2e-member's mentee onboarding to
  `to_do` in the database for the test and puts it back
  (`restoreAccountsAfterEach`, and teardown's snapshot). Nothing is
  dispatched by it: no cron reads training status.

## Not covered

- Completing Add email without `E2E_EMAIL_OTP=1` (needs a code from the
  inbox).
- Actually switching the primary, removing a sign-in identity, and the API's
  own refusal to delete a primary (see above).
- The "Update your profile?" write-back on submitting an application
  (recruiting).
