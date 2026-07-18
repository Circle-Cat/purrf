import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { toast } from "sonner";
import NotificationBell from "@/components/layout/NotificationBell";
import * as api from "@/api/recruitingApi";

vi.mock("@/api/recruitingApi");
vi.spyOn(toast, "error").mockImplementation(() => {});

beforeEach(() => vi.clearAllMocks());

describe("NotificationBell", () => {
  it("shows no unread badge when there are no notifications", async () => {
    api.listNotifications.mockResolvedValue({
      data: { notifications: [], unreadCount: 0 },
    });
    render(<NotificationBell />);

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
            type: "assigned_to_evaluate",
            applicationId: 7,
            jobId: 1,
            round: 1,
            jobTitle: "Backend Engineer",
            applicantName: "Ada Lovelace",
            actorName: "Grace Hopper",
            createdAt: "2026-07-09T00:00:00Z",
          },
        ],
      },
    });
    render(<NotificationBell />);

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
            type: "mentioned",
            applicationId: 7,
            jobId: 1,
            round: null,
            jobTitle: "Backend Engineer",
            applicantName: "Ada Lovelace",
            actorName: "Grace Hopper",
            createdAt: "2026-07-09T00:00:00Z",
          },
        ],
      },
    });
    api.dismissNotification.mockResolvedValue({ data: { unreadCount: 0 } });
    render(<NotificationBell />);

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
            type: "mentioned",
            applicationId: 7,
            jobId: 1,
            round: null,
            jobTitle: "Backend Engineer",
            applicantName: "Ada Lovelace",
            actorName: "Grace Hopper",
            createdAt: "2026-07-09T00:00:00Z",
          },
          {
            id: 2,
            type: "mentioned",
            applicationId: 8,
            jobId: 1,
            round: null,
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
    render(<NotificationBell />);

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
    render(<NotificationBell />);

    await waitFor(() => expect(api.listNotifications).toHaveBeenCalledTimes(1));
    await user.click(screen.getByRole("button", { name: "Notifications" }));

    await waitFor(() =>
      expect(
        screen.getByText("Couldn't load notifications."),
      ).toBeInTheDocument(),
    );
  });
});
