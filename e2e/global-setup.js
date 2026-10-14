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
      `${role}: missing ${missing.join(", ")} and no .tokens/superadmin.txt to grant them`,
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
  if (!any) throw new Error("No tokens in .tokens/; see README.md");
  await checkBanner(any);

  fs.mkdirSync(path.dirname(STATE_FILE), { recursive: true });
  fs.writeFileSync(STATE_FILE, JSON.stringify(state, null, 2));
}
