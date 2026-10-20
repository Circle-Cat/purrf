-- Training e2e seed for the shared TEST database.
--
--   psql "$E2E_DATABASE_URL" -X -v ON_ERROR_STOP=1 -f e2e/seed/training-seed.sql
--
-- Creates four trainees (user_id 990201-990204, "E2E Trainee 1".."4"),
-- external and active, whose only address is a confirmed plus alias of the
-- test mailbox, wangyanpei76+e2e-trainee-<n>@gmail.com. They cannot sign in;
-- the specs assign courses to them. Courses are not seeded: the specs create
-- their own "E2E …" courses through the API. Undo with training-cleanup.sql.
--
-- Prints "trainee<TAB>n<TAB>user_id" lines last.

\set ON_ERROR_STOP on

SELECT EXISTS (SELECT 1 FROM users WHERE user_id BETWEEN 990201 AND 990299)
    OR EXISTS (SELECT 1 FROM user_emails WHERE email LIKE 'wangyanpei76+e2e-trainee-%')
    AS already \gset
\if :already
  \echo 'training-seed.sql: refused. Seed trainees already exist; run training-cleanup.sql first.'
  \quit
\endif

BEGIN;

CREATE TEMP TABLE e2e_trainees ON COMMIT DROP AS
SELECT 990200 + n AS user_id, n FROM generate_series(1, 4) AS n;

INSERT INTO users (
    user_id, first_name, last_name, timezone, timezone_updated_at,
    communication_channel, is_active, is_internal, is_super_admin, is_blocked,
    updated_timestamp
)
SELECT user_id, 'E2E', 'Trainee ' || n, 'America/Los_Angeles', now(),
       'email', true, false, false, false, now()
FROM e2e_trainees;

INSERT INTO user_emails (user_id, email, otp_confirmed, is_primary)
SELECT user_id, 'wangyanpei76+e2e-trainee-' || n || '@gmail.com', true, true
FROM e2e_trainees;

\pset tuples_only on
\pset format unaligned
\pset fieldsep '\t'
SELECT 'trainee', n, user_id FROM e2e_trainees ORDER BY n;

COMMIT;
