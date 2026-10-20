# Recruiting e2e: side effects audit

What each recruiting write does outside the database on test, who it reaches,
and whether the suite lets it out. Read from the backend at the commit the
suite was written against (main as of 2026-10-15). Paths are under
`backend/`.

## How mail and invites leave Purrf on test

- There is no non-prod allowlist or redirect anywhere in the mail path. Test
  sends real Gmail and real Calendar invites.
- **Bell notifications become email.** `record_event`
  (`notification_management/event_recorder.py`) writes one notification row
  per resolved recipient (minus the actor, blocked and deactivated users),
  publishes each to Pub/Sub after commit, and `/api/notifications/deliver`
  emails it (`notification_event_email_service.py`).
  - To: the recipient's contact email, i.e. primary row, else oldest claim;
    not filtered by `otp_confirmed` (`repository/user_emails_repository.py`).
  - From: `GMAIL_SENDER_NOTIFICATION` (test: `notification-test@circlecat.org`).
  - No Cc or Bcc.
  - A `PENDING` row older than the claim timeout is republished by the
    straggler sweep, so the seed never inserts notification rows.
- **Candidate email** (`POST /api/recruiting/applications/{id}/emails`,
  `recruiting/board_service.py:send_application_email`): Gmail API,
  synchronous.
  - From: `GMAIL_SENDER_RECRUITING` (test: `recruiting-test@circlecat.org`).
  - To, new thread: the `to[]` of the request, each of which the server
    requires to be one of the candidate's `otp_confirmed` addresses
    (`communication/person_email_service.py`); anything else is a 400.
  - To, reply (`threadId` set): the thread's last inbound sender, which the
    request does not name.
  - No Cc or Bcc.
- **Interview calendar** (`recruiting/interview_scheduling_service.py`,
  `service/google_service.py`): events on `INTERVIEW_CALENDAR_ID`, which test
  shares with staging; insert, update and delete all use `sendUpdates="all"`.
  - Attendees on booking: the candidate, the `assigneeId` of the request and
    the signed-in user, each at their contact email.
  - Attendees on update: the candidate, `assigneeId` and the original
    `scheduled_by`.
  - Cancel (DELETE, or `cancelInterview` on a stage or round change) mails
    the same attendees.
- **Auth0**: no recruiting or block-request path calls it. Approving a block
  only sets `users.is_blocked` (`admin/block_service.py:apply_block_kernel`).
- **Résumé upload**: writes an object to `RESUME_BUCKET`. Parsing is
  client-side. No LLM call anywhere in recruiting.
- **Cron**: no scheduled job reads recruiting rows or sends reminders or
  digests (`helm/purrf/values.yaml` cronjobs; no Cloud Scheduler). The daily
  `gmail-watch-maintain` only touches existing mail threads.

## Who each write reaches

Recipients of bell notifications (and so of their email), from
`recruiting/recipient_resolvers.py`:

| Write                                      | Event                                                                                                                                                                                    | Recipients                                                       | Set by                          |
| ------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------- | ------------------------------- |
| create / edit / discard / delete posting   | `job_created` or none                                                                                                                                                                    | nobody                                                           | —                               |
| submit, request close, request reopen      | `review_opened`                                                                                                                                                                          | the `reviewerId` picked                                          | request body                    |
| change reviewer                            | `review_reassigned`                                                                                                                                                                      | the new reviewer                                                 | request body                    |
| approve / reject review                    | `review_decided`                                                                                                                                                                         | the submitter                                                    | who submitted                   |
| withdraw review                            | `review_decided`                                                                                                                                                                         | the reviewer                                                     | earlier request                 |
| apply (and edit while Applied)             | `application_submitted` / `auto_rejected`                                                                                                                                                | posting owners (`pipelineConfig.ownerIds`)                       | posting                         |
| apply onto a stage with a default assignee | `auto_assigned`                                                                                                                                                                          | that assignee                                                    | posting                         |
| stage / round change                       | `stage_changed`, `round_advanced`                                                                                                                                                        | owners + current assignee                                        | posting + body                  |
| sub-status                                 | `sub_status_changed`                                                                                                                                                                     | owners                                                           | posting                         |
| reassign interviewer                       | `reassigned`                                                                                                                                                                             | owners + new assignee                                            | posting + body                  |
| book / move / cancel interview             | `interview_*`                                                                                                                                                                            | owners + assignee, plus Google's invite to the attendees above   | posting + body + signed-in user |
| confirm evaluation                         | `evaluation_confirmed`                                                                                                                                                                   | owners                                                           | posting                         |
| comment with `@[id]`                       | `mentioned`                                                                                                                                                                              | the mentioned users (only owners or the assignee can be)         | body                            |
| candidate email                            | `email_sent`                                                                                                                                                                             | nobody (plus the email itself)                                   | body                            |
| hired                                      | training row for mentor/mentee activity postings only; `mentor_admitted` email to the candidate for mentor activity postings                                                             | candidate                                                        | posting kind                    |
| raise / withdraw block request             | `block_requested` / decided                                                                                                                                                              | the `reviewerId` picked / the raiser                             | body                            |
| reassign block request                     |                                                                                                                                                                                          | new and previous reviewer                                        | body                            |
| approve block                              | `user.blocked` (nobody); `blacklisted` per application of the person on **every** posting, to that posting's owners; cancels the person's interviews and mentorship meetings on Calendar | owners of every posting the person applied to, meeting attendees | the person's whole history      |

