-- Leave e2e seed for the shared TEST database.
--
--   psql "$E2E_DATABASE_URL" -X -v ON_ERROR_STOP=1 \
--        -v reviewer=276 -v member=279 -v accounts=267,276,277,279,280 \
--        -f e2e/seed/leave-seed.sql
--
-- Creates ten seed employees (990501-990510, "E2E Leave …"), external,
-- whose only address is wangyanpei76+e2e-leave-<n>@gmail.com, primary and
-- confirmed; no company address and no Redis profile, so none can file.
-- Every request below is filed against :reviewer (e2e-reviewer), with the
-- approval_request row the shared approval flow would have written.
-- Holidays: 2019 (edited through the UI) and 2099 (approvals recount
-- against it), all named "E2E …". No event or notification rows. Undo with
-- leave-cleanup.sql.
--
-- Weekend is Sunday + Monday (backend/leave/leave_policy.py). Every date
-- below is a Tuesday unless noted: 2099-03-04 Wed, 03-14 Sat, 03-21 Sat,
-- 04-25 Sat, 05-01 Fri. Hours equal leave_workdays.request_hours under the
-- seeded 2099 calendar, or approving refuses (except R5, which is meant to).
--
-- Prints "person<TAB>key<TAB>user_id" and "request<TAB>key<TAB>id" lines.

\set ON_ERROR_STOP on

SELECT EXISTS (SELECT 1 FROM users WHERE user_id BETWEEN 990501 AND 990599)
    OR EXISTS (SELECT 1 FROM user_emails WHERE email LIKE 'wangyanpei76+e2e-leave-%')
    OR EXISTS (SELECT 1 FROM leave_holiday WHERE year IN (2019, 2099))
    OR EXISTS (SELECT 1 FROM leave_request
               WHERE user_id = ANY (string_to_array(:'accounts', ',')::int[]))
    OR EXISTS (SELECT 1 FROM leave_ledger
               WHERE user_id = ANY (string_to_array(:'accounts', ',')::int[]))
    AS already \gset
\if :already
  \echo 'leave-seed.sql: refused. Leave rows of the suite (or holidays in 2019/2099) already exist; run leave-cleanup.sql first.'
  \quit
\endif

BEGIN;

CREATE TEMP TABLE e2e_leave_people (n int, user_id int, last_name text, active bool) ON COMMIT DROP;
INSERT INTO e2e_leave_people VALUES
  (1,  990501, 'Leave Approve',   true),
  (2,  990502, 'Leave Reject',    true),
  (3,  990503, 'Leave Overdraft', true),
  (4,  990504, 'Leave Exchange',  true),
  (5,  990505, 'Leave Recount',   true),
  (6,  990506, 'Leave Started',   true),
  (7,  990507, 'Leave Inactive',  false),
  (8,  990508, 'Leave History',   true),
  (9,  990509, 'Leave Late',      true),
  (10, 990510, 'Leave Adjust',    true);

INSERT INTO users (
    user_id, first_name, last_name, timezone, timezone_updated_at,
    communication_channel, is_active, is_internal, is_super_admin, is_blocked,
    updated_timestamp
)
SELECT user_id, 'E2E', last_name, 'Asia/Shanghai', now(),
       'email', active, false, false, false, now()
FROM e2e_leave_people;

INSERT INTO user_emails (user_id, email, otp_confirmed, is_primary)
SELECT user_id, 'wangyanpei76+e2e-leave-' || n || '@gmail.com', true, true
FROM e2e_leave_people;

-- 2019: one segment for the Yearly setup spec to edit.
-- 2099: Labour Day (not exchangeable) and one exchangeable day.
INSERT INTO leave_holiday (year, date, name, is_exchangeable)
SELECT 2019, d::date, 'E2E National Day 2019', false
FROM generate_series('2019-10-01'::date, '2019-10-07'::date, '1 day') AS d
UNION ALL
SELECT 2099, d::date, 'E2E Labour Day 2099', false
FROM generate_series('2099-05-01'::date, '2099-05-05'::date, '1 day') AS d
UNION ALL
SELECT 2099, '2099-06-02'::date, 'E2E Exchange Day 2099', true;

