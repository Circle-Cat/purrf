import { ENV } from "./env.js";
import { flag } from "./flags.js";
import { ROLES, readAccountState } from "./accounts.js";
import { loginAddress, mailbox } from "./login.js";
import {
  PROFILE_ID_CEILING,
  PROFILE_ID_FLOOR,
  SEED_USER_ID_FLOOR,
  emailRowById,
  isSuiteCourse,
  readSeedState,
  rowsOf,
  suiteLeaveRequest,
  suiteThreadFacts,
  suiteTraining,
} from "./seed.js";

/**
 * Non-GET calls the app makes on its own just to read something. They are
 * let through even where writes are forbidden.
 */
const READ_STYLE_CALLS = [
  { method: "POST", path: /^\/api\/summary(\/me)?$/ },
  // DataSearch queries: the body is the filter, nothing is written
  // (tests/dashboard/SIDE-EFFECTS.md).
  {
    method: "POST",
    path: /^\/api\/(microsoft\/chat\/count|google\/chat\/count|jira\/brief|jira\/detail\/batch|gerrit\/stats|calendar\/events)$/,
  },
];

/**
 * API errors that show up on every run and are not regressions. `message`,
 * when given, must match the error's message too.
 */
const KNOWN_API_ERRORS = [
  {
    method: "POST",
    path: /^\/api\/summary\/me$/,
    status: 403,
    message: /^The activity summary needs a confirmed CircleCat address/,
    // PUR-804: no test account has a company address.
    why: "the account has no confirmed CircleCat address",
  },
  {
    method: "POST",
    path: /^\/api\/summary\/me$/,
    status: 403,
    message: /^View personal summary feature is not yet available/,
    why: "the view-personal-summary flag is off for the account",
    // Declared on, the 403 is a real failure.
    unless: () => flag("view-personal-summary") === true,
  },
];

/**
 * Anything that makes mail leave Purrf: Kit broadcasts and drafts, the
 * single-person send, and replies from a participant's thread. Always
 * aborted, whoever it is for.
 */
const SENDS_MAIL = [
  /^\/api\/mentorship\/admin\/kit-drafts/,
  /^\/api\/mentorship\/admin\/email-sends$/,
  /^\/api\/mentorship\/admin\/email-sends\/person$/,
  /^\/api\/mentorship\/admin\/email-sends\/\d+\/[a-z-]+$/,
  /^\/api\/mentorship\/admin\/rounds\/\d+\/participants\/\d+\/emails(\/[^/]+\/reply)?$/,
];

/** Writes whose round and target person sit in the path. */
const PERSON_IN_PATH =
  /^\/api\/mentorship\/admin\/rounds\/(\d+)\/participants\/(\d+)\/(exemption-request|withdraw-request|mark-request|end-pair-request|notes)$/;

/**
 * A participant page's "Refresh emails": it pulls the person's Gmail threads
 * into the database, so it is a write, only about a seeded person in a
 * seeded round.
 */
const EMAILS_REFRESH =
  /^\/api\/mentorship\/admin\/rounds\/(\d+)\/participants\/(\d+)\/emails\/refresh$/;

/** Writes on a request the suite raised itself; the id sits in the path. */
const REQUEST_IN_PATH = [
  /^\/api\/mentorship\/admin\/approvals\/(\d+)\/(decide|reassign|withdraw)$/,
  /^\/api\/block-requests\/(\d+)\/(decide|reassign|withdraw)$/,
];

/** Writes that name their people in the body. */
const PEOPLE_IN_BODY = [
  /^\/api\/block-requests$/,
  /^\/api\/mentorship\/admin\/match-runs$/,
  /^\/api\/mentorship\/admin\/rounds\/\d+\/notifications\/mark$/,
  /^\/api\/mentorship\/admin\/email-sends\/notified$/,
];

/**
 * What a participant does to their own records, allowed for e2e-member:
 * registering and feedback only in a seeded round, meetings anywhere (they
 * can only be about the member's own pairs).
 */
const OWN_ROUND_RECORDS =
  /^\/api\/mentorship\/rounds\/(\d+)\/(registration|feedback)$/;
const OWN_RECORDS = [/^\/api\/mentorship\/v1\/meetings(\/.*)?$/];

