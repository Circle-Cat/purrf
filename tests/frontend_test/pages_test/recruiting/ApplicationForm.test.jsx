import {
  describe,
  it,
  expect,
  vi,
  beforeEach,
  afterEach,
  onTestFinished,
} from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
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
  api.getMyApplicationDraft.mockResolvedValue({ data: null });
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

const SEND_BUTTON = /submit application/i;

/** The confirmation dialog's own Submit button, on a new application. */
const CONFIRM_BUTTON = /^submit$/i;

/**
 * Press the send button, then confirm. A form that fails validation never
 * asks, so there is nothing to confirm then.
 */
const clickSend = async (user) => {
  await user.click(screen.getByRole("button", { name: SEND_BUTTON }));
  const confirm = screen.queryByRole("button", { name: CONFIRM_BUTTON });
  if (confirm) await user.click(confirm);
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

    await clickSend(user);
    expect(api.submitApplication).toHaveBeenCalledTimes(1);
    expect(api.submitApplication.mock.calls[0][0]).toMatchObject({
      jobId: 5,
    });
    expect(onSubmitted).toHaveBeenCalled();
  });

  describe("answers a changed gate no longer shows", () => {
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

    /** An earlier submission holding an answer to the gated q2. */
    const SEED_WITH_GATED_ANSWER = {
      submission: {
        personal: REQUIRED_PERSONAL,
        education: [],
        experience: [],
        answers: { q1: "Yes", q2: "F-1 OPT" },
      },
    };

    it("submits straight away when the save costs nothing", async () => {
      const user = userEvent.setup();
      api.submitApplication.mockResolvedValue({ data: { id: 100 } });
      render(<ApplicationForm job={GATED_JOB} onSubmitted={vi.fn()} />);
      await screen.findByLabelText("Contact email");

      await clickSend(user);

      expect(api.submitApplication).toHaveBeenCalledTimes(1);
      expect(
        screen.queryByText("Some answers will be removed"),
      ).not.toBeInTheDocument();
    });

    it("submits what is on screen without asking about answers it drops", async () => {
      // The candidate wrote a visa type, then said they need no sponsorship.
      // The server keeps only what the form is showing, so that text is gone
      // the moment this is sent -- but the candidate is not asked: a question
      // they cannot see is not one to make them approve deleting.
      const user = userEvent.setup();
      api.submitApplication.mockResolvedValue({ data: { id: 100 } });
      const onSubmitted = vi.fn();
      render(
        <ApplicationForm
          job={GATED_JOB}
          seed={SEED_WITH_GATED_ANSWER}
          seedApplicationId={7}
          onSubmitted={onSubmitted}
        />,
      );
      await screen.findByLabelText("Contact email");
      await user.click(screen.getByRole("radio", { name: "No" }));

      await clickSend(user);

      expect(
        screen.queryByText("Some answers will be removed"),
      ).not.toBeInTheDocument();
      await waitFor(() =>
        expect(api.submitApplication).toHaveBeenCalledTimes(1),
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

      await clickSend(user);

      expect(
        await screen.findByText("This question is required"),
      ).toBeInTheDocument();
      expect(api.submitApplication).not.toHaveBeenCalled();
    });

    it("clears the error as soon as the field is filled in", async () => {
      const user = userEvent.setup();
      render(<ApplicationForm job={REQUIRED_JOB} onSubmitted={vi.fn()} />);
      await screen.findByLabelText("Contact email");
      await clickSend(user);
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

      await clickSend(user);

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
          screen.getByRole("button", { name: SEND_BUTTON }),
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

      await clickSend(user);

      await waitFor(() => expect(onSubmitted).toHaveBeenCalled());
      expect(toast.error).not.toHaveBeenCalled();
    });

    it("still surfaces any other failure as an error", async () => {
      const user = userEvent.setup();
      api.submitApplication.mockRejectedValue(new Error("boom"));
      const onSubmitted = vi.fn();
      render(<ApplicationForm job={JOB} onSubmitted={onSubmitted} />);
      await screen.findByLabelText("Contact email");

      await clickSend(user);

      await waitFor(() => expect(toast.error).toHaveBeenCalledWith("boom"));
      expect(onSubmitted).not.toHaveBeenCalled();
    });
  });

  it("renders exactly one Contact email field", async () => {
    render(<ApplicationForm job={JOB} onSubmitted={vi.fn()} />);
    expect(await screen.findAllByLabelText("Contact email")).toHaveLength(1);
  });

  it("prefills from `seed` and submits it as a new application", async () => {
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

    await clickSend(user);

    expect(api.submitApplication).toHaveBeenCalledTimes(1);
    expect(api.submitApplication.mock.calls[0][0]).toMatchObject({
      jobId: 5,
      // From the profile: `seed` prefills the answers, not the person.
      personal: { ...REQUIRED_PERSONAL },
    });
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
      screen.queryByRole("button", { name: SEND_BUTTON }),
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
        screen.getByRole("button", { name: SEND_BUTTON }),
      ).toBeInTheDocument(),
    );
    await clickSend(user);

    expect(api.submitApplication.mock.calls[0][0]).toMatchObject({
      personal: { ...REQUIRED_PERSONAL, firstName: "Ann", lastName: "Liu" },
    });
  });

  it("reads the profile on the reapply path too", async () => {
    // The snapshot is for reading, the profile is for filling.
    render(
      <ApplicationForm
        job={JOB}
        seed={FILLED_EXISTING.current}
        onSubmitted={vi.fn()}
      />,
    );

    await screen.findByLabelText("Contact email");
    expect(profileApi.getMyProfile).toHaveBeenCalledTimes(1);
  });

  it("asks for the required fields when the profile prefill fetch fails", async () => {
    // The prefill is a convenience, so a failure must not wedge the form --
    // but the fields it would have filled are required of everyone, so what
    // the candidate gets is a form that tells them what is missing rather
    // than one that submits an empty personal block.
    // A zone no listed entry shares an offset with, so the browser default
    // leaves the timezone empty whatever zone and date the runner is on.
    const real = Intl.DateTimeFormat;
    const zoneSpy = vi
      .spyOn(Intl, "DateTimeFormat")
      .mockImplementation((...args) =>
        args.length
          ? new real(...args)
          : { resolvedOptions: () => ({ timeZone: "Pacific/Chatham" }) },
      );
    onTestFinished(() => zoneSpy.mockRestore());
    const user = userEvent.setup();
    profileApi.getMyProfile.mockRejectedValue(new Error("boom"));
    api.submitApplication.mockResolvedValue({ data: { id: 100 } });
    const onSubmitted = vi.fn();
    render(<ApplicationForm job={JOB} onSubmitted={onSubmitted} />);

    // The profile is read on every path now, so the form loads first.
    await screen.findByLabelText("Contact email");

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: SEND_BUTTON }),
      ).toBeInTheDocument(),
    );
    await clickSend(user);

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

    const button = await screen.findByRole("button", { name: SEND_BUTTON });
    await clickSend(user);
    await user.click(button);

    expect(api.submitApplication).toHaveBeenCalledTimes(1);
    resolveSubmit({ data: { id: 1 } });
    await waitFor(() => expect(button).not.toBeDisabled());
  });

  // The rows come from the profile, so a difference can only be something the
  // candidate did here. The save-to-profile box is ticked by default.
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
      api.submitApplication.mockResolvedValue({ data: { id: 7 } });
      render(<ApplicationForm job={job} onSubmitted={vi.fn()} />);
      await screen.findByLabelText("Contact email");
    };

    const submitForm = async (user) => clickSend(user);

    it("writes nothing when the candidate changed nothing", async () => {
      const user = userEvent.setup();
      await render_();

      await submitForm(user);

      await waitFor(() => expect(api.submitApplication).toHaveBeenCalled());
      expect(profileApi.updateMyProfile).not.toHaveBeenCalled();
    });

    it("replaces the edited block", async () => {
      const user = userEvent.setup();
      await render_();
      fireEvent.change(screen.getByDisplayValue("Tsinghua University"), {
        target: { value: "Peking University" },
      });

      await submitForm(user);

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

    await clickSend(user);
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
    await screen.findByRole("button", { name: SEND_BUTTON });
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

    await clickSend(user);
    expect(api.submitApplication.mock.calls[0][0]).toMatchObject({
      resumeSha256: null,
      resumeObjectKey: null,
    });
  });

  it("hides the résumé-on-file banner once a fresh file replaces the carried-forward résumé", async () => {
    api.resumeUrl.mockImplementation((id) => `/resume/${id}`);
    api.uploadResume.mockResolvedValue({
      data: { sha256: "new123", objectKey: "resumes/new123.pdf" },
    });
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

    await clickSend(user);

    expect(await screen.findByText("A résumé is required")).toBeInTheDocument();
    expect(api.submitApplication).not.toHaveBeenCalled();
  });

  it("sends when a résumé carried over from a previous application is on file", async () => {
    const user = userEvent.setup();
    api.submitApplication.mockResolvedValue({ data: { id: 101 } });
    const seedWithResume = {
      ...FILLED_EXISTING.current,
      resumeObjectKey: "resumes/7.pdf",
    };
    render(
      <ApplicationForm
        job={RESUME_JOB}
        seed={seedWithResume}
        seedApplicationId={7}
        onSubmitted={vi.fn()}
      />,
    );
    await screen.findByLabelText("Contact email");

    await clickSend(user);

    await waitFor(() => expect(api.submitApplication).toHaveBeenCalledTimes(1));
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
    api.submitApplication.mockResolvedValue({ data: { id: 101 } });
    render(
      <ApplicationForm
        job={NO_SECTIONS_JOB}
        seed={FILLED_EXISTING.current}
        seedApplicationId={7}
        onSubmitted={vi.fn()}
      />,
    );
    await screen.findByLabelText("Contact email");

    await clickSend(user);

    await waitFor(() => expect(api.submitApplication).toHaveBeenCalledTimes(1));
    const body = api.submitApplication.mock.calls[0][0];
    expect(body.education).toEqual([]);
    expect(body.experience).toEqual([]);
  });

  it("still sends the rows of a section it does collect", async () => {
    const user = userEvent.setup();
    api.submitApplication.mockResolvedValue({ data: { id: 101 } });
    // The form's rows come from the profile, so that is where they live.
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
    render(<ApplicationForm job={JOB} onSubmitted={vi.fn()} />);
    await screen.findByLabelText("Contact email");

    await clickSend(user);

    await waitFor(() => expect(api.submitApplication).toHaveBeenCalledTimes(1));
    const body = api.submitApplication.mock.calls[0][0];
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

    await clickSend(user);

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

    await clickSend(user);

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

    await clickSend(user);

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

  it("reads the profile even when reapplying from a submission that says otherwise", async () => {
    // The earlier submission has MIT; the profile has Tsinghua. The profile
    // wins, while the answers still come from the submission.
    profileApi.getMyProfile.mockResolvedValue({
      data: { profile: STORED_PROFILE },
    });
    render(
      <ApplicationForm
        job={JOB}
        seed={FILLED_EXISTING.current}
        seedApplicationId={7}
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

  it("still takes the answers from the submission it reapplies from", async () => {
    profileApi.getMyProfile.mockResolvedValue({
      data: { profile: STORED_PROFILE },
    });
    const withAnswer = {
      ...FILLED_EXISTING.current,
      submission: {
        ...FILLED_EXISTING.current.submission,
        answers: { q1: "kept" },
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
        seed={withAnswer}
        seedApplicationId={7}
        onSubmitted={vi.fn()}
      />,
    );

    expect(await screen.findByDisplayValue("kept")).toBeInTheDocument();
  });
});

describe("ApplicationForm after a new mentorship application", () => {
  const MENTEE_JOB = { ...JOB, id: 41, mentorshipRole: "mentee" };

  // An earlier block restores every spy, the module-level toast ones too.
  beforeEach(() => {
    vi.spyOn(toast, "success").mockImplementation(() => {});
  });

  /** The form on its apply route, beside the dashboard it can lead to. */
  const renderOnRoute = (props) => {
    const router = createMemoryRouter(
      [
        {
          path: "/recruiting/jobs/:jobId/apply",
          element: <ApplicationForm {...props} />,
        },
        { path: "/dashboard/me", element: <p>Dashboard page</p> },
      ],
      { initialEntries: ["/recruiting/jobs/41/apply"] },
    );
    return render(<RouterProvider router={router} />);
  };

  const submit = async (user) => {
    await screen.findByLabelText("Contact email");
    await clickSend(user);
  };

  it("explains what comes next instead of moving straight on", async () => {
    const user = userEvent.setup();
    api.submitApplication.mockResolvedValue({ data: { id: 300 } });
    const onSubmitted = vi.fn();
    const onViewApplication = vi.fn();
    renderOnRoute({
      job: MENTEE_JOB,
      onSubmitted,
      onViewApplication,
    });

    await submit(user);

    expect(
      await screen.findByRole("dialog", { name: "Application submitted" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Applying is the first step. Here's what comes next:"),
    ).toBeInTheDocument();
    expect(screen.getByText("Get admitted")).toBeInTheDocument();
    expect(screen.getByText("Register for a round")).toBeInTheDocument();
    expect(onSubmitted).not.toHaveBeenCalled();
    // The dialog's title already says it; a toast would say it twice.
    expect(toast.success).not.toHaveBeenCalled();
  });

  it("leads to the application through onViewApplication", async () => {
    const user = userEvent.setup();
    api.submitApplication.mockResolvedValue({ data: { id: 301 } });
    const onSubmitted = vi.fn();
    const onViewApplication = vi.fn();
    renderOnRoute({ job: MENTEE_JOB, onSubmitted, onViewApplication });

    await submit(user);
    await user.click(
      await screen.findByRole("button", { name: "View my application" }),
    );

    expect(onViewApplication).toHaveBeenCalledTimes(1);
    expect(onSubmitted).not.toHaveBeenCalled();
  });

  it("falls back to onSubmitted with the new application when there is no onViewApplication", async () => {
    const user = userEvent.setup();
    api.submitApplication.mockResolvedValue({ data: { id: 302 } });
    const onSubmitted = vi.fn();
    renderOnRoute({ job: MENTEE_JOB, onSubmitted });

    await submit(user);
    await user.click(
      await screen.findByRole("button", { name: "View my application" }),
    );

    expect(onSubmitted).toHaveBeenCalledWith({ id: 302 });
  });

  it("treats dismissing the dialog as viewing the application", async () => {
    const user = userEvent.setup();
    api.submitApplication.mockResolvedValue({ data: { id: 303 } });
    const onViewApplication = vi.fn();
    renderOnRoute({
      job: MENTEE_JOB,
      onSubmitted: vi.fn(),
      onViewApplication,
    });

    await submit(user);
    await screen.findByRole("dialog", { name: "Application submitted" });
    await user.keyboard("{Escape}");

    expect(onViewApplication).toHaveBeenCalledTimes(1);
  });

  it("goes to the Personal Dashboard from the dialog", async () => {
    const user = userEvent.setup();
    api.submitApplication.mockResolvedValue({ data: { id: 304 } });
    const onSubmitted = vi.fn();
    const onViewApplication = vi.fn();
    renderOnRoute({ job: MENTEE_JOB, onSubmitted, onViewApplication });

    await submit(user);
    await user.click(
      await screen.findByRole("button", { name: "Go to Personal Dashboard" }),
    );

    expect(await screen.findByText("Dashboard page")).toBeInTheDocument();
    expect(onViewApplication).not.toHaveBeenCalled();
  });

  it("also explains it on a reapply, which is a new application too", async () => {
    const user = userEvent.setup();
    api.submitApplication.mockResolvedValue({ data: { id: 305 } });
    const onSubmitted = vi.fn();
    renderOnRoute({
      job: MENTEE_JOB,
      seed: FILLED_EXISTING.current,
      seedApplicationId: 7,
      onSubmitted,
    });

    await submit(user);

    expect(
      await screen.findByRole("dialog", { name: "Application submitted" }),
    ).toBeInTheDocument();
    expect(onSubmitted).not.toHaveBeenCalled();
  });

  it("moves straight on for an employment posting", async () => {
    const user = userEvent.setup();
    api.submitApplication.mockResolvedValue({ data: { id: 306 } });
    const onSubmitted = vi.fn();
    renderOnRoute({
      job: { ...JOB, id: 42, kind: "employment", mentorshipRole: null },
      onSubmitted,
      onViewApplication: vi.fn(),
    });

    await submit(user);

    await waitFor(() => expect(onSubmitted).toHaveBeenCalledWith({ id: 306 }));
    expect(toast.success).toHaveBeenCalledWith("Application submitted.");
    expect(
      screen.queryByRole("dialog", { name: "Application submitted" }),
    ).not.toBeInTheDocument();
  });

  it("moves straight on for an activity posting with no mentorship role", async () => {
    const user = userEvent.setup();
    api.submitApplication.mockResolvedValue({ data: { id: 307 } });
    const onSubmitted = vi.fn();
    renderOnRoute({
      job: { ...JOB, id: 43, mentorshipRole: null },
      onSubmitted,
      onViewApplication: vi.fn(),
    });

    await submit(user);

    await waitFor(() => expect(onSubmitted).toHaveBeenCalledWith({ id: 307 }));
    expect(
      screen.queryByRole("dialog", { name: "Application submitted" }),
    ).not.toBeInTheDocument();
  });
});

describe("ApplicationForm drafts on a new application", () => {
  /** A posting with one required question, so validation has something to say. */
  const QUESTION_JOB = {
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

  /** A saved draft whose every field differs from the profile's. */
  const DRAFT = {
    jobId: 5,
    personal: {
      firstName: "Dora",
      lastName: "Drafton",
      timezone: "Europe/Paris",
    },
    education: [
      {
        id: "rpf-9",
        institution: "Draft University",
        degree: "Master",
        field: "Math",
        startMonth: "October",
        startYear: "2019",
        endMonth: "June",
        endYear: "2021",
      },
    ],
    experience: [],
    answers: { q1: "Lisbon" },
    resumeSha256: "draft-sha",
    resumeObjectKey: "resumes/draft-key.pdf",
    updatedAt: "2026-11-17T08:00:00Z",
  };

  beforeEach(() => {
    vi.spyOn(toast, "success").mockImplementation(() => {});
    vi.spyOn(toast, "error").mockImplementation(() => {});
    vi.spyOn(toast, "warning").mockImplementation(() => {});
    profileApi.getMyProfile.mockResolvedValue({
      data: { profile: { user: PROFILE_USER } },
    });
    profileApi.updateMyProfile.mockResolvedValue({ data: {} });
    api.getMyLatestProfile.mockResolvedValue({
      data: { personal: {}, education: [], experience: [] },
    });
    api.getMyApplicationDraft.mockResolvedValue({ data: null });
    api.saveApplicationDraft.mockResolvedValue({ data: DRAFT });
    api.submitApplication.mockResolvedValue({ data: { id: 100 } });
  });

  const renderForm = async (props = {}) => {
    render(
      <ApplicationForm job={QUESTION_JOB} onSubmitted={vi.fn()} {...props} />,
    );
    await screen.findByLabelText("Contact email");
  };

  const fillQuestion = () =>
    fireEvent.change(screen.getByLabelText("Where are you based?"), {
      target: { value: "Taipei" },
    });

  it("fills the form from a saved draft rather than the profile", async () => {
    const user = userEvent.setup();
    api.getMyApplicationDraft.mockResolvedValue({ data: DRAFT });
    await renderForm();

    expect(api.getMyApplicationDraft).toHaveBeenCalledWith(5);
    expect(screen.getByLabelText(/^First name/)).toHaveValue("Dora");
    expect(screen.getByDisplayValue("Draft University")).toBeInTheDocument();
    expect(screen.getByLabelText("Where are you based?")).toHaveValue("Lisbon");
    expect(
      screen.getByText(/Résumé attached to your saved draft/),
    ).toBeInTheDocument();

    await clickSend(user);

    await waitFor(() => expect(api.submitApplication).toHaveBeenCalled());
    expect(api.submitApplication.mock.calls[0][0]).toMatchObject({
      jobId: 5,
      personal: DRAFT.personal,
      answers: { q1: "Lisbon" },
      resumeSha256: "draft-sha",
      resumeObjectKey: "resumes/draft-key.pdf",
    });
  });

  it("falls back to the profile when the draft cannot be read", async () => {
    api.getMyApplicationDraft.mockRejectedValue(new Error("draft down"));
    await renderForm();

    expect(screen.getByLabelText(/^First name/)).toHaveValue("Cand");
    expect(screen.getByLabelText("Where are you based?")).toHaveValue("");
    expect(
      screen.queryByText(/Résumé attached to your saved draft/),
    ).not.toBeInTheDocument();
    expect(toast.error).not.toHaveBeenCalled();
  });

  it("saves a draft of what is on screen without checking it", async () => {
    const user = userEvent.setup();
    await renderForm();

    await user.click(screen.getByRole("button", { name: "Save draft" }));

    await waitFor(() =>
      expect(api.saveApplicationDraft).toHaveBeenCalledTimes(1),
    );
    expect(api.saveApplicationDraft.mock.calls[0][0]).toEqual({
      jobId: 5,
      personal: expect.objectContaining(REQUIRED_PERSONAL),
      education: [],
      experience: [],
      answers: {},
      resumeSha256: null,
      resumeObjectKey: null,
    });
    expect(toast.success).toHaveBeenCalledWith("Draft saved.");
    expect(
      screen.queryByText("This question is required"),
    ).not.toBeInTheDocument();
    expect(api.submitApplication).not.toHaveBeenCalled();
  });

  it("says why a draft could not be saved", async () => {
    const user = userEvent.setup();
    api.saveApplicationDraft.mockRejectedValue(
      new Error("This posting is no longer accepting applications"),
    );
    await renderForm();

    await user.click(screen.getByRole("button", { name: "Save draft" }));

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith(
        "This posting is no longer accepting applications",
      ),
    );
    expect(toast.success).not.toHaveBeenCalled();
  });

  it("offers to save to the profile, ticked by default", async () => {
    await renderForm();
    expect(
      screen.getByRole("checkbox", {
        name: "Also save these changes to my profile",
      }),
    ).toBeChecked();
    expect(
      screen.getByText(
        "Your profile will be updated with what you entered here.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Only you can see a draft. You can't change your application after you submit it.",
      ),
    ).toBeInTheDocument();
  });

  it("asks for confirmation only once the form is valid", async () => {
    const user = userEvent.setup();
    await renderForm();

    await user.click(
      screen.getByRole("button", { name: "Submit application" }),
    );
    expect(
      await screen.findByText("This question is required"),
    ).toBeInTheDocument();
    expect(
      screen.queryByText("Submit your application?"),
    ).not.toBeInTheDocument();

    fillQuestion();
    await user.click(
      screen.getByRole("button", { name: "Submit application" }),
    );

    expect(
      await screen.findByText("Submit your application?"),
    ).toBeInTheDocument();
    expect(api.submitApplication).not.toHaveBeenCalled();
  });

  it("sends nothing when the candidate keeps editing", async () => {
    const user = userEvent.setup();
    await renderForm();
    fillQuestion();

    await user.click(
      screen.getByRole("button", { name: "Submit application" }),
    );
    await user.click(
      await screen.findByRole("button", { name: "Keep editing" }),
    );

    await waitFor(() =>
      expect(
        screen.queryByText("Submit your application?"),
      ).not.toBeInTheDocument(),
    );
    expect(api.submitApplication).not.toHaveBeenCalled();
  });

  it("saves to the profile when the box stays ticked", async () => {
    const user = userEvent.setup();
    await renderForm();
    fillQuestion();

    await clickSend(user);

    await waitFor(() => expect(api.submitApplication).toHaveBeenCalled());
    expect(api.submitApplication.mock.calls[0][0]).toMatchObject({
      saveToProfile: true,
      answers: { q1: "Taipei" },
    });
  });

  it("leaves the profile alone when the box is unticked", async () => {
    const user = userEvent.setup();
    await renderForm();
    fillQuestion();
    await user.click(
      screen.getByRole("checkbox", {
        name: "Also save these changes to my profile",
      }),
    );

    await clickSend(user);

    await waitFor(() => expect(api.submitApplication).toHaveBeenCalled());
    expect(api.submitApplication.mock.calls[0][0]).toMatchObject({
      saveToProfile: false,
    });
    expect(profileApi.updateMyProfile).not.toHaveBeenCalled();
  });
});
