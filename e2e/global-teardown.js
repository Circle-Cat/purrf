import { readAccountState, readToken } from "./lib/accounts.js";
import { apiAs, getData } from "./lib/api.js";
import {
  bookedSuiteInterviews,
  cleanup,
  inboxAdminCleanup,
  leaveCleanup,
  profileCleanup,
  readSeedState,
  restoreAccounts,
  realAccountsFingerprint,
  realLeaveFingerprint,
  realRecruitingFingerprint,
  realRoundFingerprint,
  realTrainingFingerprint,
  recruitingCleanup,
  suitePackagePrefixes,
  suiteRealThreadState,
  trainingCleanup,
} from "./lib/seed.js";

/**
 * Interviews a failed test left booked would keep their calendar events
 * after the rows go; cancel them the way the board does, which deletes the
 * event and tells its (test) attendees.
 */
async function cancelSuiteInterviews(seeded) {
  const token = readToken("admin");
  if (!token || !seeded.adminId) return;
  const api = await apiAs(token);
  try {
    for (const id of bookedSuiteInterviews(seeded.adminId)) {
      const res = await api.delete(
        `/api/recruiting/applications/${id}/interview`,
      );
      console.log(
        `[teardown] cancelled the interview of application ${id}: ${res.status()}`,
      );
    }
  } finally {
    await api.dispose();
  }
}

/** Warn when a real posting or its applications changed during the run. */
function compareRecruitingFingerprint(seeded) {
  const before = seeded.recruitingFingerprint;
  if (!before) return;
  const after = realRecruitingFingerprint();
  const key = (jobs) => JSON.stringify(jobs, null, 2);
  if (key(before) === key(after)) {
    console.log(
      `[teardown] real postings and applications unchanged (${before.length} postings)`,
    );
    return;
  }
  console.log(
    [
      "",
      "[teardown] WARNING: a real posting or its applications changed during the run.",
      `[teardown] before: ${key(before)}`,
      `[teardown] after:  ${key(after)}`,
      "",
    ].join("\n"),
  );
}

/** Warn when a real course, its packages or its assignments changed. */
function compareTrainingFingerprint(seeded) {
  const before = seeded.trainingFingerprint;
  if (!before) return;
  const after = realTrainingFingerprint();
  const key = (courses) => JSON.stringify(courses, null, 2);
  if (key(before) === key(after)) {
    console.log(
      `[teardown] real training courses unchanged (${before.length} courses)`,
    );
    return;
  }
  console.log(
    [
      "",
      "[teardown] WARNING: a real training course changed during the run.",
      `[teardown] before: ${key(before)}`,
      `[teardown] after:  ${key(after)}`,
      "",
    ].join("\n"),
  );
}

/**
 * The SQL cleanup drops package rows but not their files; Purrf only deletes
 * files when a package is discarded or replaced through it.
 */
function cleanupTraining() {
  const left = suitePackagePrefixes();
  trainingCleanup();
  for (const prefix of left) {
    console.log(`[teardown] left in the training bucket: ${prefix}`);
  }
}

/**
 * A publish request left pending by a failed test would stop anyone else
 * publishing the round; SQL cleanup cannot reach it, so take it back here.
 */
async function withdrawOwnPublishRequest(seeded) {
  const admin = readAccountState().admin;
  const token = readToken("admin");
  if (!admin || !token) return;
  const api = await apiAs(token);
  try {
    for (const round of Object.values(seeded.rounds ?? {})) {
      const run = await getData(
        api,
        `/api/mentorship/admin/match-runs/${round.id}`,
      ).catch(() => null);
      const pending = run?.publishRequest;
      if (
        pending &&
        String(pending.raisedBy?.userId) === String(admin.userId)
      ) {
        await api.post(
          `/api/mentorship/admin/approvals/${pending.requestId}/withdraw`,
        );
        console.log(`[teardown] withdrew publish request ${pending.requestId}`);
      }
    }
  } finally {
    await api.dispose();
  }
}

/** Warn, loudly, when a real round in progress changed during the run. */
async function compareFingerprint(seeded) {
  const before = seeded.fingerprint;
  const token = readToken("admin");
  if (!before || !token) return;
  const after = await realRoundFingerprint(token);
  const key = (rounds) =>
    JSON.stringify(
      [...rounds].sort((a, b) => a.roundId - b.roundId),
      null,
      2,
    );
  if (key(before) === key(after)) {
    console.log(
      `[teardown] real rounds in progress unchanged: ${before
        .map((r) => r.name)
        .join(", ")}`,
    );
    return;
  }
  console.log(
    [
      "",
      "[teardown] WARNING: a real round in progress changed during the run.",
      "[teardown] Someone else may have worked on it, or the suite touched it.",
      `[teardown] before: ${key(before)}`,
      `[teardown] after:  ${key(after)}`,
      "",
    ].join("\n"),
  );
}

/**
 * Warn when a real account, a real permission grant, a block request about a
 * real person or a mail thread that is not the suite's changed, and when the
 * suite's real threads are not back where the run found them.
 */
