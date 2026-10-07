import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { toast } from "sonner";
import NotificationBell from "@/components/layout/NotificationBell";
import * as api from "@/api/recruitingApi";

vi.mock("@/api/recruitingApi");
vi.spyOn(toast, "error").mockImplementation(() => {});

beforeEach(() => vi.clearAllMocks());

// The bell reads useLocation(), so it needs router context.  react-router-dom
// re-exports live hooks from react-router and vi.mock does not intercept them
// in the Bazel sandbox, so use a real router -- createMemoryRouter also hands
// back a navigate() the pathname-trigger tests need.
const renderBell = (initialPath = "/") => {
  const router = createMemoryRouter(
    [{ path: "*", element: <NotificationBell /> }],
    {
      initialEntries: [initialPath],
    },
  );
  const result = render(<RouterProvider router={router} />);
  return { ...result, router };
};

/** Set document.visibilityState, which is read-only in jsdom. */
const setVisibility = (state) =>
  Object.defineProperty(document, "visibilityState", {
    value: state,
    configurable: true,
  });

afterEach(() => setVisibility("visible"));

describe("NotificationBell", () => {
  it("shows no unread badge when there are no notifications", async () => {
    api.listNotifications.mockResolvedValue({
      data: { notifications: [], unreadCount: 0 },
    });
    renderBell();

    await waitFor(() => expect(api.listNotifications).toHaveBeenCalledTimes(1));
    expect(screen.queryByText("0")).not.toBeInTheDocument();
  });

  it("shows the unread count badge and lists notifications in the popover", async () => {
    const user = userEvent.setup();
    api.listNotifications.mockResolvedValue({
      data: {
        unreadCount: 1,
        notifications: [
          {
            id: 1,
            eventType: "recruiting.reassigned",
            jobTitle: "Backend Engineer",
            applicantName: "Ada Lovelace",
            actorName: "Grace Hopper",
            createdAt: "2026-07-09T00:00:00Z",
          },
        ],
      },
    });
    renderBell();

    await waitFor(() => expect(screen.getByText("1")).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: "Notifications" }));

    expect(
      screen.getByText(
        "Grace Hopper assigned you to evaluate Ada Lovelace — Backend Engineer",
      ),
    ).toBeInTheDocument();
  });

  it("dismisses a single notification and updates the badge on the X", async () => {
    const user = userEvent.setup();
    api.listNotifications.mockResolvedValue({
      data: {
        unreadCount: 1,
        notifications: [
          {
            id: 1,
            eventType: "recruiting.mentioned",
            jobTitle: "Backend Engineer",
            applicantName: "Ada Lovelace",
            actorName: "Grace Hopper",
            createdAt: "2026-07-09T00:00:00Z",
          },
        ],
      },
    });
    api.dismissNotification.mockResolvedValue({ data: { unreadCount: 0 } });
    renderBell();

    await waitFor(() => expect(screen.getByText("1")).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: "Notifications" }));
    await user.click(
      screen.getByRole("button", { name: "Dismiss notification" }),
    );

    expect(api.dismissNotification).toHaveBeenCalledWith(1);
    await waitFor(() =>
      expect(screen.getByText("No notifications yet.")).toBeInTheDocument(),
    );
  });

  it("clears every notification and the badge on Clear all", async () => {
    const user = userEvent.setup();
    api.listNotifications.mockResolvedValue({
      data: {
        unreadCount: 2,
        notifications: [
          {
            id: 1,
            eventType: "recruiting.mentioned",
            jobTitle: "Backend Engineer",
            applicantName: "Ada Lovelace",
            actorName: "Grace Hopper",
            createdAt: "2026-07-09T00:00:00Z",
          },
          {
            id: 2,
            eventType: "recruiting.mentioned",
            jobTitle: "Backend Engineer",
            applicantName: "Grace Hopper",
            actorName: "Ada Lovelace",
            createdAt: "2026-07-09T00:00:00Z",
          },
        ],
      },
    });
    api.dismissAllNotifications.mockResolvedValue({
      data: { unreadCount: 0 },
    });
    renderBell();

    await waitFor(() => expect(screen.getByText("2")).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: "Notifications" }));
    await user.click(screen.getByRole("button", { name: "Clear all" }));

    expect(api.dismissAllNotifications).toHaveBeenCalledTimes(1);
    await waitFor(() =>
      expect(screen.queryByText("2")).not.toBeInTheDocument(),
    );
  });

  it("shows an inline error when the initial load fails", async () => {
    const user = userEvent.setup();
    api.listNotifications.mockRejectedValue(new Error("boom"));
    renderBell();

    await waitFor(() => expect(api.listNotifications).toHaveBeenCalledTimes(1));
    await user.click(screen.getByRole("button", { name: "Notifications" }));

    await waitFor(() =>
      expect(
        screen.getByText("Couldn't load notifications."),
      ).toBeInTheDocument(),
    );
  });

  it.each([
    [
      "recruiting.application_submitted",
      {},
      "employment",
      "Ada Lovelace applied to Backend Engineer",
    ],
    [
      "recruiting.auto_rejected",
      {},
      "employment",
      "Ada Lovelace applied to Backend Engineer and was rejected automatically",
    ],
    [
      "recruiting.application_submitted",
      { screenAutoHireRuleId: "r1" },
      "activity",
      "Ada Lovelace applied to Backend Engineer and was admitted automatically",
    ],
    [
      "recruiting.application_submitted",
      { screenAutoHireRuleId: "r1" },
      "employment",
      "Ada Lovelace applied to Backend Engineer and was hired automatically",
    ],
    // The one entry written to the person it happened to, rather than to
    // staff watching a pipeline.
    [
      "mentorship.mentor_admitted",
      {},
      "activity",
      "You were admitted to Backend Engineer",
    ],
  ])(
    "describes a %s notification (%s posting)",
    async (eventType, details, jobKind, text) => {
      const user = userEvent.setup();
      api.listNotifications.mockResolvedValue({
        data: {
          unreadCount: 1,
          notifications: [
            {
              id: 1,
              eventType,
              details,
              jobTitle: "Backend Engineer",
              jobKind,
              applicantName: "Ada Lovelace",
              actorName: "Ada Lovelace",
              createdAt: "2026-07-30T00:00:00Z",
            },
          ],
        },
      });
      renderBell();

      await waitFor(() =>
        expect(api.listNotifications).toHaveBeenCalledTimes(1),
      );
      await user.click(screen.getByRole("button", { name: "Notifications" }));

      expect(screen.getByText(text)).toBeInTheDocument();
    },
  );

  it("describes an automatic assignment without naming an actor", async () => {
    // An automatic assignment is the one assignment line that arrives with
    // actorName null: the pipeline's own default-assignee rule made it, so
    // the event carries no actor. It must not read through the
    // `actorName ?? "Someone"` fallback the actor-bearing lines use --
    // "Someone assigned you" credits the decision to a person nobody can
    // name. The bell keeps its own copy switch, separate from the email
    // renderer's, so this invariant needs pinning on both sides.
    const user = userEvent.setup();
    api.listNotifications.mockResolvedValue({
      data: {
        unreadCount: 1,
        notifications: [
          {
            id: 1,
            eventType: "recruiting.auto_assigned",
            details: { stage: "recruiter_screening", round: 1 },
            jobTitle: "Backend Engineer",
            jobKind: "employment",
            applicantName: "Ada Lovelace",
            actorName: null,
            createdAt: "2026-08-18T00:00:00Z",
          },
        ],
      },
    });
    renderBell();

    await waitFor(() => expect(api.listNotifications).toHaveBeenCalledTimes(1));
    await user.click(screen.getByRole("button", { name: "Notifications" }));

    expect(
      screen.getByText(
        "You were auto-assigned to evaluate Ada Lovelace — Backend Engineer",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText(/Someone/)).not.toBeInTheDocument();
  });

  it("says Someone for an assignment whose actor no longer resolves", async () => {
    // An actor id that no longer resolves to a user arrives as an empty
    // name, which is a third state distinct from the null above: a person
    // did make this decision, they just cannot be named any more. The copy
    // has to fall back to "Someone" for it rather than render a blank, and
    // the email renderer words this case the same way.
    const user = userEvent.setup();
    api.listNotifications.mockResolvedValue({
      data: {
        unreadCount: 1,
        notifications: [
          {
            id: 1,
            eventType: "recruiting.reassigned",
            jobTitle: "Backend Engineer",
            applicantName: "Ada Lovelace",
            actorName: "",
            createdAt: "2026-08-18T00:00:00Z",
          },
        ],
      },
    });
    renderBell();

    await waitFor(() => expect(api.listNotifications).toHaveBeenCalledTimes(1));
    await user.click(screen.getByRole("button", { name: "Notifications" }));

    expect(
      screen.getByText(
        "Someone assigned you to evaluate Ada Lovelace — Backend Engineer",
      ),
    ).toBeInTheDocument();
  });
  // -- the block-request lines -------------------------------------------
  //
  // These rows are written under subject_type "user", so they carry no job or
  // applicant -- only subjectName. Before these cases existed the bell listed
  // them as blank rows that still counted towards the unread badge.

  const blockRow = (overrides) => ({
    id: 4,
    jobTitle: "",
    applicantName: "",
    subjectName: "Ada Lovelace",
    actorName: "Grace Hopper",
    createdAt: "2026-09-19T00:00:00Z",
    ...overrides,
  });

  const openWith = async (notification) => {
    const user = userEvent.setup();
    api.listNotifications.mockResolvedValue({
      data: { unreadCount: 1, notifications: [notification] },
    });
    renderBell();
    await waitFor(() => expect(api.listNotifications).toHaveBeenCalledTimes(1));
    await user.click(screen.getByRole("button", { name: "Notifications" }));
  };

  it("tells a reviewer a block request is waiting for them", async () => {
    await openWith(blockRow({ eventType: "user.block_requested" }));

    expect(
      screen.getByText("Grace Hopper asked you to block Ada Lovelace"),
    ).toBeInTheDocument();
  });

  it("tells the raiser their block request was rejected", async () => {
    await openWith(
      blockRow({
        eventType: "user.block_request_decided",
        details: { requestId: 12, decision: "rejected" },
      }),
    );

    expect(
      screen.getByText(
        "Grace Hopper rejected the block request you raised about Ada Lovelace",
      ),
    ).toBeInTheDocument();
  });

  it("tells the raiser their block request was approved", async () => {
    await openWith(
      blockRow({
        eventType: "user.block_request_decided",
        details: { requestId: 12, decision: "approved" },
      }),
    );

    expect(
      screen.getByText(
        "Grace Hopper approved the block request you raised about Ada Lovelace",
      ),
    ).toBeInTheDocument();
  });

  it("tells the reviewer the raiser withdrew the block request", async () => {
    await openWith(
      blockRow({
        eventType: "user.block_request_decided",
        details: { requestId: 12, decision: "withdrawn" },
      }),
    );

    expect(
      screen.getByText(
        "Grace Hopper withdrew the block request about Ada Lovelace",
      ),
    ).toBeInTheDocument();
  });

  it("reads the decision field, not the old approved flag", async () => {
    await openWith(
      blockRow({
        eventType: "user.block_request_decided",
        details: { requestId: 12, approved: true, decision: "rejected" },
      }),
    );

    expect(
      screen.getByText(
        "Grace Hopper rejected the block request you raised about Ada Lovelace",
      ),
    ).toBeInTheDocument();
  });

  it("tells both reviewers a block request moved", async () => {
    await openWith(blockRow({ eventType: "user.block_request_reassigned" }));

    expect(
      screen.getByText(
        "Grace Hopper reassigned the block request about Ada Lovelace",
      ),
    ).toBeInTheDocument();
  });

  // -- posting reviews ----------------------------------------------------

  it.each([
    ["approved", 'Rae Kim approved "Backend Engineer"'],
    ["rejected", 'Rae Kim rejected "Backend Engineer"'],
    ["withdrawn", 'Rae Kim withdrew the review of "Backend Engineer"'],
  ])("says a posting review was %s", async (decision, text) => {
    await openWith({
      id: 11,
      eventType: "recruiting.review_decided",
      jobTitle: "Backend Engineer",
      applicantName: "",
      subjectName: "",
      actorName: "Rae Kim",
      createdAt: "2026-10-07T00:00:00Z",
      details: { kind: "initial", reviewId: 31, decision },
    });

    expect(screen.getByText(text)).toBeInTheDocument();
  });

  // -- mentorship approvals ----------------------------------------------
  //
  // Written under subject_type "mentorship_round": what is asked for, the
  // round and the person come from details.

  const approvalRow = (eventType, details) => ({
    id: 9,
    eventType,
    jobTitle: "",
    applicantName: "",
    subjectName: "",
    actorName: "Ada Ng",
    createdAt: "2026-10-07T00:00:00Z",
    details: {
      requestId: 31,
      action: "publish_matching",
      roundName: "Spring 2026",
      ...details,
    },
  });

  it("tells a reviewer a publish request is waiting on them", async () => {
    await openWith(approvalRow("mentorship.approval_requested", {}));

    expect(
      screen.getByText(
        "Ada Ng asked you to approve: publish the matching result for Spring 2026",
      ),
    ).toBeInTheDocument();
  });

  it("names the person an exemption is for", async () => {
    await openWith(
      approvalRow("mentorship.approval_reassigned", {
        action: "exempt_matching",
        personName: "Ann Lee",
      }),
    );

    expect(
      screen.getByText(
        "Ada Ng moved to you a request to approve: exempt Ann Lee from the matching history check in Spring 2026",
      ),
    ).toBeInTheDocument();
  });

  it.each([
    [
      "approved",
      "Ada Ng approved your request: publish the matching result for Spring 2026",
    ],
    [
      "rejected",
      "Ada Ng rejected your request: publish the matching result for Spring 2026",
    ],
    [
      "withdrawn",
      "Ada Ng withdrew the request: publish the matching result for Spring 2026",
    ],
  ])("tells the other side a request was %s", async (decision, text) => {
    await openWith(approvalRow("mentorship.approval_decided", { decision }));

    expect(screen.getByText(text)).toBeInTheDocument();
  });

  // -- leave requests -----------------------------------------------------
  //
  // What the leave was for comes from details; the manager hears of a filing
  // or a withdrawal, the employee of the decision.

  const leaveRow = (eventType, details) => ({
    id: 11,
    eventType,
    jobTitle: "",
    applicantName: "",
    subjectName: "",
    actorName: "Ann Lee",
    createdAt: "2026-10-07T00:00:00Z",
    details: {
      requestId: 40,
      leaveType: "paid",
      startDate: "2026-11-03",
      endDate: "2026-11-05",
      ...details,
    },
  });

  it("tells a manager a leave request was filed", async () => {
    await openWith(leaveRow("leave.request_submitted", {}));

    expect(
      screen.getByText("Ann Lee asked for paid leave, Nov 3 – Nov 5, 2026"),
    ).toBeInTheDocument();
  });

  it.each([
    ["approved", "Ann Lee approved your paid leave, Nov 3 – Nov 5, 2026"],
    ["rejected", "Ann Lee rejected your paid leave, Nov 3 – Nov 5, 2026"],
    [
      "withdrawn",
      "Ann Lee withdrew their request for paid leave, Nov 3 – Nov 5, 2026",
    ],
  ])("tells the other side a leave request was %s", async (decision, text) => {
    await openWith(leaveRow("leave.request_decided", { decision }));

    expect(screen.getByText(text)).toBeInTheDocument();
  });

  // -- the matching-run line ---------------------------------------------
  //
  // Written under subject_type "mentorship_round", so everything it says comes
  // from details. Before this case existed the admin who started a run saw a
  // blank row that still counted towards the unread badge.

  const runRow = (details) => ({
    id: 5,
    eventType: "mentorship.matching_run_completed",
    jobTitle: "",
    applicantName: "",
    subjectName: "",
    actorName: null,
    createdAt: "2026-09-26T00:00:00Z",
    details: {
      roundName: "Mentorship 2026 Fall",
      status: "succeeded",
      ...details,
    },
  });

  it("tells the admin their matching run finished", async () => {
    await openWith(runRow({}));

    expect(
      screen.getByText(
        "The matching run you started for Mentorship 2026 Fall has finished",
      ),
    ).toBeInTheDocument();
  });

  it("tells the admin their matching run did not finish", async () => {
    await openWith(runRow({ status: "failed", error: "PayloadError" }));

    expect(
      screen.getByText(
        "The matching run you started for Mentorship 2026 Fall did not finish",
      ),
    ).toBeInTheDocument();
  });

  it("leaves the round out rather than naming a blank one", async () => {
    await openWith(runRow({ roundName: "   " }));

    expect(
      screen.getByText("The matching run you started has finished"),
    ).toBeInTheDocument();
  });

  it("tells an ops.maintain holder the Gmail sync needs attention", async () => {
    await openWith({
      id: 6,
      eventType: "ops.gmail_sync_alert",
      jobTitle: "",
      applicantName: "",
      subjectName: "",
      actorName: null,
      createdAt: "2026-09-30T00:00:00Z",
      details: { kind: "watch_renewal_failed" },
    });

    expect(
      screen.getByText("Gmail sync needs attention: watch renewal failed"),
    ).toBeInTheDocument();
  });

  it("tells the recipients a reply arrived, naming the application", async () => {
    // The actor is the candidate under their preferred name; the line reads
    // the application's applicant name, so the two differ here.
    await openWith({
      id: 7,
      eventType: "recruiting.email_received",
      jobTitle: "Backend Engineer",
      applicantName: "Ada Lovelace",
      subjectName: "",
      actorName: "Ada L.",
      createdAt: "2026-10-01T00:00:00Z",
      details: { threadId: 3 },
    });

    expect(
      screen.getByText(
        "New reply on the email thread about Ada Lovelace — Backend Engineer",
      ),
    ).toBeInTheDocument();
  });

  it("tells the sender their email bounced, naming the application", async () => {
    await openWith({
      id: 8,
      eventType: "recruiting.email_bounced",
      jobTitle: "Backend Engineer",
      applicantName: "Ada Lovelace",
      subjectName: "",
      actorName: null,
      createdAt: "2026-10-03T00:00:00Z",
      details: { threadId: 3, failedRecipients: ["bad@x.com"] },
    });

    expect(
      screen.getByText(
        "Your email about Ada Lovelace — Backend Engineer could not be delivered",
      ),
    ).toBeInTheDocument();
  });

  it("tells whoever can handle the thread that an email needs a reply", async () => {
    await openWith({
      id: 9,
      eventType: "inbox.needs_reply",
      jobTitle: "",
      applicantName: "",
      subjectName: "",
      actorName: null,
      createdAt: "2026-10-07T00:00:00Z",
      details: { subject: "Regarding Q4 plans" },
    });

    expect(
      screen.getByText("New email needs a reply: Regarding Q4 plans"),
    ).toBeInTheDocument();
  });

  it("shows fallback subject when inbox.needs_reply has no subject", async () => {
    await openWith({
      id: 10,
      eventType: "inbox.needs_reply",
      jobTitle: "",
      applicantName: "",
      subjectName: "",
      actorName: null,
      createdAt: "2026-10-07T00:00:00Z",
      details: { subject: "" },
    });

    expect(
      screen.getByText("New email needs a reply: (no subject)"),
    ).toBeInTheDocument();
  });

  it("tells the sender their email to a recipient bounced", async () => {
    await openWith({
      id: 11,
      eventType: "inbox.bounced",
      jobTitle: "",
      applicantName: "",
      subjectName: "",
      actorName: null,
      createdAt: "2026-10-07T00:00:00Z",
      details: { bouncedTo: "recipient@example.com" },
    });

    expect(
      screen.getByText("Your email to recipient@example.com was not delivered"),
    ).toBeInTheDocument();
  });
});

