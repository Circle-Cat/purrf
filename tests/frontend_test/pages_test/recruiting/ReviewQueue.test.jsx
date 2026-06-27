import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import ReviewQueue from "@/pages/Recruiting/components/ReviewQueue";

describe("ReviewQueue", () => {
  it("lists pending reviews and opens one", () => {
    const onOpen = vi.fn();
    const reviews = [
      {
        reviewId: 5,
        jobId: 1,
        jobTitle: "SWE Intern",
        kind: "initial",
        submitMessage: "hi",
      },
    ];
    render(<ReviewQueue reviews={reviews} onOpen={onOpen} />);
    expect(screen.getByText("SWE Intern")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Review" }));
    expect(onOpen).toHaveBeenCalledWith(reviews[0]);
  });

  it("falls back to Job #jobId when jobTitle is absent", () => {
    const reviews = [{ reviewId: 6, jobId: 42, kind: "initial" }];
    render(<ReviewQueue reviews={reviews} onOpen={() => {}} />);
    expect(screen.getByText("Job #42")).toBeInTheDocument();
  });

  it("shows an empty state", () => {
    render(<ReviewQueue reviews={[]} onOpen={() => {}} />);
    expect(screen.getByText("No pending reviews.")).toBeInTheDocument();
  });
});
