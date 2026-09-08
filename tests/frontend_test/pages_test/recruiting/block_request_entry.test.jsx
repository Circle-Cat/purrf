import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { toast } from "sonner";
import ApplicationDetailPage from "@/pages/Recruiting/applications/ApplicationDetailPage";
import * as api from "@/api/recruitingApi";
import * as adminApi from "@/api/adminAccountsApi";

vi.mock("@/api/recruitingApi");
vi.mock("@/api/adminAccountsApi");
// Bazel-sandbox module resolution: `vi.mock("sonner", factory)` doesn't
// intercept the module the component resolved at import time. Spy on the
// real toast instead, matching the rest of the recruiting page tests.
vi.spyOn(toast, "error").mockImplementation(() => {});
vi.spyOn(toast, "success").mockImplementation(() => {});

const authState = vi.hoisted(() => ({ userId: 500, permissions: [] }));
vi.mock("@/context/auth/AuthContext", () => ({
  useAuth: () => ({
    user: { userId: authState.userId },
    permissions: authState.permissions,
  }),
}));

const OWNER_ID = 500;
const ASSIGNEE_ID = 10;
const APPLICANT_ID = 5;

const ADVANCE = "recruiting.application.advance";
const EVALUATE = "recruiting.interview.evaluate";

const JOB = {
  id: 1,
  title: "Mentor",
  kind: "employment",
  pipelineConfig: {
    ownerIds: [OWNER_ID],
    stages: [
      { stage: "recruiter_screening", rounds: 1 },
      { stage: "behavioral", rounds: 1 },
    ],
  },
};

/**
 * The `user.admin` holders the reviewer pickers choose from. The owner is in
 * the list on purpose: the request dialog has to drop them (nobody reviews
 * their own request) while the reassign dialog has to keep them (they are not
 * the reviewer who currently holds it).
 */
const HOLDERS = [
  { userId: 77, name: "Rita Reviewer" },
  { userId: 88, name: "Sam Steward" },
  { userId: OWNER_ID, name: "Olive Owner" },
];

/** A BlockRequestDto as the create/reassign endpoints return it. */
const requestDto = (reviewerId, reviewerName) => ({
  id: 42,
  userId: APPLICANT_ID,
  reviewerId,
  reviewerName,
  status: "pending",
});

const makeDetail = () => ({
  application: {
    id: 101,
    jobId: 1,
    userId: APPLICANT_ID,
    stage: "recruiter_screening",
    subStatus: "pending",
    tags: null,
    currentRound: 1,
    current: {
      version: 1,
      isFrozen: false,
      submission: {
        personal: { firstName: "Alice", lastName: "Smith" },
        education: [],
        experience: [],
        answers: {},
      },
    },
    editable: false,
  },
  applicantName: "Alice Smith",
  applicantEmail: "alice@example.com",
  resumeAvailable: false,
  formSchema: { questions: [] },
  isOwner: true,
  canView: true,
  assigneeId: ASSIGNEE_ID,
  interview: null,
  viewerTimezone: "America/Los_Angeles",
});

beforeEach(() => {
  vi.clearAllMocks();
  authState.userId = OWNER_ID;
  authState.permissions = [ADVANCE];
  api.resumeUrl.mockImplementation(
    (id) => `/api/recruiting/applications/${id}/resume`,
  );
  api.getApplicationDetail.mockResolvedValue({ data: makeDetail() });
  api.getJob.mockResolvedValue({ data: JOB });
  api.listInterviewPool.mockResolvedValue({ data: [] });
  api.getEvaluationsForApplication.mockResolvedValue({ data: [] });
  api.getApplicationActivity.mockResolvedValue({ data: [] });
  api.getApplicationComments.mockResolvedValue({ data: [] });
  api.getMentionableUsers.mockResolvedValue({ data: [] });
  api.getOtherApplications.mockResolvedValue({
    data: { otherJobs: [], previousSameJob: [] },
  });
  api.getApplicationEmails.mockResolvedValue({
    data: { threads: [], defaultTo: null },
  });
  api.getApplicationEmailTemplates.mockResolvedValue({
    data: { templates: [], signatureHtml: "" },
  });
  adminApi.getBlockPreflight.mockResolvedValue({
    data: { applicationCount: 2, interviewTimes: [] },
  });
  adminApi.getUserAdmins.mockResolvedValue({ data: HOLDERS });
  adminApi.createBlockRequest.mockResolvedValue({
    data: requestDto(77, "Rita Reviewer"),
  });
  adminApi.reassignBlockRequest.mockResolvedValue({
    data: requestDto(88, "Sam Steward"),
  });
});