CREATE TEMP TABLE e2e_leave_spec (
  key text, user_id int, type text, start_date date, end_date date,
  start_time time, end_time time, hours numeric, status text,
  is_overdraft bool, is_late bool, reason text,
  approval text, comment text
) ON COMMIT DROP;
INSERT INTO e2e_leave_spec VALUES
  -- Waiting on e2e-reviewer.
  ('R1', 990501, 'paid',     '2099-03-03', '2099-03-04', NULL, NULL, 16, 'pending', false, false, 'E2E R1 approve me', 'pending', NULL),
  ('R2', 990502, 'sick',     '2099-03-10', '2099-03-14', NULL, NULL, 40, 'pending', false, false, 'E2E R2 reject me',  'pending', NULL),
  ('R3', 990503, 'paid',     '2099-03-17', '2099-03-21', NULL, NULL, 40, 'pending', true,  false, 'E2E R3 overdraft',  'pending', NULL),
  ('R4', 990504, 'exchange', '2099-06-02', '2099-06-02', NULL, NULL,  8, 'pending', false, false, 'E2E R4 exchange',   'pending', NULL),
  -- Stored 8 h, but 2099-05-05 is a seeded holiday: recounts to 0.00.
  ('R5', 990505, 'paid',     '2099-05-05', '2099-05-05', NULL, NULL,  8, 'pending', false, false, 'E2E R5 recount',    'pending', NULL),
  ('R6', 990506, 'paid',     '2019-10-08', '2019-10-08', NULL, NULL,  8, 'pending', false, false, 'E2E R6 started',    'pending', NULL),
  ('R7', 990507, 'paid',     '2099-03-24', '2099-03-24', NULL, NULL,  8, 'pending', false, false, 'E2E R7 inactive',   'pending', NULL),
  ('R9', 990509, 'paid',     '2099-03-31', '2099-03-31', NULL, NULL,  8, 'pending', false, true,  'E2E R9 late',       'pending', NULL),
  -- Already decided by e2e-reviewer.
  ('H1', 990508, 'paid',     '2099-04-07', '2099-04-07', NULL, NULL,  8, 'approved',  true,  false, 'E2E H1 approved', 'approved',  NULL),
  ('H2', 990508, 'paid',     '2099-04-14', '2099-04-14', NULL, NULL,  8, 'rejected',  false, false, 'E2E H2 rejected', 'rejected',  'E2E H2 clashes with the release'),
  ('H3', 990508, 'sick',     '2099-04-21', '2099-04-25', NULL, NULL, 40, 'withdrawn', false, false, 'E2E H3 withdrawn', 'withdrawn', NULL),
  -- e2e-member's own.
  ('M1', :member, 'paid',    '2099-07-07', '2099-07-07', NULL, NULL,  8, 'pending',  false, false, 'E2E M1 family trip', 'pending', NULL),
  ('M2', :member, 'paid',    '2099-07-14', '2099-07-14', NULL, NULL,  8, 'pending',  false, false, 'E2E M2 approve me',  'pending', NULL),
  ('M3', :member, 'paid',    '2099-07-21', '2099-07-21', NULL, NULL,  8, 'rejected', false, false, 'E2E M3 rejected',    'rejected', 'E2E M3 please move it'),
  -- Sick leave of a day or less is approved on filing, with no approval row.
  ('M4', :member, 'sick',    '2099-07-28', '2099-07-28', NULL, NULL,  8, 'approved', false, false, 'E2E M4 flu',         NULL, NULL),
  ('M5', :member, 'paid',    '2099-08-04', '2099-08-04', '09:00', '13:00', 4, 'pending', false, true, 'E2E M5 dentist', 'pending', NULL);

CREATE TEMP TABLE e2e_leave_ids (key text, leave_request_id int) ON COMMIT DROP;
WITH ins AS (
  INSERT INTO leave_request (user_id, type, start_date, end_date, start_time, end_time,
                             hours, status, approver_user_id, reason, is_overdraft, is_late_notice)
  SELECT user_id, type::leave_request_type_enum, start_date, end_date, start_time, end_time,
         hours, status::leave_request_status_enum, :reviewer, reason, is_overdraft, is_late
  FROM e2e_leave_spec
  RETURNING leave_request_id, reason
)
INSERT INTO e2e_leave_ids
SELECT s.key, ins.leave_request_id FROM ins JOIN e2e_leave_spec s USING (reason);

INSERT INTO approval_request (action, target_type, target_id, payload, raised_by, reviewer_id,
                              status, decided_by, decided_at, decision_comment)
SELECT 'leave_approval', 'leave_request', i.leave_request_id::text, '{}'::jsonb,
       s.user_id, :reviewer, s.approval::approval_request_status_enum,
       CASE WHEN s.approval IN ('approved', 'rejected') THEN :reviewer
            WHEN s.approval = 'withdrawn' THEN s.user_id END,
       CASE WHEN s.approval <> 'pending' THEN now() END,
       s.comment
FROM e2e_leave_spec s JOIN e2e_leave_ids i USING (key)
WHERE s.approval IS NOT NULL;

-- e2e-member: +60 opening, -12 taken on 1 January of this Beijing year (on
-- or before today whatever the day), so the card reads Available 28 /
-- Pending 20 / Used 12.
-- 990501 and the people whose approval is refused hold 40, so R3 is the only
-- waiting paid request over the balance. 990508's H1 approval wrote -8.
-- 990510 holds 52 for the balance correction.
INSERT INTO leave_ledger (user_id, entry_type, hours, effective_date, source_request_id, note, created_by)
VALUES
  (:member, 'manual_adjustment', 60, '2019-12-31', NULL, 'E2E opening balance', NULL),
  (:member, 'leave_deduction', -12,
     make_date(extract(year FROM now() AT TIME ZONE 'Asia/Shanghai')::int, 1, 1),
     NULL, NULL, :reviewer),
  (990501, 'manual_adjustment', 40, '2019-12-31', NULL, 'E2E opening balance', NULL),
  (990505, 'manual_adjustment', 40, '2019-12-31', NULL, 'E2E opening balance', NULL),
  (990506, 'manual_adjustment', 40, '2019-12-31', NULL, 'E2E opening balance', NULL),
  (990507, 'manual_adjustment', 40, '2019-12-31', NULL, 'E2E opening balance', NULL),
  (990509, 'manual_adjustment', 40, '2019-12-31', NULL, 'E2E opening balance', NULL),
  (990510, 'manual_adjustment', 52, '2019-12-31', NULL, 'E2E opening balance', NULL);
INSERT INTO leave_ledger (user_id, entry_type, hours, effective_date, source_request_id, created_by)
SELECT 990508, 'leave_deduction', -8, '2099-04-07', leave_request_id, :reviewer
FROM e2e_leave_ids WHERE key = 'H1';

\pset tuples_only on
\pset format unaligned
\pset fieldsep '\t'
SELECT 'person', last_name, user_id FROM e2e_leave_people ORDER BY n;
SELECT 'request', key, leave_request_id FROM e2e_leave_ids ORDER BY key;

COMMIT;
