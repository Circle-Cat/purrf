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

  it("renders status badge, Recruiter line, and no action buttons", () => {
    render(
      <PostingsList
        jobs={[job]}
        ownersById={{ 2: "Alice", 3: "Bob" }}
        onRowClick={vi.fn()}
      />,
    );

    expect(screen.getByText("Draft")).toBeInTheDocument();
    expect(screen.getByText("Recruiter: Alice, Bob")).toBeInTheDocument();
    // The row itself is a <button> (for click-through navigation), so
    // assert there are no *extra* action buttons beyond that single row.
    expect(screen.getAllByRole("button")).toHaveLength(1);
  });

  it("omits the Recruiter line when no owners are configured", () => {
    render(
      <PostingsList
        jobs={[{ ...job, pipelineConfig: null }]}
        ownersById={{}}
        onRowClick={vi.fn()}
      />,
    );

    expect(screen.queryByText(/Recruiter/)).not.toBeInTheDocument();
  });

  it("shows an unresolved owner in red with an 'unavailable, remove' suffix, alongside a resolved one", () => {
    render(
      <PostingsList
        jobs={[job]}
        ownersById={{ 2: "Alice" }}
        onRowClick={vi.fn()}
      />,
    );

    expect(screen.getByText(/Alice/)).toBeInTheDocument();
    expect(
      screen.getByText("User 3 — unavailable, remove"),
    ).toBeInTheDocument();
  });

  it("calls onRowClick with the job when the row is clicked", () => {
    const onRowClick = vi.fn();
    render(
      <PostingsList jobs={[job]} ownersById={{}} onRowClick={onRowClick} />,
    );

    fireEvent.click(screen.getByText("Backend Engineer"));

    expect(onRowClick).toHaveBeenCalledWith(job);
  });

  it("calls onRowClick when the reject badge itself is clicked", () => {
    const onRowClick = vi.fn();
    const rejected = {
      ...job,
      lastRejectComment: "Please fix the salary range.",
      lastRejectKind: "initial",
    };
    render(
      <PostingsList
        jobs={[rejected]}
        ownersById={{}}
        onRowClick={onRowClick}
      />,
    );

    // The badge is plain text now, so a click on it falls through to the row
    // instead of being swallowed by a popover trigger.
    fireEvent.click(screen.getByText("Initial submission rejected"));

    expect(onRowClick).toHaveBeenCalledWith(rejected);
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
    expect(screen.getByText("Initial submission rejected")).toBeInTheDocument();
    // Still just the row button -- the badge is not interactive.
    expect(screen.getAllByRole("button")).toHaveLength(1);
  });

  it("shows a close-request-rejected badge for a published, close-rejected job", () => {
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

    expect(screen.getByText("Published")).toBeInTheDocument();
    expect(screen.getByText("Close request rejected")).toBeInTheDocument();
  });

  it("never shows the reject comment itself, only the kind badge", () => {
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

    // The comment text lives only on the posting detail page.
    expect(
      screen.queryByText("Please fix the salary range."),
    ).not.toBeInTheDocument();
  });

  it("falls back to a 'Sent back' badge for an unknown reject kind", () => {
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

    expect(screen.getByText("Sent back")).toBeInTheDocument();
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
