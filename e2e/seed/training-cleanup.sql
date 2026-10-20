-- Removes what training-seed.sql created and what the training e2e specs did.
--
--   psql "$E2E_DATABASE_URL" -X -v ON_ERROR_STOP=1 -f e2e/seed/training-cleanup.sql
--
-- Idempotent. What it removes is fixed by two sets:
--   E2E courses     every course named "E2E …" with no category (the four
--                   real courses all carry one; a course created through the
--                   API never does), with every assignment on it, whoever
--                   holds it (test accounts included), their progress, and
--                   the course's package rows.
--   seed trainees   user_id 990201-990299 whose every email is a
--                   wangyanpei76+e2e-trainee-…@gmail.com alias.
--
-- Not cleaned here: package files in the training bucket (see
-- tests/training/SIDE-EFFECTS.md), the id sequences.

\set ON_ERROR_STOP on

BEGIN;

CREATE TEMP TABLE e2e_courses ON COMMIT DROP AS
SELECT course_id FROM training_course
WHERE name LIKE 'E2E %' AND category IS NULL;

CREATE TEMP TABLE e2e_trainees ON COMMIT DROP AS
SELECT u.user_id FROM users u
WHERE u.user_id BETWEEN 990201 AND 990299
  AND EXISTS (SELECT 1 FROM user_emails e
              WHERE e.user_id = u.user_id AND e.email LIKE 'wangyanpei76+e2e-trainee-%@gmail.com')
  AND NOT EXISTS (SELECT 1 FROM user_emails e
                  WHERE e.user_id = u.user_id
                    AND e.email NOT LIKE 'wangyanpei76+e2e-trainee-%@gmail.com');

CREATE TEMP TABLE e2e_trainings ON COMMIT DROP AS
SELECT training_id FROM training
WHERE course_id IN (SELECT course_id FROM e2e_courses)
   OR user_id IN (SELECT user_id FROM e2e_trainees);

DELETE FROM training_progress WHERE training_id IN (SELECT training_id FROM e2e_trainings);
DELETE FROM training WHERE training_id IN (SELECT training_id FROM e2e_trainings);
DELETE FROM training_course_package WHERE course_id IN (SELECT course_id FROM e2e_courses);
DELETE FROM training_course WHERE course_id IN (SELECT course_id FROM e2e_courses);

DELETE FROM user_identities WHERE user_id IN (SELECT user_id FROM e2e_trainees);
DELETE FROM user_permissions WHERE user_id IN (SELECT user_id FROM e2e_trainees);
DELETE FROM user_emails WHERE user_id IN (SELECT user_id FROM e2e_trainees);
DELETE FROM users WHERE user_id IN (SELECT user_id FROM e2e_trainees);

SELECT (SELECT count(*) FROM e2e_courses)   AS courses_removed,
       (SELECT count(*) FROM e2e_trainings) AS assignments_removed,
       (SELECT count(*) FROM e2e_trainees)  AS trainees_removed;

COMMIT;
