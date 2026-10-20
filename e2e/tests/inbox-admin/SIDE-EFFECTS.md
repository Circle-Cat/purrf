# Inbox and account console e2e: side effects audit

What each Inbox, account console and permission page write does outside its
own rows on test, who it reaches, and whether the suite lets it out. Read
from the backend deployed on test (main at `5c2dbbed`, 2026-10-15); the
direct block row re-read on main at `1ee0fdbc` (2026-10-20). Paths are
under `backend/`.

## Inbox

Routes: `communication/inbox_controller.py`; writes:
`communication/inbox_writes.py`. Every route needs one of
`mentorship.admin.write`, `recruiting.application.advance`,
`inquiries.manage`; each thread is then checked against the viewer's
services, and one the viewer cannot see answers 400 as if it did not exist.

| Write                     | Gmail                                                                                                                                                       | Events and who they notify (`communication/recipient_resolvers.py`)                                                                                                        |
| ------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Reply (`POST …/reply`)    | **Sends** through Gmail as the service alias (Send-As), into the thread's Gmail thread, to `reply_contact`: the newest human inbound sender. No Cc, no Bcc. | none                                                                                                                                                                       |
| Archive / Unarchive       | none (no label change)                                                                                                                                      | `inbox.archived` / `inbox.unarchived`: nobody                                                                                                                              |
| File (`PUT …/assignment`) | none                                                                                                                                                        | `inbox.assigned`: nobody                                                                                                                                                   |
| Transfer (`POST …/move`)  | none                                                                                                                                                        | `inbox.moved`: nobody. **If the thread needs a reply**, also `inbox.needs_reply` to every active holder of the target service's permission (real staff), by bell and email |
| Attachment download       | reads the attachment from Gmail                                                                                                                             | none                                                                                                                                                                       |

- Reply is refused with 409 `THREAD_CHANGED` before anything is sent when a
  newer message is stored than the one the sender last saw.
- Inbound mail is claimed by the alias it was sent to
  (`communication/inbox_router.py`): the sender plays no part. Test and
  staging share the mailbox and aliases; only test has
  `GMAIL_INBOX_ENABLED`, so only test claims new mail. The thread is stored
  with `user_id` empty: the person is matched by the sender address
  (`user_emails`, primary or alternative) each time the list is read, and
  only filing sets `user_id`. Each new thread that needs a reply notifies
  every holder of the service's permission (`inbox.needs_reply`), real staff
  included.
- **Sync and deleted rows.** Gmail history is read for `messageAdded` only
  (`common/gmail_client.py:list_history`), and a thread is synced by listing
  its Gmail message ids and storing the ones missing from the database
  (`email_conversation_service.sync_thread`). A message row deleted from the
  database therefore comes back the next time a message is added to that
  Gmail thread, or in a full resync (manual, or after the history cursor
  expires), or when a participant page's email refresh reads a thread filed
  there. A thread whose Gmail id does not exist (the suite's inserted
  `e2e-…` threads) would fail that sync: the full resync logs and counts it
  and moves on (`inbox_sync_handler.resync_all`), and the participant
  refresh would answer an error, which is why inserted threads are never
  filed and never live past their test.
- Cron: `gmail-watch-maintain` (daily 11:15 UTC) renews the watch and catches
  up from the history cursor; it only reaches threads Gmail reports as
  changed. Nothing else reads Inbox threads on a schedule.
- Auth0: none.

### What the suite lets out

The four real threads Yuji sent from the test mailbox (`wangyanpei76@gmail.com`)
on 2026-10-15 to the test aliases are the suite's and are reused every run:

| Thread | Subject                  | Sent to                         | Used for                                        |
| ------ | ------------------------ | ------------------------------- | ----------------------------------------------- |
| 14     | `E2E inbox recruiting 1` | `recruiting-test@circlecat.org` | File to Candidate R01's seeded application      |
| 15     | `E2E inbox mentorship 1` | `mentorship-test@circlecat.org` | File to Mentee R1; Reply; Transfer once replied |
| 19     | `E2E inbox inquiries 1`  | `inquiries-test@circlecat.org`  | reading, the attachment (a 380 KB jpeg)         |
| 21     | `E2E inbox inquiries 2`  | `inquiries-test@circlecat.org`  | Archive, Unarchive, back on new mail            |

They are recognised by subject (`E2E inbox …`) and by every inbound sender
being the test mailbox or an e2e alias of it. The suite also inserts
threads of its own straight into the database (`gmail_thread_id` and
`gmail_message_id` `e2e-…`): list and filter fixtures, the HTML rendering
check, the Transfer of a thread that needs no reply, the access checks.

`lib/guard.js` lets an Inbox write out only when the thread is one of
these (checked in the database on every call), and:

| Write     | Let out when                                                                                                        | Real mail                                                        |
| --------- | ------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------- |
| Reply     | a real suite thread (an inserted one has no Gmail thread) whose newest human sender is the test mailbox or an alias | **let out**: from `mentorship-test@` to `wangyanpei76@gmail.com` |
| Archive   | always                                                                                                              | none                                                             |
| Unarchive | always                                                                                                              | none                                                             |
| File      | the person is seeded (id ≥ 990001), and the round is seeded or the application is a seeded one                      | none                                                             |
| Transfer  | the thread needs no reply (no human inbound newer than our last outbound), so `inbox.needs_reply` is not raised     | none                                                             |

