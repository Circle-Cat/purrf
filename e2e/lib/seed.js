import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { readLocal } from "./local.js";
import { apiAs, getData } from "./api.js";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const SEED_DIR = path.join(ROOT, "seed");
export const SEED_STATE_FILE = path.join(ROOT, ".state", "seed.json");

/** First user id the seed hands out; everything at or above it is seeded. */
export const SEED_USER_ID_FLOOR = 990001;

/** How many people seed.sql creates, e2e-member not counted. */
const SEEDED_PEOPLE = 28;

/**
 * psql wants a libpq URL; the backend's DATABASE_URL is SQLAlchemy-shaped
 * (`postgresql+asyncpg://…?ssl=require`). Accept either.
 */
export function libpqUrl(url) {
  return url
    .replace("+asyncpg", "")
    .replace(/([?&])ssl=require/, "$1sslmode=require");
}

const URL_FILE = path.join(ROOT, ".tokens", "database-url.txt");

/**
 * The test database's URL, from E2E_DATABASE_URL, `e2e.local.json` or
 * `.tokens/database-url.txt`.
 */
export function databaseUrl() {
  if (process.env.E2E_DATABASE_URL) return process.env.E2E_DATABASE_URL;
  const local = readLocal().databaseUrl?.trim();
  if (local) return local;
  if (fs.existsSync(URL_FILE))
    return fs.readFileSync(URL_FILE, "utf8").trim() || null;
  return null;
}

function psql(args) {
  const url = databaseUrl();
  if (!url) throw new Error("No database URL; see README.md");
  return execFileSync(
    "psql",
    [libpqUrl(url), "-X", "-q", "-v", "ON_ERROR_STOP=1", ...args],
    { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] },
  );
}

/** Rows of a query as arrays of strings. */
export const rowsOf = (sql) =>
  psql(["-At", "-F", "\t", "-c", sql])
    .trim()
    .split("\n")
    .filter(Boolean)
    .map((line) => line.split("\t"));

/**
 * Remove whatever an earlier run left behind: every "E2E seed …" round and
 * every seeded person. Safe when nothing is there.
 */
export function cleanup({ memberId }) {
  if (!Number.isInteger(memberId)) throw new Error(`bad member id ${memberId}`);
  psql([
    "-v",
    `member_id=${memberId}`,
    "-f",
    path.join(SEED_DIR, "cleanup.sql"),
  ]);
}

/**
 * Seed the suite's rounds and people. Returns the rounds by kind (live,
 * registration, feedback, previous; registration is absent when no real
 * round was open for registration), who was created (user id by last name;
 * the seed names people "E2E" + a role label), and e2e-member's id. The live
 * round is also `roundId` / `roundName`, and the previous one `prevRoundId`,
 * which is what most specs use.
 */
export function seed({ memberId }) {
  if (!Number.isInteger(memberId)) throw new Error(`bad member id ${memberId}`);
  const out = psql([
    "-v",
    `member_id=${memberId}`,
    "-f",
    path.join(SEED_DIR, "seed.sql"),
  ]);
  const rounds = Object.fromEntries(
    out
      .split("\n")
      .filter((line) => line.startsWith("round\t"))
      .map((line) => {
        const [, kind, id, name] = line.split("\t");
        return [kind, { id: Number(id), name }];
      }),
  );
  const byName = Object.fromEntries(
    rowsOf(
      `SELECT user_id, last_name FROM users WHERE user_id BETWEEN ${SEED_USER_ID_FLOOR} AND 990099 ORDER BY user_id`,
    ).map(([id, name]) => [name, Number(id)]),
  );
  // seed.sql refuses with exit code 0 when rows are already there, so check
  // that the people and rounds actually came into being.
  if (Object.keys(byName).length !== SEEDED_PEOPLE || !rounds.live) {
    throw new Error(
      `seed created ${Object.keys(byName).length} people (expected ${SEEDED_PEOPLE}) and rounds ${JSON.stringify(rounds)}; run cleanup.sql and look at the psql output:\n${out}`,
    );
  }
  return {
    rounds,
    roundId: rounds.live.id,
    roundName: rounds.live.name,
    prevRoundId: rounds.previous.id,
    memberId,
    byName,
    people: [...Object.values(byName), memberId],
  };
}

/**
 * What a real round in progress holds, to compare before and after a run:
 * per round (every round in progress not named "E2E …"), how many
 * registrations, pairs, notes and approval requests are about it. The
 * matching run is added by the caller, from the API.
 */
