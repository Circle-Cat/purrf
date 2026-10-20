import { test, expect, expectNoErrorToast } from "../../fixtures.js";
import {
  callApi,
  editModal,
  entryForms,
  field,
  needProfileSeed,
  openProfile,
  pickDate,
  profileCard,
  recordWrites,
  restoreAccountsAfterEach,
  storedProfile,
} from "./helpers.js";

// e2e-readonly adds, edits and removes its own education and work history.
// Both live in one experience row as JSON lists; saving a section replaces
// its list. Every test puts the account back (restoreAccountsAfterEach).

restoreAccountsAfterEach();

async function openEducation(page) {
  await page.getByRole("button", { name: "Edit Education" }).click();
  const modal = editModal(page, "Edit Education");
  await expect(modal).toBeVisible();
  return modal;
}

async function openExperience(page) {
  await page.getByRole("button", { name: "Edit Experience" }).click();
  const modal = editModal(page, "Edit Experience");
  await expect(modal).toBeVisible();
  return modal;
}

/** Add an education entry at the top of the modal and fill it. */
async function addEducation(modal, e) {
  await modal.getByRole("button", { name: "+", exact: true }).click();
  const form = entryForms(modal).first();
  await field(form, "School").fill(e.school);
  await field(form, "Degree").selectOption(e.degree);
  await field(form, "Field of study").fill(e.field);
  await pickDate(form, "Start date", e.start);
  await pickDate(form, "End date", e.end);
}

/** Add an experience entry at the top of the modal and fill it. */
async function addExperience(modal, e) {
  await modal.getByRole("button", { name: "+", exact: true }).click();
  const form = entryForms(modal).first();
  await field(form, "Title").fill(e.title);
  await field(form, "Company or organization").fill(e.company);
  await pickDate(form, "Start date", e.start);
  if (e.current) {
    await form.getByLabel("I am currently working in this role").check();
  } else {
    await pickDate(form, "End date", e.end);
  }
}

async function save(page, modal) {
  const saved = page.waitForResponse(
    (r) =>
      r.request().method() === "PATCH" &&
      new URL(r.url()).pathname === "/api/profiles/me",
  );
  await modal.getByRole("button", { name: "Save" }).click();
  const res = await saved;
  expect(res.status()).toBe(200);
  await expect(modal).toBeHidden();
  return res.request().postDataJSON();
}

/** The entries a section card lists, as their text, top first. */
const listed = (page, heading) =>
  profileCard(page, heading).locator("div.rounded-xl").allInnerTexts();

const SCHOOL_A = {
  school: "E2E Example University",
  degree: "Bachelor",
  field: "Computer Science",
  start: ["September", "2015"],
  end: ["June", "2019"],
};
const SCHOOL_B = {
  school: "E2E Second College",
  degree: "Master",
  field: "Data Science",
  start: ["August", "2019"],
  end: ["May", "2021"],
};

