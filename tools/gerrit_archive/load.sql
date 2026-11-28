-- Step 2 of the Gerrit archive: load the export.sh CSVs into code_weekly_stats.
-- Needs the migration that creates code_weekly_stats (f320a5c564a7) applied.
--
-- Run through load.sh, which fills in the CSV paths:
--   bash tools/gerrit_archive/load.sh '<url>'            dry run, ROLLBACK
--   bash tools/gerrit_archive/load.sh '<url>' --commit   after a Neon branch
--
-- Safe to run again: Gerrit rows are upserted on the primary key and nothing
-- with source = 'github' is touched.
\set ON_ERROR_STOP on
BEGIN;

CREATE TEMP TABLE archive_rows (
  account text, repo text, week_start date,
  merged int, loc_merged int, reviewed int, closed int
) ON COMMIT DROP;
CREATE TEMP TABLE archive_globals (
  account text, week_start date,
  merged int, loc_merged int, reviewed int, closed int
) ON COMMIT DROP;

\copy archive_rows FROM '__ROWS_FILE__' WITH (FORMAT csv, HEADER true)
\copy archive_globals FROM '__GLOBALS_FILE__' WITH (FORMAT csv, HEADER true)

-- Buckets with nothing in them carry no information.
DELETE FROM archive_rows WHERE merged = 0 AND loc_merged = 0 AND reviewed = 0 AND closed = 0;

INSERT INTO code_weekly_stats (source, account, repo, week_start, merged, loc_merged, reviewed, closed)
SELECT 'gerrit', account, repo, week_start, merged, loc_merged, reviewed, closed
FROM archive_rows
ON CONFLICT (source, account, repo, week_start) DO UPDATE
SET merged = EXCLUDED.merged, loc_merged = EXCLUDED.loc_merged,
    reviewed = EXCLUDED.reviewed, closed = EXCLUDED.closed, updated_at = now();

-- Check 1: totals. archived must equal per_project; per_person is Redis's own
-- per-person total and should match too.
SELECT 'totals' AS check_name,
       (SELECT count(*) FROM code_weekly_stats WHERE source = 'gerrit') AS archived_rows,
       (SELECT sum(merged) FROM code_weekly_stats WHERE source = 'gerrit') AS archived_merged,
       (SELECT sum(merged) FROM archive_rows) AS per_project_merged,
       (SELECT sum(merged) FROM archive_globals) AS per_person_merged,
       (SELECT sum(reviewed) FROM code_weekly_stats WHERE source = 'gerrit') AS archived_reviewed,
       (SELECT sum(reviewed) FROM archive_globals) AS per_person_reviewed,
       (SELECT min(week_start) FROM code_weekly_stats WHERE source = 'gerrit') AS first_week,
       (SELECT max(week_start) FROM code_weekly_stats WHERE source = 'gerrit') AS last_week;

-- Check 2: person-weeks where the per-project rows do not add up to Redis's
-- per-person bucket. Expect none; any rows here are worth a look before commit.
SELECT coalesce(p.account, g.account) AS account, coalesce(p.week_start, g.week_start) AS week_start,
       p.merged AS projects_merged, g.merged AS person_merged,
       p.loc_merged AS projects_loc, g.loc_merged AS person_loc,
       p.reviewed AS projects_reviewed, g.reviewed AS person_reviewed,
       p.closed AS projects_closed, g.closed AS person_closed
FROM (SELECT account, week_start, sum(merged) merged, sum(loc_merged) loc_merged,
             sum(reviewed) reviewed, sum(closed) closed
      FROM code_weekly_stats WHERE source = 'gerrit' GROUP BY 1, 2) p
FULL JOIN (SELECT * FROM archive_globals
           WHERE merged + loc_merged + reviewed + closed > 0) g
  ON g.account = p.account AND g.week_start = p.week_start
WHERE p.merged IS DISTINCT FROM g.merged OR p.loc_merged IS DISTINCT FROM g.loc_merged
   OR p.reviewed IS DISTINCT FROM g.reviewed OR p.closed IS DISTINCT FROM g.closed
ORDER BY 1, 2
LIMIT 50;

\if :{?commit}
  COMMIT;
  \echo 'COMMITTED'
\else
  ROLLBACK;
  \echo 'DRY RUN: rolled back. Re-run with --commit to keep it.'
\endif