export function realRoundCounts() {
  const rows = rowsOf(`
    SELECT r.round_id, r.name,
      (SELECT count(*) FROM mentorship_round_participants p WHERE p.round_id = r.round_id),
      (SELECT count(*) FROM mentorship_pairs p WHERE p.round_id = r.round_id),
      (SELECT count(*) FROM mentorship_participant_note n WHERE n.round_id = r.round_id),
      (SELECT count(*) FROM approval_request a
        WHERE (a.target_type = 'round_participant'
               AND split_part(a.target_id, ':', 1) = r.round_id::text)
           OR (a.target_type = 'mentorship_pair'
               AND a.target_id IN (SELECT p.pair_id::text FROM mentorship_pairs p
                                   WHERE p.round_id = r.round_id))
           OR (a.target_type = 'matching_run'
               AND a.payload ->> 'round_id' = r.round_id::text))
    FROM mentorship_round r
    WHERE r.name NOT LIKE 'E2E %'
      AND r.promotion_start_at <= now() AND now() <= r.feedback_deadline_at
    ORDER BY r.round_id`);
  return rows.map(([id, name, participants, pairs, notes, requests]) => ({
    roundId: Number(id),
    name,
    participants: Number(participants),
    pairs: Number(pairs),
    notes: Number(notes),
    approvalRequests: Number(requests),
  }));
}

/**
 * A fingerprint of every real round in progress: its counts from the
 * database and its latest matching run from the API. Teardown takes it again
 * and warns when anything moved, since the suite should never touch them.
 */
export async function realRoundFingerprint(token) {
  const api = await apiAs(token);
  try {
    const rounds = realRoundCounts();
    for (const round of rounds) {
      const run = await getData(
        api,
        `/api/mentorship/admin/match-runs/${round.roundId}`,
      ).catch((e) => ({ error: e.message }));
      round.matchingRun = run?.error ?? {
        status: run?.status ?? null,
        runId: run?.runId ?? null,
        editLockedBy: run?.editLock?.userId ?? null,
        publishRequest: run?.publishRequest?.requestId ?? null,
      };
    }
    return rounds;
  } finally {
    await api.dispose();
  }
}

/** The recruiting seed's fixed id range and candidate address pattern. */
export const CANDIDATE_ID_FLOOR = 990101;
export const TEST_ALIAS = /^wangyanpei76(\+e2e-[a-z0-9-]+)?@gmail\.com$/;

/**
 * Every email row of the test accounts must be the test mailbox or one of
 * its e2e aliases: recruiting mail and calendar invites to them are let
 * through by the guard on that assumption.
 */
export function checkAccountEmails(userIds) {
  const ids = userIds.filter(Number.isInteger);
  if (ids.length === 0) return;
  const bad = rowsOf(
    `SELECT user_id, email FROM user_emails WHERE user_id IN (${ids.join(",")})`,
  ).filter(([, email]) => !TEST_ALIAS.test(email));
  if (bad.length > 0) {
    throw new Error(
      `test accounts hold addresses outside the test mailbox: ${bad.map((r) => r.join(" ")).join(", ")}`,
    );
  }
}

export function recruitingCleanup({ adminId }) {
  if (!Number.isInteger(adminId)) throw new Error(`bad admin id ${adminId}`);
  psql([
    "-v",
    `admin_id=${adminId}`,
    "-f",
    path.join(SEED_DIR, "recruiting-cleanup.sql"),
  ]);
}

/** Seed candidates assigned to e2e-reviewer (B1 and I1). */
const REVIEWER_ASSIGNED_CANDIDATES = [990102, 990105];

/**
 * Seed the recruiting postings and candidates. Returns the postings by kind
 * ({id, title}), the seeded applications by candidate last name
 * ({applicationId, userId}), and the candidates' user ids. With
 * `reviewerEmail` (e2e-reviewer's address as the API reports it), B1 and I1
 * are assigned to whoever holds it; without, to nobody.
 */
export function recruitingSeed({ adminId, reviewerEmail = null }) {
  if (!Number.isInteger(adminId)) throw new Error(`bad admin id ${adminId}`);
  if (reviewerEmail != null && !TEST_ALIAS.test(reviewerEmail))
    throw new Error(`reviewer ${reviewerEmail} is not a test mailbox alias`);
  const out = psql([
    "-v",
    `admin_id=${adminId}`,
    "-v",
    `reviewer_email=${reviewerEmail ?? ""}`,
    "-f",
    path.join(SEED_DIR, "recruiting-seed.sql"),
  ]);
  const lines = out.split("\n").map((line) => line.split("\t"));
  const jobs = Object.fromEntries(
    lines
      .filter(([tag]) => tag === "job")
      .map(([, kind, id, title]) => [kind, { id: Number(id), title }]),
  );
  const applications = Object.fromEntries(
    lines
      .filter(([tag]) => tag === "application")
      .map(([, name, id, userId]) => [
        name,
        { applicationId: Number(id), userId: Number(userId) },
      ]),
  );
  if (!jobs.board || Object.keys(applications).length !== 31) {
    throw new Error(
      `recruiting seed created jobs ${JSON.stringify(jobs)} and ${Object.keys(applications).length} applications; run recruiting-cleanup.sql and look at the psql output:\n${out}`,
    );
  }
  if (reviewerEmail != null) {
    const [[assigned]] = rowsOf(`
      SELECT count(*) FROM application_assignment s
      JOIN application a USING (application_id)
      JOIN user_emails e ON e.user_id = s.assignee_id
      WHERE a.user_id IN (${REVIEWER_ASSIGNED_CANDIDATES.join(",")})
        AND lower(e.email) = lower(${sqlText(reviewerEmail)})`);
    if (Number(assigned) !== REVIEWER_ASSIGNED_CANDIDATES.length) {
      throw new Error(
        `recruiting seed assigned ${assigned} of ${REVIEWER_ASSIGNED_CANDIDATES.length} applications (B1, I1) to ${reviewerEmail}; run recruiting-cleanup.sql and look at the psql output:\n${out}`,
      );
    }
  }
  return {
    jobs,
    applications,
    candidates: Object.values(applications).map((a) => a.userId),
  };
}

