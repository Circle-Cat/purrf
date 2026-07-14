import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
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

    expect(screen.queryByRole("button")).not.toBeInTheDocument();
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
    expect(
      screen.getByRole("button", { name: "Initial submission rejected" }),
    ).toBeInTheDocument();
  });

  it("falls back to 'Sent back' / 'Rejected' for an unrecognized reject kind", () => {
    render(
      <PostingStatusBadges
        job={{
          status: "draft",
          lastRejectComment: "Please fix the salary range.",
          lastRejectKind: "some_future_kind",
        }}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Sent back" }));

    expect(screen.getByText("Rejected")).toBeInTheDocument();
  });

  it("calls onRejectBadgeClick when the reject badge is clicked", () => {
    const onRejectBadgeClick = vi.fn();
    render(
      <PostingStatusBadges
        job={{
          status: "draft",
          lastRejectComment: "Please fix the salary range.",
          lastRejectKind: "initial",
        }}
        onRejectBadgeClick={onRejectBadgeClick}
      />,
    );

    fireEvent.click(
      screen.getByRole("button", { name: "Initial submission rejected" }),
    );

    expect(onRejectBadgeClick).toHaveBeenCalledTimes(1);
  });
});
