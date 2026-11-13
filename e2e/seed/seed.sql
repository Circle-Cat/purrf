-- Mentorship e2e seed for the shared TEST database.
--
--   psql "$E2E_DATABASE_URL" -X -v ON_ERROR_STOP=1 \
--        -v member_id=<e2e-member user_id> -f e2e/seed/seed.sql
--
-- Creates rounds of its own, named "E2E seed …", and fake people (user_id
-- 990001-990028, primary emails @e2e.purrf.test) in them, and registers
-- e2e-member. No real round is read from or written to, except that the
-- registration round's dates are placed after every real round open for
-- registration. Undo with cleanup.sql, which takes the same member_id.
--
-- Rounds, all dates relative to now():
--   E2E seed live round          in progress, past matching: registration
--                                closed 40 days ago, the meeting window open,
--                                feedback not open yet. Every console spec
--                                works here.
--   E2E seed registration round  registration open now. Its application and
--                                onboarding deadlines lie after those of
--                                every real round open for registration, so
--                                the Personal Dashboard and the admission
--                                email (both take the open round closing
--                                first) keep pointing at the real round.
--                                Created only while a real round is open for
--                                registration: otherwise it would be the
--                                round they point at.
--   E2E seed feedback round      meetings over 5 days ago, feedback open.
--   E2E seed previous round      ended 200 days ago (participation history).
--
-- Seeded people, in the live round unless noted:
--   Mentor A1 + Mentee A1, Mentor A2 + Mentee A2   matched, active pair
--   Mentor C1 + Mentee C1                          matched, active pair (blocked by a test)
--   Mentee S1                                      signed_up, no pair
--   Mentee W1                                      withdrawn, inactive pair to
--   Mentor W-M1                                    un_matched (partner left)
--   Mentor B1, Mentor B2, Mentee B1, Mentee B2     signed_up, eligible
--   e2e-member (:member_id)                        signed_up mentee, eligible
--   Mentee H1                                      signed_up; in the previous
--                                                  round withdrew after being
--                                                  matched to Mentor H-M1, so
--                                                  needs a matching exemption
--                                                  (quit_after_match)
--   Mentor H-M1                                    previous round only; also
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
--   Mentee H2                                      like Mentee H1
--   Mentee X1                                      signed_up, account
--                                                  deactivated, onboarding
--                                                  training not done
--   Mentor G1 + Mentee G1                          matched, active pair with one
--                                                  completed Google Meet meeting,
--                                                  so its log is v2 and an admin
--                                                  can edit it
--   Mentor L1, Mentee L1                           signed_up, eligible: the
--                                                  edit-lock test's own run
--   Mentor F1 + e2e-member                         feedback round only: a pair
--                                                  that met the round's
--                                                  requirement (so it holds
--                                                  nothing against the member
--                                                  in the live round)
--   Mentee R1                                      registration round only,
--                                                  signed_up
--
-- Every seeded participant but Mentee X1 has DONE onboarding training for their role, which
-- is what the matching gate and the participant list's Training column read
-- (training.category + training.status = 'done').
--
-- e2e-member's mentee onboarding training is set to done as well (inserted
-- when missing, updated when not done). cleanup.sql does not undo that: it is
-- the test account's steady state.
--
-- Prints the new rounds as "kind<TAB>round_id<TAB>name" lines last.

\set ON_ERROR_STOP on

\if :{?member_id}
\else
  \echo 'seed.sql: pass -v member_id=<id>'
  \quit
\endif

SELECT NOT EXISTS (SELECT 1 FROM users WHERE user_id = :member_id) AS bad_input \gset
\if :bad_input
  \echo 'seed.sql: refused. member_id must be an existing user.'
  \quit
\endif

SELECT EXISTS (
           SELECT 1 FROM users u
           WHERE u.user_id >= 990001
             AND EXISTS (SELECT 1 FROM user_emails e
                         WHERE e.user_id = u.user_id
                           AND e.email LIKE '%@e2e.purrf.test'))
    OR EXISTS (SELECT 1 FROM user_emails WHERE email LIKE '%@e2e.purrf.test')
    OR EXISTS (SELECT 1 FROM mentorship_round WHERE name LIKE 'E2E seed %')
    AS already \gset