test.describe("education and experience", { tag: "@profile" }, () => {
  test("adds, edits and removes education entries, and the list survives a reload", async ({
    as,
  }) => {
    test.setTimeout(120_000);
    const page = await as("readonly");
    needProfileSeed(page);
    page.allowProfileWrites();
    const id = page.account.userId;
    await openProfile(page);
    await expect(profileCard(page, "Education")).toContainText(
      "No education added.",
    );

    let modal = await openEducation(page);
    await addEducation(modal, SCHOOL_A);
    let body = await save(page, modal);
    expect(body.education).toEqual([
      {
        school: SCHOOL_A.school,
        degree: "Bachelor",
        fieldOfStudy: "Computer Science",
        startDate: "2015-09-01",
        endDate: "2019-06-01",
      },
    ]);
    expect(await listed(page, "Education")).toEqual([
      expect.stringMatching(
        /E2E Example University\s+Bachelor's degree, Computer Science\s+Sep 2015 - Jun 2019/,
      ),
    ]);
    const [stored] = storedProfile(id).education;
    expect(stored.id).toMatch(/^[0-9a-f-]{36}$/);

    // Rename the first, add a later one: newest end date lists first.
    modal = await openEducation(page);
    await field(entryForms(modal).first(), "School").fill(
      "E2E Example University Renamed",
    );
    await addEducation(modal, SCHOOL_B);
    body = await save(page, modal);
    expect(body.education.map((e) => e.id ?? null)).toEqual([null, stored.id]);
    await openProfile(page);
    expect(await listed(page, "Education")).toEqual([
      expect.stringContaining("E2E Second College"),
      expect.stringContaining("E2E Example University Renamed"),
    ]);
    const both = storedProfile(id).education;
    expect(both.map((e) => e.school).sort()).toEqual([
      "E2E Example University Renamed",
      "E2E Second College",
    ]);
    expect(both.find((e) => e.id === stored.id).school).toBe(
      "E2E Example University Renamed",
    );

    // Remove the renamed one; the other keeps its id.
    modal = await openEducation(page);
    const renamed = entryForms(modal).nth(1);
    await expect(field(renamed, "School")).toHaveValue(
      "E2E Example University Renamed",
    );
    await renamed.getByRole("button", { name: "-" }).click();
    await expect(entryForms(modal)).toHaveCount(1);
    await save(page, modal);
    await openProfile(page);
    expect(await listed(page, "Education")).toEqual([
      expect.stringContaining("E2E Second College"),
    ]);
    const left = storedProfile(id).education;
    expect(left).toHaveLength(1);
    expect(left[0].id).toBe(
      both.find((e) => e.school === "E2E Second College").id,
    );
    await expectNoErrorToast(page);
  });

  test("removing every entry asks first, and the saved section is really empty", async ({
    as,
  }) => {
    test.setTimeout(120_000);
    const page = await as("readonly");
    needProfileSeed(page);
    page.allowProfileWrites();
    const id = page.account.userId;
    await openProfile(page);

    let modal = await openEducation(page);
    await addEducation(modal, SCHOOL_A);
    await save(page, modal);
    modal = await openExperience(page);
    await addExperience(modal, {
      title: "E2E Engineer",
      company: "E2E Robotics",
      start: ["March", "2020"],
      end: ["April", "2022"],
    });
    await save(page, modal);
    expect(storedProfile(id).education).toHaveLength(1);
    expect(storedProfile(id).workHistory).toHaveLength(1);

    for (const [open, heading, section, key, empty] of [
      [
        openEducation,
        "Education",
        "education",
        "education",
        "No education added.",
      ],
      [
        openExperience,
        "Experience",
        "work experience",
        "workHistory",
        "No experience added.",
      ],
    ]) {
      modal = await open(page);
      await entryForms(modal).getByRole("button", { name: "-" }).click();
      await expect(entryForms(modal)).toHaveCount(0);
      const writes = recordWrites(page);
      await modal.getByRole("button", { name: "Save" }).click();
      const confirm = page.getByRole("dialog", {
        name: `Remove all ${section}?`,
      });
      await expect(confirm).toBeVisible();
      await confirm.getByRole("button", { name: "Cancel" }).click();
      await expect(confirm).toBeHidden();
      await expect(modal).toBeVisible();
      expect(writes).toEqual([]);

      await modal.getByRole("button", { name: "Save" }).click();
      const saved = page.waitForResponse(
        (r) =>
          r.request().method() === "PATCH" &&
          new URL(r.url()).pathname === "/api/profiles/me",
      );
      await confirm.getByRole("button", { name: "Remove all" }).click();
      expect((await saved).request().postDataJSON()).toEqual({ [key]: [] });
      await expect(modal).toBeHidden();
      await expect(profileCard(page, heading)).toContainText(empty);
      expect(storedProfile(id)[key]).toEqual([]);
    }

    await openProfile(page);
    await expect(profileCard(page, "Education")).toContainText(
      "No education added.",
    );
    await expect(profileCard(page, "Experience")).toContainText(
      "No experience added.",
    );
  });

  test("education dates and required fields are checked before anything is sent", async ({
    as,
  }) => {
    const page = await as("readonly");
    needProfileSeed(page);
    page.allowProfileWrites();
    const before = storedProfile(page.account.userId);
    await openProfile(page);
    const writes = recordWrites(page);
    const modal = await openEducation(page);
    await modal.getByRole("button", { name: "+", exact: true }).click();
    await modal.getByRole("button", { name: "Save" }).click();
    for (const message of [
      "School is required",
      "Degree is required",
      "Field of study is required",
      "Start date is required",
      "End date is required",
    ]) {
      await expect(modal.getByText(message, { exact: true })).toBeVisible();
    }

    const form = entryForms(modal).first();
    await field(form, "School").fill("E2E Date Check University");
    await field(form, "Degree").selectOption("Bachelor");
    await field(form, "Field of study").fill("History");
    await pickDate(form, "Start date", ["March", "2020"]);
    await pickDate(form, "End date", ["January", "2019"]);
    await modal.getByRole("button", { name: "Save" }).click();
    await expect(
      modal.getByText("End date cannot be earlier than start date"),
    ).toBeVisible();
    await expect(modal.getByText("School is required")).toHaveCount(0);

    // The start picker stops at the current year, so in December no month
    // it offers is later than today. The browser's clock is held at
    // mid-January of that year instead (the year list is already built) and
    // June is picked; the end comes after it, so only the start is refused.
    const year = await page.evaluate(() => new Date().getFullYear());
    await page.clock.setFixedTime(new Date(`${year}-01-15T12:00:00Z`));
    await pickDate(form, "Start date", ["June", String(year)]);
    await pickDate(form, "End date", ["June", String(year + 2)]);
    await modal.getByRole("button", { name: "Save" }).click();
    await expect(
      modal.getByText("Start date cannot be in the future"),
    ).toBeVisible();
    await expect(
      modal.getByText("End date cannot be earlier than start date"),
    ).toHaveCount(0);

    await modal.getByRole("button", { name: "Cancel" }).click();
    expect(writes).toEqual([]);
    expect(storedProfile(page.account.userId)).toEqual(before);
  });

  test("a current role needs no end date, shows as Present, and only one role is current", async ({
    as,
  }) => {
    test.setTimeout(120_000);
    const page = await as("readonly");
    needProfileSeed(page);
    page.allowProfileWrites();
    const id = page.account.userId;
    await openProfile(page);

    const modal = await openExperience(page);
    await addExperience(modal, {
      title: "E2E Past Role",
      company: "E2E Old Co",
      start: ["January", "2018"],
      end: ["December", "2019"],
    });
    await addExperience(modal, {
      title: "E2E Current Role",
      company: "E2E New Co",
      start: ["February", "2020"],
      current: true,
    });
    const current = entryForms(modal).first();
    await expect(
      field(current, "End date").locator("select").first(),
    ).toBeDisabled();

    // Marking the older one current unmarks the newer one.
    const older = entryForms(modal).nth(1);
    await older.getByLabel("I am currently working in this role").check();
    await expect(
      current.getByLabel("I am currently working in this role"),
    ).not.toBeChecked();
    await modal.getByRole("button", { name: "Save" }).click();
    await expect(current.getByText("End date is required")).toBeVisible();
    await current.getByLabel("I am currently working in this role").check();
    await expect(
      older.getByLabel("I am currently working in this role"),
    ).not.toBeChecked();
    await pickDate(older, "End date", ["December", "2019"]);

    const body = await save(page, modal);
    expect(body.workHistory).toEqual([
      {
        title: "E2E Current Role",
        companyOrOrganization: "E2E New Co",
        isCurrentJob: true,
        startDate: "2020-02-01",
        endDate: null,
      },
      {
        title: "E2E Past Role",
        companyOrOrganization: "E2E Old Co",
        isCurrentJob: false,
        startDate: "2018-01-01",
        endDate: "2019-12-01",
      },
    ]);
    await openProfile(page);
    expect(await listed(page, "Experience")).toEqual([
      expect.stringMatching(
        /E2E Current Role\s+E2E New Co\s+Feb 2020 - Present/,
      ),
      expect.stringMatching(/E2E Past Role\s+E2E Old Co\s+Jan 2018 - Dec 2019/),
    ]);
    const stored = storedProfile(id).workHistory;
    expect(stored.find((w) => w.title === "E2E Current Role")).toMatchObject({
      is_current_job: true,
      end_date: null,
    });
  });

  test("the API refuses education and work history the form would refuse", async ({
    as,
  }) => {
    // PUR-794: EducationRequestDto and WorkHistoryRequestDto apply the form's
    // rules (backend/dto/profile_create_dto.py), and FastAPI answers 400 with
    // the first error: "Validation Error: <last loc> - <msg>".
    const page = await as("readonly");
    needProfileSeed(page);
    page.allowProfileWrites();
    const before = storedProfile(page.account.userId);
    await openProfile(page);
    page.expectApiError({
      method: "PATCH",
      path: /^\/api\/profiles\/me$/,
      status: 400,
    });
    // The API's now is UTC+14, at most one calendar year ahead of UTC, so
    // January two years on is always a future month.
    const futureYear = new Date().getUTCFullYear() + 2;
    const school = {
      school: "E2E Checked University",
      degree: "Bachelor",
      fieldOfStudy: "History",
      startDate: "2020-03-01",
      endDate: "2022-06-01",
    };
    const job = {
      title: "E2E Checked Role",
      companyOrOrganization: "E2E Checked Co",
      isCurrentJob: false,
      startDate: "2020-03-01",
      endDate: "2022-06-01",
    };
    const ENDS_BEFORE =
      "Validation Error: 0 - Value error, End date cannot be earlier than start date";
    const IN_FUTURE =
      "Validation Error: 0 - Value error, Start date cannot be in the future";
    const BLANK = (name) =>
      `Validation Error: ${name} - String should have at least 1 character`;
    for (const [body, message] of [
      [
        {
          education: [
            { ...school, startDate: "2020-03-01", endDate: "2019-01-01" },
          ],
        },
        ENDS_BEFORE,
      ],
      [
        {
          education: [
            {
              ...school,
              startDate: `${futureYear}-01-01`,
              endDate: `${futureYear}-06-01`,
            },
          ],
        },
        IN_FUTURE,
      ],
      [{ education: [{ ...school, school: "   " }] }, BLANK("school")],
      [{ education: [{ ...school, fieldOfStudy: "" }] }, BLANK("fieldOfStudy")],
      [
        {
          workHistory: [
            { ...job, startDate: "2020-03-01", endDate: "2019-01-01" },
          ],
        },
        ENDS_BEFORE,
      ],
      [
        {
          workHistory: [
            {
              ...job,
              isCurrentJob: true,
              startDate: `${futureYear}-01-01`,
              endDate: null,
            },
          ],
        },
        IN_FUTURE,
      ],
      [
        { workHistory: [{ ...job, endDate: null }] },
        "Validation Error: 0 - Value error, End date is required unless this is a current job",
      ],
      [{ workHistory: [{ ...job, title: " " }] }, BLANK("title")],
      [
        { workHistory: [{ ...job, companyOrOrganization: "" }] },
        BLANK("companyOrOrganization"),
      ],
    ]) {
      const res = await callApi(page, "PATCH", "/api/profiles/me", body);
      expect(
        { status: res.status, message: res.json?.message },
        JSON.stringify(body),
      ).toEqual({ status: 400, message });
    }
    expect(storedProfile(page.account.userId)).toEqual(before);

    // The month the API counts as now is accepted, both as a start and as
    // an end in the same month.
    const now = new Date();
    const thisMonth = `${now.getUTCFullYear()}-${String(now.getUTCMonth() + 1).padStart(2, "0")}-01`;
    const res = await callApi(page, "PATCH", "/api/profiles/me", {
      workHistory: [{ ...job, startDate: thisMonth, endDate: thisMonth }],
    });
    expect(res.status).toBe(200);
    expect(storedProfile(page.account.userId).workHistory).toEqual([
      expect.objectContaining({
        title: job.title,
        start_date: thisMonth,
        end_date: thisMonth,
      }),
    ]);
  });
});