Between tests and in setup and teardown, `seed/inbox-thread-reset.sql` puts
the real threads back: unfiled, unarchived, in the service of the alias
they were sent to, without outbound rows, without inserted inbound rows,
without events a person recorded on them (the sync's own `inbox.needs_reply`
from arrival stays); and deletes every inserted thread. It runs before the
mentorship and recruiting cleanups, because a real thread filed to a seeded
person or application would otherwise be deleted with them
(`email_thread.user_id` cascades). The replies the suite sent stay in Gmail
and come back into the database when the thread next syncs; the next reset
removes them again.

## Account console (`/admin/accounts`)

Routes: `admin/user_account_controller.py`, `admin/block_controller.py`;
gate `user.admin` (raising a block request: the permission of the page it
comes from, `RAISE_PERMISSION_BY_SOURCE`).

| Write                        | Effect beyond the user row                                                                                                                                                                                                                                                                                                                                                                 | Notified (`user_identity/user_recipient_resolvers.py`)                                                                                                                                             |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Deactivate / Reactivate      | `user.deactivated` / `user.reactivated` on the timeline                                                                                                                                                                                                                                                                                                                                    | nobody                                                                                                                                                                                             |
| Block directly               | `apply_block_kernel`: ends the person's mentorship pairs in rounds under way (cancelling their meetings on Google Calendar), rejects and tags every application, cancels their booked interviews (Calendar invites to attendees); `user.blocked`; closes a pending request as superseded (`approval_service.supersede_pending`: `user.block_request_decided` with `decision` `superseded`) | applications' posting owners (`blacklisted`), Calendar attendees; for a superseded request its raiser and its reviewer, the blocker left out (`event_recorder` drops the actor); the person nobody |
| Unblock                      | `user.unblocked`                                                                                                                                                                                                                                                                                                                                                                           | nobody                                                                                                                                                                                             |
| Raise a request              | `user.block_requested`                                                                                                                                                                                                                                                                                                                                                                     | the named reviewer                                                                                                                                                                                 |
| Reassign (raiser only)       | `user.block_request_reassigned`                                                                                                                                                                                                                                                                                                                                                            | new and previous reviewer                                                                                                                                                                          |
| Decide (named reviewer only) | approve runs `apply_block_kernel`; `user.block_request_decided`                                                                                                                                                                                                                                                                                                                            | the raiser                                                                                                                                                                                         |
| Withdraw (raiser only)       | `user.block_request_decided`                                                                                                                                                                                                                                                                                                                                                               | the reviewer                                                                                                                                                                                       |

- **Auth0: none.** Neither deactivation (`users_repository.deactivate`) nor
  any block path calls it; `common/auth0_client.py` is only used by sign-in
  and email management. Deactivated and blocked accounts are stopped by the
  auth middleware (`utils/auth_middleware.py`), which checks `is_active`
  first, then `is_blocked`, on every request.
- The person deactivated or blocked is never a recipient.
- Cron: none reads these rows.

## Permission page (`/admin/users`)

Gate `permission.manage`. Grant and revoke write `user_permissions` rows
(the audit log is those rows); no event, no notification, no Auth0. A grant
changes what the person can reach and which pickers list them
(`get_active_users_with_permission`), so the suite grants only
`internal_activity.read`, which feeds no picker or notification.

## What the suite lets out

The seed (`seed/inbox-admin-seed.sql`) creates nine ops people, user ids
990301–990309, external, whose only addresses are confirmed
`wangyanpei76+e2e-ops-<n>@gmail.com` aliases (Ops Search also has
`…e2e-ops-3-alt@…`); they have no applications, pairs, meetings or
identities, so a block reaches nothing beyond their own row.

| Write                                                                        | Let out when                                            | Real mail                                                                                |
| ---------------------------------------------------------------------------- | ------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| `POST /api/admin/accounts/{id}/deactivate`, `reactivate`, `block`, `unblock` | `{id}` is seeded (≥ 990001, created by setup)           | none; a `block` that supersedes a suite request: bell email to its test-account reviewer |
| `POST /api/admin/users/{id}/permissions/grant`, `revoke`                     | `{id}` is seeded                                        | none                                                                                     |
| `POST /api/admin/users/{id}/super-admin`                                     | never                                                   | —                                                                                        |
| `POST /api/block-requests`                                                   | the person is seeded; the reviewer a test account       | bell email to e2e-reviewer                                                               |
| reassign / decide / withdraw                                                 | a request the suite raised; new reviewer a test account | bell email to test accounts                                                              |

No test account is ever deactivated, blocked or granted anything by a spec
(global setup still tops up their own lists, straight in the database).

Teardown fingerprints, before and after: how many real users (below
990001, test accounts aside) are deactivated and blocked, their active and
total permission grants, block requests about them, the test accounts'
`is_active`/`is_blocked`, every mail thread that is not the suite's (service,
person, filing, archive, message count), and the suite's real threads, which
must be back as setup found them.

## Not tested, and why

- **The 403 a deactivated or blocked person gets.** It needs that person
  signed in; the ops people cannot sign in, and no test account may be
  deactivated or blocked (later tests would all fail to sign in). The specs
  check the row, the console and the timeline instead.
- **Transfer of a thread that needs a reply**: notifies every holder of the
  target service's permission, real staff included. The guard refuses it and
  a spec proves the refusal.
- **Reply on an inserted thread**: there is no Gmail thread to reply into.
- **Withdrawing a block request** from the console: there is no withdraw
  control there; the mentorship and recruiting block specs withdraw from
  their pages.
- **Super-admin grant and revoke**, and granting any permission to a real
  person or a test account.
- **The Inbox's own notifications** (`inbox.needs_reply` on new mail,
  `inbox.bounced`): raised by the Gmail sync, not by anything the suite does;
  inserting rows does not raise them.
