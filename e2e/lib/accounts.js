import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
export const TOKENS_DIR = path.join(ROOT, ".tokens");
export const STATE_FILE = path.join(ROOT, ".state", "accounts.json");

/**
 * What each test account must hold. The super admin only tops these up and
 * never drives a test: it bypasses permission checks and would hide bugs in
 * them.
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
  reviewer: ["mentorship.admin.read", "mentorship.approve"],
  member: [],
};

export const ROLES = Object.keys(ROLE_PERMISSIONS);

/** The role's Cloudflare Access cookie, or null when none was handed over. */
export function readToken(role) {
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