/** Round-level writes with the round in the path; only in a seeded round. */
const ROUND_IN_PATH =
  /^\/api\/mentorship\/admin\/rounds\/(\d+)\/notifications\/mark$/;

/** Dismissing one's own bell notifications, one or all: the bell's writes. */
const OWN_NOTIFICATIONS = [
  { method: "DELETE", path: /^\/api\/recruiting\/notifications(\/\d+)?$/ },
];

const PERSON_KEYS = new Set([
  "userId",
  "userIds",
  "participantIds",
  "menteeId",
  "mentorId",
]);

/** Every person id named anywhere in a JSON body. */
function peopleIn(value, found = []) {
  if (Array.isArray(value)) value.forEach((v) => peopleIn(v, found));
  else if (value && typeof value === "object") {
    for (const [key, v] of Object.entries(value)) {
      if (PERSON_KEYS.has(key))
        [v]
          .flat()
          .filter((x) => x != null)
          .forEach((x) => found.push(Number(x)));
      else peopleIn(v, found);
    }
  }
  return found;
}

const parse = (text) => {
  try {
    return JSON.parse(text ?? "null");
  } catch {
    return null;
  }
};

/**
 * Who the suite may write about, shared by every context in the worker:
 * seeded people and e2e-member, the rounds global setup seeded, the requests
 * the suite raised, and the pairs it has seen those people in.
 */
export const allowed = {
  people: new Set(),
  seedRounds: new Set(),
  requests: new Set(),
  pairs: new Set(),
  runs: new Set(),
  rounds: new Set(),
  // Recruiting: the test accounts, the suite's postings (seeded or created
  // as "E2E …"), the applications to them, and the posting reviews on them.
  testAccounts: new Set(),
  jobs: new Set(),
  applications: new Set(),
  reviews: new Set(),
  // Training: the seed trainees, the suite's "E2E …" courses, and the
  // assignments on them held by a test account or a trainee.
  trainees: new Set(),
  trainingCourses: new Set(),
  trainings: new Set(),
  // Account console: the seeded ops people.
  opsPeople: new Set(),
  // Profile and Sign in & security: the roles a test lets edit their own
  // profile (it restores them afterwards), and whether it may upload a
  // résumé. Both are reset at the start of every test.
  // Leave: the seed employees (990501-990599) a balance may be corrected for.
  leavePeople: new Set(),
  profileWriters: new Set(),
  resumeUploads: false,
};

/**
 * A seeded person: their id is in the seed range and global setup created
 * them. e2e-member is in `allowed.people` but below the range, so it never
 * counts; the test accounts never do either.
 */
const isSeedUser = (id) =>
  Number.isInteger(Number(id)) &&
  Number(id) >= SEED_USER_ID_FLOOR &&
  (allowed.people.has(Number(id)) || allowed.opsPeople.has(Number(id)));

/**
 * The test mailbox and its e2e aliases. Seed candidates and the test
 * accounts hold nothing else (global setup checks the accounts), so mail
 * and invites about them can only land there.
 */
const TEST_ALIAS = /^wangyanpei76(\+e2e-[a-z0-9-]+)?@gmail\.com$/i;

const JOB_PATH = /^\/api\/recruiting\/jobs\/(\d+)(\/.*)?$/;
const APPLICATION_PATH = /^\/api\/recruiting\/applications\/(\d+)(\/.*)?$/;

/** Owners and default assignees of a posting body, all test accounts. */
function strangersInPosting(body) {
  const config = body?.pipelineConfig ?? {};
  const ids = [
    ...(config.ownerIds ?? []),
    ...(config.ownerId != null ? [config.ownerId] : []),
    ...(config.stages ?? []).map((s) => s.defaultAssigneeId),
  ].filter((id) => id != null);
  return ids.filter((id) => !allowed.testAccounts.has(Number(id)));
}

/**
 * Recruiting writes. Every one must be about a suite posting or an
 * application to one, and every person it names (reviewer, interviewer,
 * owner, mentioned user, email recipient) must be a test account or an
 * alias. Returns undefined when the path is not a recruiting write.
 */
