-- Mentorship e2e seed for the shared TEST database.
--
--   psql "$E2E_DATABASE_URL" -X -v ON_ERROR_STOP=1 \
--        -v round_id=<round in progress> -v prev_round_id=<latest ended round> \
--        -v member_id=<e2e-member user_id> -f e2e/seed/seed.sql
--
-- Creates fake people (user_id 990001-990022, primary emails @e2e.purrf.test)
-- and registers e2e-member as a mentee in :round_id. Undo with cleanup.sql,
-- which takes the same round_id and member_id.
--
-- Seeded people, all in :round_id unless noted:
--   Mentor A1 + Mentee A1, Mentor A2 + Mentee A2   matched, active pair
--   Mentor C1 + Mentee C1                          matched, active pair (blocked by a test)
--   Mentee S1                                      signed_up, no pair
--   Mentee W1                                      withdrawn, inactive pair to
--   Mentor W-M1                                    un_matched (partner left)
--   Mentor B1, Mentor B2, Mentee B1, Mentee B2     signed_up, eligible
--   e2e-member (:member_id)                        signed_up mentee, eligible
--   Mentee H1                                      signed_up; in :prev_round_id
--                                                  withdrew after being matched
--                                                  to Mentor H-M1, so needs a
--                                                  matching exemption
--                                                  (quit_after_match)
--   Mentor H-M1                                    :prev_round_id only; also
--                                                  admitted as a mentor (a hired
--                                                  application to the mentor
--                                                  activity posting), so on
--                                                  the Not registered list
--   Mentor D1 (1 slot), Mentee D1, Mentee D2       signed_up, eligible: a run
--                                                  over them leaves a mentee
--                                                  unmatched
--   Mentor E1 + Mentee E1                          matched, active pair with two
--                                                  meetings: one completed, one
--                                                  where Mentee E1 was absent
--                                                  (an attendance issue).
--                                                  Mentor E1 is internal.
--   Mentee H2                                      like Mentee H1 (needs an
--                                                  exemption, quit after being
--                                                  matched to Mentor H-M1)
--   Mentee X1                                      signed_up, account
--                                                  deactivated, onboarding
--                                                  training not done
--
-- Every seeded participant but Mentee X1 has DONE onboarding training for their role, which
-- is what the matching gate and the participant list's Training column read
-- (training.category + training.status = 'done').
--
-- e2e-member's mentee onboarding training is set to done as well (inserted
-- when missing, updated when not done). cleanup.sql does not undo that: it is
-- the test account's steady state.

\set ON_ERROR_STOP on

\if :{?round_id}
\else
  \echo 'seed.sql: pass -v round_id=<id>'
  \quit
\endif
\if :{?prev_round_id}
\else
  \echo 'seed.sql: pass -v prev_round_id=<id>'
  \quit
\endif
\if :{?member_id}
\else
  \echo 'seed.sql: pass -v member_id=<id>'
  \quit
\endif

-- The rounds and the member must exist, and the previous round must sort
-- before the current one the way the eligibility code orders history: by
-- meetings_completion_deadline_at, both non-null.
SELECT NOT (
        EXISTS (SELECT 1 FROM users WHERE user_id = :member_id)
    AND EXISTS (
        SELECT 1
        FROM mentorship_round cur, mentorship_round prev
        WHERE cur.round_id = :round_id
          AND prev.round_id = :prev_round_id
          AND cur.round_id <> prev.round_id
          AND prev.meetings_completion_deadline_at IS NOT NULL
          AND cur.meetings_completion_deadline_at IS NOT NULL
          AND prev.meetings_completion_deadline_at < cur.meetings_completion_deadline_at
    )
) AS bad_input \gset
\if :bad_input
  \echo 'seed.sql: refused. member_id must be an existing user, and prev_round_id must end (meetings_completion_deadline_at) before round_id.'
  \quit
\endif

