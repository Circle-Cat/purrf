import { test, expect, settle } from "../../fixtures.js";
import {
  callApi,
  idOf,
  needFlagOn,
  needSeed,
  openParticipants,
  rowFor,
} from "./helpers.js";

// Two writers on one matching result. e2e-admin runs matching over Mentor L1
// and Mentee L1 in the live round and starts editing, which takes the edit
// lock; e2e-reviewer2 (who also holds mentorship.admin.write) sees who holds
// it and cannot edit, through the page or the API. e2e-admin then stops
// editing and the lock is free again. Nothing is published, so the run is
// still there, succeeded and unlocked, when e2e-readonly opens it.

const RUN_GROUP = ["Mentor L1", "Mentee L1"];

test.describe(
  "matching edit lock",
  { tag: ["@mentorship", "@flag:matching-run"] },
  () => {
    test.describe.configure({ mode: "serial" });

    test("a second writer sees who holds the lock and cannot edit", async ({
      as,
    }) => {
      needFlagOn("matching-run");
      test.setTimeout(10 * 60_000);
      const other = await as("reviewer2");
      const page = await as("admin");
      needSeed(page);
      test.skip(
        !other.account.permissions.includes("mentorship.admin.write"),
        "reviewer2 does not hold mentorship.admin.write",
      );
      const { roundId } = page.seed;
      const results = `/mentorship-management/matching/${roundId}`;

      await openParticipants(page, {
        round: roundId,
        eligible: "1",
        sort: "user_id",
        order: "desc",
      });
      for (const name of RUN_GROUP) {
        await rowFor(page, idOf(page, name)).getByRole("checkbox").check();
      }
      await page.getByRole("button", { name: "Run matching · 2" }).click();
      const dialog = page.getByRole("dialog");
      await expect(dialog).toContainText("1 mentors and 1 mentees.");
      await dialog.getByRole("button", { name: "Run", exact: true }).click();
      await expect(page).toHaveURL(new RegExp(`${results}$`));
      await expect(async () => {
        await page.reload();
        await expect(
          page.getByText(/^(Succeeded|Failed|Unusable)$/),
        ).toBeVisible({ timeout: 10_000 });
      }).toPass({ timeout: 8 * 60_000, intervals: [15_000] });
      await expect(page.getByText("Succeeded", { exact: true })).toBeVisible();

      await page.getByRole("button", { name: "Edit", exact: true }).click();
      await expect(
        page.getByRole("button", { name: "Stop editing" }),
      ).toBeVisible();

      try {
        await other.goto(results);
        await expect(other.getByText("Succeeded", { exact: true })).toBeVisible(
          { timeout: 20_000 },
        );
        await settle(other);
        await expect(
          other.getByText(/^Being edited by \S/),
          "the page names who holds the lock",
        ).toBeVisible();
        await expect(
          other.getByRole("button", { name: "Edit", exact: true }),
        ).toBeDisabled();

        // Asked directly, the lock is refused too, naming the holder.
        const lockPath = `/api/mentorship/admin/match-runs/${roundId}/edit-lock`;
        other.expectApiError({
          method: "POST",
          path: new RegExp(`^${lockPath}$`),
          status: 409,
        });
        const taken = await callApi(other, "POST", lockPath);
        expect(taken.status, JSON.stringify(taken.json)).toBe(409);
        expect(taken.json?.message).toMatch(/^Being edited by /);
      } finally {
        await page.getByRole("button", { name: "Stop editing" }).click();
        await expect(
          page.getByRole("button", { name: "Edit", exact: true }),
        ).toBeEnabled();
      }

      // Released, the other writer may edit.
      await other.reload();
      await expect(other.getByText("Succeeded", { exact: true })).toBeVisible({
        timeout: 20_000,
      });
      await settle(other);
      await expect(other.getByText(/^Being edited by /)).toHaveCount(0);
      await expect(
        other.getByRole("button", { name: "Edit", exact: true }),
      ).toBeEnabled();
    });

    test("a reader sees the succeeded result with no Edit and no Request publishing", async ({
      as,
    }) => {
      needFlagOn("matching-run");
      const page = await as("readonly");
      needSeed(page);
      await page.goto(`/mentorship-management/matching/${page.seed.roundId}`);
      await expect(page.getByText("Succeeded", { exact: true })).toBeVisible({
        timeout: 20_000,
      });
      await expect(
        page.getByRole("tab", { name: /^Matched \(/ }),
      ).toBeVisible();
      await settle(page);
      await expect(
        page.getByRole("button", { name: "Edit", exact: true }),
      ).toHaveCount(0);
      await expect(
        page.getByRole("button", { name: "Request publishing" }),
      ).toHaveCount(0);
    });
  },
);
