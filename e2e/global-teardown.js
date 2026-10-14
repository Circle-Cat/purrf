import { readAccountState, readToken } from "./lib/accounts.js";
import { apiAs, getData } from "./lib/api.js";
import { cleanup, readSeedState } from "./lib/seed.js";

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
    const run = await getData(
      api,
      `/api/mentorship/admin/match-runs/${seeded.roundId}`,
    );
    const pending = run?.publishRequest;
    if (pending && String(pending.raisedBy?.userId) === String(admin.userId)) {
      await api.post(
        `/api/mentorship/admin/approvals/${pending.requestId}/withdraw`,
      );
      console.log(`[teardown] withdrew publish request ${pending.requestId}`);
    }
  } finally {
    await api.dispose();
  }
}

/** Remove the seeded people and everything the tests did to them. */
export default async function globalTeardown() {
  const seeded = readSeedState();
  if (!seeded || process.env.E2E_KEEP_SEED) return;
  await withdrawOwnPublishRequest(seeded);
  cleanup(seeded);
  console.log(`[teardown] cleaned up ${seeded.roundName}`);
}
