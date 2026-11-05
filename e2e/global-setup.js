import fs from "node:fs";
import path from "node:path";
import { chromium } from "@playwright/test";
import { ENV } from "./lib/env.js";
import {
  ROLES,
  ROLE_PERMISSIONS,
  STATE_FILE,
  readToken,
  tokenExpiry,
} from "./lib/accounts.js";
import { apiAs, getData } from "./lib/api.js";
import { browserCookies } from "./lib/cookies.js";
import { verifyFlags } from "./lib/flags.js";
import { refreshLogins } from "./lib/login.js";
import { grantInDatabase } from "./lib/db.js";
import {
  SEED_STATE_FILE,
  accountSnapshot,
  checkAccountEmails,
  cleanup,
  databaseUrl,
  inboxAdminCleanup,
  inboxAdminSeed,
  leaveCleanup,
  leaveSeed,
  profileCleanup,
  profileSeed,
  realAccountsFingerprint,
  realLeaveFingerprint,
  realRecruitingFingerprint,
  realRoundFingerprint,
  realTrainingFingerprint,
  recruitingCleanup,
  recruitingSeed,
  seed,
  suiteRealThreadState,
  trainingCleanup,
  trainingSeed,
  writeSeedState,
} from "./lib/seed.js";
import { writeFixtures } from "./lib/scorm-fixtures.js";

const COMPANY_DOMAINS = ["@circlecat.org", "@u.circlecat.org"];

async function whoAmI(role, token) {
  const left = tokenExpiry(token) - Date.now() / 1000;
  if (left < 15 * 60) {
    throw new Error(
      `${role}: token expires in ${Math.round(left / 60)} min; log in again and replace .tokens/${role}.txt`,
    );
  }
  const api = await apiAs(token);
  try {
    return await getData(api, "/api/permissions/me");
  } catch (e) {
    throw new Error(
      `${role}: ${e.message}; is .tokens/${role}.txt for ${ENV.name}?`,
    );
  } finally {
    await api.dispose();
  }
}

/** Grant whatever the account is missing, using the super admin's token. */
async function topUp(role, me, superToken) {
  const want = ROLE_PERMISSIONS[role];
  const missing = want.filter((p) => !me.permissions.includes(p));
  if (missing.length === 0) return me;
  // Never grant anything to an account that is not a plain test account.
  checkIdentity(role, me);
  if (ENV.writesAllowed && databaseUrl()) {
    // Throws, writing nothing, unless the database holds me.email for
    // me.user_id, i.e. it is the one the API talks to.
    grantInDatabase(me.user_id, me.email, missing);
    console.log(
      `[setup] ${role}: granted ${missing.join(", ")} in the database`,
    );
    return whoAmI(role, readToken(role));
  }
  if (!superToken) {
    throw new Error(
      `${role}: missing ${missing.join(", ")} and no superadmin token (an account with permission.manage) to grant them`,
    );
  }
  const api = await apiAs(superToken);
  try {
    // Grants are not deduplicated server side, so only ask for what is absent.
    const held = await getData(
      api,
      `/api/admin/users/${me.user_id}/permissions`,
    );
    const toGrant = want.filter((p) => !held.active.includes(p));
    if (toGrant.length > 0) {
      const res = await api.post(
        `/api/admin/users/${me.user_id}/permissions/grant`,
        { data: { permissionNames: toGrant } },
      );
      if (res.status() !== 200) {
        throw new Error(
          `${role}: granting ${toGrant.join(", ")} -> ${res.status()}`,
        );
      }
      console.log(`[setup] ${role}: granted ${toGrant.join(", ")}`);
    }
  } finally {
    await api.dispose();
  }
  return whoAmI(role, readToken(role));
}

function checkIdentity(role, me) {
  if (me.is_super_admin) {
    throw new Error(
      `${role} (${me.email}) is a super admin; use a plain account`,
    );
  }
  if (COMPANY_DOMAINS.some((d) => me.email.endsWith(d))) {
    throw new Error(
      `${role} (${me.email}) is a company address, which gets the employee permission bundle; use a personal address`,
    );
  }
}

