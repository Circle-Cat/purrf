import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
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

/** The three fields the form requires of everyone, as the profile API returns them. */
const PROFILE_USER = {
  firstName: "Cand",
  lastName: "Idate",
  timezone: "Asia/Taipei",
};

/** The same three, in the shape a stored submission holds them. */
const REQUIRED_PERSONAL = {
  firstName: "Cand",
  lastName: "Idate",
  timezone: "Asia/Taipei",
};

beforeEach(() => {
  vi.clearAllMocks();
  profileApi.getMyProfile.mockResolvedValue({
    data: { profile: { user: PROFILE_USER } },
  });
  api.getMyLatestProfile.mockResolvedValue({
    data: { personal: {}, education: [], experience: [] },
  });
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

/**
 * A profile with one complete education row and one complete (ongoing)
 * experience row.
 *
 * It used to carry a deliberately incomplete education row as well, to show
 * write-back skipping it. The form now refuses to submit an incomplete row at
 * all, so that can no longer be reached from here; `profileWriteBack.test.js`
 * pins the filter directly instead.
 */
const FILLED_EXISTING = {
  id: 7,
  current: {
    submission: {
      personal: { ...REQUIRED_PERSONAL, firstName: "Ann" },
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
  lastName: REQUIRED_PERSONAL.lastName,
  preferredName: null,
  timezone: REQUIRED_PERSONAL.timezone,
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

  describe("discard warning", () => {
    /** A posting whose q2 only appears while q1 answers "Yes". */
    const GATED_JOB = {
      ...JOB,
      formSchema: {
        questions: [
          {
            id: "q1",
            type: "single_choice",
            label: "Need sponsorship?",
            options: ["Yes", "No"],
          },
          {
            id: "q2",
            type: "long_text",
            label: "Which visa?",
            showWhen: { questionId: "q1", equals: "Yes" },
          },
        ],
      },
    };

    /** An editable application already holding an answer to the gated q2. */
    const EXISTING_WITH_GATED_ANSWER = {
      id: 7,
      current: {
        submission: {
          personal: REQUIRED_PERSONAL,
          education: [],
          experience: [],
          answers: { q1: "Yes", q2: "F-1 OPT" },
        },
      },
    };

    it("submits straight away when the save costs nothing", async () => {
      const user = userEvent.setup();
      api.submitApplication.mockResolvedValue({ data: { id: 100 } });
      render(<ApplicationForm job={GATED_JOB} onSubmitted={vi.fn()} />);
      await screen.findByLabelText("Contact email");

      await user.click(screen.getByRole("button", { name: /submit/i }));

      expect(api.submitApplication).toHaveBeenCalledTimes(1);
      expect(
        screen.queryByText("Some answers will be removed"),
      ).not.toBeInTheDocument();
    });

    it("asks before deleting an answer the form no longer shows", async () => {
      // The candidate wrote a visa type, then said they need no sponsorship.
      // The server keeps only what the form is showing and overwrites in
      // place, so that text is gone for good the moment this is sent.
      const user = userEvent.setup();
      api.updateApplication.mockResolvedValue({ data: { id: 7 } });
      render(
        <ApplicationForm
          job={GATED_JOB}
          existing={EXISTING_WITH_GATED_ANSWER}
          onSubmitted={vi.fn()}
        />,
      );
      await screen.findByLabelText("Contact email");
      await user.click(screen.getByRole("radio", { name: "No" }));

      await user.click(
        screen.getByRole("button", { name: /submit application/i }),
      );

      expect(
        await screen.findByText("Some answers will be removed"),
      ).toBeInTheDocument();
      expect(screen.getByText("Which visa?")).toBeInTheDocument();
      expect(api.updateApplication).not.toHaveBeenCalled();
    });

    it("sends nothing when the candidate goes back to editing", async () => {
      const user = userEvent.setup();
      api.updateApplication.mockResolvedValue({ data: { id: 7 } });
      render(
        <ApplicationForm
          job={GATED_JOB}
          existing={EXISTING_WITH_GATED_ANSWER}
          onSubmitted={vi.fn()}
        />,
      );
      await screen.findByLabelText("Contact email");
      await user.click(screen.getByRole("radio", { name: "No" }));
      await user.click(
        screen.getByRole("button", { name: /submit application/i }),
      );
      await screen.findByText("Some answers will be removed");

      await user.click(screen.getByRole("button", { name: "Keep editing" }));

      expect(api.updateApplication).not.toHaveBeenCalled();
      await waitFor(() =>
        expect(
          screen.queryByText("Some answers will be removed"),
        ).not.toBeInTheDocument(),
      );
    });

    it("sends once the candidate confirms", async () => {
      const user = userEvent.setup();
      api.updateApplication.mockResolvedValue({ data: { id: 7 } });
      const onSubmitted = vi.fn();
      render(
        <ApplicationForm
          job={GATED_JOB}
          existing={EXISTING_WITH_GATED_ANSWER}
          onSubmitted={onSubmitted}
        />,
      );
      await screen.findByLabelText("Contact email");
      await user.click(screen.getByRole("radio", { name: "No" }));
      await user.click(
        screen.getByRole("button", { name: /submit application/i }),
      );
      await screen.findByText("Some answers will be removed");

      await user.click(screen.getByRole("button", { name: "Submit anyway" }));

      await waitFor(() =>
        expect(api.updateApplication).toHaveBeenCalledTimes(1),
      );
      expect(onSubmitted).toHaveBeenCalled();
    });
  });

  describe("submit validation", () => {
    const REQUIRED_JOB = {
      ...JOB,
      formSchema: {
        questions: [
          {
            id: "q1",
            type: "short_text",
            label: "Where are you based?",
            required: true,
          },
        ],
      },
    };

    it("does not send an application that fails validation", async () => {
      // The API reports one failure at a time, naming the question `q1` --
      // a string that appears nowhere on the candidate's screen.
      const user = userEvent.setup();
      render(<ApplicationForm job={REQUIRED_JOB} onSubmitted={vi.fn()} />);
      await screen.findByLabelText("Contact email");

      await user.click(screen.getByRole("button", { name: /submit/i }));

      expect(
        await screen.findByText("This question is required"),
      ).toBeInTheDocument();
      expect(api.submitApplication).not.toHaveBeenCalled();
    });

    it("clears the error as soon as the field is filled in", async () => {
      const user = userEvent.setup();
      render(<ApplicationForm job={REQUIRED_JOB} onSubmitted={vi.fn()} />);
      await screen.findByLabelText("Contact email");
      await user.click(screen.getByRole("button", { name: /submit/i }));
      await screen.findByText("This question is required");

      fireEvent.change(screen.getByLabelText("Where are you based?"), {
        target: { value: "Taipei" },
      });

      await waitFor(() =>
        expect(
          screen.queryByText("This question is required"),
        ).not.toBeInTheDocument(),
      );
    });

    it("stays quiet until the candidate tries to submit", async () => {
      render(<ApplicationForm job={REQUIRED_JOB} onSubmitted={vi.fn()} />);
      await screen.findByLabelText("Contact email");
      expect(
        screen.queryByText("This question is required"),
      ).not.toBeInTheDocument();
    });

    it("sends once the form is valid", async () => {
      const user = userEvent.setup();
      api.submitApplication.mockResolvedValue({ data: { id: 100 } });
      render(<ApplicationForm job={REQUIRED_JOB} onSubmitted={vi.fn()} />);
      await screen.findByLabelText("Contact email");
      fireEvent.change(screen.getByLabelText("Where are you based?"), {
        target: { value: "Taipei" },
      });

      await user.click(screen.getByRole("button", { name: /submit/i }));

      await waitFor(() =>
        expect(api.submitApplication).toHaveBeenCalledTimes(1),
      );
    });
  });

  describe("in-flight résumé and lost responses", () => {
    it("holds Submit while a résumé is still uploading", async () => {
      // The preview renders the moment the file is picked, so without this a
      // candidate who clicks Submit two seconds later lands an application
      // with no résumé attached and no error to tell them.
      let resolveUpload;
      api.uploadResume.mockReturnValue(
        new Promise((resolve) => {
          resolveUpload = resolve;
        }),
      );
      render(<ApplicationForm job={JOB} onSubmitted={vi.fn()} />);
      await screen.findByLabelText("Contact email");

      fireEvent.change(screen.getByTestId("resume-file-input"), {
        target: {
          files: [
            new File(["%PDF-1.4"], "cv.pdf", { type: "application/pdf" }),
          ],
        },
      });

      const button = await screen.findByRole("button", {
        name: /uploading résumé/i,
      });
      expect(button).toBeDisabled();
      expect(api.submitApplication).not.toHaveBeenCalled();

      resolveUpload({ data: { sha256: "a", objectKey: "k" } });
      await waitFor(() =>
        expect(
          screen.getByRole("button", { name: /submit application/i }),
        ).not.toBeDisabled(),
      );
    });

    it("moves on instead of looping when the application already exists", async () => {
      // A create whose response was lost -- typically to a timeout -- leaves
      // the row committed, so every retry returns this and only a manual
      // reload used to get the candidate out.
      const user = userEvent.setup();
      api.submitApplication.mockRejectedValue(
        new Error(
          "you already have an application for this job; edit it instead",
        ),
      );
      const onSubmitted = vi.fn();
      render(<ApplicationForm job={JOB} onSubmitted={onSubmitted} />);
      await screen.findByLabelText("Contact email");

      await user.click(screen.getByRole("button", { name: /submit/i }));

      await waitFor(() => expect(onSubmitted).toHaveBeenCalled());
      expect(toast.error).not.toHaveBeenCalled();
    });

    it("still surfaces any other failure as an error", async () => {
      const user = userEvent.setup();
      api.submitApplication.mockRejectedValue(new Error("boom"));
      const onSubmitted = vi.fn();
      render(<ApplicationForm job={JOB} onSubmitted={onSubmitted} />);
      await screen.findByLabelText("Contact email");

      await user.click(screen.getByRole("button", { name: /submit/i }));

      await waitFor(() => expect(toast.error).toHaveBeenCalledWith("boom"));
      expect(onSubmitted).not.toHaveBeenCalled();
    });
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

    // The profile is read on every path now, so the form loads first.
    await screen.findByLabelText("Contact email");

    await user.click(screen.getByRole("button", { name: /submit/i }));
    expect(api.updateApplication).toHaveBeenCalledTimes(1);
    expect(api.updateApplication.mock.calls[0][0]).toBe(7);
    expect(api.submitApplication).not.toHaveBeenCalled();
    expect(onSubmitted).toHaveBeenCalled();
    // `ApplicationEditDto` forbids extra fields -- `jobId` must never be
    // sent on the edit path, or every edit 422s.
    expect(api.updateApplication.mock.calls[0][1]).not.toHaveProperty("jobId");
    expect(api.updateApplication.mock.calls[0][1]).toMatchObject({
      // From the profile, not from the application being edited.
      personal: { ...REQUIRED_PERSONAL },
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

    // The profile is read on every path now, so the form loads first.
    await screen.findByLabelText("Contact email");

    await user.click(screen.getByRole("button", { name: /submit/i }));

    expect(api.submitApplication).toHaveBeenCalledTimes(1);
    expect(api.submitApplication.mock.calls[0][0]).toMatchObject({
      jobId: 5,
      // From the profile: `seed` prefills the answers, not the person.
      personal: { ...REQUIRED_PERSONAL },
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

    // Deliberately not awaited: this test is about the loading state itself.
    expect(screen.getByText("Loading…")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /submit/i }),
    ).not.toBeInTheDocument();

    resolveProfile({
      data: {
        profile: {
          user: { ...PROFILE_USER, firstName: "Ann", lastName: "Liu" },
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
      personal: { ...REQUIRED_PERSONAL, firstName: "Ann", lastName: "Liu" },
    });
  });

  it("reads the profile on the edit and reapply paths too", async () => {
    // These used to assert the profile was NOT fetched when an earlier
    // submission was available. That is exactly the behaviour this changed:
    // the snapshot is for reading, the profile is for filling.
    for (const props of [
      { existing: FILLED_EXISTING },
      { seed: FILLED_EXISTING.current },
    ]) {
      profileApi.getMyProfile.mockClear();
      render(<ApplicationForm job={JOB} {...props} onSubmitted={vi.fn()} />);

      // The profile is read on every path now, so the form loads first.
      await screen.findByLabelText("Contact email");
      expect(profileApi.getMyProfile).toHaveBeenCalledTimes(1);
    }
  });

  it("asks for the required fields when the profile prefill fetch fails", async () => {
    // The prefill is a convenience, so a failure must not wedge the form --
    // but the fields it would have filled are required of everyone, so what
    // the candidate gets is a form that tells them what is missing rather
    // than one that submits an empty personal block.
    const user = userEvent.setup();
    profileApi.getMyProfile.mockRejectedValue(new Error("boom"));
    api.submitApplication.mockResolvedValue({ data: { id: 100 } });
    const onSubmitted = vi.fn();
    render(<ApplicationForm job={JOB} onSubmitted={onSubmitted} />);

    // The profile is read on every path now, so the form loads first.
    await screen.findByLabelText("Contact email");

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: /submit/i }),
      ).toBeInTheDocument(),
    );
    await user.click(screen.getByRole("button", { name: /submit/i }));

    expect(
      await screen.findByText("First name is required"),
    ).toBeInTheDocument();
    expect(screen.getByText("Last name is required")).toBeInTheDocument();
    expect(screen.getByText("Timezone is required")).toBeInTheDocument();
    expect(api.submitApplication).not.toHaveBeenCalled();
    expect(onSubmitted).not.toHaveBeenCalled();
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

  // The old write-back tests are gone with the behaviour they described: the
  // form's rows came from an earlier submission, an "Also save to my profile"
  // checkbox defaulted to on, and each list was overwritten silently. The rows
  // now come from the profile, so a difference can only be something the
  // candidate did here, and they are asked about it before anything is written.
  describe("saving changes back to the profile", () => {
    /** A profile holding one education row and one job, in backend shape. */
    const STORED = {
      user: {
        ...PROFILE_USER,
        preferredName: null,
        linkedinLink: null,
        communicationMethod: "email",
      },
      education: [
        {
          id: 41,
          school: "Tsinghua University",
          degree: "Bachelor",
          fieldOfStudy: "Computer Science",
          startDate: "2018-09-01",
          endDate: "2022-06-01",
        },
      ],
      workHistory: [],
    };

    const render_ = async (profile = STORED, job = JOB) => {
      profileApi.getMyProfile.mockResolvedValue({ data: { profile } });
      profileApi.updateMyProfile.mockResolvedValue({ data: {} });
      api.updateApplication.mockResolvedValue({ data: { id: 7 } });
      render(
        <ApplicationForm
          job={job}
          existing={FILLED_EXISTING}
          onSubmitted={vi.fn()}
        />,
      );
      await screen.findByLabelText("Contact email");
    };

    const submitForm = async (user) =>
      user.click(screen.getByRole("button", { name: /submit application/i }));

    it("asks nothing and writes nothing when the candidate changed nothing", async () => {
      const user = userEvent.setup();
      await render_();

      await submitForm(user);

      await waitFor(() => expect(api.updateApplication).toHaveBeenCalled());
      expect(
        screen.queryByText("Update your profile?"),
      ).not.toBeInTheDocument();
      expect(profileApi.updateMyProfile).not.toHaveBeenCalled();
    });

    it("asks once the candidate edits a row, and writes nothing if they decline", async () => {
      const user = userEvent.setup();
      await render_();
      fireEvent.change(screen.getByDisplayValue("Tsinghua University"), {
        target: { value: "Peking University" },
      });

      await submitForm(user);
      expect(
        await screen.findByText("Update your profile?"),
      ).toBeInTheDocument();
      await user.click(screen.getByRole("button", { name: /don't update/i }));

      await waitFor(() =>
        expect(api.updateApplication).toHaveBeenCalledTimes(1),
      );
      expect(profileApi.updateMyProfile).not.toHaveBeenCalled();
    });

    it("replaces the edited block when they accept", async () => {
      const user = userEvent.setup();
      await render_();
      fireEvent.change(screen.getByDisplayValue("Tsinghua University"), {
        target: { value: "Peking University" },
      });

      await submitForm(user);
      await screen.findByText("Update your profile?");
      await user.click(
        screen.getByRole("button", { name: /update & submit/i }),
      );

      await waitFor(() =>
        expect(profileApi.updateMyProfile).toHaveBeenCalledTimes(1),
      );
      expect(profileApi.updateMyProfile).toHaveBeenCalledWith({
        education: [
          {
            // The profile's own row id, so this updates that row rather than
            // replacing it with a copy under a new id.
            id: 41,
            school: "Peking University",
            degree: "Bachelor",
            fieldOfStudy: "Computer Science",
            startDate: "2018-09-01",
            endDate: "2022-06-01",
          },
        ],
      });
    });

    it("clears a block the candidate emptied, because that is what they asked for", async () => {
      const user = userEvent.setup();
      await render_();
      // The row's delete control has no accessible name of its own; it is a
      // bare "-". Worth labelling one day, but not from here.
      await user.click(screen.getByRole("button", { name: "-" }));

      await submitForm(user);
      await screen.findByText("Update your profile?");
      await user.click(
        screen.getByRole("button", { name: /update & submit/i }),
      );

      await waitFor(() =>
        expect(profileApi.updateMyProfile).toHaveBeenCalledTimes(1),
      );
      expect(profileApi.updateMyProfile).toHaveBeenCalledWith({
        education: [],
      });
    });

    it("never writes a block the posting did not show", async () => {
      // The rows are still in the form's state, carried over from the earlier
      // submission, but nobody saw them on this posting.
      const user = userEvent.setup();
      const noEducation = {
        ...JOB,
        profileConfig: { ...JOB.profileConfig, education: "off" },
      };
      await render_(STORED, noEducation);
      fireEvent.change(screen.getByLabelText(/^First name/), {
        target: { value: "Changed" },
      });

      await submitForm(user);
      await screen.findByText("Update your profile?");
      await user.click(
        screen.getByRole("button", { name: /update & submit/i }),
      );

      await waitFor(() =>
        expect(profileApi.updateMyProfile).toHaveBeenCalledTimes(1),
      );
      const payload = profileApi.updateMyProfile.mock.calls[0][0];
      expect(payload).not.toHaveProperty("education");
      expect(payload.user).toMatchObject({ firstName: "Changed" });
    });

    it("keeps the application when writing the profile fails", async () => {
      const user = userEvent.setup();
      await render_();
      profileApi.updateMyProfile.mockRejectedValue(new Error("boom"));
      fireEvent.change(screen.getByDisplayValue("Tsinghua University"), {
        target: { value: "Peking University" },
      });

      await submitForm(user);
      await screen.findByText("Update your profile?");
      await user.click(
        screen.getByRole("button", { name: /update & submit/i }),
      );

      await waitFor(() =>
        expect(toast.success).toHaveBeenCalledWith("Application submitted."),
      );
      expect(toast.warning).toHaveBeenCalledWith(
        "Application submitted, but saving to your profile failed.",
      );
    });

    it("keeps the application when the profile cannot be re-read", async () => {
      const user = userEvent.setup();
      await render_();
      fireEvent.change(screen.getByDisplayValue("Tsinghua University"), {
        target: { value: "Peking University" },
      });
      // The prefill already happened; this is the re-read write-back does.
      profileApi.getMyProfile.mockRejectedValue(new Error("boom"));

      await submitForm(user);
      await screen.findByText("Update your profile?");
      await user.click(
        screen.getByRole("button", { name: /update & submit/i }),
      );

      await waitFor(() =>
        expect(toast.warning).toHaveBeenCalledWith(
          "Application submitted, but saving to your profile failed.",
        ),
      );
      expect(profileApi.updateMyProfile).not.toHaveBeenCalled();
    });
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

    // The profile is read on every path now, so the form loads first.
    await screen.findByLabelText("Contact email");

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

    // The profile is read on every path now, so the form loads first.
    await screen.findByLabelText("Contact email");

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

    // The profile is read on every path now, so the form loads first.
    await screen.findByLabelText("Contact email");

    expect(
      await screen.findByText(/on file from your previous application/i),
    ).toBeInTheDocument();
    // Keep the test focused on the résumé fields, not profile write-back.

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

    // The profile is read on every path now, so the form loads first.
    await screen.findByLabelText("Contact email");

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

describe("ApplicationForm résumé requirement", () => {
  const RESUME_JOB = {
    ...JOB,
    profileConfig: { ...JOB.profileConfig, resume: "required" },
  };

  it("refuses to send an application with no résumé when the posting needs one", async () => {
    const user = userEvent.setup();
    render(<ApplicationForm job={RESUME_JOB} onSubmitted={vi.fn()} />);
    await screen.findByLabelText("Contact email");

    await user.click(screen.getByRole("button", { name: /submit/i }));

    expect(await screen.findByText("A résumé is required")).toBeInTheDocument();
    expect(api.submitApplication).not.toHaveBeenCalled();
  });

  it("sends when a résumé carried over from a previous application is on file", async () => {
    const user = userEvent.setup();
    api.updateApplication.mockResolvedValue({ data: { id: 7 } });
    const withResume = {
      ...FILLED_EXISTING,
      current: { ...FILLED_EXISTING.current, resumeObjectKey: "resumes/7.pdf" },
    };
    render(
      <ApplicationForm
        job={RESUME_JOB}
        existing={withResume}
        onSubmitted={vi.fn()}
      />,
    );
    await screen.findByLabelText("Contact email");

    await user.click(screen.getByRole("button", { name: /submit/i }));

    await waitFor(() => expect(api.updateApplication).toHaveBeenCalledTimes(1));
    expect(screen.queryByText("A résumé is required")).not.toBeInTheDocument();
  });
});

describe("ApplicationForm sections the posting does not collect", () => {
  const NO_SECTIONS_JOB = {
    ...JOB,
    profileConfig: { education: "off", workExperience: "off", resume: "off" },
  };

  it("sends no rows for a section the posting switched off", async () => {
    // The section is not rendered, so these rows -- carried over from an
    // earlier submission -- were never on this candidate's screen.
    const user = userEvent.setup();
    api.updateApplication.mockResolvedValue({ data: { id: 7 } });
    render(
      <ApplicationForm
        job={NO_SECTIONS_JOB}
        existing={FILLED_EXISTING}
        onSubmitted={vi.fn()}
      />,
    );
    await screen.findByLabelText("Contact email");

    await user.click(screen.getByRole("button", { name: /submit/i }));

    await waitFor(() => expect(api.updateApplication).toHaveBeenCalledTimes(1));
    const body = api.updateApplication.mock.calls[0][1];
    expect(body.education).toEqual([]);
    expect(body.experience).toEqual([]);
  });

  it("still sends the rows of a section it does collect", async () => {
    const user = userEvent.setup();
    api.updateApplication.mockResolvedValue({ data: { id: 7 } });
    // The form's rows come from the profile now, so that is where they live.
    profileApi.getMyProfile.mockResolvedValue({
      data: {
        profile: {
          user: { ...PROFILE_USER },
          education: [
            {
              id: 41,
              school: "Tsinghua University",
              degree: "Bachelor",
              fieldOfStudy: "Computer Science",
              startDate: "2018-09-01",
              endDate: "2022-06-01",
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
    render(
      <ApplicationForm
        job={JOB}
        existing={FILLED_EXISTING}
        onSubmitted={vi.fn()}
      />,
    );
    await screen.findByLabelText("Contact email");

    await user.click(screen.getByRole("button", { name: /submit/i }));

    await waitFor(() => expect(api.updateApplication).toHaveBeenCalledTimes(1));
    const body = api.updateApplication.mock.calls[0][1];
    expect(body.education).toHaveLength(1);
    expect(body.experience).toHaveLength(1);
  });
});

describe("ApplicationForm timezone default", () => {
  afterEach(() => vi.restoreAllMocks());

  /** Make the environment claim it is in `zone`, leaving formatting alone. */
  const inZone = (zone) => {
    const real = Intl.DateTimeFormat;
    vi.spyOn(Intl, "DateTimeFormat").mockImplementation((...args) =>
      args.length
        ? new real(...args)
        : { resolvedOptions: () => ({ timeZone: zone }) },
    );
  };

  it("submits the candidate's own zone when their profile has none", async () => {
    // Without this the candidate has to hunt through the picker for a value
    // the browser already knows, on a posting that may ask nothing else of
    // their profile at all.
    inZone("Asia/Shanghai");
    const user = userEvent.setup();
    api.submitApplication.mockResolvedValue({ data: { id: 100 } });
    profileApi.getMyProfile.mockResolvedValue({
      data: { profile: { user: { firstName: "Cand", lastName: "Idate" } } },
    });
    render(<ApplicationForm job={JOB} onSubmitted={vi.fn()} />);
    await screen.findByLabelText("Contact email");

    await user.click(screen.getByRole("button", { name: /submit/i }));

    await waitFor(() => expect(api.submitApplication).toHaveBeenCalledTimes(1));
    expect(api.submitApplication.mock.calls[0][0].personal.timezone).toBe(
      "Asia/Shanghai",
    );
  });

  it("treats a stored blank as no zone at all", async () => {
    // The users row defaults these to "" rather than leaving them null, so a
    // check for a missing key would sail straight past it.
    inZone("Asia/Shanghai");
    const user = userEvent.setup();
    api.submitApplication.mockResolvedValue({ data: { id: 100 } });
    profileApi.getMyProfile.mockResolvedValue({
      data: {
        profile: {
          user: { firstName: "Cand", lastName: "Idate", timezone: "" },
        },
      },
    });
    render(<ApplicationForm job={JOB} onSubmitted={vi.fn()} />);
    await screen.findByLabelText("Contact email");

    await user.click(screen.getByRole("button", { name: /submit/i }));

    await waitFor(() => expect(api.submitApplication).toHaveBeenCalledTimes(1));
    expect(api.submitApplication.mock.calls[0][0].personal.timezone).toBe(
      "Asia/Shanghai",
    );
  });

  it("leaves a stored zone alone", async () => {
    inZone("Asia/Shanghai");
    const user = userEvent.setup();
    api.submitApplication.mockResolvedValue({ data: { id: 100 } });
    profileApi.getMyProfile.mockResolvedValue({
      data: {
        profile: {
          user: {
            firstName: "Cand",
            lastName: "Idate",
            timezone: "America/New_York",
          },
        },
      },
    });
    render(<ApplicationForm job={JOB} onSubmitted={vi.fn()} />);
    await screen.findByLabelText("Contact email");

    await user.click(screen.getByRole("button", { name: /submit/i }));

    await waitFor(() => expect(api.submitApplication).toHaveBeenCalledTimes(1));
    expect(api.submitApplication.mock.calls[0][0].personal.timezone).toBe(
      "America/New_York",
    );
  });
});

describe("ApplicationForm where the profile block comes from", () => {
  // The invariant: a snapshot is for reading, the profile is for filling. The
  // form's profile block therefore always starts from the profile, whatever
  // an earlier submission happened to say -- otherwise a candidate who has
  // since tidied their profile would reapply with stale rows, and the sync
  // they are about to be offered would push those stale rows back.
  const STORED_PROFILE = {
    user: { ...PROFILE_USER },
    education: [
      {
        id: 41,
        school: "Tsinghua University",
        degree: "BSc",
        fieldOfStudy: "Computer Science",
        startDate: "2018-09-01",
        endDate: "2022-06-01",
      },
    ],
    workHistory: [],
  };

  it("reads the profile even when editing an application that says otherwise", async () => {
    // The stored application has MIT; the profile has Tsinghua. The profile
    // wins, while the answers still come from the application.
    profileApi.getMyProfile.mockResolvedValue({
      data: { profile: STORED_PROFILE },
    });
    render(
      <ApplicationForm
        job={JOB}
        existing={FILLED_EXISTING}
        onSubmitted={vi.fn()}
      />,
    );

    // The profile is read on every path now, so the form loads first.
    await screen.findByLabelText("Contact email");

    expect(
      await screen.findByDisplayValue("Tsinghua University"),
    ).toBeInTheDocument();
    expect(screen.queryByDisplayValue("MIT")).not.toBeInTheDocument();
  });

  it("falls back to the last submission for a block the profile has nothing for", async () => {
    // Applied before, declined to save it, now applying again: rather than a
    // blank form, start from what they already sent once.
    profileApi.getMyProfile.mockResolvedValue({
      data: {
        profile: { user: { ...PROFILE_USER }, education: [], workHistory: [] },
      },
    });
    api.getMyLatestProfile.mockResolvedValue({
      data: {
        personal: PROFILE_USER,
        education: [
          {
            id: "rpf-9",
            institution: "Peking University",
            degree: "MSc",
            field: "Statistics",
            startMonth: "September",
            startYear: "2022",
            endMonth: "June",
            endYear: "2024",
          },
        ],
        experience: [],
      },
    });

    render(<ApplicationForm job={JOB} onSubmitted={vi.fn()} />);

    // The profile is read on every path now, so the form loads first.
    await screen.findByLabelText("Contact email");

    expect(
      await screen.findByDisplayValue("Peking University"),
    ).toBeInTheDocument();
  });

  it("leaves a block empty when neither the profile nor any submission has one", async () => {
    profileApi.getMyProfile.mockResolvedValue({
      data: {
        profile: { user: { ...PROFILE_USER }, education: [], workHistory: [] },
      },
    });
    api.getMyLatestProfile.mockResolvedValue({
      data: { personal: {}, education: [], experience: [] },
    });

    render(<ApplicationForm job={JOB} onSubmitted={vi.fn()} />);
    await screen.findByLabelText("Contact email");

    expect(
      screen.queryByDisplayValue("Peking University"),
    ).not.toBeInTheDocument();
  });

  it("still takes the answers from the application being edited", async () => {
    profileApi.getMyProfile.mockResolvedValue({
      data: { profile: STORED_PROFILE },
    });
    const withAnswer = {
      ...FILLED_EXISTING,
      current: {
        ...FILLED_EXISTING.current,
        submission: {
          ...FILLED_EXISTING.current.submission,
          answers: { q1: "kept" },
        },
      },
    };
    const answeredJob = {
      ...JOB,
      formSchema: {
        questions: [{ id: "q1", type: "short_text", label: "Why us?" }],
      },
    };

    render(
      <ApplicationForm
        job={answeredJob}
        existing={withAnswer}
        onSubmitted={vi.fn()}
      />,
    );

    expect(await screen.findByDisplayValue("kept")).toBeInTheDocument();
  });
});