function refuseRecruiting({ method, path, body }) {
  const json = parse(body);
  const notTest = (id) => id != null && !allowed.testAccounts.has(Number(id));
  if (method === "POST" && path === "/api/recruiting/jobs") {
    if (!String(json?.title ?? "").startsWith("E2E "))
      return "a posting must be titled E2E …";
    const strangers = strangersInPosting(json);
    return strangers.length ? `names users ${strangers.join(", ")}` : null;
  }
  if (method === "POST" && path === "/api/recruiting/applications") {
    return allowed.jobs.has(Number(json?.jobId))
      ? null
      : `posting ${json?.jobId} is not the suite's`;
  }
  if (path === "/api/recruiting/resumes")
    return allowed.resumeUploads ? null : "résumé uploads are not used";
  const review = path.match(/^\/api\/recruiting\/reviews\/(\d+)$/);
  if (review) {
    return allowed.reviews.has(Number(review[1]))
      ? null
      : `review ${review[1]} is not on a suite posting`;
  }
  const job = path.match(JOB_PATH);
  if (job) {
    if (!allowed.jobs.has(Number(job[1])))
      return `posting ${job[1]} is not the suite's`;
    if (method === "PUT") {
      if (!String(json?.title ?? "").startsWith("E2E "))
        return "a posting must stay titled E2E …";
      const strangers = strangersInPosting(json);
      return strangers.length ? `names users ${strangers.join(", ")}` : null;
    }
    return notTest(json?.reviewerId)
      ? `reviewer ${json.reviewerId} is not a test account`
      : null;
  }
  const application = path.match(APPLICATION_PATH);
  if (application) {
    if (!allowed.applications.has(Number(application[1])))
      return `application ${application[1]} is not on a suite posting`;
    const rest = application[2] ?? "";
    if (notTest(json?.assigneeId))
      return `assignee ${json.assigneeId} is not a test account`;
    if (rest === "/comments") {
      const mentioned = [...String(json?.body ?? "").matchAll(/@\[(\d+)\]/g)]
        .map((m) => Number(m[1]))
        .filter(notTest);
      return mentioned.length ? `mentions users ${mentioned.join(", ")}` : null;
    }
    if (rest === "/emails") {
      if (json?.threadId != null)
        return "replies go to whoever wrote last, which the suite cannot vouch for";
      const to = json?.to ?? [];
      const outside = to.filter((a) => !TEST_ALIAS.test(a));
      if (to.length === 0 || outside.length)
        return `mails ${outside.join(", ") || "nobody"}`;
      return null;
    }
    return null;
  }
  if (path.startsWith("/api/recruiting/")) return undefined;
  return undefined;
}

const TRAINING_COURSE_PATH =
  /^\/api\/training\/courses\/(\d+)(\/package|\/package\/publish|\/trial|\/preview-session)?$/;
const TRAINING_RUN_PATH =
  /^\/api\/training\/(\d+)\/(session|trial-session|progress)$/;

const suiteCourse = (id) => {
  if (allowed.trainingCourses.has(id)) return true;
  if (!isSuiteCourse(id)) return false;
  allowed.trainingCourses.add(id);
  return true;
};

const suiteTrainingRow = (id) => {
  if (allowed.trainings.has(id)) return true;
  if (!suiteTraining(id, [...allowed.testAccounts])) return false;
  allowed.trainings.add(id);
  return true;
};

/**
 * Training writes. Courses must be the suite's ("E2E …" with no category,
 * which the four real courses never are), assignments may only name seed
 * trainees and test accounts, and a run (session, trial session, progress)
 * must be on an assignment of a suite course held by one of them. Returns
 * undefined when the path is not a training write.
 */
function refuseTraining({ method, path, body }) {
  if (!path.startsWith("/api/training/")) return undefined;
  const json = parse(body);
  if (method === "POST" && path === "/api/training/courses") {
    return String(json?.name ?? "").startsWith("E2E ")
      ? null
      : "a course must be named E2E …";
  }
  const course = path.match(TRAINING_COURSE_PATH);
  if (course) {
    if (!suiteCourse(Number(course[1])))
      return `course ${course[1]} is not the suite's`;
    if (json?.name != null && !String(json.name).startsWith("E2E "))
      return "a course must stay named E2E …";
    return null;
  }
  if (method === "POST" && path === "/api/training/assignments/bulk") {
    if (!suiteCourse(Number(json?.courseId)))
      return `course ${json?.courseId} is not the suite's`;
    const strangers = (json?.userIds ?? []).filter(
      (id) =>
        !allowed.trainees.has(Number(id)) &&
        !allowed.testAccounts.has(Number(id)),
    );
    if ((json?.userIds ?? []).length === 0) return "assigns nobody";
    return strangers.length ? `assigns users ${strangers.join(", ")}` : null;
  }
  const run = path.match(TRAINING_RUN_PATH);
  if (run) {
    return suiteTrainingRow(Number(run[1]))
      ? null
      : `training ${run[1]} is not on a suite course`;
  }
  return `${method} ${path} is not on the write list`;
}