const MENTION = {
  id: 1,
  eventType: "recruiting.mentioned",
  jobTitle: "Backend Engineer",
  applicantName: "Ada Lovelace",
  actorName: "Grace Hopper",
  createdAt: "2026-07-09T00:00:00Z",
};
const MENTION_TEXT =
  "Grace Hopper mentioned you in a comment on Ada Lovelace — Backend Engineer";

/** Resolve listNotifications with a given unread count and no rows. */
const mockUnread = (unreadCount, notifications = []) =>
  api.listNotifications.mockResolvedValue({
    data: { unreadCount, notifications },
  });

/** Wait for the mount fetch to land so later call counts start from 1. */
const waitForInitialLoad = () =>
  waitFor(() => expect(api.listNotifications).toHaveBeenCalledTimes(1));

describe("NotificationBell refetch triggers", () => {
  it("refetches when the tab becomes visible again", async () => {
    mockUnread(1);
    renderBell();
    await waitForInitialLoad();

    mockUnread(4);
    setVisibility("visible");
    await act(async () => {
      document.dispatchEvent(new Event("visibilitychange"));
    });

    expect(api.listNotifications).toHaveBeenCalledTimes(2);
    await waitFor(() => expect(screen.getByText("4")).toBeInTheDocument());
  });

  it("does not refetch when the tab is hidden", async () => {
    mockUnread(1);
    renderBell();
    await waitForInitialLoad();

    setVisibility("hidden");
    await act(async () => {
      document.dispatchEvent(new Event("visibilitychange"));
    });

    expect(api.listNotifications).toHaveBeenCalledTimes(1);
  });

  it("refetches when the window regains focus", async () => {
    mockUnread(1);
    renderBell();
    await waitForInitialLoad();

    mockUnread(3);
    await act(async () => {
      window.dispatchEvent(new Event("focus"));
    });

    expect(api.listNotifications).toHaveBeenCalledTimes(2);
    await waitFor(() => expect(screen.getByText("3")).toBeInTheDocument());
  });

  it("issues one request when visibilitychange and focus both fire", async () => {
    mockUnread(1);
    renderBell();
    await waitForInitialLoad();

    setVisibility("visible");
    await act(async () => {
      document.dispatchEvent(new Event("visibilitychange"));
      window.dispatchEvent(new Event("focus"));
    });

    expect(api.listNotifications).toHaveBeenCalledTimes(2);
  });

  it("stops listening once unmounted", async () => {
    const consoleError = vi
      .spyOn(console, "error")
      .mockImplementation(() => {});
    mockUnread(1);
    const { unmount } = renderBell();
    await waitForInitialLoad();

    unmount();
    setVisibility("visible");
    await act(async () => {
      document.dispatchEvent(new Event("visibilitychange"));
      window.dispatchEvent(new Event("focus"));
    });

    expect(api.listNotifications).toHaveBeenCalledTimes(1);
    const reactWarnings = consoleError.mock.calls.filter(([first]) =>
      /not wrapped in act|unmounted component/.test(String(first)),
    );
    expect(reactWarnings).toEqual([]);
    consoleError.mockRestore();
  });

  it("refetches once on mount and again when the pathname changes", async () => {
    mockUnread(1);
    const { router } = renderBell("/recruiting/postings");
    await waitForInitialLoad();

    mockUnread(5);
    await act(async () => {
      await router.navigate("/recruiting/board");
    });

    expect(api.listNotifications).toHaveBeenCalledTimes(2);
    await waitFor(() => expect(screen.getByText("5")).toBeInTheDocument());
  });

  it("does not refetch when only the query string changes", async () => {
    mockUnread(1);
    const { router } = renderBell("/recruiting/board?jobId=1");
    await waitForInitialLoad();

    await act(async () => {
      await router.navigate("/recruiting/board?jobId=2");
    });

    expect(api.listNotifications).toHaveBeenCalledTimes(1);
  });

  it("refetches when the panel opens but not when it closes", async () => {
    const user = userEvent.setup();
    mockUnread(1);
    renderBell();
    await waitForInitialLoad();

    mockUnread(2, [MENTION]);
    await user.click(screen.getByRole("button", { name: "Notifications" }));

    expect(api.listNotifications).toHaveBeenCalledTimes(2);
    await waitFor(() =>
      expect(screen.getByText(MENTION_TEXT)).toBeInTheDocument(),
    );

    // Assert the panel really closed, so the call count below is meaningful
    // rather than passing because onOpenChange never fired at all.
    await user.keyboard("{Escape}");
    await waitFor(() =>
      expect(screen.queryByText(MENTION_TEXT)).not.toBeInTheDocument(),
    );
    expect(api.listNotifications).toHaveBeenCalledTimes(2);
  });

  it("keeps the previous data and stays silent when a refetch fails", async () => {
    mockUnread(1, [MENTION]);
    renderBell();
    await waitForInitialLoad();

    api.listNotifications.mockRejectedValue(new Error("offline"));
    setVisibility("visible");
    await act(async () => {
      document.dispatchEvent(new Event("visibilitychange"));
    });

    expect(toast.error).not.toHaveBeenCalled();
    expect(screen.getByText("1")).toBeInTheDocument();
  });

  it("does not resurrect a notification dismissed while a refetch is in flight", async () => {
    const user = userEvent.setup();
    const stale = { data: { unreadCount: 1, notifications: [MENTION] } };
    api.listNotifications.mockResolvedValueOnce(stale);
    api.dismissNotification.mockResolvedValue({ data: { unreadCount: 0 } });
    renderBell();
    await waitForInitialLoad();

    let resolveRefetch;
    api.listNotifications.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveRefetch = resolve;
      }),
    );
    await user.click(screen.getByRole("button", { name: "Notifications" }));
    await user.click(
      screen.getByRole("button", { name: "Dismiss notification" }),
    );

    await act(async () => {
      resolveRefetch(stale);
    });

    expect(screen.queryByText(MENTION_TEXT)).not.toBeInTheDocument();
    expect(screen.queryByText("1")).not.toBeInTheDocument();
  });
});