/** Upcoming interviews booked on the suite's applications, to cancel. */
export function bookedSuiteInterviews(adminId) {
  return rowsOf(`
    SELECT i.application_id FROM application_interview i
    JOIN application a USING (application_id)
    JOIN job j USING (job_id)
    WHERE i.end_at > now()
      AND (a.user_id BETWEEN ${CANDIDATE_ID_FLOOR} AND 990199
           OR (j.title LIKE 'E2E %'
               AND jsonb_typeof(j.pipeline_config -> 'ownerIds') = 'array'
               AND j.pipeline_config -> 'ownerIds' <> '[]'::jsonb
               AND j.pipeline_config -> 'ownerIds' <@ jsonb_build_array(${Number(adminId)})))
    ORDER BY 1`).map(([id]) => Number(id));
}

/**
 * What every real posting and its applications hold, to compare before and
 * after a run: per posting not titled "E2E …", its status and last update,
 * and counts and last updates of its applications, submissions,
 * assignments, evaluations, comments, interviews and reviews.
 */
export function realRecruitingFingerprint() {
  return rowsOf(`
    SELECT j.job_id, j.status, j.updated_timestamp, md5(COALESCE(j.pending_payload::text, '')),
      (SELECT count(*) || '/' || COALESCE(max(a.updated_timestamp)::text, '-')
              || '/' || COALESCE(string_agg(a.stage::text, ',' ORDER BY a.application_id), '')
         FROM application a WHERE a.job_id = j.job_id),
      (SELECT count(*) FROM application_submission s JOIN application a USING (application_id) WHERE a.job_id = j.job_id),
      (SELECT count(*) FROM application_assignment s JOIN application a USING (application_id) WHERE a.job_id = j.job_id),
      (SELECT count(*) || '/' || COALESCE(max(e.updated_timestamp)::text, '-') FROM evaluation e JOIN application a USING (application_id) WHERE a.job_id = j.job_id),
      (SELECT count(*) FROM application_comment c JOIN application a USING (application_id) WHERE a.job_id = j.job_id),
      (SELECT count(*) || '/' || COALESCE(max(i.updated_at)::text, '-') FROM application_interview i JOIN application a USING (application_id) WHERE a.job_id = j.job_id),
      (SELECT count(*) || '/' || COALESCE(string_agg(r.status::text, ',' ORDER BY r.request_id), '')
         FROM approval_request r WHERE r.target_type = 'job' AND r.target_id = j.job_id::text)
    FROM job j
    WHERE j.title NOT LIKE 'E2E %'
    ORDER BY j.job_id`).map(
    ([
      jobId,
      status,
      updated,
      pending,
      applications,
      submissions,
      assignments,
      evaluations,
      comments,
      interviews,
      reviews,
    ]) => ({
      jobId: Number(jobId),
      status,
      updated,
      pending,
      applications,
      submissions: Number(submissions),
      assignments: Number(assignments),
      evaluations,
      comments: Number(comments),
      interviews,
      reviews,
    }),
  );
}

export function writeSeedState(state) {
  fs.mkdirSync(path.dirname(SEED_STATE_FILE), { recursive: true });
  fs.writeFileSync(SEED_STATE_FILE, JSON.stringify(state, null, 2));
}

/** What global setup seeded this run, or null when it did not seed. */
export function readSeedState() {
  if (!fs.existsSync(SEED_STATE_FILE)) return null;
  return JSON.parse(fs.readFileSync(SEED_STATE_FILE, "utf8"));
}

/** The training seed's fixed id range and trainee address pattern. */
export const TRAINEE_ID_FLOOR = 990201;
export const TRAINEE_ID_CEILING = 990299;

export function trainingCleanup() {
  psql(["-f", path.join(SEED_DIR, "training-cleanup.sql")]);
}

/** Seed the trainees; returns their user ids in order (Trainee 1 first). */
export function trainingSeed() {
  const out = psql(["-f", path.join(SEED_DIR, "training-seed.sql")]);
  const trainees = out
    .split("\n")
    .map((line) => line.split("\t"))
    .filter(([tag]) => tag === "trainee")
    .map(([, , id]) => Number(id));
  if (trainees.length !== 4) {
    throw new Error(
      `training seed created ${trainees.length} trainees; run training-cleanup.sql and look at the psql output:\n${out}`,
    );
  }
  return { trainees };
}

