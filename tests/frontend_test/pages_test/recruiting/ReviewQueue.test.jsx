import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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

  // "No pending reviews." told a reviewer nothing they could act on. An
  // empty queue is the normal state, and the useful facts are that someone
  // else has to name them and that they can never review their own work.
  it("explains an empty queue rather than only stating it is empty", () => {
    render(<ReviewQueue reviews={[]} onOpen={() => {}} />);

    expect(
      screen.getByText("Postings submitted for your approval appear here."),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "An author picks you as the reviewer when they submit a posting.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "You can't add one yourself, and you can't review your own postings.",
      ),
    ).toBeInTheDocument();
  });

  it("explains what approving or rejecting each request kind does", async () => {
    const user = userEvent.setup();
    render(
      <ReviewQueue
        reviews={[{ reviewId: 1, jobId: 2, jobTitle: "T", kind: "close" }]}
        onOpen={() => {}}
      />,
    );

    (await screen.findByText("Close Request")).focus();

    expect(
      await screen.findByText(
        "A request to close a published posting. Rejecting just aborts the request.",
      ),
    ).toBeInTheDocument();
  });

  it("falls back to the raw kind for one the glossary does not know", () => {
    render(
      <ReviewQueue
        reviews={[
          { reviewId: 1, jobId: 2, jobTitle: "T", kind: "some_future_kind" },
        ]}
        onOpen={() => {}}
      />,
    );
    expect(screen.getByText("some_future_kind")).toBeInTheDocument();
  });
});