\if :already
  \echo 'seed.sql: refused. Seed rows or E2E seed rounds already exist; run cleanup.sql first.'
  \quit
\endif

-- The fixed ids must be free: a real user there would be mistaken for seed.
SELECT EXISTS (SELECT 1 FROM users WHERE user_id BETWEEN 990001 AND 990028)
    AS ids_taken \gset
\if :ids_taken
  \echo 'seed.sql: refused. A user with an id in 990001-990028 exists and is not seed data.'
  \quit
\endif

BEGIN;

-- The rounds. created_datetime has a server default; every other date is set.
CREATE TEMP TABLE e2e_rounds (
    kind     text PRIMARY KEY,
    round_id integer NOT NULL
) ON COMMIT DROP;

WITH t AS (SELECT date_trunc('hour', now()) AS n),
created AS (
    INSERT INTO mentorship_round (
        name, required_meetings, description,
        promotion_start_at, mentor_application_deadline_at,
        mentee_application_deadline_at, onboarding_notification_at,
        onboarding_deadline_at, match_notification_at,
        first_meeting_deadline_at, meeting_log_reminder_at,
        meetings_completion_deadline_at, feedback_start_at, feedback_deadline_at
    )
    SELECT v.name, v.required, NULL,
           t.n + v.promo, t.n + v.app, t.n + v.app, t.n + v.onb_note,
           t.n + v.onb, t.n + v.match, t.n + v.first, t.n + v.log_reminder,
           t.n + v.done, t.n + v.fb_start, t.n + v.fb_end
    FROM t CROSS JOIN (VALUES
        ('E2E seed live round', 5,
         interval '-60 days', interval '-45 days', interval '-44 days',
         interval '-40 days', interval '-30 days', interval '-20 days',
         interval '20 days', interval '40 days', interval '42 days', interval '50 days'),
        ('E2E seed feedback round', 3,
         interval '-120 days', interval '-105 days', interval '-104 days',
         interval '-100 days', interval '-95 days', interval '-85 days',
         interval '-40 days', interval '-5 days', interval '-4 days', interval '10 days'),
        ('E2E seed previous round', 5,
         interval '-320 days', interval '-305 days', interval '-304 days',
         interval '-300 days', interval '-295 days', interval '-285 days',
         interval '-240 days', interval '-200 days', interval '-198 days', interval '-190 days')
    ) AS v(name, required, promo, app, onb_note, onb, match, first,
           log_reminder, done, fb_start, fb_end)
    RETURNING round_id, name
)
INSERT INTO e2e_rounds (kind, round_id)
SELECT CASE name WHEN 'E2E seed live round' THEN 'live'
                 WHEN 'E2E seed feedback round' THEN 'feedback'
                 ELSE 'previous' END,
       round_id
FROM created;

