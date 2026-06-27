import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import Postings from "@/pages/Recruiting/Postings";
import * as api from "@/api/recruitingApi";

vi.mock("@/api/recruitingApi");
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock("@/context/auth/AuthContext", () => ({ useAuth: () => ({ user: { userId: 1 } }) }));

beforeEach(() => {
  vi.clearAllMocks();
  api.listJobs.mockResolvedValue({ data: [{ id: 1, title: "SWE", kind: "employment", status: "draft" }] });
  api.listApprovers.mockResolvedValue({ data: [] });
  api.closeJob.mockResolvedValue({ data: {} });
});

describe("Postings page", () => {
  it("loads and lists jobs on mount", async () => {
    render(<Postings />);
    expect(await screen.findByText("SWE")).toBeInTheDocument();
    expect(api.listJobs).toHaveBeenCalled();
  });

  it("closes a job then refetches", async () => {
    render(<Postings />);
    await screen.findByText("SWE");
    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    await waitFor(() => expect(api.closeJob).toHaveBeenCalledWith(1));
    expect(api.listJobs).toHaveBeenCalledTimes(2);
  });
});