No recruiting write fans out to "every holder of a permission". The only
such resolvers are the Inbox ones (`inbox.needs_reply` to every holder of
`recruiting.application.advance`, fired by inbound mail that matches no
application thread) and the ops Gmail-sync alert; nothing the suite does
raises them.

## What the suite lets out

The seed makes every person the flows can reach a test account or an alias
of the test mailbox:

- Seeded postings and every posting the specs create are owned by e2e-admin
  alone, with no default assignee except test accounts.
- Seed candidates (user ids 990101–990134) hold only
  `wangyanpei76+e2e-cand-<n>@gmail.com` addresses, primary and confirmed.
- Global setup refuses to run if any test account (267, 276, 277, 279, 280)
  holds an address other than the test mailbox or an e2e alias of it.

`lib/guard.js` then allows a recruiting write only when everything it names
belongs to the suite, and fails the test otherwise:

| Write                                                            | Let out when                                                          | Real mail or invite                                                             |
| ---------------------------------------------------------------- | --------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| `POST /api/recruiting/jobs`                                      | titled `E2E …`, owners and default assignees are test accounts        | none                                                                            |
| `PUT /api/recruiting/jobs/{id}`                                  | the suite's posting, still `E2E …`, same people rule                  | none                                                                            |
| submit / close / reopen / reviewer / withdraw / discard / delete | the suite's posting; `reviewerId` a test account                      | bell email to a test account                                                    |
| `PATCH /api/recruiting/reviews/{id}`                             | the review is on a suite posting                                      | bell email to e2e-admin                                                         |
| `POST /api/recruiting/applications`                              | the posting is the suite's                                            | bell email to e2e-admin                                                         |
| stage / sub-status / round / assignment                          | a seeded or suite application; `assigneeId` a test account            | bell email to test accounts                                                     |
| `POST/PATCH/DELETE …/interview`                                  | a seeded or suite application; `assigneeId` a test account            | **let out**: Calendar invite to the alias candidate, e2e-reviewer and e2e-admin |
| `PUT …/evaluation`                                               | a seeded or suite application                                         | bell email to e2e-admin                                                         |
| `POST …/comments`                                                | a seeded or suite application; every `@[id]` a test account           | bell email to a test account                                                    |
| `POST …/emails`                                                  | a seeded or suite application; no `threadId`; every `to` an e2e alias | **let out**: Gmail from recruiting-test@ to the alias                           |
| `POST /api/block-requests`                                       | the person is seeded; `reviewerId` a test account                     | bell email to e2e-reviewer                                                      |
| block reassign / withdraw / decide                               | a request the suite raised; new reviewer a test account               | bell email to test accounts                                                     |
| `POST /api/recruiting/resumes`                                   | never                                                                 | —                                                                               |
| Kit, mentorship single sends and replies                         | never                                                                 | —                                                                               |

Specs only assert what Purrf records: the request succeeded, the timeline or
thread shows the send, the interview row carries a calendar event id. Nobody
reads the mailbox.

Calendar events: the interview spec cancels what it books through the
board's own Cancel button; global teardown then cancels any interview still
booked on a suite application (`DELETE …/interview`, which deletes the
Google event and mails the test attendees) before the SQL cleanup. While a
run lasts the events are visible on the interview calendar test shares with
staging.

## Not tested, and why

- **Replies to a candidate thread** (`emails` with `threadId`): the reply goes
  to the thread's last inbound sender, which the request does not name and
  the guard cannot check. Blocked.
- **Blocking a test account or anyone with history** (approving a block):
  sweeps every application of the person on every posting and notifies the
  owners of each (real staff for real postings), and cancels their meetings.
  Only seed Candidate K1, whose one application is on a suite posting, is
  ever blocked.
- **Hiring onto a mentor activity posting**: emails the candidate and
  assigns training; the suite's postings are employment postings, so the
  hire it tests assigns no training (the spec checks no training row
  appears).
- **Résumé upload**: leaves an object in the test bucket that cleanup cannot
  remove; the suite's postings do not collect résumés.
- **Inbox (unmatched inbound mail)**: notifies every holder of
  `recruiting.application.advance`, real staff included. Nothing the suite
  sends invites a reply, and it never mails the recruiting mailbox.
- Picking reviewers, interviewers or mentions from a list by position: the
  lists hold real staff; specs always pick a test account by user id.