-- The registration round opens a week ago and closes a week after the last
-- deadline of any real round open for registration now (none open: no
-- registration round). "Open" is get_open_registration_round's rule.
WITH open_real AS (
    SELECT max(GREATEST(mentor_application_deadline_at,
                        mentee_application_deadline_at,
                        onboarding_deadline_at)) AS last_deadline
    FROM mentorship_round
    WHERE name NOT LIKE 'E2E %'
      AND promotion_start_at <= now()
      AND onboarding_deadline_at > now()
),
base AS (
    SELECT date_trunc('hour', GREATEST(now(), last_deadline)) + interval '1 hour' AS b
    FROM open_real
    WHERE last_deadline IS NOT NULL
),
created AS (
    INSERT INTO mentorship_round (
        name, required_meetings,
        promotion_start_at, mentor_application_deadline_at,
        mentee_application_deadline_at, onboarding_notification_at,
        onboarding_deadline_at, match_notification_at,
        first_meeting_deadline_at, meeting_log_reminder_at,
        meetings_completion_deadline_at, feedback_start_at, feedback_deadline_at
    )
    SELECT 'E2E seed registration round', 5,
           date_trunc('hour', now()) - interval '7 days',
           b + interval '7 days', b + interval '7 days', b + interval '8 days',
           b + interval '10 days', b + interval '12 days', b + interval '20 days',
           b + interval '40 days', b + interval '70 days', b + interval '72 days',
           b + interval '80 days'
    FROM base
    RETURNING round_id
)
INSERT INTO e2e_rounds (kind, round_id)
SELECT 'registration', round_id FROM created;

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
    (990022, 'Mentee X1',   'mentee.x1',  'mentee'),
    (990023, 'Mentor F1',   'mentor.f1',  'mentor'),
    (990024, 'Mentor G1',   'mentor.g1',  'mentor'),
    (990025, 'Mentee G1',   'mentee.g1',  'mentee'),
    (990026, 'Mentor L1',   'mentor.l1',  'mentor'),
    (990027, 'Mentee L1',   'mentee.l1',  'mentee'),
    (990028, 'Mentee R1',   'mentee.r1',  'mentee');

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
       (SELECT r.onboarding_deadline_at FROM mentorship_round r
        JOIN e2e_rounds e USING (round_id) WHERE e.kind = 'live'),
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
       (SELECT r.onboarding_deadline_at FROM mentorship_round r
        JOIN e2e_rounds e USING (round_id) WHERE e.kind = 'live'),
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
-- stay null. Mentors waiting for matching take two mentees. e2e-member is
-- registered here too (user_id 0 stands for :member_id).
INSERT INTO mentorship_round_participants (
    participant_id, user_id, round_id, participant_role, approval_status,
    match_email_sent, max_partners, goal, current_stage, time_urgency
)
SELECT gen_random_uuid(), u.user_id, r.round_id, u.role::participant_role,
       v.status::approval_status, v.status = 'matched', v.max_partners,
       CASE WHEN u.role = 'mentee' THEN 'E2E seed goal: land a software engineering role.' END,
       CASE WHEN u.role = 'mentee' THEN 'job_searching' END,
       CASE WHEN u.role = 'mentee' THEN 'within_6_months' END
FROM (VALUES
    (990001, 'live',         'matched',    1),
    (990002, 'live',         'matched',    1),
    (990003, 'live',         'matched',    1),
    (990004, 'live',         'matched',    1),
    (990005, 'live',         'signed_up',  1),
    (990006, 'live',         'withdrawn',  1),
    (990007, 'live',         'un_matched', 1),
    (990008, 'live',         'signed_up',  2),
    (990009, 'live',         'signed_up',  2),
    (990010, 'live',         'signed_up',  1),
    (990011, 'live',         'signed_up',  1),
    (990012, 'live',         'signed_up',  1),
    (990012, 'previous',     'withdrawn',  1),
    (990013, 'previous',     'un_matched', 1),
    (990014, 'live',         'matched',    1),
    (990015, 'live',         'matched',    1),
    (990016, 'live',         'signed_up',  1),
    (990017, 'live',         'signed_up',  1),
    (990018, 'live',         'signed_up',  1),
    (990019, 'live',         'matched',    1),
    (990020, 'live',         'matched',    1),
    (990021, 'live',         'signed_up',  1),
    (990021, 'previous',     'withdrawn',  1),
    (990022, 'live',         'signed_up',  1),
    (990023, 'feedback',     'matched',    1),
    (990024, 'live',         'matched',    1),
    (990025, 'live',         'matched',    1),
    (990026, 'live',         'signed_up',  1),
    (990027, 'live',         'signed_up',  1),
    (990028, 'registration', 'signed_up',  1),
    (0,      'live',         'signed_up',  1),
    (0,      'feedback',     'matched',    1)
) AS v(person, kind, status, max_partners)
JOIN e2e_rounds r USING (kind)
JOIN (SELECT user_id AS person, user_id, role FROM e2e_people
      UNION ALL SELECT 0, :member_id, 'mentee') u USING (person);

-- The personal dashboard shows the mentorship card only to someone with a
-- hired application to a mentee activity posting, and registering needs it
-- too, so the member gets one. Tagged so cleanup removes this row and never
-- a real application.
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

