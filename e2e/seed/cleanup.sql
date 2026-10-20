-- Removes what seed.sql created and what the e2e suite did there.
--
--   psql "$E2E_DATABASE_URL" -X -v ON_ERROR_STOP=1 \
--        -v member_id=<e2e-member user_id> -f e2e/seed/cleanup.sql
--
-- Idempotent. What it removes is fixed by two sets and nothing else:
--   seeded rounds  every round named "E2E seed …", with everything in or
--                  about it: registrations, pairs (with meetings), notes,
--                  approval requests (about a participant, a pair, or
--                  publishing its matching run), Kit email sends, and the
--                  events and notifications recorded about them. That is any
--                  user's rows in those rounds: a real tester who registered
--                  into the registration round during a run loses that
--                  registration, which is accepted (the round is the suite's
--                  and goes too).
--   seeded users   user_id 990001-990099 whose every email ends @e2e.purrf.test
--                  (every round, every table).
-- Plus e2e-member's tagged application (seed.sql's "e2e" tag).
--
-- Rows of real people can go only where they hang off the sets above: a note
-- or a pair of a real person whose pair partner is seeded, or the
-- approval_requested / approval_decided notifications sent to the reviewer
-- accounts.
--
-- Not cleaned here:
--   * Matching run state in Redis (run envelope, groups, results, draft edits,
--     edit locks), keyed by round id. Round ids are never reused, so it is
--     inert once the round is gone.
--   * Anything sent out of the database: emails, Google Calendar events for
--     meetings, Auth0 state.
--   * e2e-member's onboarding training row (seed.sql sets it to done), their
--     global mentorship preferences (registering rewrites them with what the
--     form had), and any email_thread on e2e-member; mail threads of seeded
--     users cascade away.
--   * The users_user_id_seq and mentorship_round_round_id_seq sequences.
-- No other round is ever touched: every round-scoped delete is keyed on the
-- E2E seed round ids.

\set ON_ERROR_STOP on

\if :{?member_id}
\else
  \echo 'cleanup.sql: pass -v member_id=<id>'
  \quit
\endif

BEGIN;

CREATE TEMP TABLE e2e_rounds ON COMMIT DROP AS
SELECT round_id FROM mentorship_round WHERE name LIKE 'E2E seed %';

CREATE TEMP TABLE e2e_users ON COMMIT DROP AS
SELECT u.user_id
FROM users u
WHERE u.user_id BETWEEN 990001 AND 990099
  AND EXISTS (SELECT 1 FROM user_emails e
              WHERE e.user_id = u.user_id AND e.email LIKE '%@e2e.purrf.test')
  AND NOT EXISTS (SELECT 1 FROM user_emails e
                  WHERE e.user_id = u.user_id AND e.email NOT LIKE '%@e2e.purrf.test');

CREATE TEMP TABLE e2e_pairs ON COMMIT DROP AS
SELECT p.pair_id
FROM mentorship_pairs p
WHERE p.round_id IN (SELECT round_id FROM e2e_rounds)
   OR p.mentor_id IN (SELECT user_id FROM e2e_users)
   OR p.mentee_id IN (SELECT user_id FROM e2e_users);

CREATE TEMP TABLE e2e_sends ON COMMIT DROP AS
SELECT send_id FROM mentorship_email_send
WHERE round_id IN (SELECT round_id FROM e2e_rounds);

-- Target ids: round_participant -> '<round_id>:<user_id>',
-- mentorship_pair -> '<pair_id>', user (block_user) -> '<user_id>',
-- matching_run -> the run id, with the round in payload.round_id.
CREATE TEMP TABLE e2e_requests ON COMMIT DROP AS
SELECT r.request_id
FROM approval_request r
WHERE (r.target_type = 'round_participant'
       AND (split_part(r.target_id, ':', 1) IN (SELECT round_id::text FROM e2e_rounds)
            OR split_part(r.target_id, ':', 2) IN (SELECT user_id::text FROM e2e_users)))
   OR (r.target_type = 'mentorship_pair'
       AND r.target_id IN (SELECT pair_id::text FROM e2e_pairs))
   OR (r.target_type = 'user'
       AND r.target_id IN (SELECT user_id::text FROM e2e_users))
   OR (r.target_type = 'matching_run'
       AND r.payload ->> 'round_id' IN (SELECT round_id::text FROM e2e_rounds));

