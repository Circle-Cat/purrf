import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import RejectedBlockRequest from "@/pages/AdminAccounts/components/RejectedBlockRequest";

const rejected = {
  status: "rejected",
  decidedByName: "Rita Reviewer",
  decidedAt: "2026-10-20T17:00:00Z",
  decisionNote: "Not enough evidence",
};

describe("RejectedBlockRequest", () => {
  it("shows a rejected badge with who rejected it and why, the date on hover", () => {
    render(<RejectedBlockRequest request={rejected} tz="UTC" />);

    expect(screen.getByText("Request rejected")).toBeInTheDocument();
    expect(
      screen.getByText("Rita Reviewer: Not enough evidence"),
    ).toBeInTheDocument();
    expect(screen.getByTitle("Rejected 2026-10-20 UTC")).toBeInTheDocument();
    expect(screen.queryByText(/UTC/)).not.toBeInTheDocument();
  });

  it("shows nothing for any other outcome or no request", () => {
    const { container, rerender } = render(
      <RejectedBlockRequest
        request={{ ...rejected, status: "withdrawn" }}
        tz="UTC"
      />,
    );
    expect(container).toBeEmptyDOMElement();

    rerender(<RejectedBlockRequest request={null} tz="UTC" />);
    expect(container).toBeEmptyDOMElement();
  });
});
