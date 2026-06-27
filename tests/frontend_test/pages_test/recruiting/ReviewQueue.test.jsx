import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import ReviewQueue from "@/pages/Recruiting/components/ReviewQueue";

describe("ReviewQueue", () => {
  it("lists pending reviews and opens one", () => {
    const onOpen = vi.fn();
    const reviews = [
      { reviewId: 5, jobId: 1, kind: "initial", submitMessage: "hi" },
    ];
    render(<ReviewQueue reviews={reviews} onOpen={onOpen} />);
    expect(screen.getByText("Job #1")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Review" }));
    expect(onOpen).toHaveBeenCalledWith(reviews[0]);
  });

  it("shows an empty state", () => {
    render(<ReviewQueue reviews={[]} onOpen={() => {}} />);
    expect(screen.getByText("No pending reviews.")).toBeInTheDocument();
  });
});
