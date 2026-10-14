import { ENV } from "./env.js";
import { flag } from "./flags.js";

/**
 * Non-GET calls the app makes on its own just to read something. They are
 * let through even where writes are forbidden.
 */
const READ_STYLE_CALLS = [
  { method: "POST", path: /^\/api\/summary(\/me)?$/ },
  {
    method: "POST",
    path: /^\/api\/mentorship\/admin\/rounds\/\d+\/participants\/\d+\/emails\/refresh$/,
  },
];

/** API errors that show up on every run and are not regressions. */
const KNOWN_API_ERRORS = [
  {
    method: "POST",
    path: /^\/api\/summary\/me$/,
    status: 403,
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
  /^\/api\/recruiting\/applications\/\d+\/emails/,
];

/** Writes whose target person sits in the path. */
const PERSON_IN_PATH =
  /^\/api\/mentorship\/admin\/rounds\/\d+\/participants\/(\d+)\/(exemption-request|withdraw-request|mark-request|end-pair-request|notes)$/;

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

/** What a participant does to their own records, allowed for e2e-member. */
const OWN_RECORDS = [
  /^\/api\/mentorship\/rounds\/\d+\/registration$/,
  /^\/api\/mentorship\/rounds\/\d+\/feedback$/,
  /^\/api\/mentorship\/v1\/meetings(\/.*)?$/,
];

/** Marking one's own bell notifications read. */
const OWN_NOTIFICATIONS = [
  /^\/api\/recruiting\/notifications(\/\d+)?$/,
  /^\/api\/notifications/,
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
 * seeded people and e2e-member, the requests the suite raised, and the
 * pairs it has seen those people in.
 */
export const allowed = {
  people: new Set(),
  requests: new Set(),
  pairs: new Set(),
  runs: new Set(),
};

/**
 * Work on a round's latest matching result, allowed only once the suite has
 * itself started a run there over allowed people; otherwise the latest run
 * could be someone else's, over real people.
 */
const ON_OWN_RUN =
  /^\/api\/mentorship\/admin\/match-runs\/(\d+)\/(draft|edit-lock|publish-request)$/;

/** Decide whether one write may go out; returns the reason when it may not. */
function refuseWrite({ role, method, path, body }) {
  if (SENDS_MAIL.some((re) => re.test(path))) return "sends mail";
  const person = path.match(PERSON_IN_PATH);
  if (person) {
    return allowed.people.has(Number(person[1]))
      ? null
      : `targets user ${person[1]}`;
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
    return allowed.runs.has(Number(run[1]))
      ? null
      : `round ${run[1]} has no run started by the suite`;
  }
  if (PEOPLE_IN_BODY.some((re) => re.test(path))) {
    const strangers = peopleIn(parse(body)).filter(
      (id) => !allowed.people.has(id),
    );
    return strangers.length === 0
      ? null
      : `names users ${strangers.join(", ")}`;
  }
  if (role === "member" && OWN_RECORDS.some((re) => re.test(path))) return null;
  if (OWN_NOTIFICATIONS.some((re) => re.test(path))) return null;
  return `${method} ${path} is not on the write list`;
}

/** Remember what the suite raised and which pairs belong to allowed people. */
function learn(path, method, json, body) {
  const data = json?.data;
  if (!data) return;
  if (method === "POST" && path === "/api/mentorship/admin/match-runs") {
    allowed.runs.add(Number(parse(body)?.roundId));
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
 * place and checked when the test ends.
 */
export async function guardContext(context, { role, writesAllowed, problems }) {
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
      const known = KNOWN_API_ERRORS.some(
        (k) =>
          matches(k, method, path) &&
          k.status === res.status() &&
          !k.unless?.(),
      );
      if (!known) problems.push(`API ${res.status()}: ${method} ${path}`);
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
