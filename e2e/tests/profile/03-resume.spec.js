import { test, expect, settle } from "../../fixtures.js";
import { readSeedState } from "../../lib/seed.js";
import { RESUMES, writeResumeFixtures } from "../../lib/resume-fixtures.js";
import {
  field,
  needProfileSeed,
  recordWrites,
  restoreAccountsAfterEach,
  rowsOf,
  storedProfile,
} from "./helpers.js";

// The Profile page has no résumé: a résumé belongs to an application. It is
// picked on a posting's application form, parsed in the browser
// (frontend/src/lib/resume-parser) to prefill the form, and, when the
// posting collects one, uploaded content-addressed to the résumé bucket
// (POST /api/recruiting/resumes, no database row). The member never submits
// here, so no application and no profile change comes of it. Two postings
// of the suite's own, created and removed by this file:
//   collects   résumé, education and experience optional: the file is uploaded
//   prefill    résumé off: parsed for prefill only, never uploaded

restoreAccountsAfterEach();

const POSTINGS = {
  collects: {
    title: "E2E profile résumé posting",
    profile: {
      resume: "optional",
      education: "optional",
      workExperience: "optional",
    },
  },
  prefill: {
    title: "E2E profile prefill posting",
    profile: {
      resume: "off",
      education: "optional",
      workExperience: "optional",
    },
  },
};

const jobs = {};
let files;

const lit = (v) => `'${String(v).replace(/'/g, "''")}'`;

test.beforeAll(() => {
  const seed = readSeedState();
  if (!seed?.profile || !seed.adminId) return;
  files = writeResumeFixtures();
  for (const [key, p] of Object.entries(POSTINGS)) {
    const [[id]] = rowsOf(`
      INSERT INTO job (kind, status, title, description, form_schema, pipeline_config,
                       screen_rules, profile_config, was_published, cooldown_days, updated_timestamp)
      VALUES ('employment', 'published', ${lit(p.title)},
              'E2E regression posting: résumé parsing on the application form.',
              '{"nextSeq": 1, "questions": []}'::jsonb,
              ${lit(JSON.stringify({ ownerIds: [seed.adminId], stages: [{ stage: "recruiter_screening", rounds: 1 }] }))}::jsonb,
              NULL, ${lit(JSON.stringify(p.profile))}::jsonb, true, 0, now())
      RETURNING job_id`);
    jobs[key] = Number(id);
  }
});

test.afterAll(() => {
  const ids = Object.values(jobs);
  if (ids.length)
    rowsOf(
      `DELETE FROM job WHERE job_id IN (${ids.join(",")}) RETURNING job_id`,
    );
});

async function openApply(page, key) {
  needProfileSeed(page);
  await page.goto(`/recruiting/jobs/${jobs[key]}/apply`);
  await expect(
    page.getByRole("heading", { name: POSTINGS[key].title }).first(),
  ).toBeVisible({ timeout: 20_000 });
  await expect(page.getByRole("heading", { name: /^Resume/ })).toBeVisible();
  await settle(page);
}

const fileInput = (page) => page.getByTestId("resume-file-input");

/** The education or experience entry forms of the application form. */
const section = (page, heading) =>
  page.locator("section").filter({
    has: page.getByRole("heading", {
      level: 3,
      name: new RegExp(`^${heading}`),
    }),
  });

const entries = (page, heading) =>
  section(page, heading).locator("div.relative.rounded-xl");

/** Check the form holds what a résumé says. */
async function expectPrefilled(page, r) {
  await expect(page.getByLabel("First name")).toHaveValue(r.firstName, {
    timeout: 15_000,
  });
  await expect(page.getByLabel("Last name")).toHaveValue(r.lastName);
  await expect(page.getByLabel("LinkedIn")).toHaveValue(r.linkedin);
  const edu = entries(page, "Education");
  await expect(edu).toHaveCount(1);
  await expect(field(edu, "School")).toHaveValue(r.school);
  await expect(field(edu, "Degree")).toHaveValue(r.degree);
  await expect(field(edu, "Field of study")).toHaveValue(r.field);
  const eduStart = field(edu, "Start date").locator("select");
  await expect(eduStart.nth(0)).toHaveValue(r.eduStart[0]);
  await expect(eduStart.nth(1)).toHaveValue(r.eduStart[1]);
  const eduEnd = field(edu, "End date").locator("select");
  await expect(eduEnd.nth(0)).toHaveValue(r.eduEnd[0]);
  await expect(eduEnd.nth(1)).toHaveValue(r.eduEnd[1]);
  const job = entries(page, "Experience");
  await expect(job).toHaveCount(1);
  await expect(field(job, "Title")).toHaveValue(r.title);
  await expect(field(job, "Company or organization")).toHaveValue(r.company);
  await expect(
    job.getByLabel("I am currently working in this role"),
  ).toBeChecked();
}

