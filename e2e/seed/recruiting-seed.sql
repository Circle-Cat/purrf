-- Recruiting e2e seed for the shared TEST database.
--
--   psql "$E2E_DATABASE_URL" -X -v ON_ERROR_STOP=1 \
--        -v admin_id=<e2e-admin user_id> \
--        -v reviewer_email=<e2e-reviewer's address, or empty> \
--        -f e2e/seed/recruiting-seed.sql
--
-- Creates postings of its own, named "E2E seed …", owned by e2e-admin only,
-- and fake candidates (user_id 990101-990199) whose only email is a plus
-- alias of the test mailbox, wangyanpei76+e2e-cand-<n>@gmail.com, confirmed.
-- Any mail or calendar invite about them therefore lands in the test
-- mailbox. No real posting or application is read from or written to.
-- Undo with recruiting-cleanup.sql.
--
-- Postings (all employment, published, recruiter e2e-admin):
--   E2E seed board posting     Recruiter screening (1 session), Behavioral
--                              (2 sessions). The board, stage and interview
--                              specs work here.
--   E2E seed open posting      Two questions, no screen rules: e2e-member
--                              applies.
--   E2E seed screened posting  One question; answering "No" is rejected by
--                              a screen rule: e2e-member is screened out.
--
-- Candidates on the board posting:
--   Candidate A1   Recruiter screening, nobody assigned (stage advance,
--                  evaluation, comments)
--   Candidate B1   Behavioral session 1, e2e-reviewer assigned; also has a
--                  second confirmed alias, ...e2e-cand-2-alt@gmail.com
--                  (search by secondary email)
--   Candidate C1   Recruiter screening (candidate email, timeline)
--   Candidate K1   Recruiter screening (block request, approved)
--   Candidate I1   Behavioral session 1, e2e-reviewer assigned (interview
--                  booking)
--   Candidate O1   Behavioral session 2 (offer, hired)
--   Candidate R01-R25   Rejected, so the Rejected lane has a second page
--
-- Prints "job<TAB>kind<TAB>job_id<TAB>title" and
-- "application<TAB>last_name<TAB>application_id<TAB>user_id" lines last.

\set ON_ERROR_STOP on

\if :{?admin_id}
\else
  \echo 'recruiting-seed.sql: pass -v admin_id=<id>'
  \quit
\endif
\if :{?reviewer_email}
\else
  \echo 'recruiting-seed.sql: pass -v reviewer_email=<address> (empty for no reviewer)'
  \quit
\endif

SELECT EXISTS (SELECT 1 FROM users WHERE user_id BETWEEN 990101 AND 990199)
    OR EXISTS (SELECT 1 FROM user_emails WHERE email LIKE 'wangyanpei76+e2e-cand-%')
    OR EXISTS (SELECT 1 FROM job WHERE title LIKE 'E2E %')
    AS already \gset
\if :already
  \echo 'recruiting-seed.sql: refused. Seed candidates or E2E postings already exist; run recruiting-cleanup.sql first.'
  \quit
\endif

BEGIN;

CREATE TEMP TABLE e2e_cands (
    user_id   integer PRIMARY KEY,
    last_name text NOT NULL,
    n         text NOT NULL
) ON COMMIT DROP;

INSERT INTO e2e_cands VALUES
    (990101, 'Candidate A1', '1'),
    (990102, 'Candidate B1', '2'),
    (990103, 'Candidate C1', '3'),
    (990104, 'Candidate K1', '4'),
    (990105, 'Candidate I1', '5'),
    (990106, 'Candidate O1', '6');
INSERT INTO e2e_cands
SELECT 990109 + i, 'Candidate R' || lpad(i::text, 2, '0'), 'r' || i
FROM generate_series(1, 25) AS i;

INSERT INTO users (
    user_id, first_name, last_name, timezone, timezone_updated_at,
    communication_channel, is_active, is_internal, is_super_admin, is_blocked,
    updated_timestamp
)
SELECT user_id, 'E2E', last_name, 'America/Los_Angeles', now(),
       'email', true, false, false, false, now()
FROM e2e_cands;

INSERT INTO user_emails (user_id, email, otp_confirmed, is_primary)
SELECT user_id, 'wangyanpei76+e2e-cand-' || n || '@gmail.com', true, true
FROM e2e_cands;

INSERT INTO user_emails (user_id, email, otp_confirmed, is_primary)
VALUES (990102, 'wangyanpei76+e2e-cand-2-alt@gmail.com', true, false);

CREATE TEMP TABLE e2e_jobs (
    kind   text PRIMARY KEY,
    job_id integer NOT NULL
) ON COMMIT DROP;

