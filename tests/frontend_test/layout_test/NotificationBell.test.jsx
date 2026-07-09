import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { toast } from "sonner";
import NotificationBell from "@/components/layout/NotificationBell";
import * as api from "@/api/recruitingApi";

vi.mock("@/api/recruitingApi");
vi.spyOn(toast, "error").mockImplementation(() => {});

beforeEach(() => vi.clearAllMocks());

const renderBell = () => {
  const router = createMemoryRouter(
    [
      { path: "/", element: <NotificationBell /> },
      {
        path: "/recruiting/applications/:applicationId",
        element: <p>APPLICATION DETAIL</p>,
      },
      { path: "/recruiting/jobs/:jobId", element: <p>JOB DETAIL</p> },
    ],
    { initialEntries: ["/"] },
  );
  return render(<RouterProvider router={router} />);
};

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
            type: "assigned_to_evaluate",
            applicationId: 7,
            jobId: 1,
            round: 1,
            jobTitle: "Backend Engineer",
            applicantName: "Ada Lovelace",
            actorName: "Grace Hopper",
            read: false,
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

  it("navigates to the application and marks read on click", async () => {
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
            read: false,
            createdAt: "2026-07-09T00:00:00Z",
          },
        ],
      },
    });
    api.markNotificationRead.mockResolvedValue({ data: { unreadCount: 0 } });
    renderBell();

    await waitFor(() => expect(screen.getByText("1")).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: "Notifications" }));
    await user.click(
      screen.getByText(
        "Grace Hopper mentioned you in a comment on Ada Lovelace — Backend Engineer",
      ),
    );

    expect(screen.getByText("APPLICATION DETAIL")).toBeInTheDocument();
    expect(api.markNotificationRead).toHaveBeenCalledWith(1);
  });

  it("navigates to the job detail page for a job-review notification", async () => {
    const user = userEvent.setup();
    api.listNotifications.mockResolvedValue({
      data: {
        unreadCount: 1,
        notifications: [
          {
            id: 2,
            type: "job_review_requested",
            applicationId: null,
            jobId: 5,
            round: null,
            jobTitle: "Design Review",
            applicantName: "",
            actorName: "Grace Hopper",
            read: false,
            createdAt: "2026-07-09T00:00:00Z",
          },
        ],
      },
    });
    api.markNotificationRead.mockResolvedValue({ data: { unreadCount: 0 } });
    renderBell();

    await waitFor(() => expect(screen.getByText("1")).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: "Notifications" }));
    await user.click(
      screen.getByText(
        'Grace Hopper submitted "Design Review" for your review',
      ),
    );

    expect(screen.getByText("JOB DETAIL")).toBeInTheDocument();
  });

  it("marks every notification read and clears the badge on Mark all read", async () => {
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
            read: false,
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
            read: false,
            createdAt: "2026-07-09T00:00:00Z",
          },
        ],
      },
    });
    api.markAllNotificationsRead.mockResolvedValue({
      data: { unreadCount: 0 },
    });
    renderBell();

    await waitFor(() => expect(screen.getByText("2")).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: "Notifications" }));
    await user.click(screen.getByRole("button", { name: "Mark all read" }));

    expect(api.markAllNotificationsRead).toHaveBeenCalledTimes(1);
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
});
