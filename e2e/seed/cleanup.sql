-- Removes what seed.sql created and what the e2e suite did to those people.
--
--   psql "$E2E_DATABASE_URL" -X -v ON_ERROR_STOP=1 \
--        -v round_id=<same round as the seed> -v member_id=<e2e-member user_id> \
--        -f e2e/seed/cleanup.sql
--
-- Idempotent. What it removes is fixed by two sets and nothing else:
--   seeded users  user_id 990001-990099 whose every email ends @e2e.purrf.test
--                 (every round, every table);
--   e2e-member    only their participation in :round_id: the registration,
--                 notes, pairs (with meetings), and approval requests about it.
-- Their consequences go too: approval requests targeting either set, the
-- events those requests recorded (requestId in details) and the
-- notifications pointing at those events (approval notifications to the real
-- reviewers included), user-subject events about seeded users (the block
-- event), and the Kit email recipient rows of seeded users.
--
-- Rows of real people can go only where they hang off the sets above: a note
-- or a pair of a real person whose pair partner is seeded (e.g. if a test
-- published a matching run that paired a real person with a seeded one).
--
-- Not cleaned here:
--   * Matching run state in Redis (run envelope, groups, results, draft edits,
--     edit locks); a run started on the round stays the round's latest run.
--   * A publish_matching approval request (target matching_run) and the
--     mentorship.matching_run_completed event: they are round-wide, not
--     about one person. Pairs a publish created for seeded people or for
--     e2e-member in :round_id are removed.
--   * Kit broadcasts / mentorship_email_send rows (only seeded recipients go)
--     and anything sent out of the database: emails, Google Calendar events
--     for meetings, Auth0 state.
--   * e2e-member's onboarding training row (seed.sql sets it to done) and any
--     email_thread on e2e-member; mail threads of seeded users cascade away.
--   * The users_user_id_seq sequence is never touched (seed ids are explicit).

\set ON_ERROR_STOP on

\if :{?round_id}
\else
  \echo 'cleanup.sql: pass -v round_id=<id>'
  \quit
\endif
\if :{?member_id}
\else
  \echo 'cleanup.sql: pass -v member_id=<id>'
  \quit
\endif

BEGIN;

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
WHERE p.mentor_id IN (SELECT user_id FROM e2e_users)
   OR p.mentee_id IN (SELECT user_id FROM e2e_users)
   OR (p.round_id = :round_id AND :member_id IN (p.mentor_id, p.mentee_id));

-- Target ids: round_participant -> '<round_id>:<user_id>',
-- mentorship_pair -> '<pair_id>', user (block_user) -> '<user_id>'.
CREATE TEMP TABLE e2e_requests ON COMMIT DROP AS
SELECT r.request_id
FROM approval_request r
WHERE (r.target_type = 'round_participant'
       AND (split_part(r.target_id, ':', 2) IN (SELECT user_id::text FROM e2e_users)
            OR r.target_id = :'round_id' || ':' || :'member_id'))
   OR (r.target_type = 'mentorship_pair'
       AND r.target_id IN (SELECT pair_id::text FROM e2e_pairs))
   OR (r.target_type = 'user'
       AND r.target_id IN (SELECT user_id::text FROM e2e_users));

CREATE TEMP TABLE e2e_events ON COMMIT DROP AS
SELECT ev.event_id
FROM event ev
WHERE (ev.details ? 'requestId'
       AND ev.details ->> 'requestId' IN (SELECT request_id::text FROM e2e_requests))
   OR (ev.subject_type = 'user'
       AND ev.subject_id IN (SELECT user_id FROM e2e_users))
   OR ev.actor_id IN (SELECT user_id FROM e2e_users);

DELETE FROM notification
WHERE event_id IN (SELECT event_id FROM e2e_events)
   OR user_id IN (SELECT user_id FROM e2e_users);

DELETE FROM event WHERE event_id IN (SELECT event_id FROM e2e_events);

-- Notes before pairs and requests: both are referenced without cascade.
DELETE FROM mentorship_participant_note
WHERE user_id IN (SELECT user_id FROM e2e_users)
   OR (user_id = :member_id AND round_id = :round_id)
   OR pair_id IN (SELECT pair_id FROM e2e_pairs)
   OR request_id IN (SELECT request_id FROM e2e_requests);

DELETE FROM approval_request WHERE request_id IN (SELECT request_id FROM e2e_requests);

DELETE FROM mentorship_meeting WHERE pair_id IN (SELECT pair_id FROM e2e_pairs);

DELETE FROM mentorship_pairs WHERE pair_id IN (SELECT pair_id FROM e2e_pairs);

DELETE FROM mentorship_round_participants
WHERE user_id IN (SELECT user_id FROM e2e_users)
   OR (user_id = :member_id AND round_id = :round_id);

DELETE FROM training_progress
WHERE training_id IN (SELECT training_id FROM training
                      WHERE user_id IN (SELECT user_id FROM e2e_users));

DELETE FROM training WHERE user_id IN (SELECT user_id FROM e2e_users);

DELETE FROM application WHERE user_id = :member_id AND tags ->> 'e2e' = 'true';

-- Seeded people's own applications (Mentor H-M1's admission).
DELETE FROM application WHERE user_id IN (SELECT user_id FROM e2e_users);

DELETE FROM mentorship_email_recipient WHERE user_id IN (SELECT user_id FROM e2e_users);

DELETE FROM user_identities WHERE user_id IN (SELECT user_id FROM e2e_users);

DELETE FROM user_permissions WHERE user_id IN (SELECT user_id FROM e2e_users);

DELETE FROM user_emails WHERE user_id IN (SELECT user_id FROM e2e_users);

-- Block state (is_blocked, blocked_by/at/reason) lives on these rows and goes
-- with them. Anything else that still references a seeded user without a
-- cascade (a request they raised or reviewed, a permission they granted)
-- makes this fail and the whole cleanup roll back rather than guess.
DELETE FROM users WHERE user_id IN (SELECT user_id FROM e2e_users);

SELECT (SELECT count(*) FROM e2e_users)    AS users_removed,
       (SELECT count(*) FROM e2e_pairs)    AS pairs_removed,
       (SELECT count(*) FROM e2e_requests) AS requests_removed,
       (SELECT count(*) FROM e2e_events)   AS events_removed;

-- Rounds the suite created: named "E2E ...", every date at least 30 days ago, and
-- nothing pointing at them. A real round can match none of the three.
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