/**
 * What every real course holds, to compare before and after a run: per
 * course with a category or not named "E2E …", its name, active flag, live
 * and staged package (id, version, verified), and its assignment counts.
 */
export function realTrainingFingerprint() {
  return rowsOf(`
    SELECT c.course_id, c.name, COALESCE(c.category::text, '-'), c.is_active,
      COALESCE((SELECT p.package_id || '/' || COALESCE(p.package_version, '-') || '/' || (p.verified_completable_at IS NOT NULL)
                FROM training_course_package p WHERE p.course_id = c.course_id AND p.state = 'live'), '-'),
      COALESCE((SELECT p.package_id || '/' || COALESCE(p.package_version, '-') || '/' || (p.verified_completable_at IS NOT NULL)
                FROM training_course_package p WHERE p.course_id = c.course_id AND p.state = 'pending'), '-'),
      (SELECT count(*) || '/' || count(*) FILTER (WHERE t.status = 'done')
         FROM training t WHERE t.course_id = c.course_id)
    FROM training_course c
    WHERE c.category IS NOT NULL OR c.name NOT LIKE 'E2E %'
    ORDER BY c.course_id`).map(
    ([courseId, name, category, active, live, staged, assignments]) => ({
      courseId: Number(courseId),
      name,
      category,
      active,
      live,
      staged,
      assignments,
    }),
  );
}

/** Suite courses ("E2E …", no category) that still have a staged package. */
export function stagedSuiteCourses() {
  return rowsOf(`
    SELECT DISTINCT c.course_id FROM training_course c
    JOIN training_course_package p USING (course_id)
    WHERE c.name LIKE 'E2E %' AND c.category IS NULL AND p.state = 'pending'
    ORDER BY 1`).map(([id]) => Number(id));
}

/** Storage prefixes of every package row a suite course still has. */
export function suitePackagePrefixes() {
  return rowsOf(`
    SELECT p.storage_prefix FROM training_course c
    JOIN training_course_package p USING (course_id)
    WHERE c.name LIKE 'E2E %' AND c.category IS NULL
    ORDER BY 1`).map(([prefix]) => prefix);
}

/**
 * The training row, if it is on a suite course and held by a test account or
 * a seed trainee; otherwise null. The guard lets session, trial and progress
 * writes through only for such rows.
 */
export function suiteTraining(trainingId, testAccounts) {
  if (!Number.isInteger(trainingId)) return null;
  const ids = testAccounts.filter(Number.isInteger);
  const [row] = rowsOf(`
    SELECT t.training_id, t.user_id, t.course_id FROM training t
    JOIN training_course c USING (course_id)
    WHERE t.training_id = ${trainingId}
      AND c.name LIKE 'E2E %' AND c.category IS NULL
      AND (t.user_id BETWEEN ${TRAINEE_ID_FLOOR} AND ${TRAINEE_ID_CEILING}
           ${ids.length ? `OR t.user_id IN (${ids.join(",")})` : ""})`);
  return row
    ? {
        trainingId: Number(row[0]),
        userId: Number(row[1]),
        courseId: Number(row[2]),
      }
    : null;
}

/** Whether a course is the suite's: named "E2E …" with no category. */
export function isSuiteCourse(courseId) {
  if (!Number.isInteger(courseId)) return false;
  return (
    rowsOf(`
    SELECT 1 FROM training_course
    WHERE course_id = ${courseId} AND name LIKE 'E2E %' AND category IS NULL`)
      .length === 1
  );
}

/** The Inbox and account console seed's fixed id range. */
export const OPS_ID_FLOOR = 990301;
export const OPS_ID_CEILING = 990399;

/**
 * An inbound From that is the test mailbox or one of its e2e aliases, as a
 * Postgres regex. Mirrors TEST_ALIAS, allowing a display name around it.
 */
const SQL_TEST_SENDER = `'(^|[^a-z0-9.+_-])wangyanpei76(\\+e2e-[a-z0-9-]+)?@gmail\\.com'`;

/** SQL condition: thread `t` is one of the suite's real "E2E inbox" threads. */
const SUITE_REAL_THREAD = `
  t.subject LIKE 'E2E inbox%' AND t.gmail_thread_id NOT LIKE 'e2e-%'
  AND EXISTS (SELECT 1 FROM email_message m
              WHERE m.thread_id = t.thread_id AND m.direction = 'inbound'
                AND m.from_address ~* ${SQL_TEST_SENDER})
  AND NOT EXISTS (SELECT 1 FROM email_message m
                  WHERE m.thread_id = t.thread_id AND m.direction = 'inbound'
                    AND m.gmail_message_id NOT LIKE 'e2e-%'
                    AND (m.from_address IS NULL OR m.from_address !~* ${SQL_TEST_SENDER}))`;

