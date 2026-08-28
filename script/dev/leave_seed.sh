#!/usr/bin/env bash
#
# Fake leave data for local development: the postgres half. Run
# leave_seed_redis.sh afterwards -- the database alone leaves every leave
# screen empty, because level, hire date and manager live only in Redis.
#
# Seeds five people, the 2026 company holidays, a ledger with all six entry
# types and enough weekly accruals to page through, and six requests covering
# every status a screen can show.
#
# Safe to re-run: it looks people up by their corporate address before creating
# them, and clears its own ledger and request rows first.
#
# NEVER run this against staging or production.
#
#   ./script/dev/leave_seed.sh you@circlecat.org
#
# The address is the account everything is hung off -- your balance, your
# requests, the LEAVE_ADMIN grant. It has to be the @circlecat.org address you
# sign in with: an Azure ldap is matched to a purrf account by that address and
# by nothing else.
#
# The database comes from DATABASE_URL.

set -euo pipefail

EMAIL="${1:-${LEAVE_SEED_EMAIL:-}}"

if [[ -z "$EMAIL" ]]; then
    echo "usage: $0 <your-address@circlecat.org>" >&2
    echo "       (or set LEAVE_SEED_EMAIL)" >&2
    exit 2
fi

if [[ "$EMAIL" != *@* ]]; then
    echo "'$EMAIL' is not an address. Pass the full @circlecat.org one." >&2
    exit 2
fi

if [[ -z "${DATABASE_URL:-}" ]]; then
    echo "DATABASE_URL is not set." >&2
    exit 2
fi

# DATABASE_URL is written for SQLAlchemy and asyncpg, and psql understands
# neither dialect of it. Two things have to be translated:
#
#   postgresql+asyncpg://  ->  postgresql://    the driver is not part of a URI
#   ?ssl=                  ->  ?sslmode=        libpq's name for the same thing,
#                                               and it takes require/disable
#                                               rather than true/false
DB_URL="${DATABASE_URL/+asyncpg/}"
DB_URL="$(printf '%s' "$DB_URL" | sed -E '
    s/([?&])ssl=true/\1sslmode=require/I
    s/([?&])ssl=false/\1sslmode=disable/I
    s/([?&])ssl=/\1sslmode=/I
')"

# ON_ERROR_STOP matters: without it a failure halfway leaves half the fixture
# behind and still exits 0.
psql "$DB_URL" -v ON_ERROR_STOP=1 -v seed_email="$EMAIL" <<'SQL'
BEGIN;

-- Park the address where the DO block below can read it back.
SELECT set_config('purrf.seed_email', :'seed_email', false);


-- Creates a user with a corporate address if that address is not already
-- taken, and returns the account id either way. Temporary: it disappears when
-- the session ends, and never lands in a migration.
CREATE FUNCTION pg_temp.seed_user(p_email text, p_first text, p_last text)
RETURNS int AS $fn$
DECLARE
    uid int;
BEGIN
    SELECT u.user_id INTO uid
    FROM user_emails e
    JOIN users u ON u.user_id = e.user_id
    WHERE lower(e.email) = lower(p_email);

    IF uid IS NULL THEN
        -- updated_timestamp has no server default in this schema: the ORM
        -- fills it in, so raw SQL has to as well or the insert fails.
        INSERT INTO users (
            first_name, last_name, preferred_name,
            timezone, timezone_updated_at,
            communication_channel, is_active, is_internal, updated_timestamp
        ) VALUES (
            p_first, p_last, NULL,
            'Asia/Shanghai', now(),
            'email', true, true, now()
        ) RETURNING user_id INTO uid;

        INSERT INTO user_emails (user_id, email, otp_confirmed, is_primary)
        VALUES (uid, lower(p_email), true, true);
    ELSE
        -- is_internal is the third admission condition and lives on the purrf
        -- row, not in Azure. Without it the accrual engine files the person
        -- under "not internal" and pays them nothing.
        UPDATE users SET is_internal = true, is_active = true WHERE user_id = uid;
    END IF;

    RETURN uid;