const ACCOUNT_WRITE =
  /^\/api\/admin\/accounts\/(\d+)\/(deactivate|reactivate|block|unblock)$/;
const PERMISSION_WRITE =
  /^\/api\/admin\/users\/(\d+)\/(permissions\/grant|permissions\/revoke|super-admin)$/;

/**
 * Account console and permission page writes. Deactivating, reactivating,
 * blocking, unblocking and granting or revoking permissions decide whether
 * someone can sign in and what they can do, so they may only be about a
 * seeded person; super-admin is never touched. A block request may only be
 * about a seeded person too, since approving it blocks them. Returns
 * undefined when the path is none of these.
 */
function refuseAccounts({ method, path, body }) {
  const account = path.match(ACCOUNT_WRITE);
  if (account) {
    return isSeedUser(account[1])
      ? null
      : `user ${account[1]} is not a seeded person`;
  }
  const permission = path.match(PERMISSION_WRITE);
  if (permission) {
    if (permission[2] === "super-admin") return "super-admin is never changed";
    return isSeedUser(permission[1])
      ? null
      : `user ${permission[1]} is not a seeded person`;
  }
  if (method === "POST" && /^\/api\/block-requests$/.test(path)) {
    const target = parse(body)?.userId;
    if (!isSeedUser(target)) return `user ${target} is not a seeded person`;
  }
  return undefined;
}

const INBOX_WRITE =
  /^\/api\/inbox\/threads\/(\d+)\/(reply|archive|unarchive|assignment|move)$/;

/**
 * Inbox writes, only on the suite's threads (inserted "e2e-…" ones, or real
 * "E2E inbox …" mail from the test mailbox), checked in the database:
 * - reply only on a real thread whose reply goes to the test mailbox or an
 *   e2e alias (an inserted thread has no Gmail thread to reply into);
 * - move only while the thread needs no reply, since moving one that does
 *   tells every holder of the target service's permission;
 * - assignment only to a seeded person in a seeded round, or to a seeded
 *   application.
 * Returns undefined when the path is not an Inbox write.
 */
function refuseInbox({ path, body }) {
  const m = path.match(INBOX_WRITE);
  if (!m) return undefined;
  const facts = suiteThreadFacts(Number(m[1]));
  if (!facts) return `thread ${m[1]} is not the suite's`;
  const json = parse(body);
  if (m[2] === "reply") {
    if (facts.fake) return "an inserted thread has no Gmail thread to reply in";
    return TEST_ALIAS.test(facts.contact)
      ? null
      : `the reply would go to ${facts.contact}`;
  }
  if (m[2] === "move") {
    return facts.needsReply
      ? "it needs a reply, so moving it notifies the other team"
      : null;
  }
  if (m[2] === "assignment") {
    if (!isSeedUser(json?.userId))
      return `user ${json?.userId} is not a seeded person`;
    if (json?.roundId != null)
      return allowed.seedRounds.has(Number(json.roundId))
        ? null
        : `round ${json.roundId} is not a seeded round`;
    return allowed.applications.has(Number(json?.applicationId))
      ? null
      : `application ${json?.applicationId} is not a seeded one`;
  }
  return null;
}

const LEAVE_REQUEST_WRITE =
  /^\/api\/leave\/requests\/(\d+)\/(withdraw|decision)$/;
const LEAVE_HOLIDAYS_WRITE = /^\/api\/leave\/holidays\/(\d+)$/;

/**
 * Leave writes (see tests/leave/SIDE-EFFECTS.md):
 * - filing only as a test account, which global setup has proved holds no
 *   company address, so the server refuses before writing anything;
 * - withdrawing and deciding only a suite request (filed by a seed person or
 *   a test account, against a test account), checked in the database;
 * - replacing holidays only for 2019, only with "E2E …" segments, and only
 *   while 2019 holds nothing but "E2E …" rows;
 * - correcting a balance only for a leave seed person;
 * - the accrual and annual-close jobs never.
 * Returns undefined when the path is not under /api/leave/.
 */