SELECT EXISTS (
           SELECT 1 FROM users u
           WHERE u.user_id >= 990001
             AND EXISTS (SELECT 1 FROM user_emails e
                         WHERE e.user_id = u.user_id
                           AND e.email LIKE '%@e2e.purrf.test'))
    OR EXISTS (SELECT 1 FROM user_emails WHERE email LIKE '%@e2e.purrf.test')
    OR EXISTS (SELECT 1 FROM mentorship_round_participants
               WHERE user_id = :member_id AND round_id = :round_id)
    OR EXISTS (SELECT 1 FROM mentorship_pairs
               WHERE round_id = :round_id
                 AND :member_id IN (mentor_id, mentee_id))
    AS already \gset
\if :already
  \echo 'seed.sql: refused. Seed rows already exist (or e2e-member is already in round_id); run cleanup.sql first.'
  \quit
\endif

-- The fixed ids must be free: a real user there would be mistaken for seed.
SELECT EXISTS (SELECT 1 FROM users WHERE user_id BETWEEN 990001 AND 990022)
    AS ids_taken \gset
\if :ids_taken
  \echo 'seed.sql: refused. A user with an id in 990001-990022 exists and is not seed data.'
  \quit
\endif

BEGIN;

CREATE TEMP TABLE e2e_people (
    user_id     integer PRIMARY KEY,
    last_name   text NOT NULL,
    email_local text NOT NULL,
    role        text NOT NULL
) ON COMMIT DROP;

INSERT INTO e2e_people (user_id, last_name, email_local, role) VALUES
    (990001, 'Mentor A1',   'mentor.a1',  'mentor'),
    (990002, 'Mentee A1',   'mentee.a1',  'mentee'),
    (990003, 'Mentor A2',   'mentor.a2',  'mentor'),
    (990004, 'Mentee A2',   'mentee.a2',  'mentee'),
    (990005, 'Mentee S1',   'mentee.s1',  'mentee'),
    (990006, 'Mentee W1',   'mentee.w1',  'mentee'),
    (990007, 'Mentor W-M1', 'mentor.wm1', 'mentor'),
    (990008, 'Mentor B1',   'mentor.b1',  'mentor'),
    (990009, 'Mentor B2',   'mentor.b2',  'mentor'),
    (990010, 'Mentee B1',   'mentee.b1',  'mentee'),
    (990011, 'Mentee B2',   'mentee.b2',  'mentee'),
    (990012, 'Mentee H1',   'mentee.h1',  'mentee'),
    (990013, 'Mentor H-M1', 'mentor.hm1', 'mentor'),
    (990014, 'Mentor C1',   'mentor.c1',  'mentor'),
    (990015, 'Mentee C1',   'mentee.c1',  'mentee'),
    (990016, 'Mentor D1',   'mentor.d1',  'mentor'),
    (990017, 'Mentee D1',   'mentee.d1',  'mentee'),
    (990018, 'Mentee D2',   'mentee.d2',  'mentee'),
    (990019, 'Mentor E1',   'mentor.e1',  'mentor'),
    (990020, 'Mentee E1',   'mentee.e1',  'mentee'),
    (990021, 'Mentee H2',   'mentee.h2',  'mentee'),
    (990022, 'Mentee X1',   'mentee.x1',  'mentee');

-- updated_timestamp has only a client-side default, so it is set here.
INSERT INTO users (
    user_id, first_name, last_name, timezone, timezone_updated_at,
    communication_channel, is_active, is_internal, is_super_admin, is_blocked,
    updated_timestamp
)
SELECT user_id, 'E2E', last_name, 'America/Los_Angeles', now(),
       'email', user_id <> 990022, user_id = 990019, false, false, now()
FROM e2e_people;

INSERT INTO user_emails (user_id, email, otp_confirmed, is_primary)
SELECT user_id, 'e2e.' || email_local || '@e2e.purrf.test', true, true
FROM e2e_people;

-- Onboarding training for the role, done. course_id points at the catalogue
-- course for the category when there is one (null otherwise, as on rows the
-- dispatch writes when the catalogue has none).
INSERT INTO training (user_id, category, status, completed_timestamp, deadline, course_id)
SELECT p.user_id, c.category::training_category,
       CASE WHEN p.user_id = 990022 THEN 'in_progress' ELSE 'done' END::training_status,
       CASE WHEN p.user_id = 990022 THEN NULL ELSE now() - interval '10 days' END,
       (SELECT onboarding_deadline_at FROM mentorship_round WHERE round_id = :round_id),
       (SELECT tc.course_id FROM training_course tc
        WHERE tc.category::text = c.category
        ORDER BY tc.is_active DESC, tc.course_id LIMIT 1)
