#!/usr/bin/env bash
#
# Fake leave data for local development.
#
# Seeds five people, the 2026 company holidays, a ledger with all six entry
# types and enough weekly accruals to page through, and six requests covering
# every status a screen can show.
#
#   ./script/dev/leave_seed.sh you@circlecat.org
#
# The address is the account everything is hung off -- your balance, your
# requests, the LEAVE_ADMIN grant, your employment profile. It has to be the
# @circlecat.org address you sign in with: an Azure ldap is matched to a purrf
# account by that address and by nothing else.
#
# It writes to two places because the feature reads from two. The ledger, the
# requests and the holidays are rows in postgres; level, hire date and manager
# are not stored there at all -- they live only in the Redis hash the nightly
# Azure sync writes. Seed one without the other and every leave screen is still
# empty: the accrual engine walks that hash to find people, the all-hands table
# is built from it, and filing a request looks the approver up in it.
#
# Postgres comes from DATABASE_URL; Redis from REDIS_HOST, REDIS_PORT and
# REDIS_PASSWORD -- the same variables the backend reads. --db-only and
# --redis-only run one half, for when the two are not reachable from the same
# place.
#
# Safe to re-run: it looks people up by their corporate address before creating
# them, and clears its own ledger and request rows first.
#
# NEVER run this against staging or production. On any environment where the
# nightly ldap sync actually runs, the Redis profiles are deleted the next time
# it fires -- it drops every ldap Azure did not return.

set -euo pipefail

EMAIL=""
DO_DB=true
DO_REDIS=true

usage() {
    echo "usage: $0 [--db-only|--redis-only] <your-address@circlecat.org>" >&2
    echo "       (the address may also come from LEAVE_SEED_EMAIL)" >&2
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --db-only)    DO_REDIS=false ;;
        --redis-only) DO_DB=false ;;
        -h|--help)    usage; exit 0 ;;
        -*)           echo "unknown option: $1" >&2; usage; exit 2 ;;
        *)            EMAIL="$1" ;;
    esac
    shift
done

EMAIL="${EMAIL:-${LEAVE_SEED_EMAIL:-}}"

if [[ -z "$EMAIL" ]]; then
    usage
    exit 2
fi

if [[ "$EMAIL" != *@* ]]; then
    echo "'$EMAIL' is not an address. Pass the full @circlecat.org one." >&2
    exit 2
fi

seed_database() {
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
    local DB_URL="${DATABASE_URL/+asyncpg/}"
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
}

seed_redis() {
    # The hash is keyed by Azure ldap, so the address comes down to its local
    # part -- the join between an ldap and a purrf account is that address.
    local ME="${EMAIL%%@*}"
    local -a REDIS

    # Which Redis, and how to reach it.
    #
    # REDIS_HOST, REDIS_PORT and REDIS_PASSWORD are the same three the backend
    # reads, so an environment already configured for the app needs nothing more.
    # TLS is on by default whenever a host is given: the backend connects with
    # ssl=True and no way to turn it off, so a Redis it can use is a Redis that
    # speaks TLS. Set REDIS_TLS=false for one that does not.
    #
    # With no host at all this falls back to a plain local redis-cli. REDIS_CLI
    # overrides the lot -- for a client needing a CA file, a socket, or anything
    # else this does not spell:
    #
    #   REDIS_CLI="redis-cli -h host -p 6379 -a secret --tls --cacert ca.pem"
    if [[ -n "${REDIS_CLI:-}" ]]; then
        read -r -a REDIS <<< "$REDIS_CLI"
    elif [[ -n "${REDIS_HOST:-}" ]]; then
        REDIS=(redis-cli -h "$REDIS_HOST" -p "${REDIS_PORT:-6379}")
        if [[ -n "${REDIS_PASSWORD:-}" ]]; then
            REDIS+=(-a "$REDIS_PASSWORD" --no-auth-warning)
        fi
        if [[ "${REDIS_TLS:-true}" != "false" ]]; then
            REDIS+=(--tls)
        fi
    else
        REDIS=(redis-cli)
    fi
    KEY=leave:employment

    # level      -- L1 has no annual entitlement, L2 to L4 get 80 hours a year.
    # annual_hours -- what the engine pays towards; it does not re-derive it.
    # hire_date  -- where accrual starts counting, as a Beijing calendar date.
    # leave_date -- null while they are still here.
    # manager_ldap -- who approves for them. Missing means they cannot file
    #                 anything at all, sick leave included.
    # problems   -- what the data-health page lists them under.

    # You: an L3 with a manager, so you can file requests.
    "${REDIS[@]}" HSET "$KEY" "$ME" '{"account_enabled": true, "annual_hours": 80, "hire_date": "2024-03-04", "leave_date": null, "level": "L3", "manager_ldap": "bob.li", "problems": []}'

    # Your manager. He is at the top of the tree with nobody above him, which is
    # what the "No manager in Azure" column on the data-health page is for -- and
    # it means Bob himself cannot file a request.
    "${REDIS[@]}" HSET "$KEY" bob.li '{"account_enabled": true, "annual_hours": 80, "hire_date": "2021-06-01", "leave_date": null, "level": "L4", "manager_ldap": null, "problems": ["missing_manager"]}'

    # Reports to you. An L1: no entitlement, so no accrual rows and a permanently
    # negative balance once he takes paid leave. Expected, not broken.
    "${REDIS[@]}" HSET "$KEY" dan.zhao '{"account_enabled": true, "annual_hours": 0, "hire_date": "2025-09-15", "leave_date": null, "level": "L1", "manager_ldap": "'"$ME"'", "problems": []}'

    # Reports to you. Ordinary L2.
    "${REDIS[@]}" HSET "$KEY" frank.sun '{"account_enabled": true, "annual_hours": 80, "hire_date": "2023-01-10", "leave_date": null, "level": "L2", "manager_ldap": "'"$ME"'", "problems": []}'

    # Reports to you, but her Azure job title does not parse into a level, so she
    # accrues nothing while looking exactly like an L1 in the figures. The
    # data-health page exists to tell those two apart.
    "${REDIS[@]}" HSET "$KEY" erin.guo '{"account_enabled": true, "annual_hours": 0, "hire_date": "2024-11-04", "leave_date": null, "level": null, "manager_ldap": "'"$ME"'", "problems": ["unparseable_job_title"]}'

    echo
    echo "Profiles now in $KEY:"
    "${REDIS[@]}" HKEYS "$KEY"
}

if [[ "$DO_DB" == true ]]; then
    seed_database
fi

if [[ "$DO_REDIS" == true ]]; then
    seed_redis
fi