function refuseLeave({ role, method, path, body }) {
  if (!path.startsWith("/api/leave/")) return undefined;
  const testAccounts = [...allowed.testAccounts];
  if (path.startsWith("/api/leave/jobs/")) return "leave jobs are never run";
  if (method === "POST" && path === "/api/leave/requests") {
    const me = readAccountState()[role]?.userId;
    return allowed.testAccounts.has(Number(me))
      ? null
      : `${role} is not a test account`;
  }
  const request = path.match(LEAVE_REQUEST_WRITE);
  if (method === "POST" && request) {
    return testAccounts.length &&
      suiteLeaveRequest(Number(request[1]), testAccounts)
      ? null
      : `leave request ${request[1]} is not the suite's`;
  }
  const holidays = path.match(LEAVE_HOLIDAYS_WRITE);
  if (method === "PUT" && holidays) {
    if (holidays[1] !== "2019") return `holidays of ${holidays[1]} are real`;
    const segments = parse(body)?.segments;
    if (!Array.isArray(segments)) return "no segments";
    if (segments.some((s) => !String(s?.name ?? "").startsWith("E2E ")))
      return "every 2019 holiday must be named E2E …";
    const real = rowsOf(
      `SELECT count(*) FROM leave_holiday WHERE year = 2019 AND name NOT LIKE 'E2E %'`,
    );
    return Number(real[0]?.[0]) === 0 ? null : "2019 holds real holidays";
  }
  if (method === "POST" && path === "/api/leave/adjustments") {
    const target = Number(parse(body)?.userId);
    return allowed.leavePeople.has(target)
      ? null
      : `user ${parse(body)?.userId} is not a leave seed person`;
  }
  return `${method} ${path} is not on the write list`;
}

/** Every address the suite signs in with, lower-cased. */
const loginAddresses = () =>
  new Set(
    [mailbox(), ...ROLES.map(loginAddress)]
      .filter(Boolean)
      .map((a) => a.toLowerCase()),
  );

/**
 * An extra address of a test account the suite may add and remove:
 * `<mailbox>+e2e-<role>-<suffix>@…`. The suffix keeps it apart from the
 * role's own sign-in address, which is checked as well.
 */
export function isExtraAlias(address) {
  const box = mailbox();
  if (!box || typeof address !== "string") return false;
  const [name, domain] = box.toLowerCase().split("@");
  const value = address.trim().toLowerCase();
  const m = value.match(/^([^@+]+)\+e2e-([a-z0-9]+)-[a-z0-9-]+@(.+)$/);
  return (
    !!m &&
    m[1] === name &&
    m[3] === domain &&
    ROLES.includes(m[2]) &&
    !loginAddresses().has(value)
  );
}

/**
 * Exactly one of the addresses global setup seeded for the profile people
 * (`seed.profile.people[*].email`), ignoring case.
 */
function isProfileSeedAddress(address) {
  if (typeof address !== "string") return false;
  const value = address.trim().toLowerCase();
  return Object.values(readSeedState()?.profile?.people ?? {}).some(
    (p) => typeof p?.email === "string" && p.email.toLowerCase() === value,
  );
}

/** The claims of a JWT, unverified; null when it is not one. */
function jwtClaims(token) {
  try {
    return JSON.parse(
      Buffer.from(String(token).split(".")[1], "base64url").toString(),
    );
  } catch {
    return null;
  }
}

const EMAIL_ROW = /^\/api\/auth\/emails\/(\d+)$/;
const SET_PRIMARY = /^\/api\/auth\/emails\/(\d+)\/primary\/(initiate|confirm)$/;

/**
 * Profile and Sign in & security writes.
 * - `PATCH /api/profiles/me` only writes the caller; it goes out only for a
 *   role the test lets edit (`page.allowProfileWrites()`), which restores
 *   the account afterwards.
 * - Adding an address (initiate, verify) only for an extra alias of a test
 *   account, never a sign-in address; the code goes to that alias. Starting
 *   one with exactly a profile-seed person's address, or with something that
 *   is not an address, goes out too: the API refuses both before sending.
 * - Removing an address only when the row is the caller's extra alias, or a
 *   profile-seed person's row (to see the API refuse it).
 * - Making an address primary: starting is allowed for the caller's extra
 *   alias (the code goes to the current primary, a sign-in address of the
 *   test mailbox); confirming never, since it would move the primary off the
 *   sign-in address and a wrong code counts against that address at Auth0.
 * - Removing a sign-in identity never: confirming deletes an Auth0 user.
 * Returns undefined when the path is none of these.
 */
