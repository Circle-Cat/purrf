/**
 * Everything a row or thread shows is derived from its messages, its
 * assignment and its archive time — nothing here is a stored flag.
 */
import { ALIASES, JOBS, USERS } from "@/pages/InboxPrototype/mockData";

export const userById = (userId) => USERS.find((u) => u.userId === userId);

/**
 * Resolve an address to a user on primary or any alternative email.
 *
 * @returns {{user: object, matchedBy: "primary"|"alternative"}|null}
 */
export const matchSender = (email) => {
  const needle = email.toLowerCase();
  for (const user of USERS) {
    if (user.primaryEmail.toLowerCase() === needle) {
      return { user, matchedBy: "primary" };
    }
    if (user.alternativeEmails.some((e) => e.toLowerCase() === needle)) {
      return { user, matchedBy: "alternative" };
    }
  }
  return null;
};

const firstHumanInbound = (thread) =>
  thread.messages.find((m) => m.direction === "in" && m.kind === "human");

/** The outside party: whoever first wrote in, else whoever we first wrote to. */
export const contactOf = (thread) =>
  firstHumanInbound(thread)?.from ??
  thread.messages.find((m) => m.direction === "out")?.to ??
  "";

/** The person the thread is about: the assignee, else the matched sender. */
export const personOf = (thread) =>
  thread.assignment
    ? userById(thread.assignment.userId)
    : (matchSender(contactOf(thread))?.user ?? null);

const latest = (messages) =>
  messages.reduce((acc, m) => (!acc || m.at > acc.at ? m : acc), null);

const lastHumanInbound = (thread) =>
  latest(
    thread.messages.filter((m) => m.direction === "in" && m.kind === "human"),
  );

const lastOutbound = (thread) =>
  latest(thread.messages.filter((m) => m.direction === "out"));

export const lastMessage = (thread) => latest(thread.messages);

/**
 * Archived until a new human message arrives after the archive time; archiving
 * never hides a reply that comes in later.
 */
export const isArchived = (thread) => {
  if (!thread.archivedAt) return false;
  const inbound = lastHumanInbound(thread);
  return !inbound || inbound.at <= thread.archivedAt;
};

/** Last human inbound is newer than our last reply and than the archive time. */
export const needsReply = (thread) => {
  const inbound = lastHumanInbound(thread);
  if (!inbound) return false;
  const out = lastOutbound(thread);
  if (out && out.at >= inbound.at) return false;
  return !isArchived(thread);
};

/**
 * List order: threads that need a reply first, by their latest human inbound
 * message; then everything else by latest activity. Newest first in both.
 */
export const byListOrder = (a, b) => {
  const aNeeds = needsReply(a);
  const bNeeds = needsReply(b);
  if (aNeeds !== bNeeds) return aNeeds ? -1 : 1;
  const key = aNeeds ? lastHumanInbound : lastMessage;
  return key(b).at.localeCompare(key(a).at);
};

/**
 * Case-insensitive substring search over the sender's name, user ID (with or
 * without a leading `#`), the sender's address and the subject.
 */
export const matchesSearch = (thread, term) => {
  const needle = term.trim().toLowerCase();
  if (!needle) return true;
  const email = contactOf(thread);
  const user = matchSender(email)?.user;
  const id = needle.startsWith("#") ? needle.slice(1) : needle;
  return (
    email.toLowerCase().includes(needle) ||
    thread.subject.toLowerCase().includes(needle) ||
    (user
      ? user.name.toLowerCase().includes(needle) ||
        (id !== "" && String(user.userId).includes(id))
      : false)
  );
};

/** Tag for the most recent machine-generated inbound, if it is the latest inbound. */
export const machineTagOf = (thread) => {
  const inbound = latest(thread.messages.filter((m) => m.direction === "in"));
  if (inbound?.kind === "auto_reply") return "Auto-reply";
  if (inbound?.kind === "bounce") return "Delivery failed";
  return null;
};

/** The newest bounce that no later outbound has superseded. */
export const openBounceOf = (thread) => {
  const b = latest(thread.messages.filter((m) => m.kind === "bounce"));
  if (!b) return null;
  const out = lastOutbound(thread);
  return out && out.at > b.at ? null : b;
};

/** Replies go out from the alias of the inbox that owns the thread now. */
export const replyAliasOf = (thread) => ALIASES[thread.inbox];

export const applicationById = (applicationId) => {
  for (const user of USERS) {
    const app = user.applications.find((a) => a.id === applicationId);
    if (app) return { ...app, user };
  }
  return null;
};

/** Chip text for where an assigned thread sits. */
export const assignmentLabel = (assignment) => {
  if (!assignment) return null;
  const { context } = assignment;
  if (!context) return `Assigned to ${userById(assignment.userId).name}`;
  if (context.kind === "round") return `${context.round} round`;
  const app = applicationById(context.applicationId);
  return `${JOBS[app.job].title} · application #${app.id}`;
};

export const employmentApplications = (user) =>
  (user?.applications ?? []).filter((a) => JOBS[a.job].type === "EMPLOYMENT");

export const activityApplications = (user) =>
  (user?.applications ?? []).filter((a) => JOBS[a.job].type === "ACTIVITY");

/**
 * Which application of one job a thread attaches to: the newest one still in
 * play, else the newest one overall (all rejected).
 *
 * @returns {{application: object, fallback: boolean}|null}
 */
export const pickApplication = (user, jobKey) => {
  const apps = employmentApplications(user)
    .filter((a) => a.job === jobKey)
    .sort((a, b) => b.submitted.localeCompare(a.submitted));
  if (!apps.length) return null;
  const live = apps.find((a) => a.status !== "Rejected");
  return live
    ? { application: live, fallback: false }
    : { application: apps[0], fallback: true };
};

const MONTHS = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
];

/** `2026-09-29T21:14` → `Sep 29, 21:14`. */
export const formatTime = (at) => {
  const [date, time] = at.split("T");
  const [, month, day] = date.split("-");
  return `${MONTHS[Number(month) - 1]} ${Number(day)}, ${time}`;
};

/** Advance a wall-clock string by whole minutes. */
export const addMinutes = (at, minutes) =>
  new Date(new Date(`${at}:00Z`).getTime() + minutes * 60000)
    .toISOString()
    .slice(0, 16);