-- Mentor H-M1 is admitted as a mentor and has not registered for the live
-- round, which is what puts someone on the Not registered list.
INSERT INTO application (job_id, user_id, stage, current_round, tags, updated_timestamp)
SELECT j.job_id, 990013, 'hired', 1, '{"e2e": true}'::jsonb, now()
FROM job j
WHERE j.kind = 'activity' AND j.mentorship_role = 'mentor' AND j.status = 'published'
ORDER BY j.job_id
LIMIT 1;

-- Pairs. W1's and H1's pairs are inactive: withdrawing ends the pair and
-- moves the partner from matched to un_matched (pair_endings.unmatch_if_unpaired).
-- Mentor F1 and the member met all three meetings the feedback round asks
-- for, so that round is not "short" in the member's history.
INSERT INTO mentorship_pairs (
    round_id, mentor_id, mentee_id, completed_count, status,
    mentor_action_status, mentee_action_status, recommendation_reason
)
SELECT r.round_id, v.mentor_id, COALESCE(v.mentee_id, :member_id), v.completed,
       v.status::pair_status_enum, 'pending', 'pending', 'e2e seed'
FROM (VALUES
    ('live',     990001, 990002, 0, 'active'),
    ('live',     990003, 990004, 0, 'active'),
    ('live',     990007, 990006, 0, 'inactive'),
    ('previous', 990013, 990012, 0, 'inactive'),
    ('live',     990014, 990015, 0, 'active'),
    ('previous', 990013, 990021, 0, 'inactive'),
    ('live',     990019, 990020, 1, 'active'),
    ('live',     990024, 990025, 1, 'active'),
    ('feedback', 990023, NULL,   3, 'active')
) AS v(kind, mentor_id, mentee_id, completed, status)
JOIN e2e_rounds r USING (kind);

-- Google Meet meetings, so these pair logs are v2. Mentor E1 and Mentee E1
-- have met once; at the second meeting Mentee E1 did not come. Mentor G1 and
-- Mentee G1 have met once. Mentor F1 and e2e-member met all three times the
-- feedback round asks for: eligibility counts these rows, not
-- completed_count, so without them the member would be "meetings short" in
-- the live round.
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
JOIN e2e_rounds r ON r.round_id = p.round_id
JOIN (VALUES
    ('live',     990020, 1, interval '14 days', true,  NULL::integer),
    ('live',     990020, 2, interval '7 days',  false, 990020),
    ('live',     990025, 1, interval '10 days', true,  NULL::integer),
    ('feedback', 0,      1, interval '80 days', true,  NULL::integer),
    ('feedback', 0,      2, interval '60 days', true,  NULL::integer),
    ('feedback', 0,      3, interval '40 days', true,  NULL::integer)
) AS v(kind, mentee, n, ago, done, absent)
  ON v.kind = r.kind
 AND p.mentee_id = CASE v.mentee WHEN 0 THEN :member_id ELSE v.mentee END;

SELECT u.user_id, u.first_name || ' ' || u.last_name AS name,
       r.round_id, r.participant_role AS role, r.approval_status AS status,
       (SELECT string_agg(p.status::text || ' pair ' || p.pair_id, ', ')
        FROM mentorship_pairs p
        WHERE p.round_id = r.round_id
          AND u.user_id IN (p.mentor_id, p.mentee_id)) AS pairs
FROM mentorship_round_participants r
JOIN users u ON u.user_id = r.user_id
WHERE r.round_id IN (SELECT round_id FROM e2e_rounds)
ORDER BY r.round_id DESC, u.user_id;

COMMIT;

\pset format unaligned
\pset tuples_only on
\pset fieldsep '\t'
SELECT 'round', CASE name WHEN 'E2E seed live round' THEN 'live'
                          WHEN 'E2E seed registration round' THEN 'registration'
                          WHEN 'E2E seed feedback round' THEN 'feedback'
                          ELSE 'previous' END,
       round_id, name
FROM mentorship_round
WHERE name LIKE 'E2E seed %'
ORDER BY round_id;
