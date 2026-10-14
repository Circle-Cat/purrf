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
import {
  SEED_STATE_FILE,
  cleanup,
  databaseUrl,
  seed,
  writeSeedState,
} from "./lib/seed.js";

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

function checkAccount(role, me) {
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

export default async function globalSetup() {
  const superToken = readToken("superadmin");
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

/** The round in progress and the last round that started before it. */
async function pickRounds(token) {
  const api = await apiAs(token);
  try {
    const rounds = await getData(
      api,
      "/api/mentorship/rounds?need_details=true",
    );
    const current = rounds.find((r) => r.isInProgress);
    if (!current) return {};
    const started = (r) => r.timeline?.promotionStartAt ?? "";
    const prev = rounds
      .filter((r) => r.id !== current.id && started(r) < started(current))
      .sort((a, b) => started(b).localeCompare(started(a)))[0];
    const run = await getData(
      api,
      `/api/mentorship/admin/match-runs/${current.id}`,
    ).catch(() => null);
    const busy = Boolean(
      run &&
      (run.status === "running" ||
        run.editLock ||
        // E2E_TAKE_MATCHING=1 says someone's leftover draft may be thrown
        // away by the suite's own run; locks, running runs and pending
        // publish requests still win.
        (run.draftCount > 0 && !process.env.E2E_TAKE_MATCHING) ||
        run.publishRequest),
    );
    return { current, prev, matchingBusy: busy };
  } finally {
    await api.dispose();
  }
}

/**
 * Seed the round in progress for the write tests. Skipped, with the write
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
  const { current, prev, matchingBusy } = await pickRounds(readToken("admin"));
  if (!current || !prev) {
    console.log(
      "[setup] not seeding: no round in progress with a round before it",
    );
    return;
  }
  const ids = {
    roundId: current.id,
    prevRoundId: prev.id,
    memberId: state.member.userId,
  };
  cleanup(ids);
  const seeded = seed(ids);
  writeSeedState({ ...seeded, roundName: current.name, matchingBusy });
  console.log(
    `[setup] seeded ${seeded.people.length} people into ${current.name}` +
      (matchingBusy
        ? "; its matching is in use, matching tests will be skipped"
        : ""),
  );
}
