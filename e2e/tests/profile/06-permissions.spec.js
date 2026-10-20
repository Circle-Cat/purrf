import { test, expect } from "../../fixtures.js";
import {
  callApi,
  needProfileSeed,
  restoreAccountsAfterEach,
  rowsOf,
  storedEmails,
  storedProfile,
} from "./helpers.js";

// Whose profile and addresses a member can reach. The profile endpoints
// take no user id, so the only way at someone else's data is through
// mentorship: a partner's contact address is handed out only for a live
// pair, only in a round the member is matched in, and only the primary.
// The member is matched with the seeded Mentor F1 in the feedback round.

restoreAccountsAfterEach();

const partnerIdOf = (page) => page.seed.byName["Mentor F1"];

test.describe("whose profile a member can reach", { tag: "@profile" }, () => {
  test("there is no route to another person's profile, and the update cannot name one", async ({
    as,
  }) => {
    const page = await as("member");
    const people = needProfileSeed(page);
    page.allowProfileWrites();
    const owner = people.owner.userId;
    const ownerBefore = storedProfile(owner);
    const mineBefore = storedProfile(page.account.userId);
    await page.goto("/profile");

    const mine = await callApi(page, "GET", "/api/profiles/me");
    expect(mine.status).toBe(200);
    expect(mine.json.data.profile.id).toBe(page.account.userId);
    expect(mine.json.data.profile.user.id).toBe(page.account.userId);

    page.expectApiError({
      method: "GET",
      path: new RegExp(`^/api/profiles/${owner}$`),
      status: 404,
    });
    const theirs = await callApi(page, "GET", `/api/profiles/${owner}`);
    expect(theirs.status).toBe(404);

    page.expectApiError({
      method: "PATCH",
      path: /^\/api\/profiles\/me$/,
      status: 400,
    });
    for (const extra of [{ id: owner }, { userId: owner }]) {
      const res = await callApi(page, "PATCH", "/api/profiles/me", {
        ...extra,
        user: {
          firstName: "E2E",
          lastName: "Not Mine",
          timezone: "UTC",
          communicationMethod: "email",
        },
      });
      // The DTO forbids extra fields; the error handler names the first one.
      expect({ status: res.status, message: res.json?.message }).toEqual({
        status: 400,
        message: `Validation Error: ${Object.keys(extra)[0]} - Extra inputs are not permitted`,
      });
    }
    expect(storedProfile(owner)).toEqual(ownerBefore);
    expect(storedProfile(page.account.userId)).toEqual(mineBefore);
  });

  test("the address list holds only the member's own addresses", async ({
    as,
  }) => {
    const page = await as("member");
    needProfileSeed(page);
    await page.goto("/settings/sign-in");
    const res = await callApi(page, "GET", "/api/auth/emails");
    expect(res.status).toBe(200);
    expect(res.json.data.emails.map((e) => e.email).sort()).toEqual(
      storedEmails(page.account.userId)
        .map((e) => e.email)
        .sort(),
    );
    expect(res.json.data.internalIdentities).toEqual([]);
  });

  test("a matched partner's address is shown only for the round of the live pair, and only the primary", async ({
    as,
  }) => {
    const page = await as("member");
    needProfileSeed(page);
    const seed = page.seed;
    const partner = partnerIdOf(page);
    const [primary] = storedEmails(partner).filter((e) => e.primary);
    const alt = "e2e.mentor.f1.alt@e2e.purrf.test";
    const [[altId]] = rowsOf(`
      INSERT INTO user_emails (user_id, email, otp_confirmed, is_primary)
      VALUES (${partner}, '${alt}', true, false) RETURNING email_id`);
    try {
      await page.goto("/dashboard/me");
      const all = await callApi(page, "GET", "/api/mentorship/partners/me");
      expect(all.status).toBe(200);
      const fromAll = all.json.data.find((p) => p.id === partner);
      expect(fromAll).toBeTruthy();
      for (const p of all.json.data) expect(p.primaryEmail ?? null).toBeNull();

      const matched = await callApi(
        page,
        "GET",
        `/api/mentorship/partners/me?round_id=${seed.rounds.feedback.id}`,
      );
      expect(matched.status).toBe(200);
      expect(matched.json.data).toEqual([
        expect.objectContaining({
          id: partner,
          lastName: "Mentor F1",
          primaryEmail: primary.email,
          isActive: true,
        }),
      ]);

      // The live round: the member starts signed up with no pair, and a
      // matching spec earlier in the run may have paired them. Either way
      // an address comes only with an active pair while the member is
      // matched there.
      const live = await callApi(
        page,
        "GET",
        `/api/mentorship/partners/me?round_id=${seed.rounds.live.id}`,
      );
      expect(live.status).toBe(200);
      const expected = rowsOf(`
        SELECT CASE WHEN p.mentor_id = ${page.account.userId} THEN p.mentee_id ELSE p.mentor_id END,
               p.status = 'active' AND r.approval_status = 'matched',
               (SELECT e.email FROM user_emails e
                 WHERE e.user_id = CASE WHEN p.mentor_id = ${page.account.userId}
                                        THEN p.mentee_id ELSE p.mentor_id END
                   AND e.is_primary)
        FROM mentorship_pairs p
        JOIN mentorship_round_participants r
          ON r.round_id = p.round_id AND r.user_id = ${page.account.userId}
        WHERE p.round_id = ${seed.rounds.live.id}
          AND ${page.account.userId} IN (p.mentor_id, p.mentee_id)`);
      expect(
        live.json.data.map((p) => [p.id, p.primaryEmail ?? null]).sort(),
      ).toEqual(
        expected
          .map(([id, shown, email]) => [
            Number(id),
            shown === "t" ? email : null,
          ])
          .sort(),
      );

      for (const res of [all, matched, live]) {
        expect(JSON.stringify(res.json)).not.toContain(alt);
      }
    } finally {
      rowsOf(
        `DELETE FROM user_emails WHERE email_id = ${Number(altId)} RETURNING email_id`,
      );
    }
  });
});
