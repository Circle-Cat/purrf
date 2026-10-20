-- Puts the suite's real mail threads back and drops the threads the specs
-- inserted. Run on its own by the Inbox specs between tests, and first by
-- inbox-admin-cleanup.sql.
--
--   psql "$E2E_DATABASE_URL" -X -v ON_ERROR_STOP=1 -f e2e/seed/inbox-thread-reset.sql
--
-- Idempotent. What it touches:
--   real threads   threads Gmail brought in whose subject starts "E2E inbox"
--                  and whose every inbound sender is the test mailbox or an
--                  e2e alias of it. They are kept and reused: put back
--                  unfiled, unarchived, in the service of the alias they were
--                  sent to, without the outbound mail the specs sent, the
--                  inbound rows the specs inserted (gmail_message_id
--                  "e2e-…"), and every event a person (not the sync) recorded
--                  on them, with its notifications.
--   fake threads   gmail_thread_id "e2e-…", with their messages, events and
--                  notifications.
--
-- Not undone: replies already sent from the service aliases stay in Gmail.
-- Sync only reads a thread again when a message is added to it (Gmail
-- history "messageAdded"), or in a full resync; then the deleted outbound
-- rows come back, and the next reset removes them again.

\set ON_ERROR_STOP on

BEGIN;

CREATE TEMP TABLE e2e_real_threads ON COMMIT DROP AS
SELECT t.thread_id FROM email_thread t
WHERE t.subject LIKE 'E2E inbox%'
  AND t.gmail_thread_id NOT LIKE 'e2e-%'
  AND EXISTS (SELECT 1 FROM email_message m
              WHERE m.thread_id = t.thread_id AND m.direction = 'inbound'
                AND m.from_address ~* '(^|[^a-z0-9.+_-])wangyanpei76(\+e2e-[a-z0-9-]+)?@gmail\.com')
  AND NOT EXISTS (SELECT 1 FROM email_message m
                  WHERE m.thread_id = t.thread_id AND m.direction = 'inbound'
                    AND m.gmail_message_id NOT LIKE 'e2e-%'
                    AND (m.from_address IS NULL
                         OR m.from_address !~* '(^|[^a-z0-9.+_-])wangyanpei76(\+e2e-[a-z0-9-]+)?@gmail\.com'));

CREATE TEMP TABLE e2e_fake_threads ON COMMIT DROP AS
SELECT thread_id FROM email_thread WHERE gmail_thread_id LIKE 'e2e-%';

CREATE TEMP TABLE e2e_thread_events ON COMMIT DROP AS
SELECT event_id FROM event
WHERE subject_type = 'email_thread'
  AND (subject_id IN (SELECT thread_id FROM e2e_fake_threads)
       OR (actor_id IS NOT NULL
           AND subject_id IN (SELECT thread_id FROM e2e_real_threads)));

DELETE FROM notification WHERE event_id IN (SELECT event_id FROM e2e_thread_events);
DELETE FROM event WHERE event_id IN (SELECT event_id FROM e2e_thread_events);

DELETE FROM email_message
WHERE thread_id IN (SELECT thread_id FROM e2e_real_threads)
  AND (direction = 'outbound' OR gmail_message_id LIKE 'e2e-%');

-- The service is the test alias the first inbound mail was sent to, as the
-- router read it (terraform/environments/test/main.tf).
UPDATE email_thread t
SET context_type = COALESCE((
        SELECT CASE
                 WHEN m.to_addresses ILIKE '%mentorship-test@circlecat.org%' THEN 'mentorship_inbox'
                 WHEN m.to_addresses ILIKE '%recruiting-test@circlecat.org%' THEN 'recruiting_inbox'
                 WHEN m.to_addresses ILIKE '%inquiries-test@circlecat.org%' THEN 'inquiries_inbox'
               END
        FROM email_message m
        WHERE m.thread_id = t.thread_id AND m.direction = 'inbound'
        ORDER BY COALESCE(m.gmail_internal_date, m.created_at), m.message_id
        LIMIT 1), t.context_type),
    context_id = NULL,
    user_id = NULL,
    archived_at = NULL,
    archived_by_user_id = NULL
WHERE t.thread_id IN (SELECT thread_id FROM e2e_real_threads);

DELETE FROM email_thread WHERE thread_id IN (SELECT thread_id FROM e2e_fake_threads);

SELECT (SELECT count(*) FROM e2e_real_threads) AS real_threads_reset,
       (SELECT count(*) FROM e2e_fake_threads) AS fake_threads_removed;

COMMIT;