/** A plain test account that holds nothing beyond its role's list. */
function checkAccount(role, me) {
  checkIdentity(role, me);
  const extra = ROLE_PERMISSIONS.admin.filter(
    (p) => !ROLE_PERMISSIONS[role].includes(p) && me.permissions.includes(p),
  );
  if (extra.length > 0) {
    throw new Error(
      `${role} (${me.email}) also holds ${extra.join(", ")}; revoke them`,
    );
  }
}

async function checkBanner(token) {
  const browser = await chromium.launch();
  try {
    const context = await browser.newContext();
    await context.addCookies(browserCookies(token));
    const page = await context.newPage();
    await page.goto(ENV.web);
    const banner = await page
      .getByTestId("env-banner")
      .textContent({ timeout: 20_000 })
      .catch(() => null);
    if (banner?.trim() !== ENV.banner) {
      throw new Error(
        `${ENV.web} shows banner "${banner}", expected "${ENV.banner}"; refusing to run`,
      );
    }
  } finally {
    await browser.close();
  }
}

/** Whether Access and the API still accept this cookie for a while. */
async function tokenWorks(token) {
  if (tokenExpiry(token) - Date.now() / 1000 < 15 * 60) return false;
  const api = await apiAs(token);
  try {
    const status = await api
      .get("/api/permissions/me")
      .then((r) => r.status())
      .catch(() => null);
    if (status === 200) return true;
    // Only Access turning the cookie away means signing in again; anything
    // else is the test backend being down, and new codes would not help.
    if ([302, 401, 403].includes(status)) return false;
    throw new Error(
      `test backend not answering (${status ?? "no response"} from /api/permissions/me); try again later`,
    );
  } finally {
    await api.dispose();
  }
}

/** The dashboard specs' kept week (tests/dashboard/helpers.js, WEEK_FILE). */
const DASHBOARD_WEEK_FILE = path.join(
  path.dirname(STATE_FILE),
  "dashboard-week.json",
);

export default async function globalSetup() {
  // Each run asks for the week afresh, never reading an earlier run's rows.
  fs.rmSync(DASHBOARD_WEEK_FILE, { force: true });
  await refreshLogins(["superadmin", ...ROLES], tokenWorks);
  // Whoever grants the others their permissions: the super admin when one
  // was given, else e2e-admin, which holds permission.manage itself.
  const superToken = readToken("superadmin") ?? readToken("admin");
  const state = {};
  for (const role of ROLES) {
    const token = readToken(role);
    if (!token) {
      console.log(`[setup] ${role}: no token, its tests will be skipped`);
      continue;
    }
    let me = await whoAmI(role, token);
    if (process.env.E2E_ANY_ACCOUNT) {
      console.log(
        `[setup] ${role}: E2E_ANY_ACCOUNT set, not checking or topping up`,
      );
    } else {
      me = await topUp(role, me, superToken);
      checkAccount(role, me);
    }
    state[role] = {
      userId: me.user_id,
      email: me.email,
      permissions: me.permissions,
    };
    console.log(`[setup] ${role}: user ${me.user_id} ${me.email}`);
  }
  const any = ROLES.map(readToken).find(Boolean);
  if (!any)
    throw new Error("No tokens in e2e.local.json or .tokens/; see README.md");
  await checkBanner(any);
  await verifyFlags(
    Object.fromEntries(
      Object.keys(state).map((role) => [role, readToken(role)]),
    ),
  );

  fs.mkdirSync(path.dirname(STATE_FILE), { recursive: true });
  fs.writeFileSync(STATE_FILE, JSON.stringify(state, null, 2));

  fs.rmSync(SEED_STATE_FILE, { force: true });
  await seedIfPossible(state);
}

/**
 * Seed the suite's own rounds for the write tests. Skipped, with the write
 * tests skipping after it, on staging, without a database URL, or without
 * the admin and member accounts.
 */