const preview = (page, r) =>
  page.getByRole("button", { name: `${r.file} · Change` });

/** Nothing about the member changed: no application, no profile edit. */
function expectMemberUntouched(page, profileBefore) {
  const apps = rowsOf(`
    SELECT count(*) FROM application
    WHERE user_id = ${page.account.userId} AND job_id IN (${Object.values(jobs).join(",")})`);
  expect(Number(apps[0][0])).toBe(0);
  expect(storedProfile(page.account.userId)).toEqual(profileBefore);
}

test.describe("résumé on the application form", { tag: "@profile" }, () => {
  test("a résumé is uploaded, previewed and parsed into the form; a second replaces it; removing it keeps the filled fields", async ({
    as,
  }) => {
    test.setTimeout(120_000);
    const page = await as("member");
    page.allowResumeUploads();
    const before = storedProfile(page.account.userId);
    await openApply(page, "collects");
    await expect(
      page.getByText("The file you upload is saved with your application."),
    ).toBeVisible();

    const uploads = [];
    page.on("response", (r) => {
      if (new URL(r.url()).pathname === "/api/recruiting/resumes")
        uploads.push(r);
    });

    await fileInput(page).setInputFiles(files.first);
    await expect(preview(page, RESUMES.first)).toBeVisible({ timeout: 15_000 });
    await expect(
      page.locator(`iframe[title="Preview of ${RESUMES.first.file}"]`),
    ).toHaveAttribute("src", /^blob:/);
    await expectPrefilled(page, RESUMES.first);
    await expect.poll(() => uploads.length).toBe(1);
    expect(uploads[0].status()).toBe(200);
    const first = (await uploads[0].json()).data;
    expect(first.objectKey).toBe(`resumes/${first.sha256}.pdf`);
    await expect(
      page.getByRole("button", { name: "Submit application" }),
    ).toBeEnabled();

    await fileInput(page).setInputFiles(files.second);
    await expect(preview(page, RESUMES.second)).toBeVisible({
      timeout: 15_000,
    });
    await expect(preview(page, RESUMES.first)).toHaveCount(0);
    await expectPrefilled(page, RESUMES.second);
    await expect.poll(() => uploads.length).toBe(2);
    const second = (await uploads[1].json()).data;
    expect(second.sha256).not.toBe(first.sha256);

    await page.getByRole("button", { name: "Remove", exact: true }).click();
    await expect(preview(page, RESUMES.second)).toHaveCount(0);
    await expect(
      page.getByText("Click or drag a resume PDF here"),
    ).toBeVisible();
    await expect(page.locator("iframe")).toHaveCount(0);
    await expectPrefilled(page, RESUMES.second);
    expect(uploads).toHaveLength(2);
    expectMemberUntouched(page, before);
  });

  test("a posting that collects no résumé parses it for prefill and uploads nothing", async ({
    as,
  }) => {
    const page = await as("member");
    const before = storedProfile(page.account.userId);
    await openApply(page, "prefill");
    await expect(
      page.getByText(
        "This posting doesn't collect a resume; uploading only saves you time and the file itself isn't saved.",
      ),
    ).toBeVisible();
    const writes = recordWrites(page);
    await fileInput(page).setInputFiles(files.first);
    await expect(preview(page, RESUMES.first)).toBeVisible({ timeout: 15_000 });
    await expectPrefilled(page, RESUMES.first);
    expect(writes).toEqual([]);
    expectMemberUntouched(page, before);
  });

  test("a file that is not a PDF is turned away without parsing or uploading", async ({
    as,
  }) => {
    const page = await as("member");
    page.allowResumeUploads();
    const before = storedProfile(page.account.userId);
    await openApply(page, "collects");
    const writes = recordWrites(page);
    await fileInput(page).setInputFiles(files.notPdf);
    await expect(page.getByText("Please upload a PDF file.")).toBeVisible();
    await expect(page.getByLabel("First name")).toHaveValue("");
    await expect(
      page.getByText("Click or drag a resume PDF here"),
    ).toBeVisible();
    expect(writes).toEqual([]);
    expectMemberUntouched(page, before);
  });
});
