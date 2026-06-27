import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import PostingsList from "@/pages/Recruiting/components/PostingsList";

const job = (over) => ({
  id: 1,
  title: "SWE",
  kind: "employment",
  status: "draft",
  ...over,
});

describe("PostingsList", () => {
  it("shows a row per job with its status label", () => {
    render(
      <PostingsList
        jobs={[
          job({ id: 1, status: "draft" }),
          job({ id: 2, title: "PM", status: "published" }),
        ]}
      />,
    );
    expect(screen.getByText("SWE")).toBeInTheDocument();
    expect(screen.getByText("PM")).toBeInTheDocument();
    expect(screen.getByText("Draft")).toBeInTheDocument();
    expect(screen.getByText("Published")).toBeInTheDocument();
  });

  it("offers Edit/Submit/Close on a draft and fires callbacks", () => {
    const onEdit = vi.fn(),
      onSubmit = vi.fn(),
      onClose = vi.fn();
    render(
      <PostingsList
        jobs={[job({ status: "draft" })]}
        onEdit={onEdit}
        onSubmit={onSubmit}
        onClose={onClose}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Submit for review" }));
    expect(onSubmit).toHaveBeenCalledWith(1);
    fireEvent.click(screen.getByRole("button", { name: "Edit" }));
    expect(onEdit).toHaveBeenCalledWith(expect.objectContaining({ id: 1 }));
  });

  it("offers Reopen on a closed job only", () => {
    const onReopen = vi.fn();
    render(
      <PostingsList jobs={[job({ status: "closed" })]} onReopen={onReopen} />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Reopen" }));
    expect(onReopen).toHaveBeenCalledWith(1);
    expect(
      screen.queryByRole("button", { name: "Submit for review" }),
    ).not.toBeInTheDocument();
  });

  it("shows no actions while pending_review", () => {
    render(<PostingsList jobs={[job({ status: "pending_review" })]} />);
    expect(screen.getByText("Pending review")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Edit" }),
    ).not.toBeInTheDocument();
  });
});
