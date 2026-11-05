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

  it("shows a human-readable, Request-suffixed label for each review kind", () => {
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

  it("renders nothing when there are no pending reviews", () => {
    const { container } = render(
      <ReviewQueue reviews={[]} onOpen={() => {}} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("counts the pending reviews in its header", () => {
    const reviews = [
      { reviewId: 1, jobId: 1, jobTitle: "A", kind: "initial" },
      { reviewId: 2, jobId: 2, jobTitle: "B", kind: "close" },
    ];
    render(<ReviewQueue reviews={reviews} onOpen={() => {}} />);
    expect(screen.getByText("Pending approvals")).toBeInTheDocument();
    expect(screen.getByText("2 waiting")).toBeInTheDocument();
  });

  it("says when each review was submitted, in the viewer's timezone", () => {
    const reviews = [
      {
        reviewId: 1,
        jobId: 1,
        jobTitle: "A",
        kind: "initial",
        createdAt: "2026-09-28T03:00:00Z",
      },
    ];
    render(<ReviewQueue reviews={reviews} onOpen={() => {}} />);
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
    expect(
      screen.getByText(new RegExp(`Submitted 2026-09-2\\d ${tz}`)),
    ).toBeInTheDocument();
  });

  it("leaves the submitted time out when the review has none", () => {
    render(
      <ReviewQueue
        reviews={[{ reviewId: 1, jobId: 1, jobTitle: "A", kind: "initial" }]}
        onOpen={() => {}}
      />,
    );
    expect(screen.queryByText(/Submitted/)).not.toBeInTheDocument();
  });

  it("explains what approving or rejecting each request kind does", async () => {
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

  it("warns that approving a reopen may publish a staged edit", async () => {
    render(
      <ReviewQueue
        reviews={[{ reviewId: 1, jobId: 2, jobTitle: "T", kind: "reopen" }]}
        onOpen={() => {}}
      />,
    );

    (await screen.findByText("Reopen Request")).focus();

    expect(
      await screen.findByText(/approving republishes that proposed version/),
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