const renderPage = () => {
  const router = createMemoryRouter(
    [
      {
        path: "/recruiting/applications/:applicationId",
        element: <ApplicationDetailPage />,
      },
    ],
    { initialEntries: ["/recruiting/applications/101"] },
  );
  return render(<RouterProvider router={router} />);
};

const waitLoaded = () =>
  waitFor(() =>
    expect(screen.getByText("alice@example.com")).toBeInTheDocument(),
  );

/**
 * The Operate row's block-request confirmation. Scoped lookups matter here:
 * the application's own stage Reassign button is on the same row and carries
 * the same label.
 */
const requestRow = () => screen.findByText(/^Block requested — sent to /);

/** Open the dialog, fill it in, and send the request. */
const raiseRequest = async (user, reviewerValue = "77") => {
  await user.click(screen.getByRole("button", { name: "Request block" }));
  await screen.findByRole("heading", { name: /Request a block/ });
  await user.selectOptions(screen.getByLabelText("Reviewer"), reviewerValue);
  await user.type(screen.getByLabelText(/^Reason/), "repeated no-shows");
  await user.click(screen.getByRole("button", { name: "Send request" }));
};

describe("Request block — permission gate", () => {
  it("disables the button, rather than hiding it, without the advance grant", async () => {
    const user = userEvent.setup();
    authState.permissions = [];
    renderPage();
    await waitLoaded();

    const button = screen.getByRole("button", { name: "Request block" });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute(
      "title",
      "Requires the recruiting advance permission",
    );

    await user.click(button);
    expect(adminApi.getBlockPreflight).not.toHaveBeenCalled();
    expect(
      screen.queryByRole("heading", { name: /Request a block/ }),
    ).not.toBeInTheDocument();
  });

  it("enables the button on the advance grant alone", async () => {
    authState.permissions = [ADVANCE];
    renderPage();
    await waitLoaded();

    expect(screen.getByRole("button", { name: "Request block" })).toBeEnabled();
  });

  it("does not enable the button on the evaluate grant alone", async () => {
    // Being eligible for the interviewer pool is not standing to sanction
    // someone: the evaluate grant only marks eligibility to be assigned, and
    // a row-level assignee check is what says who is actually on a case. The
    // backend raise gate excludes it for the same reason.
    authState.permissions = [EVALUATE];
    renderPage();
    await waitLoaded();

    expect(
      screen.getByRole("button", { name: "Request block" }),
    ).toBeDisabled();
  });

  it("shows no Operate row at all to a non-owner who can only read", async () => {
    authState.userId = 42;
    authState.permissions = [ADVANCE, EVALUATE];
    api.getApplicationDetail.mockResolvedValue({
      data: { ...makeDetail(), isOwner: false, canView: true },
    });
    renderPage();
    await waitLoaded();

    expect(screen.queryByText("Operate:")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Request block" }),
    ).not.toBeInTheDocument();
  });
});

describe("Request block — opening the dialog", () => {
  it("reads the pre-flight for the applicant and the reviewer list on click", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitLoaded();

    expect(adminApi.getBlockPreflight).not.toHaveBeenCalled();
    expect(adminApi.getUserAdmins).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "Request block" }));

    // Scoped to the candidate, not to the application being viewed: a block
    // is org-wide, so it sweeps their other postings too.
    await waitFor(() =>
      expect(adminApi.getBlockPreflight).toHaveBeenCalledWith(APPLICANT_ID),
    );
    expect(adminApi.getUserAdmins).toHaveBeenCalled();
    expect(
      await screen.findByRole("heading", { name: /Request a block/ }),
    ).toBeInTheDocument();
    expect(
      await screen.findByText(/Tag 2 affected applications/),
    ).toBeInTheDocument();
  });

  it("leaves the raiser out of the reviewer options", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitLoaded();

    await user.click(screen.getByRole("button", { name: "Request block" }));

    const select = await screen.findByLabelText("Reviewer");
    const names = within(select)
      .getAllByRole("option")
      .map((o) => o.textContent);
    expect(names).toContain("Rita Reviewer");
    expect(names).toContain("Sam Steward");
    expect(names).not.toContain("Olive Owner");
  });
});

