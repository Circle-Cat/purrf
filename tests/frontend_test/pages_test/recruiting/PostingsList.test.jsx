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

  it("offers Edit/Submit/Close/View on a draft and fires callbacks", () => {
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
    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(onClose).toHaveBeenCalledWith(1);
    expect(screen.getByRole("button", { name: "View" })).toBeInTheDocument();
  });

  it("offers Edit and Request close (not plain Close) on published, and View", () => {
    const onEdit = vi.fn(),
      onRequestClose = vi.fn();
    render(
      <PostingsList
        jobs={[job({ status: "published" })]}
        onEdit={onEdit}
        onRequestClose={onRequestClose}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Edit" }));
    expect(onEdit).toHaveBeenCalledWith(expect.objectContaining({ id: 1 }));
    fireEvent.click(screen.getByRole("button", { name: "Request close" }));
    expect(onRequestClose).toHaveBeenCalledWith(1);
    expect(
      screen.queryByRole("button", { name: "Close" }),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "View" })).toBeInTheDocument();
  });

  it("offers Submit for review and View on published_pending_revision (no close)", () => {
    const onSubmit = vi.fn();
    render(
      <PostingsList
        jobs={[job({ status: "published_pending_revision" })]}
        onSubmit={onSubmit}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Submit for review" }));
    expect(onSubmit).toHaveBeenCalledWith(1);
    expect(
      screen.queryByRole("button", { name: "Close" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Request close" }),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "View" })).toBeInTheDocument();
  });

  it("shows no lifecycle buttons on pending_review (View only)", () => {
    const onView = vi.fn();
    render(
      <PostingsList
        jobs={[job({ status: "pending_review" })]}
        onView={onView}
      />,
    );
    expect(screen.getByText("Pending review")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Edit" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Submit for review" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Close" }),
    ).not.toBeInTheDocument();
    const viewBtn = screen.getByRole("button", { name: "View" });
    expect(viewBtn).toBeInTheDocument();
    fireEvent.click(viewBtn);
    expect(onView).toHaveBeenCalledWith(expect.objectContaining({ id: 1 }));
  });

  it("shows no lifecycle buttons on pending_close (View only)", () => {
    render(<PostingsList jobs={[job({ status: "pending_close" })]} />);
    expect(screen.getByText("Pending close")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Edit" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Close" }),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "View" })).toBeInTheDocument();
  });

  it("shows no lifecycle buttons on pending_reopen (View only)", () => {
    render(<PostingsList jobs={[job({ status: "pending_reopen" })]} />);
    expect(screen.getByText("Pending reopen")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Edit" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Request reopen" }),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "View" })).toBeInTheDocument();
  });

  it("offers Edit, Request reopen and View for closed+wasPublished", () => {
    const onEdit = vi.fn(),
      onRequestReopen = vi.fn();
    render(
      <PostingsList
        jobs={[job({ status: "closed", wasPublished: true })]}
        onEdit={onEdit}
        onRequestReopen={onRequestReopen}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Edit" }));
    expect(onEdit).toHaveBeenCalledWith(expect.objectContaining({ id: 1 }));
    fireEvent.click(screen.getByRole("button", { name: "Request reopen" }));
    expect(onRequestReopen).toHaveBeenCalledWith(1);
    expect(
      screen.queryByRole("button", { name: "Delete" }),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "View" })).toBeInTheDocument();
  });

  it("offers Delete and View for closed without wasPublished (never published)", () => {
    const onDelete = vi.fn();
    render(
      <PostingsList
        jobs={[job({ status: "closed", wasPublished: false })]}
        onDelete={onDelete}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    expect(onDelete).toHaveBeenCalledWith(1);
    expect(
      screen.queryByRole("button", { name: "Edit" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Request reopen" }),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "View" })).toBeInTheDocument();
  });

  it("shows View button for every status and calls onView", () => {
    const onView = vi.fn();
    render(
      <PostingsList
        jobs={[job({ id: 7, status: "published" })]}
        onView={onView}
      />,
    );
    const viewBtn = screen.getByRole("button", { name: "View" });
    fireEvent.click(viewBtn);
    expect(onView).toHaveBeenCalledWith(expect.objectContaining({ id: 7 }));
  });

  it("shows 'Sent back' badge (not 'Draft') for a draft with lastRejectComment", () => {
    render(
      <PostingsList
        jobs={[job({ status: "draft", lastRejectComment: "fix the form" })]}
      />,
    );
    expect(screen.getByText("Sent back")).toBeInTheDocument();
    expect(screen.queryByText("Draft")).not.toBeInTheDocument();
  });

  it("shows 'Draft' badge for a draft without lastRejectComment", () => {
    render(<PostingsList jobs={[job({ status: "draft" })]} />);
    expect(screen.getByText("Draft")).toBeInTheDocument();
    expect(screen.queryByText("Sent back")).not.toBeInTheDocument();
  });

  it("clicking 'Sent back' badge opens a popover with the rejection comment", async () => {
    render(
      <PostingsList
        jobs={[job({ status: "draft", lastRejectComment: "fix the form" })]}
      />,
    );
    const sentBackBadge = screen.getByText("Sent back");
    expect(sentBackBadge).toBeInTheDocument();
    // The popover content is not yet visible
    expect(screen.queryByText("fix the form")).not.toBeInTheDocument();
    // Click the trigger to open the popover
    fireEvent.click(sentBackBadge);
    // Now the rejection comment should be visible
    expect(await screen.findByText("fix the form")).toBeInTheDocument();
    expect(screen.getByText("Rejection comment")).toBeInTheDocument();
  });
});