async function seedIfPossible(state) {
  const why = !ENV.writesAllowed
    ? `${ENV.name} is read-only`
    : !databaseUrl()
      ? "no database URL"
      : !state.admin || !state.member
        ? "admin and member tokens are both needed"
        : null;
  if (why) {
    console.log(`[setup] not seeding: ${why}; write tests will be skipped`);
    return;
  }
  checkAccountEmails(Object.values(state).map((s) => s.userId));
  const fingerprint = await realRoundFingerprint(readToken("admin"));
  const recruitingFingerprint = realRecruitingFingerprint();
  const trainingFingerprint = realTrainingFingerprint();
  const ids = { memberId: state.member.userId };
  const adminIds = { adminId: state.admin.userId };
  // First: it puts back real threads filed to seeded people, which the
  // cleanups below would delete along with those people.
  inboxAdminCleanup();
  profileCleanup();
  cleanup(ids);
  recruitingCleanup(adminIds);
  trainingCleanup();
  const testAccountIds = Object.values(state).map((s) => s.userId);
  leaveCleanup(testAccountIds);
  const leaveFingerprint = realLeaveFingerprint(testAccountIds);
  const seeded = seed(ids);
  // B1 and I1 are assigned to e2e-reviewer, by the address the API reports.
  const recruiting = recruitingSeed({
    ...adminIds,
    reviewerEmail: state.reviewer?.email ?? null,
  });
  const training = trainingSeed();
  const inboxAdmin = inboxAdminSeed();
  const profile = profileSeed();
  // Every seeded request is filed against e2e-reviewer.
  const leave = state.reviewer
    ? leaveSeed({
        reviewerId: state.reviewer.userId,
        memberId: state.member.userId,
        testAccounts: testAccountIds,
      })
    : null;
  const testAccounts = Object.values(state).map((s) => s.userId);
  const profileSnapshot = accountSnapshot(testAccounts);
  const accountsFingerprint = realAccountsFingerprint(testAccounts);
  const suiteThreads = suiteRealThreadState();
  writeFixtures();
  writeSeedState({
    ...seeded,
    adminId: state.admin.userId,
    testAccounts,
    recruiting,
    training,
    inboxAdmin,
    profile,
    leave,
    leaveFingerprint,
    profileSnapshot,
    accountsFingerprint,
    suiteThreads,
    fingerprint,
    recruitingFingerprint,
    trainingFingerprint,
  });
  console.log(
    `[setup] seeded trainees ${training.trainees.join(", ")}; real courses: ${trainingFingerprint
      .map((c) => `${c.courseId} ${c.name} live ${c.live}`)
      .join("; ")}`,
  );
  console.log(
    `[setup] seeded ops people ${Object.values(inboxAdmin.people).join(", ")}; the suite's real Inbox threads: ${
      suiteThreads.length ? suiteThreads.join("; ") : "none"
    }`,
  );
  console.log(
    leave
      ? `[setup] seeded leave people ${Object.values(leave.people).join(", ")}; real leave data: ${leaveFingerprint.requests?.length ?? 0} requests, ${leaveFingerprint.ledger[0]} ledger rows, ${leaveFingerprint.holidays[0]} holidays`
      : "[setup] not seeding leave: no reviewer token; its write tests will be skipped",
  );
  console.log(
    `[setup] seeded profile owner ${profile.people.owner.userId}; test accounts as found: ${profileSnapshot.users
      .map((u) => `${u.user_id} "${u.first_name} ${u.last_name}"`)
      .join(", ")}`,
  );
  console.log(
    `[setup] seeded postings ${Object.values(recruiting.jobs)
      .map((j) => `${j.title} (${j.id})`)
      .join(", ")} with ${recruiting.candidates.length} candidates`,
  );
  console.log(
    `[setup] seeded ${seeded.people.length} people into ${Object.values(
      seeded.rounds,
    )
      .map((r) => `${r.name} (${r.id})`)
      .join(", ")}` +
      (seeded.rounds.registration
        ? ""
        : "; no real round is open for registration, so no registration round (its tests skip)"),
  );
  for (const round of fingerprint) {
    console.log(`[setup] real round in progress: ${JSON.stringify(round)}`);
  }
}