describe("Request block — sending the request", () => {
  it("tags the request with the page it was raised from", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitLoaded();

    await raiseRequest(user);

    await waitFor(() =>
      expect(adminApi.createBlockRequest).toHaveBeenCalledWith(
        { userId: APPLICANT_ID, reason: "repeated no-shows", reviewerId: 77 },
        "recruiting_application",
      ),
    );
    expect(toast.success).toHaveBeenCalledWith(
      "Block requested — sent to Rita Reviewer.",
    );
  });

  it("closes the dialog and names the reviewer on the Operate row", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitLoaded();

    await raiseRequest(user);

    const row = await requestRow();
    expect(row).toHaveTextContent("Block requested — sent to Rita Reviewer");
    expect(within(row).getByRole("button", { name: "Reassign" })).toBeEnabled();
    await waitFor(() =>
      expect(
        screen.queryByRole("button", { name: "Send request" }),
      ).not.toBeInTheDocument(),
    );
  });

  it("keeps the row clear of any request until one is actually raised", async () => {
    renderPage();
    await waitLoaded();

    expect(screen.queryByText(/Block requested/)).not.toBeInTheDocument();
  });

  it("keeps the row clear when the request is refused", async () => {
    const user = userEvent.setup();
    adminApi.createBlockRequest.mockRejectedValue(new Error("nope"));
    renderPage();
    await waitLoaded();

    await raiseRequest(user);

    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("nope"));
    expect(screen.queryByText(/Block requested/)).not.toBeInTheDocument();
  });
});

describe("Request block — reassigning it", () => {
  it("leaves out the current reviewer, the raiser and the target", async () => {
    // Not everyone except the current user: this is redirecting a question
    // the raiser asked, so the raiser stays pickable and the holder does not.
    const user = userEvent.setup();
    renderPage();
    await waitLoaded();
    await raiseRequest(user);
    const row = await requestRow();

    await user.click(within(row).getByRole("button", { name: "Reassign" }));

    const select = await within(
      await screen.findByRole("dialog"),
    ).findByLabelText("Reviewer");
    const names = within(select)
      .getAllByRole("option")
      .map((o) => o.textContent);
    // Three exclusions, all of which the backend's _validate_reviewer refuses:
    // the reviewer who has it now, the raiser, and the person it is about.
    expect(names).not.toContain("Rita Reviewer");
    expect(names).not.toContain("Olive Owner");
    expect(names).toContain("Sam Steward");
  });

  it("hands the request over and re-labels the row with the new reviewer", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitLoaded();
    await raiseRequest(user);
    const row = await requestRow();

    await user.click(within(row).getByRole("button", { name: "Reassign" }));
    const dialog = await screen.findByRole("dialog");
    await user.selectOptions(within(dialog).getByLabelText("Reviewer"), "88");
    await user.click(within(dialog).getByRole("button", { name: "Reassign" }));

    await waitFor(() =>
      expect(adminApi.reassignBlockRequest).toHaveBeenCalledWith(42, 88),
    );
    await waitFor(() =>
      expect(row).toHaveTextContent("Block requested — sent to Sam Steward"),
    );
  });
});

describe("Request block — the raised request lives only in page state", () => {
  it("loses the row on remount, because nothing reads it back", async () => {
    // Known gap, not an accident. There is no backend read scoped to the
    // raiser: the create response is the only place the request is ever seen,
    // so the confirmation and the Reassign link survive exactly as long as
    // this mount does. A reload drops them and a second viewer never gets
    // them. No DTO carries the request, so there is nothing to fixture here.
    const user = userEvent.setup();
    const { unmount } = renderPage();
    await waitLoaded();
    await raiseRequest(user);
    await requestRow();

    unmount();
    renderPage();
    await waitLoaded();

    expect(adminApi.createBlockRequest).toHaveBeenCalledTimes(1);
    expect(screen.queryByText(/Block requested/)).not.toBeInTheDocument();
  });
});