function compareAccountsFingerprint(seeded) {
  const before = seeded.accountsFingerprint;
  if (before) {
    const after = realAccountsFingerprint(seeded.testAccounts ?? []);
    const key = (f) => JSON.stringify(f, null, 2);
    if (key(before) === key(after)) {
      console.log(
        `[teardown] real accounts, grants and mail threads unchanged (${before.deactivated} deactivated, ${before.blocked} blocked, ${before.activeGrants} active grants, ${before.threads.length} threads)`,
      );
    } else {
      console.log(
        [
          "",
          "[teardown] WARNING: a real account, grant, block request or mail thread changed during the run.",
          `[teardown] before: ${key(before)}`,
          `[teardown] after:  ${key(after)}`,
          "",
        ].join("\n"),
      );
    }
  }
  if (seeded.suiteThreads) {
    const after = suiteRealThreadState();
    const key = (rows) => JSON.stringify(rows, null, 2);
    console.log(
      key(seeded.suiteThreads) === key(after)
        ? `[teardown] the suite's real Inbox threads are back as found (${after.length})`
        : `[teardown] WARNING: the suite's real Inbox threads differ from the start of the run.\n[teardown] before: ${key(seeded.suiteThreads)}\n[teardown] after:  ${key(after)}`,
    );
  }
}

/**
 * Put the test accounts' names, experience, addresses and training back as
 * global setup found them, and say whether they are.
 */
function restoreTestAccounts(seeded) {
  const snapshot = seeded.profileSnapshot;
  if (!snapshot) return;
  const left = restoreAccounts(snapshot);
  const names = snapshot.users
    .map((u) => `${u.user_id} "${u.first_name} ${u.last_name}"`)
    .join(", ");
  console.log(
    left.length === 0
      ? `[teardown] test accounts restored as found: ${names}; addresses ${snapshot.emails
          .map(
            (e) => `${e.user_id} ${e.email}${e.is_primary ? " (primary)" : ""}`,
          )
          .join(", ")}`
      : `[teardown] WARNING: test accounts differ from the start of the run:\n${left.join("\n")}`,
  );
}

/** Warn when real leave requests, ledger rows, holidays or approvals changed. */
function compareLeaveFingerprint(seeded) {
  const before = seeded.leaveFingerprint;
  if (!before) return;
  const after = realLeaveFingerprint(seeded.testAccounts);
  const key = (f) => JSON.stringify(f, null, 2);
  if (key(before) === key(after)) {
    console.log(
      `[teardown] real leave data unchanged (${before.requests?.length ?? 0} requests, ${before.ledger[0]} ledger rows, ${before.holidays[0]} holidays, ${before.approvals?.length ?? 0} approvals, ${before.events} events)`,
    );
    return;
  }
  console.log(
    [
      "",
      "[teardown] WARNING: real leave data changed during the run.",
      `[teardown] before: ${key(before)}`,
      `[teardown] after:  ${key(after)}`,
      "",
    ].join("\n"),
  );
}

/** Remove the seeded people and everything the tests did to them. */
export default async function globalTeardown() {
  const seeded = readSeedState();
  if (!seeded) return;
  // A failure here must not skip the cleanup; it is thrown again at the end
  // so the run still reports it.
  let restoreError = null;
  try {
    restoreTestAccounts(seeded);
  } catch (e) {
    restoreError = e;
    console.log(`[teardown] could not restore the test accounts: ${e.message}`);
  }
  if (process.env.E2E_KEEP_SEED) {
    await compareFingerprint(seeded).catch((e) =>
      console.log(`[teardown] could not compare the real rounds: ${e.message}`),
    );
    compareRecruitingFingerprint(seeded);
    compareTrainingFingerprint(seeded);
    compareAccountsFingerprint(seeded);
    compareLeaveFingerprint(seeded);
    if (restoreError) throw restoreError;
    return;
  }
  await cancelSuiteInterviews(seeded).catch((e) =>
    console.log(`[teardown] could not cancel booked interviews: ${e.message}`),
  );
  await withdrawOwnPublishRequest(seeded).catch((e) =>
    console.log(`[teardown] could not check the publish request: ${e.message}`),
  );
  inboxAdminCleanup();
  profileCleanup();
  if (seeded.testAccounts?.length) leaveCleanup(seeded.testAccounts);
  cleanup(seeded);
  if (seeded.adminId) recruitingCleanup({ adminId: seeded.adminId });
  if (seeded.training) cleanupTraining();
  console.log(
    `[teardown] cleaned up ${Object.values(seeded.rounds ?? {})
      .map((r) => r.name)
      .join(", ")}`,
  );
  await compareFingerprint(seeded).catch((e) =>
    console.log(`[teardown] could not compare the real rounds: ${e.message}`),
  );
  compareRecruitingFingerprint(seeded);
  compareTrainingFingerprint(seeded);
  compareAccountsFingerprint(seeded);
  compareLeaveFingerprint(seeded);
  if (restoreError) throw restoreError;
}