/** SQL condition: thread `t` belongs to the suite, real or inserted. */
const SUITE_THREAD = `(t.gmail_thread_id LIKE 'e2e-%' OR (${SUITE_REAL_THREAD}))`;

/**
 * Put the suite's real threads back, drop its inserted threads and remove
 * the ops people with what the specs did to them. Must run before the
 * mentorship and recruiting cleanups (see the SQL file).
 */
export function inboxAdminCleanup() {
  psql(["-f", path.join(SEED_DIR, "inbox-admin-cleanup.sql")]);
}

/** Put the suite's real threads back and drop its inserted ones. */
export function inboxThreadReset() {
  psql(["-f", path.join(SEED_DIR, "inbox-thread-reset.sql")]);
}

/** Seed the ops people; returns their user ids by key ("deactivate", …). */
export function inboxAdminSeed() {
  const out = psql(["-f", path.join(SEED_DIR, "inbox-admin-seed.sql")]);
  const people = Object.fromEntries(
    out
      .split("\n")
      .map((line) => line.split("\t"))
      .filter(([tag]) => tag === "ops")
      .map(([, key, id]) => [key, Number(id)]),
  );
  if (Object.keys(people).length !== 9) {
    throw new Error(
      `inbox-admin seed created ${Object.keys(people).length} people; run inbox-admin-cleanup.sql and look at the psql output:\n${out}`,
    );
  }
  return { people };
}

/** The address inside a From header value, lower-cased. */
export const bareAddress = (raw) =>
  (String(raw ?? "").match(/<([^>]+)>/)?.[1] ?? String(raw ?? ""))
    .trim()
    .toLowerCase();

/**
 * What the guard needs to know about an Inbox thread, or null when it is not
 * the suite's: whether it is inserted (fake) or real, who a reply goes to
 * (the newest human sender, as `reply_contact` picks it), and whether it
 * needs a reply ignoring archiving (as Transfer judges it after unarchiving).
 */
export function suiteThreadFacts(threadId) {
  if (!Number.isInteger(threadId)) return null;
  const human = `m.direction = 'inbound' AND (m.inbound_kind = 'human'
    OR (m.inbound_kind IS NULL AND m.failed_recipients IS NULL))`;
  const [row] = rowsOf(`
    SELECT t.gmail_thread_id LIKE 'e2e-%',
      (SELECT m.from_address FROM email_message m
        WHERE m.thread_id = t.thread_id AND ${human}
        ORDER BY COALESCE(m.gmail_internal_date, m.created_at) DESC, m.message_id DESC
        LIMIT 1),
      COALESCE((SELECT max(m.created_at) FROM email_message m
                 WHERE m.thread_id = t.thread_id AND ${human})
               > COALESCE((SELECT max(COALESCE(m.gmail_internal_date, m.created_at))
                             FROM email_message m
                            WHERE m.thread_id = t.thread_id AND m.direction = 'outbound'),
                          '-infinity'::timestamptz), false)
    FROM email_thread t
    WHERE t.thread_id = ${threadId} AND ${SUITE_THREAD}`);
  if (!row) return null;
  return {
    fake: row[0] === "t",
    contact: bareAddress(row[1]),
    needsReply: row[2] === "t",
  };
}

/** The suite's real threads by subject: {threadId, contextType, userId, archived}. */
export function suiteRealThreads() {
  return Object.fromEntries(
    rowsOf(`
      SELECT t.subject, t.thread_id, t.context_type, COALESCE(t.user_id::text, ''),
             t.archived_at IS NOT NULL
      FROM email_thread t WHERE ${SUITE_REAL_THREAD}
      ORDER BY t.thread_id`).map(([subject, id, context, user, archived]) => [
      subject,
      {
        threadId: Number(id),
        contextType: context,
        userId: user ? Number(user) : null,
        archived: archived === "t",
      },
    ]),
  );
}

/**
 * The suite's real threads as teardown compares them: state and how many
 * messages each holds. After cleanup they must match the start of the run.
 */
export function suiteRealThreadState() {
  return rowsOf(`
    SELECT t.thread_id, t.subject, t.context_type, COALESCE(t.user_id::text, '-'),
           COALESCE(t.context_id::text, '-'), t.archived_at IS NOT NULL,
           (SELECT count(*) FROM email_message m WHERE m.thread_id = t.thread_id)
    FROM email_thread t WHERE ${SUITE_REAL_THREAD}
    ORDER BY t.thread_id`).map((r) => r.join(" "));
}

/**
 * What real accounts and real mail threads look like, to compare before and
 * after a run: how many real users are deactivated or blocked, how many
 * permission grants they hold (and have ever held), the block requests about
 * them, the test accounts' own state, and every mail thread that is not the
 * suite's with its service, owner, archive state and message count.
 */
