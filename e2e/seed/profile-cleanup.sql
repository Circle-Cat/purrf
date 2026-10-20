-- Removes what profile-seed.sql created and what the profile e2e specs left.
--
--   psql "$E2E_DATABASE_URL" -X -v ON_ERROR_STOP=1 -f e2e/seed/profile-cleanup.sql
--
-- Idempotent. Removes:
--   profile people  user_id 990401-990499 whose every email is a
--                   wangyanpei76+e2e-profile-…@gmail.com alias, with what
--                   hangs off them.
--   extra aliases   non-primary rows wangyanpei76+e2e-<role>-…@gmail.com of
--                   the test accounts, which the specs add (in the database
--                   or through Add email) and remove again.
--
-- The test accounts' names, experience and onboarding training are put back
-- from the snapshot global setup took (lib/seed.js restoreAccounts), not
-- here. Not cleaned here: Auth0 users a completed Add email creates for an
-- alias, résumé objects in the bucket (see tests/profile/SIDE-EFFECTS.md).

\set ON_ERROR_STOP on

BEGIN;

CREATE TEMP TABLE e2e_profile_people ON COMMIT DROP AS
SELECT u.user_id FROM users u
WHERE u.user_id BETWEEN 990401 AND 990499
  AND NOT EXISTS (SELECT 1 FROM user_emails e
                  WHERE e.user_id = u.user_id
                    AND e.email NOT LIKE 'wangyanpei76+e2e-profile-%@gmail.com');

DELETE FROM experience WHERE user_id IN (SELECT user_id FROM e2e_profile_people);
DELETE FROM preferences WHERE user_id IN (SELECT user_id FROM e2e_profile_people);
DELETE FROM user_identities WHERE user_id IN (SELECT user_id FROM e2e_profile_people);
DELETE FROM user_permissions WHERE user_id IN (SELECT user_id FROM e2e_profile_people);
DELETE FROM user_emails WHERE user_id IN (SELECT user_id FROM e2e_profile_people);
DELETE FROM users WHERE user_id IN (SELECT user_id FROM e2e_profile_people);

WITH gone AS (
    DELETE FROM user_emails
    WHERE NOT is_primary
      AND user_id < 990001
      AND email ~ '^wangyanpei76\+e2e-(admin|reviewer|reviewer2|member|readonly)-[a-z0-9-]+@gmail\.com$'
    RETURNING email
)
SELECT (SELECT count(*) FROM e2e_profile_people) AS people_removed,
       (SELECT count(*) FROM gone) AS extra_aliases_removed;

COMMIT;
