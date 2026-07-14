import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import PostingStatusBadges from "@/pages/Recruiting/components/PostingStatusBadges";

describe("PostingStatusBadges", () => {
  it("renders the status label for the job's status", () => {
    render(<PostingStatusBadges job={{ status: "published" }} />);

    expect(screen.getByText("Published")).toBeInTheDocument();
  });

  it("does not render a reject badge when there is no reject comment", () => {
    render(<PostingStatusBadges job={{ status: "draft" }} />);

    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("shows the status badge alongside a reject-reason badge, not instead of it", () => {
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
