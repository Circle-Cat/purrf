-- Removes what recruiting-seed.sql created and what the recruiting e2e
-- specs did there.
--
--   psql "$E2E_DATABASE_URL" -X -v ON_ERROR_STOP=1 \
--        -v admin_id=<e2e-admin user_id> -f e2e/seed/recruiting-cleanup.sql
--
-- Idempotent. What it removes is fixed by two sets:
--   E2E postings     every posting titled "E2E …" whose recruiters
--                    (ownerIds, present and non-empty) are e2e-admin alone
--                    (the seeded ones and the ones the posting specs
--                    create), with every application to them, whoever
--                    applied (e2e-member's included), and everything
--                    hanging off those: submissions, assignments,
--                    evaluations, comments and mentions, interview rows,
--                    email threads, reviews, events and notifications; and
--                    the reviews, events and notifications left behind by
--                    postings e2e-admin created and then deleted.
--   seed candidates  user_id 990101-990199 whose every email is a
--                    wangyanpei76+e2e-cand-…@gmail.com alias, in every table.
--
-- Not cleaned here: Google Calendar events (global teardown cancels any
-- interview still booked through the API before this runs), mail already
-- sent, résumé objects in the bucket (the specs upload none), the job and
-- application id sequences.

\set ON_ERROR_STOP on

\if :{?admin_id}
\else
  \echo 'recruiting-cleanup.sql: pass -v admin_id=<id>'
  \quit
\endif

BEGIN;

CREATE TEMP TABLE e2e_jobs ON COMMIT DROP AS
SELECT job_id FROM job
WHERE title LIKE 'E2E %'
  AND jsonb_typeof(pipeline_config -> 'ownerIds') = 'array'
  AND pipeline_config -> 'ownerIds' <> '[]'::jsonb
  AND pipeline_config -> 'ownerIds' <@ jsonb_build_array(:admin_id)
  AND (pending_payload IS NULL
       OR COALESCE(pending_payload -> 'pipelineConfig' -> 'ownerIds', '[]'::jsonb)
          <@ jsonb_build_array(:admin_id));

-- A posting deleted through the product leaves its reviews, events and
-- notifications behind. Those of postings e2e-admin created and that no
-- longer exist are the suite's too.
INSERT INTO e2e_jobs
SELECT DISTINCT ev.subject_id FROM event ev
WHERE ev.subject_type = 'job'
  AND ev.event_type = 'recruiting.job_created'
  AND ev.actor_id = :admin_id
  AND NOT EXISTS (SELECT 1 FROM job j WHERE j.job_id = ev.subject_id);

CREATE TEMP TABLE e2e_cands ON COMMIT DROP AS
SELECT u.user_id FROM users u
WHERE u.user_id BETWEEN 990101 AND 990199
  AND EXISTS (SELECT 1 FROM user_emails e
              WHERE e.user_id = u.user_id AND e.email LIKE 'wangyanpei76+e2e-cand-%@gmail.com')
  AND NOT EXISTS (SELECT 1 FROM user_emails e
                  WHERE e.user_id = u.user_id
                    AND e.email NOT LIKE 'wangyanpei76+e2e-cand-%@gmail.com');

CREATE TEMP TABLE e2e_apps ON COMMIT DROP AS
SELECT application_id FROM application
WHERE job_id IN (SELECT job_id FROM e2e_jobs)
   OR user_id IN (SELECT user_id FROM e2e_cands);

-- Posting reviews target the job; block requests target the user.
CREATE TEMP TABLE e2e_requests ON COMMIT DROP AS
SELECT request_id FROM approval_request
WHERE (target_type = 'job' AND target_id IN (SELECT job_id::text FROM e2e_jobs))
   OR (target_type = 'user' AND target_id IN (SELECT user_id::text FROM e2e_cands));

CREATE TEMP TABLE e2e_events ON COMMIT DROP AS
SELECT event_id FROM event
WHERE (subject_type = 'job' AND subject_id IN (SELECT job_id FROM e2e_jobs))
   OR (subject_type = 'application' AND subject_id IN (SELECT application_id FROM e2e_apps))
   OR (subject_type = 'user' AND subject_id IN (SELECT user_id FROM e2e_cands))
   OR (details ? 'requestId'
       AND details ->> 'requestId' IN (SELECT request_id::text FROM e2e_requests))
   OR actor_id IN (SELECT user_id FROM e2e_cands);

DELETE FROM notification
WHERE event_id IN (SELECT event_id FROM e2e_events)
   OR user_id IN (SELECT user_id FROM e2e_cands);

DELETE FROM event WHERE event_id IN (SELECT event_id FROM e2e_events);

DELETE FROM approval_request WHERE request_id IN (SELECT request_id FROM e2e_requests);

DELETE FROM email_thread
WHERE (context_type = 'application'
       AND context_id IN (SELECT application_id FROM e2e_apps))
   OR user_id IN (SELECT user_id FROM e2e_cands);

-- Submissions, assignments, evaluations, comments, mentions and interview
-- rows cascade with the application.
DELETE FROM application WHERE application_id IN (SELECT application_id FROM e2e_apps);

DELETE FROM job WHERE job_id IN (SELECT job_id FROM e2e_jobs);

DELETE FROM training_progress
WHERE training_id IN (SELECT training_id FROM training
                      WHERE user_id IN (SELECT user_id FROM e2e_cands));
DELETE FROM training WHERE user_id IN (SELECT user_id FROM e2e_cands);
DELETE FROM user_identities WHERE user_id IN (SELECT user_id FROM e2e_cands);
DELETE FROM user_permissions WHERE user_id IN (SELECT user_id FROM e2e_cands);
DELETE FROM user_emails WHERE user_id IN (SELECT user_id FROM e2e_cands);
DELETE FROM users WHERE user_id IN (SELECT user_id FROM e2e_cands);

SELECT (SELECT count(*) FROM e2e_jobs)     AS jobs_removed,
       (SELECT count(*) FROM e2e_cands)    AS candidates_removed,
       (SELECT count(*) FROM e2e_apps)     AS applications_removed,
       (SELECT count(*) FROM e2e_requests) AS requests_removed,
       (SELECT count(*) FROM e2e_events)   AS events_removed;

COMMIT;
