-- Inbox and account console e2e seed for the shared TEST database.
--
--   psql "$E2E_DATABASE_URL" -X -v ON_ERROR_STOP=1 -f e2e/seed/inbox-admin-seed.sql
--
-- Creates the account console's people (user_id 990301-990309, "E2E Ops …"),
-- external and active, whose only addresses are confirmed plus aliases of
-- the test mailbox, wangyanpei76+e2e-ops-<n>@gmail.com. Ops Search also
-- holds a second, alternative alias (…e2e-ops-3-alt@…) to search by. They
-- cannot sign in; the specs deactivate, block, unblock, raise block requests
-- on and grant permissions to them. Nothing is seeded for the Inbox: the
-- specs insert their own threads (gmail_thread_id "e2e-…"). Undo with
-- inbox-admin-cleanup.sql.
--
-- Prints "ops<TAB>key<TAB>user_id" lines last.

\set ON_ERROR_STOP on

SELECT EXISTS (SELECT 1 FROM users WHERE user_id BETWEEN 990301 AND 990399)
    OR EXISTS (SELECT 1 FROM user_emails WHERE email LIKE 'wangyanpei76+e2e-ops-%')
    AS already \gset
\if :already
  \echo 'inbox-admin-seed.sql: refused. Seed ops people already exist; run inbox-admin-cleanup.sql first.'
  \quit
\endif

BEGIN;

CREATE TEMP TABLE e2e_ops (
    user_id   integer PRIMARY KEY,
    key       text NOT NULL,
    last_name text NOT NULL
) ON COMMIT DROP;

INSERT INTO e2e_ops VALUES
    (990301, 'deactivate', 'Ops Deactivate'),
    (990302, 'block',      'Ops Block'),
    (990303, 'search',     'Ops Search'),
    (990304, 'approve',    'Ops Approve'),
    (990305, 'reject',     'Ops Reject'),
    (990306, 'supersede',  'Ops Supersede'),
    (990307, 'grant',      'Ops Grant'),
    (990308, 'inbox',      'Ops Inbox'),
    (990309, 'notify',     'Ops Notify');

INSERT INTO users (
    user_id, first_name, last_name, timezone, timezone_updated_at,
    communication_channel, is_active, is_internal, is_super_admin, is_blocked,
    updated_timestamp
)
SELECT user_id, 'E2E', last_name, 'America/Los_Angeles', now(),
       'email', true, false, false, false, now()
FROM e2e_ops;

INSERT INTO user_emails (user_id, email, otp_confirmed, is_primary)
SELECT user_id, 'wangyanpei76+e2e-ops-' || (user_id - 990300) || '@gmail.com', true, true
FROM e2e_ops;

INSERT INTO user_emails (user_id, email, otp_confirmed, is_primary)
VALUES (990303, 'wangyanpei76+e2e-ops-3-alt@gmail.com', true, false);

\pset tuples_only on
\pset format unaligned
\pset fieldsep '\t'
SELECT 'ops', key, user_id FROM e2e_ops ORDER BY user_id;

COMMIT;
