import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { readLocal } from "./local.js";
import { readLoginCache } from "./login.js";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
export const TOKENS_DIR = path.join(ROOT, ".tokens");
export const STATE_FILE = path.join(ROOT, ".state", "accounts.json");

/**
 * What each test account must hold. The `superadmin` token, any account
 * holding permission.manage, only tops these up and never drives a test.
 */
export const ROLE_PERMISSIONS = {
  admin: [
    "dashboard.activity_summary.read",
    "internal_activity.read",
    "mentorship.admin.read",
    "mentorship.admin.write",
    "permission.manage",
    "user.admin",
    "inquiries.manage",
    "recruiting.job.read",
    "recruiting.job.write",
    "recruiting.job.approve",
    "recruiting.application.advance",
    "recruiting.application.read.all",
    "recruiting.interview.evaluate",
    "recruiting.audit.read",
    "leave.admin",
    "training.admin.read",
    "training.admin.write",
  ],
  // user.admin lets it decide the block request a test raises. It also
  // approves e2e-admin's postings and is the interviewer the recruiting
  // specs assign.
  reviewer: [
    "mentorship.admin.read",
    "mentorship.approve",
    "user.admin",
    "recruiting.job.approve",
    "recruiting.interview.evaluate",
  ],
  // A second reviewer, so a request can really be reassigned. It also
  // writes, so it can contend with e2e-admin for the matching edit lock.
  reviewer2: [
    "mentorship.admin.read",
    "mentorship.admin.write",
    "mentorship.approve",
    "user.admin",
    "recruiting.job.approve",
  ],
  // Can look at the mentorship console but change nothing.
  readonly: ["mentorship.admin.read"],
  member: [],
};

export const ROLES = Object.keys(ROLE_PERMISSIONS);

/**
 * The role's Cloudflare Access cookie: the one global setup signed in for,
 * else one handed over in `e2e.local.json` or `.tokens/<role>.txt`, else
 * null.
 */
export function readToken(role) {
  const signedIn = readLoginCache()[role]?.token;
  if (signedIn) return signedIn;
  const local = readLocal().tokens?.[role]?.trim();
  if (local) return local;
  const file = path.join(TOKENS_DIR, `${role}.txt`);
  if (!fs.existsSync(file)) return null;
  const token = fs.readFileSync(file, "utf8").trim();
  return token || null;
}

/** Seconds since epoch at which the token stops working. */
export function tokenExpiry(token) {
  const payload = token.split(".")[1];
  return JSON.parse(Buffer.from(payload, "base64url").toString()).exp;
}

/** Roles whose accounts passed the pre-run check, written by global setup. */
export function readAccountState() {
  if (!fs.existsSync(STATE_FILE)) return {};
  return JSON.parse(fs.readFileSync(STATE_FILE, "utf8"));
}
