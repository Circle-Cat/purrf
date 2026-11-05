import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import PostingStatusBadges from "@/pages/Recruiting/components/PostingStatusBadges";

describe("PostingStatusBadges", () => {
  it("shows Draft with no action badge for draft", () => {
    render(<PostingStatusBadges job={{ status: "draft" }} />);

    expect(screen.getByText("Draft")).toBeInTheDocument();
    expect(screen.queryByText("Pending review")).not.toBeInTheDocument();
  });

  it("shows Draft alongside Pending review for pending_review", () => {
    render(<PostingStatusBadges job={{ status: "pending_review" }} />);

    expect(screen.getByText("Draft")).toBeInTheDocument();
    expect(screen.getByText("Pending review")).toBeInTheDocument();
  });

  it("shows Published with no action badge for published", () => {
    render(<PostingStatusBadges job={{ status: "published" }} />);

    expect(screen.getByText("Published")).toBeInTheDocument();
    expect(
      screen.queryByText("Revision pending review"),
    ).not.toBeInTheDocument();
  });

  it("shows Published alongside Revision pending review for published_pending_revision", () => {
    render(
      <PostingStatusBadges job={{ status: "published_pending_revision" }} />,
    );

    expect(screen.getByText("Published")).toBeInTheDocument();
    expect(screen.getByText("Revision pending review")).toBeInTheDocument();
  });

  it("shows Published alongside Pending close for pending_close", () => {
    render(<PostingStatusBadges job={{ status: "pending_close" }} />);

    expect(screen.getByText("Published")).toBeInTheDocument();
    expect(screen.getByText("Pending close")).toBeInTheDocument();
  });

  it("shows Closed alongside Pending reopen for pending_reopen", () => {
    render(<PostingStatusBadges job={{ status: "pending_reopen" }} />);

    expect(screen.getByText("Closed")).toBeInTheDocument();
    expect(screen.getByText("Pending reopen")).toBeInTheDocument();
  });

  it("shows Closed with no action badge for closed", () => {
    render(<PostingStatusBadges job={{ status: "closed" }} />);

    expect(screen.getByText("Closed")).toBeInTheDocument();
    expect(screen.queryByText("Pending reopen")).not.toBeInTheDocument();
  });

  it("does not render a reject badge when there is no reject comment", () => {
    render(<PostingStatusBadges job={{ status: "draft" }} />);

    expect(screen.queryByText(/rejected|Sent back/)).not.toBeInTheDocument();
  });

  it("shows the state badge alongside a reject-reason badge, not instead of it", () => {
    render(
      <PostingStatusBadges
        job={{
          status: "draft",
          lastRejectComment: "Please fix the salary range.",
          lastRejectKind: "initial",
        }}
      />,
    );

    expect(screen.getByText("Draft")).toBeInTheDocument();
    expect(screen.getByText("Initial submission rejected")).toBeInTheDocument();
  });

  it("renders the reject badge as plain, non-interactive text", () => {
    render(
      <PostingStatusBadges
        job={{
          status: "draft",
          lastRejectComment: "Please fix the salary range.",
          lastRejectKind: "initial",
        }}
      />,
    );

    // No popover trigger: nothing here is clickable or focusable, and the
    // comment text is never rendered by this component.
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(
      screen.queryByText("Please fix the salary range."),
    ).not.toBeInTheDocument();
  });

  it("falls back to 'Sent back' for an unrecognized reject kind", () => {
    render(
      <PostingStatusBadges
        job={{
          status: "draft",
          lastRejectComment: "Please fix the salary range.",
          lastRejectKind: "some_future_kind",
        }}
      />,
    );

    expect(screen.getByText("Sent back")).toBeInTheDocument();
  });
});