CREATE TEMP TABLE e2e_events ON COMMIT DROP AS
SELECT ev.event_id
FROM event ev
WHERE (ev.details ? 'requestId'
       AND ev.details ->> 'requestId' IN (SELECT request_id::text FROM e2e_requests))
   OR (ev.subject_type = 'mentorship_round'
       AND ev.subject_id IN (SELECT round_id FROM e2e_rounds))
   OR (ev.subject_type = 'mentorship_email_send'
       AND ev.subject_id IN (SELECT send_id FROM e2e_sends))
   OR (ev.subject_type = 'user'
       AND ev.subject_id IN (SELECT user_id FROM e2e_users))
   OR ev.actor_id IN (SELECT user_id FROM e2e_users);

DELETE FROM notification
WHERE event_id IN (SELECT event_id FROM e2e_events)
   OR user_id IN (SELECT user_id FROM e2e_users);

DELETE FROM event WHERE event_id IN (SELECT event_id FROM e2e_events);

-- Notes before pairs and requests: both are referenced without cascade.
DELETE FROM mentorship_participant_note
WHERE round_id IN (SELECT round_id FROM e2e_rounds)
   OR user_id IN (SELECT user_id FROM e2e_users)
   OR pair_id IN (SELECT pair_id FROM e2e_pairs)
   OR request_id IN (SELECT request_id FROM e2e_requests);

DELETE FROM approval_request WHERE request_id IN (SELECT request_id FROM e2e_requests);

DELETE FROM mentorship_meeting WHERE pair_id IN (SELECT pair_id FROM e2e_pairs);

DELETE FROM mentorship_pairs WHERE pair_id IN (SELECT pair_id FROM e2e_pairs);

DELETE FROM mentorship_round_participants
WHERE round_id IN (SELECT round_id FROM e2e_rounds)
   OR user_id IN (SELECT user_id FROM e2e_users);

DELETE FROM mentorship_email_recipient
WHERE send_id IN (SELECT send_id FROM e2e_sends)
   OR user_id IN (SELECT user_id FROM e2e_users);

DELETE FROM mentorship_email_send WHERE send_id IN (SELECT send_id FROM e2e_sends);

DELETE FROM training_progress
WHERE training_id IN (SELECT training_id FROM training
                      WHERE user_id IN (SELECT user_id FROM e2e_users));

DELETE FROM training WHERE user_id IN (SELECT user_id FROM e2e_users);

DELETE FROM application WHERE user_id = :member_id AND tags ->> 'e2e' = 'true';

-- Seeded people's own applications (Mentor H-M1's admission).
DELETE FROM application WHERE user_id IN (SELECT user_id FROM e2e_users);

DELETE FROM user_identities WHERE user_id IN (SELECT user_id FROM e2e_users);

DELETE FROM user_permissions WHERE user_id IN (SELECT user_id FROM e2e_users);

DELETE FROM user_emails WHERE user_id IN (SELECT user_id FROM e2e_users);

-- Block state (is_blocked, blocked_by/at/reason) lives on these rows and goes
-- with them. Anything else that still references a seeded user without a
-- cascade (a request they raised or reviewed, a permission they granted)
-- makes this fail and the whole cleanup roll back rather than guess.
DELETE FROM users WHERE user_id IN (SELECT user_id FROM e2e_users);

DELETE FROM mentorship_round WHERE round_id IN (SELECT round_id FROM e2e_rounds);

SELECT (SELECT count(*) FROM e2e_rounds)   AS rounds_removed,
       (SELECT count(*) FROM e2e_users)    AS users_removed,
       (SELECT count(*) FROM e2e_pairs)    AS pairs_removed,
       (SELECT count(*) FROM e2e_requests) AS requests_removed,
       (SELECT count(*) FROM e2e_events)   AS events_removed;

-- Rounds the round-form test created: named "E2E ...", every date at least
-- 30 days ago, and nothing pointing at them. A real round can match none of
-- the three.
DELETE FROM mentorship_round r
WHERE r.name LIKE 'E2E %'
  AND GREATEST(
        r.promotion_start_at, r.mentor_application_deadline_at,
        r.mentee_application_deadline_at, r.onboarding_notification_at,
        r.onboarding_deadline_at, r.match_notification_at,
        r.first_meeting_deadline_at, r.meeting_log_reminder_at,
        r.meetings_completion_deadline_at, r.feedback_start_at,
        r.feedback_deadline_at
      ) < now() - interval '30 days'
  AND NOT EXISTS (SELECT 1 FROM mentorship_round_participants p WHERE p.round_id = r.round_id)
  AND NOT EXISTS (SELECT 1 FROM mentorship_pairs p WHERE p.round_id = r.round_id)
  AND NOT EXISTS (SELECT 1 FROM mentorship_participant_note n WHERE n.round_id = r.round_id)
  AND NOT EXISTS (SELECT 1 FROM mentorship_email_send s WHERE s.round_id = r.round_id);

COMMIT;