FROM e2e_people p
CROSS JOIN LATERAL (
    SELECT CASE p.role WHEN 'mentor' THEN 'mentorship_mentor_onboarding'
                       ELSE 'mentorship_mentee_onboarding' END AS category
) c;

-- e2e-member: make the mentee onboarding count as done.
UPDATE training
SET status = 'done', completed_timestamp = COALESCE(completed_timestamp, now())
WHERE user_id = :member_id
  AND category = 'mentorship_mentee_onboarding'
  AND status <> 'done';

INSERT INTO training (user_id, category, status, completed_timestamp, deadline, course_id)
SELECT :member_id, 'mentorship_mentee_onboarding', 'done', now(),
       (SELECT onboarding_deadline_at FROM mentorship_round WHERE round_id = :round_id),
       (SELECT tc.course_id FROM training_course tc
        WHERE tc.category = 'mentorship_mentee_onboarding'
          AND NOT EXISTS (SELECT 1 FROM training t
                          WHERE t.user_id = :member_id AND t.course_id = tc.course_id)
        ORDER BY tc.is_active DESC, tc.course_id LIMIT 1)
WHERE NOT EXISTS (SELECT 1 FROM training
                  WHERE user_id = :member_id
                    AND category = 'mentorship_mentee_onboarding');

-- Registrations. Mentees carry the registration answers the matcher reads
-- (goal, current_stage -> mentee_stage, time_urgency -> urgency, using the
-- stored keys of MENTEE_STAGE_MAP / URGENCY_MAP). Partner preference arrays
-- stay null. Mentors waiting for matching take two mentees.
INSERT INTO mentorship_round_participants (
    participant_id, user_id, round_id, participant_role, approval_status,
    match_email_sent, max_partners, goal, current_stage, time_urgency
)
SELECT gen_random_uuid(), p.user_id, v.round_id, p.role::participant_role,
       v.status::approval_status, v.status = 'matched', v.max_partners,
       CASE WHEN p.role = 'mentee' THEN 'E2E seed goal: land a software engineering role.' END,
       CASE WHEN p.role = 'mentee' THEN 'job_searching' END,
       CASE WHEN p.role = 'mentee' THEN 'within_6_months' END
FROM (VALUES
    (990001, :round_id,      'matched',    1),
    (990002, :round_id,      'matched',    1),
    (990003, :round_id,      'matched',    1),
    (990004, :round_id,      'matched',    1),
    (990005, :round_id,      'signed_up',  1),
    (990006, :round_id,      'withdrawn',  1),
    (990007, :round_id,      'un_matched', 1),
    (990008, :round_id,      'signed_up',  2),
    (990009, :round_id,      'signed_up',  2),
    (990010, :round_id,      'signed_up',  1),
    (990011, :round_id,      'signed_up',  1),
    (990012, :round_id,      'signed_up',  1),
    (990012, :prev_round_id, 'withdrawn',  1),
    (990013, :prev_round_id, 'un_matched', 1),
    (990014, :round_id,      'matched',    1),
    (990015, :round_id,      'matched',    1),
    (990016, :round_id,      'signed_up',  1),
    (990017, :round_id,      'signed_up',  1),
    (990018, :round_id,      'signed_up',  1),
    (990019, :round_id,      'matched',    1),
    (990020, :round_id,      'matched',    1),
    (990021, :round_id,      'signed_up',  1),
    (990021, :prev_round_id, 'withdrawn',  1),
    (990022, :round_id,      'signed_up',  1)
) AS v(user_id, round_id, status, max_partners)
JOIN e2e_people p USING (user_id);

INSERT INTO mentorship_round_participants (
    participant_id, user_id, round_id, participant_role, approval_status,
    match_email_sent, max_partners, goal, current_stage, time_urgency
) VALUES (
    gen_random_uuid(), :member_id, :round_id, 'mentee', 'signed_up',
    false, 1, 'E2E seed goal: land a software engineering role.',
    'job_searching', 'within_6_months'
);

