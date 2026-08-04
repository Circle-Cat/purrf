import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { toast } from "sonner";
import ApplicationForm from "@/pages/Recruiting/ApplicationForm";
import * as api from "@/api/recruitingApi";
import * as profileApi from "@/api/profileApi";

vi.mock("@/api/recruitingApi");
vi.mock("@/api/profileApi");
vi.mock("@/lib/resume-parser", () => ({
  parseResumeFromPdf: vi.fn().mockResolvedValue({
    user: {},
    education: [],
    workHistory: [],
    projects: [],
    unmapped: {},
  }),
}));
vi.mock("@/context/auth/AuthContext.js", () => ({
  useAuth: () => ({ user: { email: "cand@x.com", userId: 2 } }),
}));

vi.spyOn(toast, "success").mockImplementation(() => {});
vi.spyOn(toast, "error").mockImplementation(() => {});
vi.spyOn(toast, "warning").mockImplementation(() => {});

beforeEach(() => {
  vi.clearAllMocks();
  profileApi.getMyProfile.mockResolvedValue({ data: { profile: {} } });
});

const JOB = {
  id: 5,
  title: "Mentee",
  kind: "activity",
  description: "",
  formSchema: { questions: [] },
  profileConfig: {
    education: "optional",
    workExperience: "optional",
    resume: "optional",
  },
};

/** A profile with one complete education row, one incomplete one, and one complete (ongoing) experience row. */
const FILLED_EXISTING = {
  id: 7,
  current: {
    submission: {
      personal: { firstName: "Ann" },
      education: [
        {
          id: "rpf-1",
          institution: "MIT",
          degree: "Bachelor",
          field: "CS",
          startMonth: "September",
          startYear: "2016",
          endMonth: "May",
          endYear: "2020",
        },
        {
          id: "rpf-2",
          institution: "",
          degree: "",
          field: "",
          startMonth: "",
          startYear: "",
          endMonth: "",
          endYear: "",
        },
      ],
      experience: [
        {
          id: "rpf-3",
          title: "SWE",
          company: "Acme",
          isCurrentlyWorking: true,
          startMonth: "June",
          startYear: "2020",
          endMonth: "",
          endYear: "",
        },
      ],
      answers: {},
    },
    resumeSha256: null,
    resumeObjectKey: null,
  },
};

/**
 * Fetched profile user matching FILLED_EXISTING's personal input
 * ({firstName: "Ann"}), so the personal write-back merges to no change.
 */
const FETCHED_USER_ANN = {
  firstName: "Ann",
  lastName: "",
  preferredName: null,
  timezone: "America/Los_Angeles",
  linkedinLink: null,
  communicationMethod: "email",
  timezoneUpdatedAt: "1970-01-01T00:00:00Z",
};

/** Fresh-account fetched user (backend defaults; timezone always changeable). */
const FETCHED_USER_NEW = {
  firstName: "",
  lastName: "",
  preferredName: null,
  timezone: "America/Los_Angeles",
  linkedinLink: null,
  communicationMethod: "email",
  timezoneUpdatedAt: "1970-01-01T00:00:00Z",
};

/** An `existing` application whose form collected only personal fields. */
const PERSONAL_ONLY_EXISTING = {
  id: 7,
  current: {
    submission: {
      personal: { firstName: "Ada", lastName: "L", timezone: "Asia/Shanghai" },
      education: [],
      experience: [],
      answers: {},
    },
    resumeSha256: null,
    resumeObjectKey: null,
  },
};

const pdfFile = () =>
  new File(["%PDF-1.4"], "resume.pdf", { type: "application/pdf" });

const selectResumeFile = (file) =>
  fireEvent.change(screen.getByTestId("resume-file-input"), {
    target: { files: [file] },
  });

