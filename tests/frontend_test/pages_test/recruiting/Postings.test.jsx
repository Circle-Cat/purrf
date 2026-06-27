import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import Postings from "@/pages/Recruiting/Postings";
import * as api from "@/api/recruitingApi";

vi.mock("@/api/recruitingApi");
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock("@/context/auth/AuthContext", () => ({
  useAuth: () => ({ user: { userId: 1 } }),
}));

const approvers = [
  { userId: 2, name: "Bob", email: "bob@x.com" },
  { userId: 3, name: "Cara", email: "cara@x.com" },
];

beforeEach(() => {
  vi.clearAllMocks();
  api.listJobs.mockResolvedValue({
    data: [{ id: 1, title: "SWE", kind: "employment", status: "draft" }],
  });
  api.listApprovers.mockResolvedValue({ data: approvers });
  api.closeJob.mockResolvedValue({ data: {} });
  api.requestClose.mockResolvedValue({ data: {} });
  api.requestReopen.mockResolvedValue({ data: {} });
  api.deleteJob.mockResolvedValue({ data: {} });
});

describe("Postings page", () => {
  it("loads and lists jobs on mount", async () => {
    render(<Postings />);
    expect(await screen.findByText("SWE")).toBeInTheDocument();
    expect(api.listJobs).toHaveBeenCalled();
  });

  it("closes a draft job directly then refetches", async () => {
    render(<Postings />);
    await screen.findByText("SWE");
    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    await waitFor(() => expect(api.closeJob).toHaveBeenCalledWith(1));
    expect(api.listJobs).toHaveBeenCalledTimes(2);
  });

  it("clicking Request close on a published job opens review dialog with title 'Request close', submits requestClose then refetches", async () => {
    api.listJobs.mockResolvedValue({
      data: [
        {
          id: 2,
          title: "PM",
          kind: "employment",
          status: "published",
        },
      ],
    });
    api.requestClose.mockResolvedValue({ data: {} });

    render(<Postings />);
    await screen.findByText("PM");

    fireEvent.click(screen.getByRole("button", { name: "Request close" }));
    await waitFor(() =>
      expect(
        screen.getByRole("heading", { name: "Request close" }),
      ).toBeInTheDocument(),
    );

    fireEvent.change(screen.getByLabelText("Reviewer"), {
      target: { value: "2" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Submit" }));

    await waitFor(() =>
      expect(api.requestClose).toHaveBeenCalledWith(2, {
        reviewerId: 2,
        message: null,
      }),
    );
    expect(api.listJobs).toHaveBeenCalledTimes(2);
  });

  it("clicking Delete on a never-published closed job shows confirm dialog, confirming calls deleteJob then refetches", async () => {
    api.listJobs.mockResolvedValue({
      data: [
        {
          id: 3,
          title: "Old Draft",
          kind: "employment",
          status: "closed",
          wasPublished: false,
        },
      ],
    });
    api.deleteJob.mockResolvedValue({ data: {} });

    render(<Postings />);
    await screen.findByText("Old Draft");

    fireEvent.click(screen.getByRole("button", { name: "Delete" }));

    expect(
      await screen.findByText(/Delete this posting\?/i),
    ).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", { name: "Delete", hidden: false }),
    );

    await waitFor(() => expect(api.deleteJob).toHaveBeenCalledWith(3));
    expect(api.listJobs).toHaveBeenCalledTimes(2);
  });
});
