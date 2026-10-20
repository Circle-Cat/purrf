import { test, expect, settle } from "../../fixtures.js";
import {
  callApi,
  candidateName,
  openPosting,
  seedApplication,
  seedJob,
} from "./helpers.js";

// What each account without the recruiter's grants cannot see or do, on
// the seeded postings. Every write sent here is refused by the backend, so
// nothing changes.
//   e2e-reviewer  recruiting.job.approve and recruiting.interview.evaluate
//                 only: reviews postings and evaluates what it is assigned
//                 (Candidate B1), nothing else
//   e2e-readonly  no recruiting grant at all
//   e2e-member    no grant: applies, nothing more

/** Expect a call to be refused with 403 (or 404 where existence is hidden). */
async function refused(page, method, path, body, statuses = [403]) {
  const re = new RegExp(
    `^${path.split("?")[0].replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}$`,
  );
  for (const status of statuses)
    page.expectApiError({ method, path: re, status });
  const res = await callApi(page, method, path, body);
  expect(
    statuses,
    `${method} ${path} -> ${res.status} ${JSON.stringify(res.json)}`,
  ).toContain(res.status);
}

// Reads gated on owning the posting answer 400 ("you are not an owner of
// this job", "application … not found") rather than 403.
const NOT_OWNER = [400, 403, 404];

const POSTING = (ownerId) => ({
  title: "E2E permission probe",
  kind: "employment",
  formSchema: { questions: [] },
  pipelineConfig: {
    ownerIds: [ownerId],
    stages: [{ stage: "recruiter_screening", rounds: 1 }],
  },
});

test.describe("recruiting permissions", { tag: "@recruiting" }, () => {
  test("a posting reviewer sees postings but cannot write them or reach the board", async ({
    as,
  }) => {
    test.setTimeout(120_000);
    const page = await as("reviewer");
    const job = seedJob(page, "board");
    const c1 = seedApplication(page, "Candidate C1");
    const b1 = seedApplication(page, "Candidate B1");

    await page.goto("/recruiting/postings");
    await expect(
      page.getByRole("heading", { name: "Job Postings" }),
    ).toBeVisible({
      timeout: 20_000,
    });
    await settle(page);
    await expect(
      page.getByRole("button", { name: "New posting" }),
    ).toBeDisabled();
    await openPosting(page, job.id);
    await expect(page.getByText("Operate:")).toHaveCount(0);
    await expect(
      page.getByRole("button", { name: "Edit", exact: true }),
    ).toHaveCount(0);

    await page.goto("/recruiting/board");
    await expect(page).toHaveURL(/\/access-denied$/);
    await page.goto("/recruiting/audit");
    await expect(page).toHaveURL(/\/access-denied$/);

    await refused(
      page,
      "POST",
      "/api/recruiting/jobs",
      POSTING(page.seed.adminId),
    );
    await refused(
      page,
      "GET",
      `/api/recruiting/jobs/${job.id}/board`,
      undefined,
      NOT_OWNER,
    );
    await refused(
      page,
      "GET",
      `/api/recruiting/applications/${c1.applicationId}`,
      undefined,
      NOT_OWNER,
    );
    await refused(
      page,
      "PATCH",
      `/api/recruiting/applications/${b1.applicationId}/stage`,
      {
        toStage: "rejected",
        reason: "Other",
      },
    );

    // Its own assignment opens in evaluation mode, with no recruiter controls.
    await page.goto(
      `/recruiting/applications/${b1.applicationId}?mode=evaluate`,
    );
    await expect(
      page.getByRole("heading", {
        level: 1,
        name: candidateName("Candidate B1"),
      }),
    ).toBeVisible({ timeout: 20_000 });
    await settle(page);
    for (const name of [
      "Reject",
      "Request block",
      "Reassign",
      "Schedule meeting",
    ]) {
      await expect(
        page.getByRole("button", { name, exact: true }),
        name,
      ).toHaveCount(0);
    }
    await expect(
      page.getByRole("button", { name: /^Advance to / }),
    ).toHaveCount(0);
  });

  test("an account without recruiting grants is turned away from every console page and endpoint", async ({
    as,
  }) => {
    const page = await as("readonly");
    const job = seedJob(page, "board");
    const a1 = seedApplication(page, "Candidate A1");
    for (const path of [
      "/recruiting/postings",
      "/recruiting/board",
      "/recruiting/audit",
      "/recruiting/my-evaluations",
    ]) {
      await page.goto(path);
      await expect(page, path).toHaveURL(/\/access-denied$/);
    }
    await refused(page, "GET", "/api/recruiting/jobs");
    await refused(
      page,
      "GET",
      `/api/recruiting/jobs/${job.id}/board`,
      undefined,
      NOT_OWNER,
    );
    await refused(
      page,
      "GET",
      "/api/recruiting/audit/overview?startDate=2026-01-01&endDate=2026-12-31",
    );
    await refused(
      page,
      "GET",
      `/api/recruiting/applications/${a1.applicationId}`,
      undefined,
      NOT_OWNER,
    );
  });

  test("a member cannot touch postings or other people's applications", async ({
    as,
  }) => {
    const page = await as("member");
    const job = seedJob(page, "board");
    const c1 = seedApplication(page, "Candidate C1");
    await page.goto("/recruiting/jobs");
    await settle(page);

    await refused(
      page,
      "POST",
      "/api/recruiting/jobs",
      POSTING(page.seed.adminId),
    );
    await refused(
      page,
      "POST",
      `/api/recruiting/jobs/${job.id}/request-close`,
      {
        reviewerId: page.account.userId,
      },
    );
    await refused(
      page,
      "GET",
      `/api/recruiting/applications/${c1.applicationId}`,
      undefined,
      NOT_OWNER,
    );
    await refused(
      page,
      "PATCH",
      `/api/recruiting/applications/${c1.applicationId}/stage`,
      {
        toStage: "rejected",
        reason: "Other",
      },
    );
    await refused(
      page,
      "POST",
      `/api/recruiting/applications/${c1.applicationId}/comments`,
      { body: "E2E regression: should be refused" },
      NOT_OWNER,
    );
    await refused(
      page,
      "PUT",
      `/api/recruiting/applications/${c1.applicationId}/evaluation`,
      {
        responses: {},
        confirm: false,
      },
      [400, 403, 404],
    );
    const mine = await callApi(page, "GET", "/api/recruiting/evaluations/mine");
    expect(
      mine.json?.data ?? [],
      "nobody assigned the member anything",
    ).toEqual([]);
  });
});