function refuseProfile({ role, method, path, body }) {
  const me = readAccountState()[role]?.userId;
  if (path === "/api/profiles/me") {
    if (!allowed.testAccounts.has(Number(me)))
      return `${role} is not a test account`;
    return allowed.profileWriters.has(role)
      ? null
      : "profile writes only in a test that restores the account";
  }
  if (path.startsWith("/api/auth/identities/"))
    return "removing a sign-in identity deletes an Auth0 user";
  if (!path.startsWith("/api/auth/emails")) return undefined;
  if (!allowed.testAccounts.has(Number(me)))
    return `${role} is not a test account`;
  if (method === "POST" && path === "/api/auth/emails/initiate") {
    const email = parse(body)?.email;
    if (isExtraAlias(email)) return null;
    // A profile-seed person's address: the API refuses it before sending.
    if (isProfileSeedAddress(email)) return null;
    // Not an address at all: the API answers 400 before sending
    // (email_management_service.py, _EMAIL_PATTERN).
    if (
      typeof email === "string" &&
      !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email.trim().toLowerCase())
    )
      return null;
    return `${email} is not an extra alias of a test account`;
  }
  if (method === "POST" && path === "/api/auth/emails/verify") {
    const email = jwtClaims(parse(body)?.state)?.email;
    return isExtraAlias(email) ? null : `verifies ${email}`;
  }
  const primary = path.match(SET_PRIMARY);
  if (primary) {
    if (primary[2] === "confirm") return "the primary address is never changed";
    const row = emailRowById(Number(primary[1]));
    return row && row.userId === Number(me) && isExtraAlias(row.email)
      ? null
      : `email ${primary[1]} is not the caller's extra alias`;
  }
  const row = path.match(EMAIL_ROW);
  if (method === "DELETE" && row) {
    const found = emailRowById(Number(row[1]));
    if (!found) return null;
    if (found.userId >= PROFILE_ID_FLOOR && found.userId <= PROFILE_ID_CEILING)
      return null;
    if (found.userId !== Number(me)) return `email ${row[1]} is someone else's`;
    if (found.isPrimary) return "the primary address is never removed";
    return isExtraAlias(found.email)
      ? null
      : `${found.email} is not an extra alias`;
  }
  return `${method} ${path} is not on the write list`;
}

/** Creating or editing a round: one endpoint, an edit carries the id. */
const ROUND_UPSERT = /^\/api\/mentorship\/rounds$/;

/** How far in the past every date of a suite round must lie. */
const PAST_MS = 30 * 86_400_000;

/**
 * A round only the suite would write: named "E2E …" with every date at
 * least 30 days ago, so it is never in progress or upcoming, and
 * cleanup.sql removes it by the same rule.
 */
const isSuiteRound = (body) =>
  typeof body?.name === "string" &&
  body.name.startsWith("E2E ") &&
  Object.values(body.timeline ?? {})
    .filter((date) => date != null)
    .every((date) => Date.parse(date) < Date.now() - PAST_MS);

/**
 * Work on a round's latest matching result, allowed in a seeded round (only
 * the suite's people are in it, so only the suite starts runs there) or once
 * the suite has itself started a run in the round over allowed people;
 * otherwise the latest run could be someone else's, over real people.
 */
const ON_OWN_RUN =
  /^\/api\/mentorship\/admin\/match-runs\/(\d+)\/(draft|edit-lock|publish-request)$/;