export function realAccountsFingerprint(testAccounts) {
  const tests = testAccounts.filter(Number.isInteger);
  const notTest = tests.length ? `AND user_id NOT IN (${tests.join(",")})` : "";
  const [counts] = rowsOf(`
    SELECT
      (SELECT count(*) FROM users WHERE user_id < 990001 ${notTest} AND NOT is_active),
      (SELECT count(*) FROM users WHERE user_id < 990001 ${notTest} AND is_blocked),
      (SELECT count(*) FROM user_permissions WHERE user_id < 990001 ${notTest} AND revoked_timestamp IS NULL),
      (SELECT count(*) FROM user_permissions WHERE user_id < 990001 ${notTest}),
      (SELECT count(*) || '/' || count(*) FILTER (WHERE status = 'pending')
         FROM approval_request WHERE target_type = 'user'
          AND target_id ~ '^[0-9]+$' AND target_id::bigint < 990001)`);
  const testState = tests.length
    ? rowsOf(`SELECT user_id, is_active, is_blocked FROM users
              WHERE user_id IN (${tests.join(",")}) ORDER BY user_id`).map(
        (r) => r.join(" "),
      )
    : [];
  const threads = rowsOf(`
    SELECT t.thread_id, t.context_type, COALESCE(t.user_id::text, '-'),
           COALESCE(t.context_id::text, '-'), t.archived_at IS NOT NULL,
           (SELECT count(*) FROM email_message m WHERE m.thread_id = t.thread_id)
    FROM email_thread t WHERE NOT ${SUITE_THREAD}
    ORDER BY t.thread_id`).map((r) => r.join(" "));
  return {
    deactivated: Number(counts[0]),
    blocked: Number(counts[1]),
    activeGrants: Number(counts[2]),
    allGrants: Number(counts[3]),
    blockRequests: counts[4],
    testAccounts: testState,
    threads,
  };
}

/** The profile seed's fixed id range. */
export const PROFILE_ID_FLOOR = 990401;
export const PROFILE_ID_CEILING = 990499;

export function profileCleanup() {
  psql(["-f", path.join(SEED_DIR, "profile-cleanup.sql")]);
}

/** Seed the profile people; returns {owner: {userId, emailId, email}, …}. */
export function profileSeed() {
  const out = psql(["-f", path.join(SEED_DIR, "profile-seed.sql")]);
  const people = Object.fromEntries(
    out
      .split("\n")
      .map((line) => line.split("\t"))
      .filter(([tag]) => tag === "profile")
      .map(([, key, userId, emailId, email]) => [
        key,
        { userId: Number(userId), emailId: Number(emailId), email },
      ]),
  );
  if (!people.owner || !people["owner-old"]) {
    throw new Error(
      `profile seed created ${JSON.stringify(people)}; run profile-cleanup.sql and look at the psql output:\n${out}`,
    );
  }
  return { people };
}

/** One user_emails row by id, or null. */
export function emailRowById(emailId) {
  if (!Number.isInteger(emailId)) return null;
  const [row] = rowsOf(
    `SELECT user_id, email, is_primary, otp_confirmed FROM user_emails WHERE email_id = ${emailId}`,
  );
  return row
    ? {
        userId: Number(row[0]),
        email: row[1],
        isPrimary: row[2] === "t",
        confirmed: row[3] === "t",
      }
    : null;
}

const sqlText = (value) => `'${String(value).replace(/'/g, "''")}'`;

const idList = (userIds) => {
  const ids = userIds.filter(Number.isInteger);
  if (ids.length === 0) throw new Error("no user ids");
  return ids.join(",");
};

/**
 * What the profile specs may change on the test accounts, as JSON: the user
 * row's profile fields, their experience row (education and work history),
 * their address rows, and their training rows' status. `restoreAccounts`
 * puts it back; comparing two snapshots tells whether it is back.
 */
export function accountSnapshot(userIds) {
  const ids = idList(userIds);
  const [[json]] = rowsOf(`
    SELECT jsonb_build_object(
      'users', (SELECT jsonb_agg(to_jsonb(x) ORDER BY x.user_id) FROM (
        SELECT user_id, first_name, last_name, preferred_name, timezone,
               timezone_updated_at, communication_channel, linkedin_link,
               has_mentorship_mentor_experience, updated_timestamp
        FROM users WHERE user_id IN (${ids})) x),
      'experience', COALESCE((SELECT jsonb_agg(to_jsonb(x) ORDER BY x.user_id) FROM (
        SELECT user_id, education, work_history, updated_timestamp, created_datetime
        FROM experience WHERE user_id IN (${ids})) x), '[]'::jsonb),
      'emails', COALESCE((SELECT jsonb_agg(to_jsonb(x) ORDER BY x.email_id) FROM (
        SELECT email_id, user_id, email, otp_confirmed, is_primary
        FROM user_emails WHERE user_id IN (${ids})) x), '[]'::jsonb),
      'training', COALESCE((SELECT jsonb_agg(to_jsonb(x) ORDER BY x.training_id) FROM (
        SELECT training_id, user_id, status, completed_timestamp
        FROM training WHERE user_id IN (${ids})) x), '[]'::jsonb)
    )::text`);
  return JSON.parse(json);
}

