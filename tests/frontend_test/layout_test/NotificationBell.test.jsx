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