/** Decide whether one write may go out; returns the reason when it may not. */
function refuseWrite({ role, method, path, body }) {
  if (SENDS_MAIL.some((re) => re.test(path))) return "sends mail";
  const leave = refuseLeave({ role, method, path, body });
  if (leave !== undefined) return leave;
  const recruiting = refuseRecruiting({ method, path, body });
  if (recruiting !== undefined) return recruiting;
  const training = refuseTraining({ method, path, body });
  if (training !== undefined) return training;
  const accounts = refuseAccounts({ method, path, body });
  if (accounts !== undefined) return accounts;
  const inbox = refuseInbox({ path, body });
  if (inbox !== undefined) return inbox;
  const profile = refuseProfile({ role, method, path, body });
  if (profile !== undefined) return profile;
  if (
    /^\/api\/block-requests$/.test(path) &&
    parse(body)?.reviewerId != null &&
    !allowed.testAccounts.has(Number(parse(body).reviewerId))
  ) {
    return `reviewer ${parse(body).reviewerId} is not a test account`;
  }
  const reassign = path.match(/^\/api\/block-requests\/\d+\/reassign$/);
  if (reassign && !allowed.testAccounts.has(Number(parse(body)?.reviewerId))) {
    return `reviewer ${parse(body)?.reviewerId} is not a test account`;
  }
  const person = path.match(PERSON_IN_PATH) ?? path.match(EMAILS_REFRESH);
  if (person) {
    if (!allowed.seedRounds.has(Number(person[1])))
      return `round ${person[1]} is not a seeded round`;
    return allowed.people.has(Number(person[2]))
      ? null
      : `targets user ${person[2]}`;
  }
  for (const re of REQUEST_IN_PATH) {
    const m = path.match(re);
    if (m)
      return allowed.requests.has(Number(m[1]))
        ? null
        : `request ${m[1]} was not raised by the suite`;
  }
  const meetings = path.match(
    /^\/api\/mentorship\/admin\/pairs\/(\d+)\/meetings$/,
  );
  if (meetings) {
    return allowed.pairs.has(Number(meetings[1]))
      ? null
      : `pair ${meetings[1]} is not a seeded pair`;
  }
  const run = path.match(ON_OWN_RUN);
  if (run) {
    const round = Number(run[1]);
    return allowed.runs.has(round) || allowed.seedRounds.has(round)
      ? null
      : `round ${run[1]} is not seeded and has no run started by the suite`;
  }
  const roundWide = path.match(ROUND_IN_PATH);
  if (roundWide && !allowed.seedRounds.has(Number(roundWide[1]))) {
    return `round ${roundWide[1]} is not a seeded round`;
  }
  if (method === "POST" && path === "/api/mentorship/admin/match-runs") {
    const roundId = Number(parse(body)?.roundId);
    if (!allowed.seedRounds.has(roundId))
      return `round ${roundId} is not a seeded round`;
  }
  if (method === "POST" && ROUND_UPSERT.test(path)) {
    const round = parse(body);
    if (!isSuiteRound(round))
      return "a round must be named E2E … with every date at least 30 days ago";
    if (round.id == null) return null;
    return allowed.rounds.has(Number(round.id))
      ? null
      : `round ${round.id} was not created by the suite`;
  }
  if (PEOPLE_IN_BODY.some((re) => re.test(path))) {
    const strangers = peopleIn(parse(body)).filter(
      (id) => !allowed.people.has(id) && !allowed.opsPeople.has(id),
    );
    return strangers.length === 0
      ? null
      : `names users ${strangers.join(", ")}`;
  }
  const own = path.match(OWN_ROUND_RECORDS);
  if (role === "member" && own) {
    return allowed.seedRounds.has(Number(own[1]))
      ? null
      : `round ${own[1]} is not a seeded round`;
  }
  if (role === "member" && OWN_RECORDS.some((re) => re.test(path))) return null;
  if (OWN_NOTIFICATIONS.some((r) => matches(r, method, path))) return null;
  return `${method} ${path} is not on the write list`;
}