/**
 * Put the test accounts back as `snapshot` found them: profile fields,
 * experience (removed when there was none), training status of the rows
 * that existed then, and addresses (rows added since are removed, but only
 * extra aliases of the test mailbox; flags are set back). Returns what
 * still differs, empty when it is back.
 */
export function restoreAccounts(snapshot) {
  const ids = idList(snapshot.users.map((u) => u.user_id));
  const known = snapshot.emails.map((e) => e.email_id);
  const strays = rowsOf(`
    SELECT email_id, email FROM user_emails
    WHERE user_id IN (${ids})
      ${known.length ? `AND email_id NOT IN (${known.join(",")})` : ""}`);
  const unexpected = strays.filter(([, email]) => !TEST_ALIAS.test(email));
  if (unexpected.length) {
    throw new Error(
      `test accounts hold addresses outside the test mailbox: ${unexpected.map((r) => r[1]).join(", ")}`,
    );
  }
  const lit = (v) => sqlText(JSON.stringify(v));
  rowsOf(`
    BEGIN;
    UPDATE users u SET
      first_name = s.first_name, last_name = s.last_name,
      preferred_name = s.preferred_name, timezone = s.timezone,
      timezone_updated_at = s.timezone_updated_at,
      communication_channel = s.communication_channel::communication_method,
      linkedin_link = s.linkedin_link,
      has_mentorship_mentor_experience = s.has_mentorship_mentor_experience,
      updated_timestamp = s.updated_timestamp
    FROM jsonb_to_recordset(${lit(snapshot.users)}::jsonb) AS s(
      user_id int, first_name text, last_name text, preferred_name text,
      timezone text, timezone_updated_at timestamptz, communication_channel text,
      linkedin_link text, has_mentorship_mentor_experience boolean,
      updated_timestamp timestamptz)
    WHERE u.user_id = s.user_id;
    DELETE FROM experience WHERE user_id IN (${ids})
      ${snapshot.experience.length ? `AND user_id NOT IN (${snapshot.experience.map((e) => e.user_id).join(",")})` : ""};
    INSERT INTO experience (user_id, education, work_history, updated_timestamp, created_datetime)
    SELECT s.user_id, s.education, s.work_history, s.updated_timestamp, s.created_datetime
    FROM jsonb_to_recordset(${lit(snapshot.experience)}::jsonb) AS s(
      user_id int, education jsonb, work_history jsonb,
      updated_timestamp timestamptz, created_datetime timestamptz)
    ON CONFLICT (user_id) DO UPDATE SET
      education = EXCLUDED.education, work_history = EXCLUDED.work_history,
      updated_timestamp = EXCLUDED.updated_timestamp,
      created_datetime = EXCLUDED.created_datetime;
    UPDATE training t SET status = s.status::training_status,
      completed_timestamp = s.completed_timestamp
    FROM jsonb_to_recordset(${lit(snapshot.training)}::jsonb) AS s(
      training_id int, status text, completed_timestamp timestamptz)
    WHERE t.training_id = s.training_id;
    ${strays.length ? `DELETE FROM user_emails WHERE email_id IN (${strays.map((r) => r[0]).join(",")});` : ""}
    UPDATE user_emails e SET is_primary = false
    FROM jsonb_to_recordset(${lit(snapshot.emails)}::jsonb) AS s(email_id int, is_primary boolean)
    WHERE e.email_id = s.email_id AND NOT s.is_primary AND e.is_primary;
    UPDATE user_emails e SET is_primary = s.is_primary, otp_confirmed = s.otp_confirmed
    FROM jsonb_to_recordset(${lit(snapshot.emails)}::jsonb) AS s(
      email_id int, is_primary boolean, otp_confirmed boolean)
    WHERE e.email_id = s.email_id;
    COMMIT;`);
  return diffAccounts(
    snapshot,
    accountSnapshot(snapshot.users.map((u) => u.user_id)),
  );
}

/**
 * Where two snapshots differ, as "section user: before -> after" lines.
 * Training rows created since the first (other layers assign courses to the
 * test accounts and remove them in their own cleanup) are not compared.
 */
export function diffAccounts(before, after) {
  const out = [];
  const key = {
    users: "user_id",
    experience: "user_id",
    emails: "email_id",
    training: "training_id",
  };
  for (const [section, id] of Object.entries(key)) {
    const a = new Map(before[section].map((r) => [r[id], JSON.stringify(r)]));
    const b = new Map(after[section].map((r) => [r[id], JSON.stringify(r)]));
    for (const [k, v] of a) {
      if (b.get(k) !== v)
        out.push(`${section} ${k}: ${v} -> ${b.get(k) ?? "gone"}`);
    }
    if (section === "training") continue;
    for (const [k, v] of b)
      if (!a.has(k)) out.push(`${section} ${k}: added ${v}`);
  }
  return out;
}

