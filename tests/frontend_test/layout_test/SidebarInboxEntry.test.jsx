import { describe, it, expect, vi, beforeEach } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, useNavigate } from "react-router-dom";

import Sidebar from "@/components/layout/Sidebar";
import { useAuth } from "@/context/auth";
import { getInboxCount } from "@/api/inboxApi";
import { PERMISSIONS } from "@/constants/Permissions";

vi.mock("@/context/auth", () => ({ useAuth: vi.fn() }));
vi.mock("@/api/inboxApi", () => ({
  getInboxCount: vi.fn(() => Promise.resolve({ data: { needsReply: 0 } })),
}));

let navigate;
const NavGrabber = () => {
  navigate = useNavigate();
  return null;
};

const renderSidebar = () =>
  render(
    <MemoryRouter>
      <NavGrabber />
      <Sidebar />
    </MemoryRouter>,
  );

describe("Sidebar Inbox entry", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getInboxCount.mockResolvedValue({ data: { needsReply: 0 } });
  });

  it.each([
    PERMISSIONS.MENTORSHIP_ADMIN_WRITE,
    PERMISSIONS.RECRUITING_APPLICATION_ADVANCE,
    PERMISSIONS.INQUIRIES_MANAGE,
  ])("is shown to a holder of %s alone", async (permission) => {
    useAuth.mockReturnValue({ permissions: [permission] });
    renderSidebar();

    expect(screen.getByText("Inbox")).toBeInTheDocument();
    await waitFor(() => expect(getInboxCount).toHaveBeenCalledTimes(1));
  });

  it("is hidden and makes no request without an inbox permission", async () => {
    useAuth.mockReturnValue({
      permissions: [PERMISSIONS.MENTORSHIP_ADMIN_READ],
    });
    renderSidebar();

    expect(screen.queryByText("Inbox")).not.toBeInTheDocument();
    await act(async () => {});
    expect(getInboxCount).not.toHaveBeenCalled();
  });

  it("shows no number when nothing needs a reply", async () => {
    useAuth.mockReturnValue({ permissions: [PERMISSIONS.INQUIRIES_MANAGE] });
    renderSidebar();

    await waitFor(() => expect(getInboxCount).toHaveBeenCalled());
    expect(screen.queryByText("0")).not.toBeInTheDocument();
  });

  it("shows the needs-reply count", async () => {
    getInboxCount.mockResolvedValue({ data: { needsReply: 3 } });
    useAuth.mockReturnValue({ permissions: [PERMISSIONS.INQUIRIES_MANAGE] });
    renderSidebar();

    expect(await screen.findByText("3")).toBeInTheDocument();
  });

  it("shows no number when the request fails", async () => {
    getInboxCount.mockRejectedValue(new Error("boom"));
    useAuth.mockReturnValue({ permissions: [PERMISSIONS.INQUIRIES_MANAGE] });
    renderSidebar();

    await waitFor(() => expect(getInboxCount).toHaveBeenCalled());
    expect(screen.getByText("Inbox")).toBeInTheDocument();
  });

  it("requests again after the route changes", async () => {
    useAuth.mockReturnValue({ permissions: [PERMISSIONS.INQUIRIES_MANAGE] });
    renderSidebar();
    await waitFor(() => expect(getInboxCount).toHaveBeenCalledTimes(1));

    await act(async () => navigate("/somewhere-else"));

    await waitFor(() => expect(getInboxCount).toHaveBeenCalledTimes(2));
  });

  it("requests again when the inbox:changed event fires", async () => {
    useAuth.mockReturnValue({ permissions: [PERMISSIONS.INQUIRIES_MANAGE] });
    renderSidebar();
    await waitFor(() => expect(getInboxCount).toHaveBeenCalledTimes(1));

    await act(async () => {
      window.dispatchEvent(new Event("inbox:changed"));
    });

    await waitFor(() => expect(getInboxCount).toHaveBeenCalledTimes(2));
  });
});