-- The personal dashboard shows the mentorship card only to someone with a
-- hired application to a mentee activity posting, so the member gets one.
-- Tagged so cleanup removes this row and never a real application.
INSERT INTO application (job_id, user_id, stage, current_round, tags, updated_timestamp)
SELECT j.job_id, :member_id, 'hired', 1, '{"e2e": true}'::jsonb, now()
FROM job j
WHERE j.kind = 'activity' AND j.mentorship_role = 'mentee' AND j.status = 'published'
  AND NOT EXISTS (
      SELECT 1 FROM application a
      WHERE a.job_id = j.job_id AND a.user_id = :member_id
  )
ORDER BY j.job_id
LIMIT 1;

-- Mentor H-M1 is admitted as a mentor and has not registered for :round_id,
-- which is what puts someone on the Not registered list.
INSERT INTO application (job_id, user_id, stage, current_round, tags, updated_timestamp)
SELECT j.job_id, 990013, 'hired', 1, '{"e2e": true}'::jsonb, now()
FROM job j
WHERE j.kind = 'activity' AND j.mentorship_role = 'mentor' AND j.status = 'published'
ORDER BY j.job_id
LIMIT 1;

-- Pairs. W1's and H1's pairs are inactive: withdrawing ends the pair and
-- moves the partner from matched to un_matched (pair_endings.unmatch_if_unpaired).
INSERT INTO mentorship_pairs (
    round_id, mentor_id, mentee_id, completed_count, status,
    mentor_action_status, mentee_action_status, recommendation_reason
)
SELECT v.round_id, v.mentor_id, v.mentee_id, 0, v.status::pair_status_enum,
       'pending', 'pending', 'e2e seed'
FROM (VALUES
    (:round_id,      990001, 990002, 'active'),
    (:round_id,      990003, 990004, 'active'),
    (:round_id,      990007, 990006, 'inactive'),
    (:prev_round_id, 990013, 990012, 'inactive'),
    (:round_id,      990014, 990015, 'active'),
    (:prev_round_id, 990013, 990021, 'inactive'),
    (:round_id,      990019, 990020, 'active')
) AS v(round_id, mentor_id, mentee_id, status);

-- Mentor E1 and Mentee E1 have met once; at the second meeting, recorded
-- from Google Meet, Mentee E1 did not come.
UPDATE mentorship_pairs SET completed_count = 1
WHERE round_id = :round_id AND mentor_id = 990019 AND mentee_id = 990020;

INSERT INTO mentorship_meeting (
    meeting_id, pair_id, source, start_datetime, end_datetime, is_completed,
    absent_user_id, late_user_ids, has_unknown_absent, has_unknown_late,
    has_insufficient_duration, last_sync_at
)
SELECT 'e2e-' || p.pair_id || '-' || v.n, p.pair_id, 'google',
       date_trunc('hour', now()) - v.ago,
       date_trunc('hour', now()) - v.ago + interval '45 minutes',
       v.done, v.absent, '{}', false, false, false, now()
FROM mentorship_pairs p
CROSS JOIN (VALUES
    (1, interval '14 days', true,  NULL::integer),
    (2, interval '7 days',  false, 990020)
) AS v(n, ago, done, absent)
WHERE p.round_id = :round_id AND p.mentor_id = 990019 AND p.mentee_id = 990020;

SELECT u.user_id, u.first_name || ' ' || u.last_name AS name,
       r.round_id, r.participant_role AS role, r.approval_status AS status,
       (SELECT string_agg(p.status::text || ' pair ' || p.pair_id, ', ')
        FROM mentorship_pairs p
        WHERE p.round_id = r.round_id
          AND u.user_id IN (p.mentor_id, p.mentee_id)) AS pairs
FROM mentorship_round_participants r
JOIN users u ON u.user_id = r.user_id
WHERE r.user_id IN (SELECT user_id FROM e2e_people)
   OR (r.user_id = :member_id AND r.round_id = :round_id)
ORDER BY r.round_id DESC, u.user_id;

COMMIT;