/** The leave seed's fixed id range. */
export const LEAVE_ID_FLOOR = 990501;
export const LEAVE_ID_CEILING = 990599;

const accountsVar = (testAccounts) => [
  "-v",
  `accounts=${idList(testAccounts)}`,
];

/** Remove the leave seed and every leave row of a test account. */
export function leaveCleanup(testAccounts) {
  psql([
    ...accountsVar(testAccounts),
    "-f",
    path.join(SEED_DIR, "leave-cleanup.sql"),
  ]);
}

/**
 * Seed the leave people, holidays, requests (all filed against the reviewer)
 * and ledger rows. Returns {people: {lastName: id}, requests: {key: id}}.
 */
export function leaveSeed({ reviewerId, memberId, testAccounts }) {
  for (const id of [reviewerId, memberId]) {
    if (!Number.isInteger(id)) throw new Error(`bad account id ${id}`);
  }
  const out = psql([
    "-v",
    `reviewer=${reviewerId}`,
    "-v",
    `member=${memberId}`,
    ...accountsVar(testAccounts),
    "-f",
    path.join(SEED_DIR, "leave-seed.sql"),
  ]);
  const lines = out.split("\n").map((line) => line.split("\t"));
  const people = Object.fromEntries(
    lines
      .filter(([tag]) => tag === "person")
      .map(([, k, id]) => [k, Number(id)]),
  );
  const requests = Object.fromEntries(
    lines
      .filter(([tag]) => tag === "request")
      .map(([, k, id]) => [k, Number(id)]),
  );
  if (
    Object.keys(people).length !== 10 ||
    Object.keys(requests).length !== 16
  ) {
    throw new Error(
      `leave seed created ${JSON.stringify({ people, requests })}; run leave-cleanup.sql and look at the psql output:\n${out}`,
    );
  }
  return { people, requests };
}

/** SQL condition: user `col` is a leave seed person or a test account. */
const leaveSuiteOwner = (col, testAccounts) =>
  `(${col} BETWEEN ${LEAVE_ID_FLOOR} AND ${LEAVE_ID_CEILING} OR ${col} IN (${idList(testAccounts)}))`;

/**
 * Whether a leave request is the suite's: filed by a seed person or a test
 * account, against a test account, and its approval rows name only those.
 */
export function suiteLeaveRequest(requestId, testAccounts) {
  if (!Number.isInteger(requestId)) return false;
  const accounts = idList(testAccounts);
  return (
    rowsOf(`
    SELECT 1 FROM leave_request r
    WHERE r.leave_request_id = ${requestId}
      AND ${leaveSuiteOwner("r.user_id", testAccounts)}
      AND r.approver_user_id IN (${accounts})
      AND NOT EXISTS (
        SELECT 1 FROM approval_request a
        WHERE a.action = 'leave_approval' AND a.target_id = r.leave_request_id::text
          AND NOT (${leaveSuiteOwner("a.raised_by", testAccounts)}
                   AND a.reviewer_id IN (${accounts})))`).length === 1
  );
}

/**
 * The real leave data, to compare before and after a run: requests, ledger
 * rows, approval rows and events not about a suite person, and holidays
 * other than the suite's "E2E …" ones in 2019 and 2099.
 */
export function realLeaveFingerprint(testAccounts) {
  const [[json]] = rowsOf(`
    SELECT jsonb_build_object(
      'requests', (SELECT jsonb_agg(jsonb_build_array(leave_request_id, user_id, status, hours, updated_timestamp) ORDER BY leave_request_id)
                   FROM leave_request
                   WHERE NOT ${leaveSuiteOwner("user_id", testAccounts)}
                     AND NOT ${leaveSuiteOwner("approver_user_id", testAccounts)}),
      'ledger', (SELECT jsonb_build_array(count(*), sum(hours), max(leave_ledger_id))
                 FROM leave_ledger WHERE NOT ${leaveSuiteOwner("user_id", testAccounts)}),
      'holidays', (SELECT jsonb_build_array(count(*), md5(string_agg(year || date::text || name || is_exchangeable, ',' ORDER BY date)))
                   FROM leave_holiday
                   WHERE NOT (year IN (2019, 2099) AND name LIKE 'E2E %')),
      'approvals', (SELECT jsonb_agg(jsonb_build_array(request_id, status) ORDER BY request_id)
                    FROM approval_request
                    WHERE action = 'leave_approval'
                      AND NOT ${leaveSuiteOwner("raised_by", testAccounts)}),
      'events', (SELECT count(*) FROM event e
                 WHERE e.event_type LIKE 'leave.%'
                   AND NOT EXISTS (SELECT 1 FROM leave_request r
                                   WHERE r.leave_request_id = e.subject_id
                                     AND ${leaveSuiteOwner("r.user_id", testAccounts)})))::text`);
  return JSON.parse(json);
}
