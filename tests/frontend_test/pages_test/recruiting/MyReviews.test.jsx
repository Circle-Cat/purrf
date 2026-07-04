import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  render,
  screen,
  fireEvent,
  waitFor,
  within,
} from "@testing-library/react";
import MyReviews from "@/pages/Recruiting/MyReviews";
import * as api from "@/api/recruitingApi";

vi.mock("@/api/recruitingApi");
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

beforeEach(() => {
  vi.clearAllMocks();
  api.listMyReviews.mockResolvedValue({
    data: [{ reviewId: 5, jobId: 1, kind: "initial", submitMessage: "hi" }],
  });
  api.getJob.mockResolvedValue({
    data: {
      id: 1,
      title: "SWE",
      description: "JD",
      formSchema: null,
      pipelineConfig: [],
    },
  });
  api.decideReview.mockResolvedValue({ data: {} });
});

describe("MyReviews page", () => {
  it("loads the queue and opens a review detail", async () => {
    render(<MyReviews />);
    fireEvent.click(await screen.findByRole("button", { name: "Review" }));
    expect(
      await screen.findByRole("heading", { level: 2, name: "SWE" }),
    ).toBeInTheDocument();
    expect(api.getJob).toHaveBeenCalledWith(1);
  });

  it("shows the How it works guide with review kinds", async () => {
    render(<MyReviews />);
    await screen.findByRole("button", { name: "Review" });
    fireEvent.click(screen.getByRole("button", { name: "How it works" }));
    const dialog = await screen.findByRole("dialog");
    expect(
      within(dialog).getByRole("heading", { name: "How reviews work" }),
    ).toBeInTheDocument();
    expect(within(dialog).getByText("Initial Request")).toBeInTheDocument();
    expect(within(dialog).getByText("Reopen Request")).toBeInTheDocument();
  });

  it("approves then returns to the refreshed queue", async () => {
    render(<MyReviews />);
    fireEvent.click(await screen.findByRole("button", { name: "Review" }));
    fireEvent.click(await screen.findByRole("button", { name: "Approve" }));
    await waitFor(() =>
      expect(api.decideReview).toHaveBeenCalledWith(5, { decision: "approve" }),
    );
    expect(api.listMyReviews).toHaveBeenCalledTimes(2);
  });

  it("disables Approve/Reject while a decision is in flight, to prevent a double-submit", async () => {
    let resolveDecide;
    api.decideReview.mockReturnValue(
      new Promise((resolve) => {
        resolveDecide = resolve;
      }),
    );
    render(<MyReviews />);
    fireEvent.click(await screen.findByRole("button", { name: "Review" }));
    fireEvent.click(await screen.findByRole("button", { name: "Approve" }));

    expect(screen.getByRole("button", { name: "Approve" })).toBeDisabled();

    resolveDecide({ data: {} });
    await waitFor(() => expect(api.listMyReviews).toHaveBeenCalledTimes(2));
  });
});
