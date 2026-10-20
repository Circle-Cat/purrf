-- Removes what inbox-admin-seed.sql created and what the Inbox and account
-- console e2e specs did.
--
--   psql "$E2E_DATABASE_URL" -X -v ON_ERROR_STOP=1 -f e2e/seed/inbox-admin-cleanup.sql
--
-- Idempotent. Run it before cleanup.sql and recruiting-cleanup.sql: a real
-- thread the specs filed to a seeded person or application would otherwise
-- be deleted with that person (email_thread.user_id cascades).
--
--   threads      inbox-thread-reset.sql: the suite's real threads put back,
--                its inserted threads removed.
--   ops people   user_id 990301-990399 whose every email is a
--                wangyanpei76+e2e-ops-…@gmail.com alias, with the block
--                requests about them and their events and notifications,
--                their permissions (grant history included) and emails.
--
-- Not cleaned here: the id sequences.

\set ON_ERROR_STOP on

\ir inbox-thread-reset.sql

BEGIN;

CREATE TEMP TABLE e2e_ops ON COMMIT DROP AS
SELECT u.user_id FROM users u
WHERE u.user_id BETWEEN 990301 AND 990399
  AND EXISTS (SELECT 1 FROM user_emails e
              WHERE e.user_id = u.user_id AND e.email LIKE 'wangyanpei76+e2e-ops-%@gmail.com')
  AND NOT EXISTS (SELECT 1 FROM user_emails e
                  WHERE e.user_id = u.user_id
                    AND e.email NOT LIKE 'wangyanpei76+e2e-ops-%@gmail.com');

CREATE TEMP TABLE e2e_requests ON COMMIT DROP AS
SELECT request_id FROM approval_request
WHERE target_type = 'user' AND target_id IN (SELECT user_id::text FROM e2e_ops);

CREATE TEMP TABLE e2e_events ON COMMIT DROP AS
SELECT event_id FROM event
WHERE (subject_type = 'user' AND subject_id IN (SELECT user_id FROM e2e_ops))
   OR (details ? 'requestId'
       AND details ->> 'requestId' IN (SELECT request_id::text FROM e2e_requests))
   OR actor_id IN (SELECT user_id FROM e2e_ops);

DELETE FROM notification
WHERE event_id IN (SELECT event_id FROM e2e_events)
   OR user_id IN (SELECT user_id FROM e2e_ops);

DELETE FROM event WHERE event_id IN (SELECT event_id FROM e2e_events);

DELETE FROM approval_request WHERE request_id IN (SELECT request_id FROM e2e_requests);
DELETE FROM user_identities WHERE user_id IN (SELECT user_id FROM e2e_ops);
DELETE FROM user_permissions WHERE user_id IN (SELECT user_id FROM e2e_ops);
DELETE FROM user_emails WHERE user_id IN (SELECT user_id FROM e2e_ops);
DELETE FROM users WHERE user_id IN (SELECT user_id FROM e2e_ops);

SELECT (SELECT count(*) FROM e2e_ops)      AS ops_removed,
       (SELECT count(*) FROM e2e_requests) AS requests_removed,
       (SELECT count(*) FROM e2e_events)   AS events_removed;

COMMIT;
