# Leave e2e: side effects audit

What each leave write does outside its own rows on test, who it reaches, and
whether the suite lets it out. Read from the backend at the commit the suite
was written against (main at `0fc17d67`, 2026-10-16). Paths are under
`backend/`. Updated since for PUR-612 (#695, the admin ledger route) and
PUR-809 (#760, only a confirmed company address gives an ldap); PUR-767
(#752) changed how the accrual job pays, which the suite never runs.

## Routes and who may call them

| Route                                                       | Gate                                             | Writes                                                                        |
| ----------------------------------------------------------- | ------------------------------------------------ | ----------------------------------------------------------------------------- |
| `GET /api/leave/me`                                         | signed in                                        | none                                                                          |
| `GET /api/leave/requests`                                   | signed in (own rows only)                        | none                                                                          |
| `GET /api/leave/requests/approvals`                         | signed in (rows filed against caller)            | none                                                                          |
| `GET /api/leave/me/ledger`                                  | signed in (own ledger only)                      | none                                                                          |
| `GET /api/leave/holidays/{year}`, `holiday-years`, `policy` | signed in                                        | none                                                                          |
| `GET /api/leave/balances`                                   | `leave.admin`                                    | none (reads the Redis population and every accruing person's balance)         |
| `GET /api/leave/ledger?userId=&page=&pageSize=`             | `leave.admin`                                    | none (everybody's ledger rows, or one person's; PUR-612 #695)                 |
| `POST /api/leave/requests`                                  | signed in; the requester is the caller           | `leave_request`, `approval_request`, `event`, `notification`                  |
| `POST /api/leave/requests/{id}/withdraw`                    | signed in; caller must own the request           | `leave_request.status`, `approval_request`, `event`, `notification`           |
| `POST /api/leave/requests/{id}/decision`                    | signed in; caller must be its approver           | as above, plus one `leave_ledger` row on approve (none for sick leave)        |
| `PUT /api/leave/holidays/{year}`                            | `leave.admin`                                    | deletes and re-inserts every `leave_holiday` row of that year                 |
| `POST /api/leave/adjustments`                               | `leave.admin`                                    | one `leave_ledger` row (`manual_adjustment`) for **any** `userId` in the body |
| `POST /api/leave/jobs/weekly-accrual`, `annual-close`       | `system.backfill.scheduled` (no person holds it) | ledger rows for everybody in the Redis population                             |

Controllers: `leave/leave_request_controller.py`, `leave_balance_controller.py`,
`leave_calendar_controller.py`, `leave_admin_controller.py`,
`leave_job_controller.py`. No route checks the `leave-management` flag; the
flag only hides the frontend.

## Who approves, and why a test account can never file

Filing (`leave_request_service.submit` → `_approver_for`) needs, in order:

1. a start date not before the Beijing day (`business_today`), end ≥ start;
2. a confirmed `@circlecat.org` address on the requester (`_ldap_of` →
   `_confirmed_ldap`): its local part is the Azure ldap. Since PUR-809 (#760)
   an unconfirmed company address counts for nothing here, in coverage
   (`GET /api/leave/me`) or in accrual;
3. that ldap in the Redis hash `leave:employment`, written only by the nightly
   employment sync (`leave/employment_sync_service.py`, called from the daily
   `update-ldap` cronjob `/api/microsoft/backfill/ldaps`, 10:20 UTC) for
   full-time employees in a `CN-` office, with every other key `HDEL`ed;
4. a `manager_ldap` in that profile;
5. `<manager_ldap>@circlecat.org`, confirmed, on a purrf account with
   `is_internal = true`
   (`leave/leave_participants.py`); that account becomes
   `leave_request.approver_user_id`, snapshotted;
6. company holidays entered for every year the leave touches
   (`load_calendar`), and so on.

The approver therefore always comes from Azure via Redis, never from the
request. On test the hash holds 5 profiles (3 accruing: user 259 `jxie`, 120
`yuji`, 154 `wuyu`; read from `GET /api/leave/balances` on 2026-10-16).

The test accounts (267, 276, 277, 279, 280) hold no confirmed
`@circlecat.org` address, and global setup refuses to run if one holds any
address but the test mailbox or an `+e2e-…` alias of it
(`checkAccountEmails` in `lib/seed.js`). So **every `POST /api/leave/requests` from a test account
is refused at step 2** ("This account has no corporate address, so its Azure
record cannot be found.") or at step 1, before anything is written. It cannot
reach a real manager.

Deciding and withdrawing are checked against the stored rows only:
`decide` requires `leave_request.approver_user_id == caller` and
`approval_request.reviewer_id == caller`; `withdraw` requires
`leave_request.user_id == caller` and `approval_request.raised_by == caller`.
A test account can only ever act on a request whose other party the seed
chose.

## Mail, notifications, calendar, Graph, Redis

- **Bell notifications become email**, as in the other layers: `record_event`
  writes one `notification` per recipient (minus the actor, blocked and
  deactivated users), publishes to Pub/Sub after commit, and
  `/api/notifications/deliver` mails the recipient's contact email (primary
  row, else oldest) from `GMAIL_SENDER_NOTIFICATION`
  (test: `notification-test@circlecat.org`). No Cc, no Bcc.
- Leave events and recipients (`leave/recipient_resolvers.py`), all read
  from the `approval_request` row the event names:

  | Write                         | Event                                          | Recipient                    |
  | ----------------------------- | ---------------------------------------------- | ---------------------------- |
  | file (not auto-approved sick) | `leave.request_submitted`                      | `reviewer_id` (the approver) |
  | file sick ≤ 24 h              | none (auto-approved, no approval row)          | nobody                       |
  | approve / reject              | `leave.request_decided`                        | `raised_by` (the employee)   |
  | withdraw                      | `leave.request_decided` (`decision=withdrawn`) | `reviewer_id` (the approver) |
  | refused approval (409)        | none                                           | nobody                       |
  | holidays, adjustment          | none                                           | nobody                       |

  `leave.request_reassigned` exists only to satisfy the handler contract and
  is never recorded. No leave event fans out to a permission's holders.
  Bodies (`leave/notification_email_copy.py`) carry the employee's name, the
  leave type and dates, and the employee's reason or manager's comment.

- **No Calendar, Teams, Graph, Auth0 or Kit** call on any leave route. Graph
  is read only by the nightly sync, which the suite neither triggers nor
  needs.
- **Redis**: `submit`, `coverage` (`GET /api/leave/me`) and
  `GET /api/leave/balances` read `leave:employment`. No route writes it; the
  suite never touches Redis.
- Approval rows are filtered by action everywhere else they are listed
  (`MENTORSHIP_ACTIONS`, `BLOCK_USER`, job reviews), so a seeded
  `leave_approval` row never shows up in another layer's queue.

## Cron

- `leave-weekly-accrual` (Sun 20:10 UTC) and `leave-annual-close` (1 Jan
  00:10 UTC) are `suspend: true` in `helm/purrf/values.yaml`; `values-test.yaml`
  does not override them. Consistent with the database: test's ledger holds no
  `weekly_accrual` or `carryover_forfeit` row at all. (Not checked against
  the live CronJob objects: no kube context here.) Even unsuspended they pay
  only the Redis population, never a seed person or a test account (neither
  has a confirmed corporate address).
- `update-ldap` (daily 10:20 UTC) runs the employment sync: it rewrites
  `leave:employment` from Graph and appends a zero-hour `level_change` row for
  a real person whose level changed. It touches nothing the suite owns.

## Global data: company holidays

`leave_holiday` is one calendar for everybody: a year's rows decide the hours
of every request dated in it, and an empty year refuses every request in it.
On test **no year has any holidays** (so nobody, real or not, can currently
file on test). `PUT /api/leave/holidays/{year}` replaces the whole year.

The suite uses two years nobody else can use:

- **2019** (past): the Yearly setup spec edits it through the UI. A request
  can never be filed or approved in the past (`submit` and
  `problems_at_approval` both refuse a start before today), and the accrual
  engine never reads holidays, so 2019 rows change nobody's hours.
- **2099** (far future): seeded by SQL only, never edited through the UI. It
  exists so seeded requests can be approved: approving recounts the hours
  against the calendar of the request's years and refuses if a year is
  empty. `load_calendar` only requires the years the leave itself covers, so
  2026–2098 may stay empty. Cost: approving a 2099 request reads 74 years of
  holiday rows (one query each).

Visible to real people while a run lasts: both years appear in the year
picker of Yearly setup (admins) and of the Company holidays dialog (every
employee with the Time off card), named `E2E …`.

## What the suite seeds

All by SQL in `seed/leave-seed.sql`; nothing is filed through the API.

- **Seed employees 990501–990510**, each with one address,
  `wangyanpei76+e2e-leave-<n>@gmail.com`, primary and confirmed; no
  `@circlecat.org` address; not in Redis. 990507 has `is_active = false`;
  990510 ("E2E Leave Adjust", 52 h) exists only for the balance correction.
- **Holidays**: 2019 one `E2E …` segment; 2099 one non-exchangeable segment
  and one exchangeable day, all named `E2E …`.
- **Requests** with `approver_user_id = 276` (e2e-reviewer) for every seed
  employee and for e2e-member (279), each with its `approval_request`
  (`action='leave_approval'`, `raised_by` = the employee, `reviewer_id` =
  276), pending or already closed.
- **Ledger** rows for e2e-member and some seed employees (opening balance as
  `manual_adjustment`, past `leave_deduction`), dated in 2019 or earlier this
  year.
- No `event` or `notification` rows (a pending notification would be
  republished by the straggler sweep).

Global setup refuses to seed if a 2019 or 2099 holiday is not named `E2E …`,
or if any test account or id in 990501–990599 already holds a leave row the
cleanup would not remove.

## What the suite lets out

`lib/guard.js` allows a leave write only when:

| Write                                    | Let out when                                                                                                                                                 | Real mail                                               |
| ---------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------- |
| `POST /api/leave/requests`               | the role is a test account (global setup has proved it holds no company address, so the server refuses before writing; the spec declares the 400)            | none                                                    |
| `POST /api/leave/requests/{id}/withdraw` | the request is the suite's: in the DB its `user_id` is a seed employee or a test account, its `approver_user_id` a test account, and its approval row agrees | **let out**: bell email to e2e-reviewer                 |
| `POST /api/leave/requests/{id}/decision` | same suite-request check                                                                                                                                     | **let out**: bell email to the seed alias or e2e-member |
| `PUT /api/leave/holidays/{year}`         | `year` is 2019; every segment in the body is named `E2E …`; every row 2019 holds now is named `E2E …`                                                        | none                                                    |
| `POST /api/leave/adjustments`            | `userId` is a seed employee (990501–990599)                                                                                                                  | none                                                    |
| `POST /api/leave/jobs/*`                 | never                                                                                                                                                        | —                                                       |

Everything else under `/api/leave/` is refused and fails the test. Specs
assert what Purrf records (request and approval status, ledger rows, the
`event` and the one `notification` row and its `user_id`); nobody reads the
mailbox.

Teardown fingerprints the real leave data and warns if anything moved:

- `leave_request` not held by or filed against a suite person: count, ids,
  statuses, max `updated_timestamp` (today: 8 rows, users 154/156, approver
  120, all from 2026-09-29, none with an approval row);
- `leave_ledger` of everybody else: count, sum, max id (today: 2 rows);
- `leave_holiday` outside 2019/2099 or not named `E2E …` (today: none);
- `approval_request` with `action='leave_approval'` not raised by a suite
  person, and the count of `leave.*` events not about a suite request.

`seed/leave-cleanup.sql` then removes, in FK order: `event` rows on suite
requests (their notifications cascade), their `approval_request` rows,
ledger rows of seed employees and test accounts, suite requests, `E2E …`
holidays in 2019 and 2099, and the seed employees (`approval_request`
references users without a cascade, so it goes first).

## Not tested, and why

- **Filing a request successfully** (`POST /api/leave/requests` returning
  201), and so `leave.request_submitted`, sick auto-approval, the overlap
  check, short-notice marking and the exchange checks on filing. It needs a
  confirmed corporate address on the filing test account plus a `leave:employment`
  profile in test's Redis whose manager is an internal account with a
  corporate address. The first breaks global setup's address check
  (`checkAccountEmails`), and an internal approver would have to be a test
  account flipped to `is_internal` (internal users must keep a company
  address as primary, `authentication/email_management_service.py`); the second means the
  suite writing to shared Redis, which the nightly sync would also delete.
  Yuji decided (2026-10-16) not to: only the refusals are tested (a past
  start, and "no corporate address" for a valid one).
- **Correcting a balance through the dialog**: the Balances list holds only
  the Redis population (real employees), so the guard aborts "Yes, write it"
  on any row; one spec proves the abort. The successful correction is made
  through `POST /api/leave/adjustments` directly, for 990510 (the server
  accepts any existing user; nothing is injected into a response), and the
  spec checks the returned balance and the `manual_adjustment` row.
- **A holiday with a blank name**: the guard only lets out 2019 bodies whose
  every segment is named `E2E …`, so the server's "Every company holiday
  needs a name." is not reached.
- **Editing this year or next year** (the Beijing year the run starts in,
  and the one after) or any year with real holidays: global; the guard
  aborts it. The guard spec tries next year, computed at run time.
- **The accrual and annual-close jobs**: they write every real employee's
  ledger; no test account may call them anyway.
- **Approval by a real manager, or a request from a real employee**: the
  server only lets a test account act on rows naming it; the seed never
  names a real person.
