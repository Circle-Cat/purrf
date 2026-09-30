/**
 * What the Emails tab and the composer derive from an application and its
 * threads. Nothing here is stored; every status is read off the messages.
 */
import { MANUAL_TEMPLATES } from "@/pages/EmailTemplatesPrototype/mockData";
import {
  ALIASES,
  CURRENT_USER,
  VIEWER_TIMEZONE,
} from "@/pages/ApplicationEmailsPrototype/mockData";

const OUR_ALIASES = new Set(Object.values(ALIASES));

/**
 * Which alias mail about an application goes out from: the mentorship alias
 * for the two ACTIVITY postings, the recruiting alias for EMPLOYMENT ones.
 */
export const senderAliasOf = (job) =>
  job.kind === "ACTIVITY" ? ALIASES.mentorship : ALIASES.recruiting;

const latest = (messages) =>
  messages.reduce(
    (acc, m) => (!acc || m.gmailInternalDate > acc.gmailInternalDate ? m : acc),
    null,
  );

/**
 * The last human inbound message is newer than our last reply and than the
 * archive time. Auto-replies and bounces never count as someone writing in.
 */
export const needsReply = (thread) => {
  const inbound = latest(
    thread.messages.filter(
      (m) => m.direction === "inbound" && m.kind === "human",
    ),
  );
  if (!inbound) return false;
  const out = latest(thread.messages.filter((m) => m.direction === "outbound"));
  if (out && out.gmailInternalDate >= inbound.gmailInternalDate) return false;
  return !thread.archivedAt || inbound.gmailInternalDate > thread.archivedAt;
};

/** The newest bounce, unless something has been sent since. */
export const openBounceOf = (thread) => {
  const bounce = latest(thread.messages.filter((m) => m.kind === "bounce"));
  if (!bounce) return null;
  const out = latest(thread.messages.filter((m) => m.direction === "outbound"));
  return out && out.gmailInternalDate > bounce.gmailInternalDate
    ? null
    : bounce;
};

/**
 * Cc to prefill on a reply: everyone copied anywhere in the thread, minus the
 * candidate and our own aliases.
 */
export const replyCcOf = (thread, applicantEmail) => {
  const seen = new Set();
  for (const m of thread.messages) {
    for (const address of m.cc ?? []) {
      const lower = address.toLowerCase();
      if (lower === applicantEmail.toLowerCase()) continue;
      if (OUR_ALIASES.has(lower)) continue;
      seen.add(address);
    }
  }
  return [...seen];
};

const escapeHtml = (text) =>
  text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");

const SIGNATURE =
  "<p>Best,<br><strong>{{sender_name}}</strong><br>" +
  "Director of People Operations<br>Circle Cat Inc</p>";

const fill = (html, values) =>
  html.replace(/\{\{(\w+)\}\}/g, (raw, name) =>
    name in values ? escapeHtml(values[name]) : raw,
  );

/**
 * The templates and signature the compose endpoint would return for this
 * application: the eight preset templates, placeholders filled.
 *
 * @returns {{templates: object[], signatureHtml: string}}
 */
export const templatesFor = (application) => {
  const values = {
    candidate_name: application.applicant.name,
    position_title: application.job.title,
    sender_name: CURRENT_USER.name,
  };
  return {
    templates: MANUAL_TEMPLATES.map((t) => ({
      key: t.key,
      label: t.name,
      subject: t.variants[0].subject,
      bodyHtml: fill(t.variants[0].body, values),
    })),
    signatureHtml: fill(SIGNATURE, values),
  };
};

const FORMATTER = new Intl.DateTimeFormat("en-US", {
  timeZone: VIEWER_TIMEZONE,
  month: "short",
  day: "numeric",
  year: "numeric",
  hour: "numeric",
  minute: "2-digit",
});

/** `Sep 29, 2026, 8:47 AM (America/Los_Angeles)`. */
export const formatWhen = (iso) =>
  `${FORMATTER.format(new Date(iso))} (${VIEWER_TIMEZONE})`;