WITH created AS (
    INSERT INTO job (
        kind, status, title, description, form_schema, pipeline_config,
        screen_rules, profile_config, was_published, cooldown_days,
        updated_timestamp
    )
    SELECT 'employment', 'published', v.title, v.description, v.form::jsonb,
           v.pipeline::jsonb, v.rules::jsonb,
           '{"resume": "off", "education": "off", "workExperience": "off"}'::jsonb,
           true, 0, now()
    FROM (VALUES
        ('E2E seed board posting',
         'E2E regression posting: the board, stages and interviews.',
         '{"nextSeq": 2, "questions": [{"id": "q1", "type": "short_text", "label": "E2E question: what do you want to work on?", "required": true}]}',
         '{"ownerIds": [' || :admin_id || '], "stages": [{"stage": "recruiter_screening", "rounds": 1}, {"stage": "behavioral", "rounds": 2}]}',
         NULL),
        ('E2E seed open posting',
         'E2E regression posting: e2e-member applies here.',
         '{"nextSeq": 3, "questions": [{"id": "q1", "type": "single_choice", "label": "E2E question: can you commit ten hours a week?", "options": ["Yes", "No"], "required": true}, {"id": "q2", "type": "short_text", "label": "E2E question: why this posting?", "required": true}]}',
         '{"ownerIds": [' || :admin_id || '], "stages": [{"stage": "recruiter_screening", "rounds": 1}]}',
         NULL),
        ('E2E seed screened posting',
         'E2E regression posting: answering No is screened out.',
         '{"nextSeq": 2, "questions": [{"id": "q1", "type": "single_choice", "label": "E2E question: do you accept the program rules?", "options": ["Yes", "No"], "required": true}]}',
         '{"ownerIds": [' || :admin_id || '], "stages": [{"stage": "recruiter_screening", "rounds": 1}]}',
         '{"rules": [{"id": "r1", "action": "reject", "condition": {"source": "answer", "operator": "equals", "questionId": "q1", "value": "No"}}]}')
    ) AS v(title, description, form, pipeline, rules)
    RETURNING job_id, title
)
INSERT INTO e2e_jobs (kind, job_id)
SELECT CASE title WHEN 'E2E seed board posting' THEN 'board'
                  WHEN 'E2E seed open posting' THEN 'open'
                  ELSE 'screened' END,
       job_id
FROM created;

CREATE TEMP TABLE e2e_apps (
    user_id integer PRIMARY KEY,
    stage   text NOT NULL,
    round   integer NOT NULL,
    ago     interval NOT NULL
) ON COMMIT DROP;

INSERT INTO e2e_apps VALUES
    (990101, 'recruiter_screening', 1, interval '3 days'),
    (990102, 'behavioral',          1, interval '4 days'),
    (990103, 'recruiter_screening', 1, interval '5 days'),
    (990104, 'recruiter_screening', 1, interval '6 days'),
    (990105, 'behavioral',          1, interval '7 days'),
    (990106, 'behavioral',          2, interval '8 days');
INSERT INTO e2e_apps
SELECT user_id, 'rejected', 1, (user_id - 990100) * interval '1 day'
FROM e2e_cands WHERE user_id >= 990110;

INSERT INTO application (
    job_id, user_id, stage, sub_status, current_round, tags,
    created_datetime, updated_timestamp, stage_entered_at
)
SELECT j.job_id, a.user_id, a.stage::application_stage_enum,
       CASE WHEN a.stage = 'rejected' THEN NULL ELSE 'pending' END,
       a.round, '{}'::jsonb,
       now() - a.ago - interval '1 day', now(), now() - a.ago
FROM e2e_apps a CROSS JOIN e2e_jobs j
WHERE j.kind = 'board';

INSERT INTO application_submission (
    application_id, version, is_frozen, submission, submitted_at
)
SELECT ap.application_id, 1, ap.stage <> 'applied',
       jsonb_build_object(
           'answers', jsonb_build_object('q1', 'E2E seed answer'),
           'personal', jsonb_build_object(
               'firstName', 'E2E', 'lastName', c.last_name,
               'timezone', 'America/Los_Angeles', 'linkedin', ''),
           'education', '[]'::jsonb,
           'experience', '[]'::jsonb,
           'formSchema', jb.form_schema),
       ap.created_datetime
FROM application ap
JOIN e2e_cands c ON c.user_id = ap.user_id
JOIN job jb ON jb.job_id = ap.job_id;

-- e2e-reviewer is whoever holds :reviewer_email; with it empty, nobody is
-- assigned.
INSERT INTO application_assignment (application_id, stage, assignee_id, assigned_by, round)
SELECT ap.application_id, ap.stage, r.user_id, :admin_id, ap.current_round
FROM application ap
CROSS JOIN (SELECT user_id FROM user_emails
            WHERE lower(email) = lower(:'reviewer_email')) r
WHERE ap.user_id IN (990102, 990105);

COMMIT;

\pset format unaligned
\pset tuples_only on
\pset fieldsep '\t'
SELECT 'job', CASE title WHEN 'E2E seed board posting' THEN 'board'
                         WHEN 'E2E seed open posting' THEN 'open'
                         ELSE 'screened' END,
       job_id, title
FROM job WHERE title LIKE 'E2E seed %' ORDER BY job_id;
SELECT 'application', u.last_name, a.application_id, a.user_id
FROM application a JOIN users u USING (user_id)
WHERE a.user_id BETWEEN 990101 AND 990199
ORDER BY a.user_id;
