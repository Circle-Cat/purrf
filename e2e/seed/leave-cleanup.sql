-- Removes what leave-seed.sql created and what the leave e2e specs did.
--
--   psql "$E2E_DATABASE_URL" -X -v ON_ERROR_STOP=1 \
--        -v accounts=267,276,277,279,280 -f e2e/seed/leave-cleanup.sql
--
-- Idempotent. Suite people: the seed employees (990501-990599 with at least
-- one address, every one a wangyanpei76+e2e-leave-… alias) and the test
-- accounts. Every leave row of a test account is the suite's: no real
-- process can write one (accrual and filing both need a company address,
-- which global setup proves the accounts lack; adjustments go through the
-- guard).
-- Holidays: only rows named "E2E …" in 2019 and 2099.

\set ON_ERROR_STOP on

BEGIN;

CREATE TEMP TABLE e2e_leave_people ON COMMIT DROP AS
SELECT u.user_id FROM users u
WHERE u.user_id BETWEEN 990501 AND 990599
  AND EXISTS (SELECT 1 FROM user_emails e
              WHERE e.user_id = u.user_id AND e.email LIKE 'wangyanpei76+e2e-leave-%@gmail.com')
  AND NOT EXISTS (SELECT 1 FROM user_emails e
                  WHERE e.user_id = u.user_id
                    AND e.email NOT LIKE 'wangyanpei76+e2e-leave-%@gmail.com');

CREATE TEMP TABLE e2e_leave_owners ON COMMIT DROP AS
SELECT user_id FROM e2e_leave_people
UNION SELECT unnest(string_to_array(:'accounts', ',')::int[]);

-- Only requests a suite person filed: a real person's request with a test
-- account as approver is not the suite's.
CREATE TEMP TABLE e2e_leave_requests ON COMMIT DROP AS
SELECT leave_request_id FROM leave_request
WHERE user_id IN (SELECT user_id FROM e2e_leave_owners);

-- Notifications cascade from their event.
CREATE TEMP TABLE e2e_leave_events ON COMMIT DROP AS
SELECT event_id FROM event
WHERE subject_type = 'leave_request'
  AND subject_id IN (SELECT leave_request_id FROM e2e_leave_requests);
DELETE FROM event WHERE event_id IN (SELECT event_id FROM e2e_leave_events);
CREATE TEMP TABLE e2e_leave_approvals ON COMMIT DROP AS
SELECT request_id FROM approval_request
WHERE action = 'leave_approval'
  AND target_id IN (SELECT leave_request_id::text FROM e2e_leave_requests);
DELETE FROM approval_request WHERE request_id IN (SELECT request_id FROM e2e_leave_approvals);
CREATE TEMP TABLE e2e_leave_entries ON COMMIT DROP AS
SELECT leave_ledger_id FROM leave_ledger
WHERE user_id IN (SELECT user_id FROM e2e_leave_owners)
   OR source_request_id IN (SELECT leave_request_id FROM e2e_leave_requests);
DELETE FROM leave_ledger WHERE leave_ledger_id IN (SELECT leave_ledger_id FROM e2e_leave_entries);
DELETE FROM leave_request
WHERE leave_request_id IN (SELECT leave_request_id FROM e2e_leave_requests);

CREATE TEMP TABLE e2e_leave_holidays ON COMMIT DROP AS
SELECT leave_holiday_id FROM leave_holiday WHERE year IN (2019, 2099) AND name LIKE 'E2E %';
DELETE FROM leave_holiday WHERE leave_holiday_id IN (SELECT leave_holiday_id FROM e2e_leave_holidays);

-- approval_request references users without a cascade; every leave_approval
-- row naming a seed person is gone by now, and no other action names one.
DELETE FROM user_identities WHERE user_id IN (SELECT user_id FROM e2e_leave_people);
DELETE FROM user_permissions WHERE user_id IN (SELECT user_id FROM e2e_leave_people);
DELETE FROM user_emails WHERE user_id IN (SELECT user_id FROM e2e_leave_people);
DELETE FROM users WHERE user_id IN (SELECT user_id FROM e2e_leave_people);

SELECT (SELECT count(*) FROM e2e_leave_requests) AS requests_removed,
       (SELECT count(*) FROM e2e_leave_approvals) AS approvals_removed,
       (SELECT count(*) FROM e2e_leave_events) AS events_removed,
       (SELECT count(*) FROM e2e_leave_entries) AS ledger_rows_removed,
       (SELECT count(*) FROM e2e_leave_holidays) AS holidays_removed,
       (SELECT count(*) FROM e2e_leave_people) AS people_removed;

COMMIT;
