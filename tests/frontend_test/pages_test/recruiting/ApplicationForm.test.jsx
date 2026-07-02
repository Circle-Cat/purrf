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

beforeEach(() => vi.clearAllMocks());

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

    const email = screen.getByLabelText("Contact email");
    expect(email).toHaveValue("cand@x.com");
    expect(email).toHaveAttribute("readonly");

    await user.click(screen.getByRole("button", { name: /submit/i }));
    expect(api.submitApplication).toHaveBeenCalledTimes(1);
    expect(api.submitApplication.mock.calls[0][0]).toMatchObject({
      jobId: 5,
    });
    expect(onSubmitted).toHaveBeenCalled();
  });

  it("renders exactly one Contact email field", () => {
    render(<ApplicationForm job={JOB} onSubmitted={vi.fn()} />);
    expect(screen.getAllByLabelText("Contact email")).toHaveLength(1);
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

  it("guards against double submission", async () => {
    const user = userEvent.setup();
    let resolveSubmit;
    api.submitApplication.mockReturnValue(
      new Promise((resolve) => {
        resolveSubmit = resolve;
      }),
    );
    render(<ApplicationForm job={JOB} onSubmitted={vi.fn()} />);

    const button = screen.getByRole("button", { name: /submit/i });
    await user.click(button);
    await user.click(button);

    expect(api.submitApplication).toHaveBeenCalledTimes(1);
    resolveSubmit({ data: { id: 1 } });
    await waitFor(() => expect(button).not.toBeDisabled());
  });

  it("merges complete new rows into the fetched profile (preserving existing rows and ids) when save-to-profile is checked", async () => {
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
    // Exact match doubles as the "personal identical to fetched -> NO user
    // key" case: the form's {firstName: "Ann"} matches FETCHED_USER_ANN.
    expect(profileApi.updateMyProfile).toHaveBeenCalledWith({
      education: [
        {
          id: 33,
          school: "Stanford",
          degree: "Master",
          fieldOfStudy: "EE",
          startDate: "2010-09-01",
          endDate: "2012-06-01",
        },
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

  it("skips duplicate rows and omits lists that gained nothing", async () => {
    const user = userEvent.setup();
    api.updateApplication.mockResolvedValue({ data: { id: 7 } });
    // Profile already holds a content-identical SWE@Acme job, but not the
    // MIT education row.
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
    // No `existing` -> empty profile, save-to-profile defaults checked.
    render(<ApplicationForm job={JOB} onSubmitted={onSubmitted} />);

    await user.click(screen.getByRole("button", { name: /submit/i }));

    await waitFor(() => expect(onSubmitted).toHaveBeenCalled());
    expect(profileApi.getMyProfile).not.toHaveBeenCalled();
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

    selectResumeFile(pdfFile());

    await waitFor(() => expect(api.uploadResume).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(toast.error).toHaveBeenCalled());
  });
});