END;
$fn$ LANGUAGE plpgsql;

DO $seed$
DECLARE
    -- Passed in on the command line. psql does not substitute variables
    -- inside a dollar-quoted body, so it travels as a setting instead.
    MY_EMAIL   text := current_setting('purrf.seed_email');

    me         int;
    bob        int;
    dan        int;
    frank      int;
    erin       int;

    req_taken    int;   -- mine, approved, deducted from the ledger
    req_exchange int;   -- mine, approved, credited to the ledger
    req_planned  int;   -- mine, still waiting: gives the card a Pending figure
    req_dan      int;   -- filed against me, waiting on my decision
    req_frank    int;   -- filed against me, approved by rule and not by a person
    req_refused  int;   -- filed against me, rejected

    accrual_weeks CONSTANT date[] := ARRAY(
        -- The weekly job runs Sunday 20:10 UTC, which is Monday morning in
        -- Beijing, so every accrual row is dated a Monday.
        SELECT d::date FROM generate_series('2026-01-05'::date,
                                            '2026-08-24'::date,
                                            '7 days') AS d
    );
BEGIN
    me    := pg_temp.seed_user(MY_EMAIL,                'Demo',  'Intern');
    bob   := pg_temp.seed_user('bob.li@circlecat.org',   'Bob',   'Li');
    dan   := pg_temp.seed_user('dan.zhao@circlecat.org', 'Dan',   'Zhao');
    frank := pg_temp.seed_user('frank.sun@circlecat.org','Frank', 'Sun');
    erin  := pg_temp.seed_user('erin.guo@circlecat.org', 'Erin',  'Guo');

    ------------------------------------------------------------------
    -- The admin side of the feature is gated on one permission.
    ------------------------------------------------------------------
    INSERT INTO user_permissions (
        user_id, permission_name, granted_source, granted_by, granted_timestamp
    )
    SELECT me, 'leave.admin', 'admin', me, now()
    WHERE NOT EXISTS (
        SELECT 1 FROM user_permissions
        WHERE user_id = me
          AND permission_name = 'leave.admin'
          AND revoked_timestamp IS NULL
    );

    ------------------------------------------------------------------
    -- 2026 company holidays.
    --
    -- A multi-day holiday is one row per day sharing a name; the calendar
    -- service groups consecutive same-name, same-exchangeability days back
    -- into the segments the screens show. Without at least one row for a
    -- year, filing leave in that year is refused outright.
    ------------------------------------------------------------------
    DELETE FROM leave_holiday WHERE year = 2026;
    INSERT INTO leave_holiday (year, date, name, is_exchangeable) VALUES
        (2026, '2026-01-01', 'New Year''s Day',           false),
        (2026, '2026-01-24', 'Cat Day',                   false),
        (2026, '2026-02-12', 'Spring Festival',           false),
        (2026, '2026-02-13', 'Spring Festival',           false),
        (2026, '2026-02-14', 'Spring Festival',           false),
        (2026, '2026-02-17', 'Spring Festival week two',  false),
        (2026, '2026-02-18', 'Spring Festival week two',  false),
        (2026, '2026-02-19', 'Spring Festival week two',  false),
        (2026, '2026-02-20', 'Spring Festival week two',  false),
        (2026, '2026-02-21', 'Spring Festival week two',  false),
        (2026, '2026-03-07', 'Eve of International Women''s Day', false),
        (2026, '2026-04-04', 'Eve of Qingming Festival',  true),
        (2026, '2026-04-25', 'Cat Day',                   false),
        (2026, '2026-05-01', 'Labour Day',                true),
        (2026, '2026-05-02', 'Labour Day',                true),
        (2026, '2026-06-19', 'Dragon Boat Festival',      true),
        (2026, '2026-07-25', 'Cat Day',                   false),
        (2026, '2026-09-25', 'Mid-Autumn Festival',       true),
        (2026, '2026-10-01', 'National Day',              true),
        (2026, '2026-10-02', 'National Day',              true),
        (2026, '2026-10-03', 'National Day',              true),
        (2026, '2026-10-06', 'National Day',              true),
        (2026, '2026-10-24', 'Cat Day',                   false);

    ------------------------------------------------------------------
    -- Start from a clean slate for these five.
    --
    -- Ledger first: its rows point at requests, so deleting requests first
    -- would blank the link rather than remove it.
    ------------------------------------------------------------------
    DELETE FROM leave_ledger  WHERE user_id IN (me, bob, dan, frank, erin);
    DELETE FROM leave_request WHERE user_id IN (me, bob, dan, frank, erin)
                                 OR approver_user_id IN (me, bob, dan, frank, erin);

    ------------------------------------------------------------------
    -- Requests.
    --
    -- The working week is Tuesday to Saturday, so every date below is a
    -- working day and the hours are what the server would have computed.
    -- start_time and end_time stay NULL: a CHECK constraint allows them only
    -- on a single-day request.
    ------------------------------------------------------------------

    -- Mine, approved by my manager, and the reason my balance shows leave taken.
    INSERT INTO leave_request (
        user_id, type, start_date, end_date, hours, status,
        approver_user_id, reason, is_overdraft, is_late_notice,
        decided_by, decided_at, updated_timestamp
    ) VALUES (
        me, 'paid', '2026-05-05', '2026-05-06', 16.00, 'approved',
        bob, 'Long weekend', false, false,
        bob, now(), now()
    ) RETURNING leave_request_id INTO req_taken;

    -- Mine: coming in on an exchangeable company holiday buys hours back.
    INSERT INTO leave_request (
        user_id, type, start_date, end_date, hours, status,
        approver_user_id, reason, is_overdraft, is_late_notice,
        decided_by, decided_at, updated_timestamp
    ) VALUES (
        me, 'exchange', '2026-04-04', '2026-04-04', 8.00, 'approved',
        bob, 'Covering the release', false, false,
        bob, now(), now()
    ) RETURNING leave_request_id INTO req_exchange;

    -- Mine, undecided: this is what the Pending figure on the card counts,
    -- and the only one of mine offering a Withdraw button.
    INSERT INTO leave_request (
        user_id, type, start_date, end_date, hours, status,
        approver_user_id, reason, is_overdraft, is_late_notice, updated_timestamp
    ) VALUES (
        me, 'paid', '2026-10-13', '2026-10-14', 16.00, 'pending',
        bob, 'Trip home', false, false, now()
    ) RETURNING leave_request_id INTO req_planned;

    -- Waiting on me. Dan is an L1 with a negative balance, so it is flagged as
    -- an overdraft: approving it takes him further below zero.
    INSERT INTO leave_request (
        user_id, type, start_date, end_date, hours, status,
        approver_user_id, reason, is_overdraft, is_late_notice, updated_timestamp
    ) VALUES (
        dan, 'paid', '2026-09-08', '2026-09-10', 24.00, 'pending',
        me, 'Family visit', true, true, now()
    ) RETURNING leave_request_id INTO req_dan;

    -- Sick leave of three days or less is approved on submission. decided_by
    -- stays NULL -- that is what says nobody decided it -- and it writes no
    -- ledger row at all, not even a zero one.
    INSERT INTO leave_request (
        user_id, type, start_date, end_date, hours, status,
        approver_user_id, reason, is_overdraft, is_late_notice,
        decided_by, decided_at, updated_timestamp
    ) VALUES (
        frank, 'sick', '2026-09-15', '2026-09-16', 16.00, 'approved',
        me, 'Flu', false, false,
        NULL, now(), now()
    ) RETURNING leave_request_id INTO req_frank;

    -- Rejected, so the approvals page has something in its decided section.
    INSERT INTO leave_request (
        user_id, type, start_date, end_date, hours, status,
        approver_user_id, reason, is_overdraft, is_late_notice,
        decided_by, decided_at, updated_timestamp
    ) VALUES (
        dan, 'paid', '2026-06-02', '2026-06-03', 16.00, 'rejected',
        me, 'Short notice', true, true,
        me, now(), now()
    ) RETURNING leave_request_id INTO req_refused;

    ------------------------------------------------------------------
    -- My ledger: one row of every entry type, plus 34 weekly accruals.
    --
    -- -20.00 + 40.00 + 52.36 - 16.00 + 8.00 + 0.00 = 64.36
    ------------------------------------------------------------------

    -- Dated 31 December, not 1 January: the annual job runs on the new year's
    -- day but the cut belongs to the year that ended.
    INSERT INTO leave_ledger (user_id, entry_type, hours, effective_date, note)
    VALUES (me, 'carryover_forfeit', -20.00, '2025-12-31', 'Over the carryover ceiling');

    INSERT INTO leave_ledger (user_id, entry_type, hours, effective_date, note, created_by)
    VALUES (me, 'manual_adjustment', 40.00, '2026-01-02', 'Carried over from 2025', me);

    INSERT INTO leave_ledger (user_id, entry_type, hours, effective_date)
    SELECT me, 'weekly_accrual', 1.54, week FROM unnest(accrual_weeks) AS week;

    -- Zero hours on purpose. The row is read for its date -- where the engine
    -- restarts the proportion from -- not for its amount.
    INSERT INTO leave_ledger (user_id, entry_type, hours, effective_date, note)
    VALUES (me, 'level_change', 0.00, '2026-07-01', 'L2 -> L3');

    INSERT INTO leave_ledger (user_id, entry_type, hours, effective_date, source_request_id, created_by)
    VALUES (me, 'leave_deduction', -16.00, '2026-05-05', req_taken, bob);

    INSERT INTO leave_ledger (user_id, entry_type, hours, effective_date, source_request_id, created_by)
    VALUES (me, 'exchange_credit', 8.00, '2026-04-04', req_exchange, bob);

    ------------------------------------------------------------------
    -- Everybody else, so the all-hands table and the ledger page have more
    -- than one name in them.
    ------------------------------------------------------------------

    -- Bob: 52.36 + 12.00 = 64.36
    INSERT INTO leave_ledger (user_id, entry_type, hours, effective_date)
    SELECT bob, 'weekly_accrual', 1.54, week FROM unnest(accrual_weeks) AS week;
    INSERT INTO leave_ledger (user_id, entry_type, hours, effective_date, note, created_by)
    VALUES (bob, 'manual_adjustment', 12.00, '2026-01-02', 'Carried over from 2025', me);

    -- Frank: 52.36 - 8.00 = 44.36
    INSERT INTO leave_ledger (user_id, entry_type, hours, effective_date)
    SELECT frank, 'weekly_accrual', 1.54, week FROM unnest(accrual_weeks) AS week;
    INSERT INTO leave_ledger (user_id, entry_type, hours, effective_date, created_by)
    VALUES (frank, 'leave_deduction', -8.00, '2026-03-17', me);

    -- Dan is an L1: no annual entitlement at all, so he has no accrual rows
    -- and taking paid leave leaves him at -16.00. That is the expected state
    -- for an L1, which is why the data-health page groups negatives by level
    -- and why a negative figure is never coloured as an error.
    INSERT INTO leave_ledger (user_id, entry_type, hours, effective_date, created_by)
    VALUES (dan, 'leave_deduction', -16.00, '2026-02-24', me);

    -- Erin has nothing: her Azure job title carries no level, so the engine
    -- pays her zero. She exists to fill the data-health page's other column.

    RAISE NOTICE 'Seeded leave data. me=% bob=% dan=% frank=% erin=%',
        me, bob, dan, frank, erin;
    RAISE NOTICE 'Redis ldap for your own profile: %', split_part(MY_EMAIL, '@', 1);
END;
$seed$;

COMMIT;
SQL