/** Remember what the suite raised and which pairs belong to allowed people. */
function learn(path, method, json, body) {
  const data = json?.data;
  if (!data) return;
  if (
    method === "POST" &&
    path === "/api/recruiting/jobs" &&
    String(parse(body)?.title ?? "").startsWith("E2E ") &&
    Number.isInteger(data.id)
  ) {
    allowed.jobs.add(data.id);
  }
  if (
    method === "POST" &&
    path === "/api/recruiting/applications" &&
    allowed.jobs.has(Number(parse(body)?.jobId))
  ) {
    for (const key of ["id", "applicationId"]) {
      if (Number.isInteger(data[key])) allowed.applications.add(data[key]);
    }
  }
  if (method === "GET" && path === "/api/recruiting/reviews") {
    for (const r of Array.isArray(data) ? data : []) {
      if (allowed.jobs.has(Number(r.jobId))) allowed.reviews.add(r.reviewId);
    }
  }
  if (
    method === "POST" &&
    path === "/api/training/courses" &&
    String(parse(body)?.name ?? "").startsWith("E2E ") &&
    Number.isInteger(data.courseId)
  ) {
    allowed.trainingCourses.add(data.courseId);
  }
  const trial = path.match(/^\/api\/training\/courses\/(\d+)\/trial$/);
  if (
    method === "POST" &&
    trial &&
    allowed.trainingCourses.has(Number(trial[1])) &&
    Number.isInteger(data.trainingId)
  ) {
    allowed.trainings.add(data.trainingId);
  }
  if (method === "POST" && path === "/api/mentorship/admin/match-runs") {
    allowed.runs.add(Number(parse(body)?.roundId));
  }
  if (
    method === "POST" &&
    ROUND_UPSERT.test(path) &&
    parse(body)?.id == null &&
    Number.isInteger(data.id)
  ) {
    allowed.rounds.add(data.id);
  }
  const raised =
    method === "POST" &&
    (PERSON_IN_PATH.test(path) ||
      /^\/api\/block-requests$/.test(path) ||
      /publish-request$/.test(path));
  if (raised) {
    for (const key of ["requestId", "id"]) {
      if (Number.isInteger(data[key])) allowed.requests.add(data[key]);
    }
  }
  const detail = path.match(
    /^\/api\/mentorship\/admin\/rounds\/\d+\/participants\/(\d+)$/,
  );
  if (method === "GET" && detail && allowed.people.has(Number(detail[1]))) {
    for (const pair of data.registration?.pairs ?? []) {
      if (Number.isInteger(pair.pairId)) allowed.pairs.add(pair.pairId);
    }
  }
}

const matches = (rule, method, path) =>
  rule.method === method && rule.path.test(path);

/**
 * Watch one browser context: abort writes the test may not make and record
 * every API error that is not on the known list. `problems` is filled in
 * place and checked when the test ends. `expectedErrors` ({method, path,
 * status}, filled in place too) are the errors one test provokes on purpose;
 * they count as known for that test only.
 */
export async function guardContext(
  context,
  { role, writesAllowed, problems, expectedErrors = [] },
) {
  await context.route(`${ENV.api}/**`, async (route) => {
    const req = route.request();
    const method = req.method();
    const path = new URL(req.url()).pathname;
    const isRead =
      ["GET", "HEAD", "OPTIONS"].includes(method) ||
      READ_STYLE_CALLS.some((r) => matches(r, method, path));
    if (!isRead) {
      const reason = writesAllowed
        ? refuseWrite({ role, method, path, body: req.postData() })
        : "writes are off for this test";
      if (reason) {
        problems.push(`blocked ${method} ${path}: ${reason}`);
        return route.abort("blockedbyclient");
      }
    }
    return route.continue();
  });

  context.on("response", async (res) => {
    if (!res.url().startsWith(ENV.api)) return;
    const method = res.request().method();
    const path = new URL(res.url()).pathname;
    if (res.status() >= 400) {
      const candidates = [...KNOWN_API_ERRORS, ...expectedErrors].filter(
        (k) =>
          matches(k, method, path) &&
          k.status === res.status() &&
          !k.unless?.(),
      );
      // A rule without a message matches on status, method and path alone.
      if (candidates.some((k) => !k.message)) return;
      if (candidates.length > 0) {
        // Every candidate needs the message; a body gone with its closing
        // page cannot be checked, so the error is not taken as known.
        const text = await res.text().catch(() => null);
        if (text === null) {
          problems.push(
            `API ${res.status()}: ${method} ${path} (body unreadable, message not checked)`,
          );
          return;
        }
        const message = parse(text)?.message ?? "";
        if (candidates.some((k) => k.message.test(message))) return;
      }
      problems.push(`API ${res.status()}: ${method} ${path}`);
      return;
    }
    if (method !== "OPTIONS")
      learn(
        path,
        method,
        parse(await res.text().catch(() => null)),
        res.request().postData(),
      );
  });

  context.on("weberror", (err) => {
    problems.push(`page error: ${err.error().message}`);
  });
}