describe("ApplicationForm", () => {
  it("shows the account email read-only and submits the application", async () => {
    const user = userEvent.setup();
    api.submitApplication.mockResolvedValue({ data: { id: 100 } });
    const onSubmitted = vi.fn();
    render(<ApplicationForm job={JOB} onSubmitted={onSubmitted} />);

    const email = await screen.findByLabelText("Contact email");
    expect(email).toHaveValue("cand@x.com");
    expect(email).toHaveAttribute("readonly");

    await user.click(screen.getByRole("button", { name: /submit/i }));
    expect(api.submitApplication).toHaveBeenCalledTimes(1);
    expect(api.submitApplication.mock.calls[0][0]).toMatchObject({
      jobId: 5,
    });
    expect(onSubmitted).toHaveBeenCalled();
  });

  it("renders exactly one Contact email field", async () => {
    render(<ApplicationForm job={JOB} onSubmitted={vi.fn()} />);
    expect(await screen.findAllByLabelText("Contact email")).toHaveLength(1);
  });

  it("updates an existing application via updateApplication when `existing` is provided", async () => {
    const user = userEvent.setup();
    api.updateApplication.mockResolvedValue({ data: { id: 7 } });
    const onSubmitted = vi.fn();
    render(
      <ApplicationForm
        job={JOB}
        existing={FILLED_EXISTING}
        onSubmitted={onSubmitted}
      />,
    );

    await user.click(screen.getByRole("button", { name: /submit/i }));
    expect(api.updateApplication).toHaveBeenCalledTimes(1);
    expect(api.updateApplication.mock.calls[0][0]).toBe(7);
    expect(api.submitApplication).not.toHaveBeenCalled();
    expect(onSubmitted).toHaveBeenCalled();
    // `ApplicationEditDto` forbids extra fields -- `jobId` must never be
    // sent on the edit path, or every edit 422s.
    expect(api.updateApplication.mock.calls[0][1]).not.toHaveProperty("jobId");
    expect(api.updateApplication.mock.calls[0][1]).toMatchObject({
      personal: { firstName: "Ann" },
      answers: {},
      resumeSha256: null,
      resumeObjectKey: null,
      saveToProfile: false,
    });
  });

  it("prefills from `seed` without switching into edit mode", async () => {
    const user = userEvent.setup();
    api.submitApplication.mockResolvedValue({ data: { id: 101 } });
    const onSubmitted = vi.fn();
    render(
      <ApplicationForm
        job={JOB}
        seed={FILLED_EXISTING.current}
        onSubmitted={onSubmitted}
      />,
    );

    // seed-only prefill still defaults save-to-profile checked (same as a
    // brand-new application, since `existing` is undefined); uncheck it so
    // this test stays focused on the seed-vs-existing submit-path split.
    await user.click(
      screen.getByRole("checkbox", { name: /save to my profile/i }),
    );
    await user.click(screen.getByRole("button", { name: /submit/i }));

    expect(api.submitApplication).toHaveBeenCalledTimes(1);
    expect(api.submitApplication.mock.calls[0][0]).toMatchObject({
      jobId: 5,
      personal: { firstName: "Ann" },
    });
    expect(api.updateApplication).not.toHaveBeenCalled();
    expect(onSubmitted).toHaveBeenCalled();
  });

  it("shows a loading placeholder, then prefills from the profile, for a brand-new application", async () => {
    const user = userEvent.setup();
    let resolveProfile;
    profileApi.getMyProfile.mockReturnValue(
      new Promise((resolve) => {
        resolveProfile = resolve;
      }),
    );
    api.submitApplication.mockResolvedValue({ data: { id: 100 } });
    render(<ApplicationForm job={JOB} onSubmitted={vi.fn()} />);

    expect(screen.getByText("Loading…")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /submit/i }),
    ).not.toBeInTheDocument();

    resolveProfile({
      data: {
        profile: {
          user: { firstName: "Ann", lastName: "Liu" },
          education: [],
          workHistory: [],
        },
      },
    });

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: /submit/i }),
      ).toBeInTheDocument(),
    );
    await user.click(screen.getByRole("button", { name: /submit/i }));

    expect(api.submitApplication.mock.calls[0][0]).toMatchObject({
      personal: { firstName: "Ann", lastName: "Liu" },
    });
  });

  it("does not fetch the profile when `existing` is provided", async () => {
    api.updateApplication.mockResolvedValue({ data: { id: 7 } });
    render(
      <ApplicationForm
        job={JOB}
        existing={FILLED_EXISTING}
        onSubmitted={vi.fn()}
      />,
    );

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: /submit/i }),
      ).toBeInTheDocument(),
    );
    expect(profileApi.getMyProfile).not.toHaveBeenCalled();
  });

  it("does not fetch the profile when `seed` is provided", async () => {
    api.submitApplication.mockResolvedValue({ data: { id: 101 } });
    render(
      <ApplicationForm
        job={JOB}
        seed={FILLED_EXISTING.current}
        onSubmitted={vi.fn()}
      />,
    );

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: /submit/i }),
      ).toBeInTheDocument(),
    );
    expect(profileApi.getMyProfile).not.toHaveBeenCalled();
  });

  it("renders an empty, submittable form when the profile prefill fetch fails", async () => {
    const user = userEvent.setup();
    profileApi.getMyProfile.mockRejectedValue(new Error("boom"));
    api.submitApplication.mockResolvedValue({ data: { id: 100 } });
    const onSubmitted = vi.fn();
    render(<ApplicationForm job={JOB} onSubmitted={onSubmitted} />);

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: /submit/i }),
      ).toBeInTheDocument(),
    );
    await user.click(screen.getByRole("button", { name: /submit/i }));

    expect(onSubmitted).toHaveBeenCalled();
    // A vacuous `toMatchObject({ personal: {} })` would pass for ANY
    // personal value (an empty object subset-matches anything) -- assert
    // the field directly to actually prove the form stayed empty.
    expect(api.submitApplication.mock.calls[0][0].personal).toEqual({});
  });

  it("guards against double submission", async () => {
    const user = userEvent.setup();
    let resolveSubmit;
    api.submitApplication.mockReturnValue(
      new Promise((resolve) => {
        resolveSubmit = resolve;
      }),
    );
    render(<ApplicationForm job={JOB} onSubmitted={vi.fn()} />);

    const button = await screen.findByRole("button", { name: /submit/i });
    await user.click(button);
    await user.click(button);

    expect(api.submitApplication).toHaveBeenCalledTimes(1);
    resolveSubmit({ data: { id: 1 } });
    await waitFor(() => expect(button).not.toBeDisabled());
  });

  it("overwrites the profile lists with the reviewed form rows (dropping stored rows the form omits) when save-to-profile is checked", async () => {
    const user = userEvent.setup();
    api.updateApplication.mockResolvedValue({ data: { id: 7 } });
    profileApi.getMyProfile.mockResolvedValue({
      data: {
        profile: {
          user: FETCHED_USER_ANN,
          education: [
            {
              id: 33,
              school: "Stanford",
              degree: "Master",
              fieldOfStudy: "EE",
              startDate: "2010-09-01",
              endDate: "2012-06-01",
            },
          ],
          workHistory: [],
        },
      },
    });
    profileApi.updateMyProfile.mockResolvedValue({ data: {} });
    render(
      <ApplicationForm
        job={JOB}
        existing={FILLED_EXISTING}
        onSubmitted={vi.fn()}
      />,
    );

    // Existing application -> save-to-profile defaults unchecked; check it.
    await user.click(
      screen.getByRole("checkbox", { name: /save to my profile/i }),
    );
    await user.click(screen.getByRole("button", { name: /submit/i }));

    await waitFor(() =>
      expect(profileApi.updateMyProfile).toHaveBeenCalledTimes(1),
    );
    expect(profileApi.getMyProfile).toHaveBeenCalledWith({
      fields: ["workHistory", "education"],
    });
    // Overwrite: the stored Stanford row is dropped -- the profile lists
    // become exactly the form's reviewed rows. Exact match also doubles as
    // the "personal identical to fetched -> NO user key" case (the form's
    // {firstName: "Ann"} matches FETCHED_USER_ANN).
    expect(profileApi.updateMyProfile).toHaveBeenCalledWith({
      education: [
        {
          school: "MIT",
          degree: "Bachelor",
          fieldOfStudy: "CS",
          startDate: "2016-09-01",
          endDate: "2020-05-01",
        },
      ],
      workHistory: [
        {
          title: "SWE",
          companyOrOrganization: "Acme",
          isCurrentJob: true,
          startDate: "2020-06-01",
          endDate: null,
        },
      ],
    });
  });

  it("omits an unchanged list and overwrites a changed one", async () => {
    const user = userEvent.setup();
    api.updateApplication.mockResolvedValue({ data: { id: 7 } });
    // Profile already holds a content-identical SWE@Acme job (so workHistory
    // is unchanged and skipped), but no education (so it's overwritten).
    profileApi.getMyProfile.mockResolvedValue({
      data: {
        profile: {
          user: FETCHED_USER_ANN,
          education: [],
          workHistory: [
            {
              id: 42,
              title: "SWE",
              companyOrOrganization: "Acme",
              isCurrentJob: true,
              startDate: "2020-06-01",
              endDate: null,
            },
          ],
        },
      },
    });
    profileApi.updateMyProfile.mockResolvedValue({ data: {} });
    render(
      <ApplicationForm
        job={JOB}
        existing={FILLED_EXISTING}
        onSubmitted={vi.fn()}
      />,
    );

    await user.click(
      screen.getByRole("checkbox", { name: /save to my profile/i }),
    );
    await user.click(screen.getByRole("button", { name: /submit/i }));

    await waitFor(() =>
      expect(profileApi.updateMyProfile).toHaveBeenCalledTimes(1),
    );
    // Exact match: the unchanged workHistory list must NOT be sent.
    expect(profileApi.updateMyProfile).toHaveBeenCalledWith({
      education: [
        {
          school: "MIT",
          degree: "Bachelor",
          fieldOfStudy: "CS",
          startDate: "2016-09-01",
          endDate: "2020-05-01",
        },
      ],
    });
  });

  it("does not clear a stored profile list when the form's section is empty", async () => {
    const user = userEvent.setup();
    api.updateApplication.mockResolvedValue({ data: { id: 7 } });
    // The form collects only personal fields (education/experience empty), but
    // the profile already has an education row -- an empty form section must
    // never overwrite (wipe) it.
    profileApi.getMyProfile.mockResolvedValue({
      data: {
        profile: {
          user: FETCHED_USER_NEW,
          education: [
            {
              id: 5,
              school: "MIT",
              degree: "Bachelor",
              fieldOfStudy: "CS",
              startDate: "2016-09-01",
              endDate: "2020-05-01",
            },
          ],
          workHistory: [],
        },
      },
    });
    profileApi.updateMyProfile.mockResolvedValue({ data: {} });
    render(
      <ApplicationForm
        job={JOB}
        existing={PERSONAL_ONLY_EXISTING}
        onSubmitted={vi.fn()}
      />,
    );

    await user.click(
      screen.getByRole("checkbox", { name: /save to my profile/i }),
    );
    await user.click(screen.getByRole("button", { name: /submit/i }));

    await waitFor(() =>
      expect(profileApi.updateMyProfile).toHaveBeenCalledTimes(1),
    );
    const payload = profileApi.updateMyProfile.mock.calls[0][0];
    expect(payload).not.toHaveProperty("education");
    expect(payload).not.toHaveProperty("workHistory");
    expect(payload).toHaveProperty("user");
  });

  it("sends no PATCH when every complete new row already exists in the profile", async () => {
    const user = userEvent.setup();
    api.updateApplication.mockResolvedValue({ data: { id: 7 } });
    profileApi.getMyProfile.mockResolvedValue({
      data: {
        profile: {
          user: FETCHED_USER_ANN,
          education: [
            {
              id: 33,
              school: "MIT",
              degree: "Bachelor",
              fieldOfStudy: "CS",
              startDate: "2016-09-01",
              endDate: "2020-05-01",
            },
          ],
          workHistory: [
            {
              id: 42,
              title: "SWE",
              companyOrOrganization: "Acme",
              isCurrentJob: true,
              startDate: "2020-06-01",
              endDate: null,
            },
          ],
        },
      },
    });
    const onSubmitted = vi.fn();
    render(
      <ApplicationForm
        job={JOB}
        existing={FILLED_EXISTING}
        onSubmitted={onSubmitted}
      />,
    );

    await user.click(
      screen.getByRole("checkbox", { name: /save to my profile/i }),
    );
    await user.click(screen.getByRole("button", { name: /submit/i }));

    await waitFor(() => expect(onSubmitted).toHaveBeenCalled());
    expect(profileApi.getMyProfile).toHaveBeenCalledTimes(1);
    expect(profileApi.updateMyProfile).not.toHaveBeenCalled();
  });

  it("sends no profile requests at all when the form has no complete rows and no personal input", async () => {
    const user = userEvent.setup();
    api.submitApplication.mockResolvedValue({ data: { id: 100 } });
    const onSubmitted = vi.fn();
    // No `existing` -> empty profile, save-to-profile defaults checked. The
    // brand-new-application prefill effect calls getMyProfile once on mount
    // regardless; this test's job is to prove write-back does NOT call it
    // again (or call updateMyProfile at all) when there's nothing to write.
    render(<ApplicationForm job={JOB} onSubmitted={onSubmitted} />);

    await user.click(await screen.findByRole("button", { name: /submit/i }));

    await waitFor(() => expect(onSubmitted).toHaveBeenCalled());
    expect(profileApi.getMyProfile).toHaveBeenCalledTimes(1);
    expect(profileApi.updateMyProfile).not.toHaveBeenCalled();
  });

  it("writes back personal fields for a fresh account (form values win, defaults pass through)", async () => {
    const user = userEvent.setup();
    api.updateApplication.mockResolvedValue({ data: { id: 7 } });
    profileApi.getMyProfile.mockResolvedValue({
      data: {
        profile: { user: FETCHED_USER_NEW, education: [], workHistory: [] },
      },
    });
    profileApi.updateMyProfile.mockResolvedValue({ data: {} });
    render(
      <ApplicationForm
        job={JOB}
        existing={PERSONAL_ONLY_EXISTING}
        onSubmitted={vi.fn()}
      />,
    );

    await user.click(
      screen.getByRole("checkbox", { name: /save to my profile/i }),
    );
    await user.click(screen.getByRole("button", { name: /submit/i }));

    await waitFor(() =>
      expect(profileApi.updateMyProfile).toHaveBeenCalledTimes(1),
    );
    // timezoneUpdatedAt is 1970, but that no longer matters -- there's no
    // cooldown restriction on timezone changes.
    expect(profileApi.updateMyProfile).toHaveBeenCalledWith({
      user: {
        firstName: "Ada",
        lastName: "L",
        preferredName: null,
        timezone: "Asia/Shanghai",
        linkedinLink: null,
        communicationMethod: "email",
      },
    });
  });

  it("always adopts a non-empty form timezone, even with a very recent timezoneUpdatedAt", async () => {
    const user = userEvent.setup();
    api.updateApplication.mockResolvedValue({ data: { id: 7 } });
    profileApi.getMyProfile.mockResolvedValue({
      data: {
        profile: {
          user: {
            ...FETCHED_USER_NEW,
            // Changed just now -- there is no cooldown restriction, so the
            // form's timezone must still win.
            timezoneUpdatedAt: new Date().toISOString(),
          },
          education: [],
          workHistory: [],
        },
      },
    });
    profileApi.updateMyProfile.mockResolvedValue({ data: {} });
    render(
      <ApplicationForm
        job={JOB}
        existing={PERSONAL_ONLY_EXISTING}
        onSubmitted={vi.fn()}
      />,
    );

    await user.click(
      screen.getByRole("checkbox", { name: /save to my profile/i }),
    );
    await user.click(screen.getByRole("button", { name: /submit/i }));

    await waitFor(() =>
      expect(profileApi.updateMyProfile).toHaveBeenCalledTimes(1),
    );
    expect(profileApi.updateMyProfile).toHaveBeenCalledWith({
      user: {
        firstName: "Ada",
        lastName: "L",
        preferredName: null,
        timezone: "Asia/Shanghai",
        linkedinLink: null,
        communicationMethod: "email",
      },
    });
  });

  it("treats an education row missing `field` as incomplete and excludes it from write-back", async () => {
    const user = userEvent.setup();
    api.updateApplication.mockResolvedValue({ data: { id: 7 } });
    const existingWithMissingField = {
      ...FILLED_EXISTING,
      current: {
        ...FILLED_EXISTING.current,
        submission: {
          ...FILLED_EXISTING.current.submission,
          // No personal input either, so the only write-back candidate is
          // the (incomplete) education row below.
          personal: {},
          education: [
            {
              id: "rpf-4",
              institution: "CMU",
              degree: "Master",
              // `field` deliberately omitted (undefined) -- would 422
              // against the backend's required `fieldOfStudy: str`.
              startMonth: "September",
              startYear: "2018",
              endMonth: "May",
              endYear: "2020",
            },
          ],
          experience: [],
        },
      },
    };
    render(
      <ApplicationForm
        job={JOB}
        existing={existingWithMissingField}
        onSubmitted={vi.fn()}
      />,
    );

    await user.click(
      screen.getByRole("checkbox", { name: /save to my profile/i }),
    );
    await user.click(screen.getByRole("button", { name: /submit/i }));

    await waitFor(() => expect(api.updateApplication).toHaveBeenCalledTimes(1));
    expect(profileApi.getMyProfile).not.toHaveBeenCalled();
    expect(profileApi.updateMyProfile).not.toHaveBeenCalled();
  });

  it("does not write back to the profile when save-to-profile is unchecked", async () => {
    const user = userEvent.setup();
    api.updateApplication.mockResolvedValue({ data: { id: 7 } });
    render(
      <ApplicationForm
        job={JOB}
        existing={FILLED_EXISTING}
        onSubmitted={vi.fn()}
      />,
    );

    // Existing application -> save-to-profile already unchecked; submit as-is.
    await user.click(screen.getByRole("button", { name: /submit/i }));

    await waitFor(() => expect(api.updateApplication).toHaveBeenCalledTimes(1));
    expect(profileApi.getMyProfile).not.toHaveBeenCalled();
    expect(profileApi.updateMyProfile).not.toHaveBeenCalled();
  });

  it("soft-fails when the profile PATCH rejects: submission still succeeds and onSubmitted still fires", async () => {
    const user = userEvent.setup();
    api.updateApplication.mockResolvedValue({ data: { id: 7 } });
    profileApi.getMyProfile.mockResolvedValue({
      data: {
        profile: { user: FETCHED_USER_ANN, education: [], workHistory: [] },
      },
    });
    profileApi.updateMyProfile.mockRejectedValue(new Error("boom"));
    const onSubmitted = vi.fn();
    render(
      <ApplicationForm
        job={JOB}
        existing={FILLED_EXISTING}
        onSubmitted={onSubmitted}
      />,
    );

    await user.click(
      screen.getByRole("checkbox", { name: /save to my profile/i }),
    );
    await user.click(screen.getByRole("button", { name: /submit/i }));

    await waitFor(() => expect(onSubmitted).toHaveBeenCalled());
    expect(toast.success).toHaveBeenCalledWith("Application submitted.");
    expect(toast.warning).toHaveBeenCalledWith(
      "Application submitted, but saving to your profile failed.",
    );
  });

  it("soft-fails when the profile fetch rejects: no PATCH, warning toast, onSubmitted still fires", async () => {
    const user = userEvent.setup();
    api.updateApplication.mockResolvedValue({ data: { id: 7 } });
    profileApi.getMyProfile.mockRejectedValue(new Error("fetch failed"));
    const onSubmitted = vi.fn();
    render(
      <ApplicationForm
        job={JOB}
        existing={FILLED_EXISTING}
        onSubmitted={onSubmitted}
      />,
    );

    await user.click(
      screen.getByRole("checkbox", { name: /save to my profile/i }),
    );
    await user.click(screen.getByRole("button", { name: /submit/i }));

    await waitFor(() => expect(onSubmitted).toHaveBeenCalled());
    expect(profileApi.updateMyProfile).not.toHaveBeenCalled();
    expect(toast.success).toHaveBeenCalledWith("Application submitted.");
    expect(toast.warning).toHaveBeenCalledWith(
      "Application submitted, but saving to your profile failed.",
    );
  });

  it("stores an uploaded resume's sha256/objectKey and includes them in the submit body", async () => {
    const user = userEvent.setup();
    api.uploadResume.mockResolvedValue({
      data: { sha256: "abc123", objectKey: "resumes/abc123.pdf" },
    });
    api.submitApplication.mockResolvedValue({ data: { id: 100 } });
    render(<ApplicationForm job={JOB} onSubmitted={vi.fn()} />);

    await screen.findByTestId("resume-file-input");
    selectResumeFile(pdfFile());
    await waitFor(() => expect(api.uploadResume).toHaveBeenCalledTimes(1));

    await user.click(screen.getByRole("button", { name: /submit/i }));
    expect(api.submitApplication.mock.calls[0][0]).toMatchObject({
      resumeSha256: "abc123",
      resumeObjectKey: "resumes/abc123.pdf",
    });
  });

  it("toasts an error when resume upload fails, without breaking the parse-and-autofill flow", async () => {
    api.uploadResume.mockRejectedValue(new Error("upload failed"));
    render(<ApplicationForm job={JOB} onSubmitted={vi.fn()} />);

    await screen.findByTestId("resume-file-input");
    selectResumeFile(pdfFile());

    await waitFor(() => expect(api.uploadResume).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(toast.error).toHaveBeenCalled());
  });

  it("does not render the job description and kind while filling the form, but does render the title", async () => {
    const jobWithDescription = {
      ...JOB,
      description:
        "This is a detailed job description with a lot of information about the role.",
    };
    render(<ApplicationForm job={jobWithDescription} onSubmitted={vi.fn()} />);

    expect(await screen.findByText("Mentee")).toBeInTheDocument();
    expect(
      screen.queryByText(/detailed job description/),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("activity")).not.toBeInTheDocument();
  });

  it("shows the résumé-on-file banner when editing an existing application with a résumé attached", async () => {
    api.resumeUrl.mockImplementation((id) => `/resume/${id}`);
    api.updateApplication.mockResolvedValue({ data: { id: 7 } });
    const existingWithResume = {
      ...FILLED_EXISTING,
      current: {
        ...FILLED_EXISTING.current,
        resumeObjectKey: "resumes/old.pdf",
      },
    };
    render(
      <ApplicationForm
        job={JOB}
        existing={existingWithResume}
        onSubmitted={vi.fn()}
      />,
    );

    expect(
      await screen.findByText(/on file from your previous application/i),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Expand" }));
    expect(screen.getByTitle("Your résumé on file")).toHaveAttribute(
      "src",
      "/resume/7",
    );
  });

  it("shows the résumé-on-file banner when reapplying with a carried-forward résumé, pointed at the prior application's id", async () => {
    api.resumeUrl.mockImplementation((id) => `/resume/${id}`);
    api.submitApplication.mockResolvedValue({ data: { id: 101 } });
    const seedWithResume = {
      ...FILLED_EXISTING.current,
      resumeObjectKey: "resumes/old.pdf",
    };
    render(
      <ApplicationForm
        job={JOB}
        seed={seedWithResume}
        seedApplicationId={9}
        onSubmitted={vi.fn()}
      />,
    );

    expect(
      await screen.findByText(/on file from your previous application/i),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Expand" }));
    expect(screen.getByTitle("Your résumé on file")).toHaveAttribute(
      "src",
      "/resume/9",
    );
  });

  it("does not show the résumé-on-file banner when there is no prior résumé reference", async () => {
    api.submitApplication.mockResolvedValue({ data: { id: 100 } });
    render(<ApplicationForm job={JOB} onSubmitted={vi.fn()} />);
    await screen.findByRole("button", { name: /submit/i });
    expect(
      screen.queryByText(/on file from your previous application/i),
    ).not.toBeInTheDocument();
  });

  it("removing the carried-forward résumé hides the banner and submits no résumé", async () => {
    const user = userEvent.setup();
    api.resumeUrl.mockImplementation((id) => `/resume/${id}`);
    api.submitApplication.mockResolvedValue({ data: { id: 101 } });
    const seedWithResume = {
      ...FILLED_EXISTING.current,
      resumeSha256: "old",
      resumeObjectKey: "resumes/old.pdf",
    };
    render(
      <ApplicationForm
        job={JOB}
        seed={seedWithResume}
        seedApplicationId={9}
        onSubmitted={vi.fn()}
      />,
    );

    expect(
      await screen.findByText(/on file from your previous application/i),
    ).toBeInTheDocument();
    // Keep the test focused on the résumé fields, not profile write-back.
    await user.click(
      screen.getByRole("checkbox", { name: /save to my profile/i }),
    );

    fireEvent.click(screen.getByRole("button", { name: "Remove" }));

    expect(
      screen.queryByText(/on file from your previous application/i),
    ).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /submit/i }));
    expect(api.submitApplication.mock.calls[0][0]).toMatchObject({
      resumeSha256: null,
      resumeObjectKey: null,
    });
  });

  it("hides the résumé-on-file banner once a fresh file replaces the carried-forward résumé", async () => {
    api.resumeUrl.mockImplementation((id) => `/resume/${id}`);
    api.updateApplication.mockResolvedValue({ data: { id: 7 } });
    api.uploadResume.mockResolvedValue({
      data: { sha256: "new123", objectKey: "resumes/new123.pdf" },
    });
    const existingWithResume = {
      ...FILLED_EXISTING,
      current: {
        ...FILLED_EXISTING.current,
        resumeObjectKey: "resumes/old.pdf",
      },
    };
    render(
      <ApplicationForm
        job={JOB}
        existing={existingWithResume}
        onSubmitted={vi.fn()}
      />,
    );

    expect(
      await screen.findByText(/on file from your previous application/i),
    ).toBeInTheDocument();

    selectResumeFile(pdfFile());
    await waitFor(() => expect(api.uploadResume).toHaveBeenCalledTimes(1));

    expect(
      screen.queryByText(/on file from your previous application/i),
    ).not.toBeInTheDocument();
  });
});
