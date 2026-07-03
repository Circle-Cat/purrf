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

  it("shows a human-readable, Request-suffixed badge for each review kind", () => {
    const reviews = [
      { reviewId: 1, jobId: 1, jobTitle: "A", kind: "initial" },
      { reviewId: 2, jobId: 2, jobTitle: "B", kind: "revision" },
      { reviewId: 3, jobId: 3, jobTitle: "C", kind: "close" },
      { reviewId: 4, jobId: 4, jobTitle: "D", kind: "reopen" },
    ];
    render(<ReviewQueue reviews={reviews} onOpen={() => {}} />);
    expect(screen.getByText("Initial Request")).toBeInTheDocument();
    expect(screen.getByText("Revision Request")).toBeInTheDocument();
    expect(screen.getByText("Close Request")).toBeInTheDocument();
    expect(screen.getByText("Reopen Request")).toBeInTheDocument();
  });

  it("shows an empty state", () => {
    render(<ReviewQueue reviews={[]} onOpen={() => {}} />);
    expect(screen.getByText("No pending reviews.")).toBeInTheDocument();
  });
});
