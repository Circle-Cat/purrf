-- Profile and Sign in & security e2e seed for the shared TEST database.
--
--   psql "$E2E_DATABASE_URL" -X -v ON_ERROR_STOP=1 -f e2e/seed/profile-seed.sql
--
-- Creates one person (user_id 990401, "E2E Profile Owner"), external and
-- active, who cannot sign in. Their confirmed primary address,
-- wangyanpei76+e2e-profile-1@gmail.com, is the one a test account tries to
-- add to see "already in use"; their unconfirmed
-- wangyanpei76+e2e-profile-1-old@gmail.com is the row a test account tries
-- to remove to see the API refuse someone else's address. Undo with
-- profile-cleanup.sql.
--
-- Prints "profile<TAB>key<TAB>user_id<TAB>email_id" lines last.

\set ON_ERROR_STOP on

SELECT EXISTS (SELECT 1 FROM users WHERE user_id BETWEEN 990401 AND 990499)
    OR EXISTS (SELECT 1 FROM user_emails WHERE email LIKE 'wangyanpei76+e2e-profile-%')
    AS already \gset
\if :already
  \echo 'profile-seed.sql: refused. Seed profile people already exist; run profile-cleanup.sql first.'
  \quit
\endif

BEGIN;

INSERT INTO users (
    user_id, first_name, last_name, timezone, timezone_updated_at,
    communication_channel, is_active, is_internal, is_super_admin, is_blocked,
    updated_timestamp
)
VALUES (990401, 'E2E', 'Profile Owner', 'America/Los_Angeles', now(),
        'email', true, false, false, false, now());

INSERT INTO user_emails (user_id, email, otp_confirmed, is_primary)
VALUES (990401, 'wangyanpei76+e2e-profile-1@gmail.com', true, true),
       (990401, 'wangyanpei76+e2e-profile-1-old@gmail.com', false, false);

\pset tuples_only on
\pset format unaligned
\pset fieldsep '\t'
SELECT 'profile', CASE WHEN is_primary THEN 'owner' ELSE 'owner-old' END,
       user_id, email_id, email
FROM user_emails WHERE user_id = 990401 ORDER BY email_id;

COMMIT;
