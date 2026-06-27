import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import PostingForm from "@/pages/Recruiting/components/PostingForm";

describe("PostingForm", () => {
  it("submits title/kind and selected pipeline stages", () => {
    const onSubmit = vi.fn();
    render(
      <PostingForm
        open
        job={null}
        onSubmit={onSubmit}
        onOpenChange={() => {}}
      />,
    );
    fireEvent.change(screen.getByLabelText("Title"), {
      target: { value: "SWE Intern" },
    });
    fireEvent.click(screen.getByLabelText("Recruiter screening"));
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        title: "SWE Intern",
        pipelineConfig: [{ stage: "recruiter_screening" }],
      }),
    );
  });

  it("blocks save when title is empty", () => {
    const onSubmit = vi.fn();
    render(
      <PostingForm
        open
        job={null}
        onSubmit={onSubmit}
        onOpenChange={() => {}}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getByText("Title is required")).toBeInTheDocument();
  });

  it("rejects invalid JSON in the form schema", () => {
    const onSubmit = vi.fn();
    render(
      <PostingForm
        open
        job={null}
        onSubmit={onSubmit}
        onOpenChange={() => {}}
      />,
    );
    fireEvent.change(screen.getByLabelText("Title"), {
      target: { value: "X" },
    });
    fireEvent.change(screen.getByLabelText("Form schema (JSON)"), {
      target: { value: "{ not json" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(onSubmit).not.toHaveBeenCalled();
    expect(
      screen.getByText("Form schema must be valid JSON"),
    ).toBeInTheDocument();
  });
});
