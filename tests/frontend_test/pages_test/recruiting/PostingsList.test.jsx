import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import PostingsList from "@/pages/Recruiting/components/PostingsList";

describe("PostingsList", () => {
  const job = {
    id: 1,
    title: "Backend Engineer",
    kind: "employment",
    status: "draft",
    pipelineConfig: { ownerIds: [2, 3] },
  };

  it("renders status badge, Managed by line, and no action buttons", () => {
    render(
      <PostingsList
        jobs={[job]}
        ownersById={{ 2: "Alice", 3: "Bob" }}
        onRowClick={vi.fn()}
      />,
    );

    expect(screen.getByText("Draft")).toBeInTheDocument();
    expect(screen.getByText("Managed by: Alice, Bob")).toBeInTheDocument();
    // The row itself is a <button> (for click-through navigation), so
    // assert there are no *extra* action buttons beyond that single row.
    expect(screen.getAllByRole("button")).toHaveLength(1);
  });

  it("omits the Managed by line when no owners are configured", () => {
    render(
      <PostingsList
        jobs={[{ ...job, pipelineConfig: null }]}
        ownersById={{}}
        onRowClick={vi.fn()}
      />,
    );

    expect(screen.queryByText(/Managed by/)).not.toBeInTheDocument();
  });

  it("calls onRowClick with the job when the row is clicked", () => {
    const onRowClick = vi.fn();
    render(
      <PostingsList jobs={[job]} ownersById={{}} onRowClick={onRowClick} />,
    );

    fireEvent.click(screen.getByText("Backend Engineer"));

    expect(onRowClick).toHaveBeenCalledWith(job);
  });

  it("does not call onRowClick when the Sent back popover trigger is clicked", () => {
    const onRowClick = vi.fn();
    render(
      <PostingsList
        jobs={[{ ...job, lastRejectComment: "Please fix the salary range." }]}
        ownersById={{}}
        onRowClick={onRowClick}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Sent back" }));

    expect(onRowClick).not.toHaveBeenCalled();
  });

  it("shows the status badge alongside the reject-reason badge, not instead of it", () => {
    render(
      <PostingsList
        jobs={[
          {
            ...job,
            lastRejectComment: "Please fix the salary range.",
            lastRejectKind: "initial",
          },
        ]}
        ownersById={{}}
        onRowClick={vi.fn()}
      />,
    );

    expect(screen.getByText("Draft")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Initial submission rejected" }),
    ).toBeInTheDocument();
  });

  it("shows a close-request-rejected badge and popover title for a published, close-rejected job", () => {
    render(
      <PostingsList
        jobs={[
          {
            ...job,
            status: "published",
            lastRejectComment: "Not yet, we still need this role.",
            lastRejectKind: "close",
          },
        ]}
        ownersById={{}}
        onRowClick={vi.fn()}
      />,
    );

    fireEvent.click(
      screen.getByRole("button", { name: "Close request rejected" }),
    );

    expect(screen.getByText("Published")).toBeInTheDocument();
    // The badge and the popover title now share the same reject-kind label.
    expect(screen.getAllByText("Close request rejected")).toHaveLength(2);
  });

  it("falls back to the raw Rejected label in the popover for an unknown reject kind", () => {
    render(
      <PostingsList
        jobs={[
          {
            ...job,
            lastRejectComment: "Please fix the salary range.",
            lastRejectKind: "some_future_kind",
          },
        ]}
        ownersById={{}}
        onRowClick={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Sent back" }));

    expect(screen.getByText("Rejected")).toBeInTheDocument();
  });

  it("shows 'Edit staged' badge for published_pending_revision with reviewerId: null", () => {
    render(
      <PostingsList
        jobs={[
          {
            ...job,
            status: "published_pending_revision",
            reviewerId: null,
          },
        ]}
        ownersById={{}}
        onRowClick={vi.fn()}
      />,
    );

    expect(screen.getByText("Edit staged")).toBeInTheDocument();
  });

  it("shows 'Revision pending review' badge for published_pending_revision with reviewerId: 9", () => {
    render(
      <PostingsList
        jobs={[
          {
            ...job,
            status: "published_pending_revision",
            reviewerId: 9,
          },
        ]}
        ownersById={{}}
        onRowClick={vi.fn()}
      />,
    );

    expect(screen.getByText("Revision pending review")).toBeInTheDocument();
  });
});
