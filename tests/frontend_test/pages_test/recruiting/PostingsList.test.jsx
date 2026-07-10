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
});
