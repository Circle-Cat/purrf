import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import EvaluationRubricForm from "@/pages/Recruiting/applications/EvaluationRubricForm";

describe("EvaluationRubricForm", () => {
  it("renders all sections and fields for stage='tech'", () => {
    render(
      <EvaluationRubricForm
        stage="tech"
        initialResponses={{}}
        onSaveDraft={vi.fn()}
        onConfirm={vi.fn()}
      />,
    );

    // 3 sections
    expect(
      screen.getByRole("heading", { name: "Technical Ability" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Interview Record" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Overall Evaluation" }),
    ).toBeInTheDocument();

    // 8 fields total, by label
    expect(
      screen.getByText(
        "Does the candidate select appropriate data structures and algorithms?",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText("How correct and complete is the implementation?"),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "How effectively does the candidate identify and fix issues?",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "How clearly does the candidate explain their thought process during problem-solving?",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("Problem Statement")).toBeInTheDocument();
    expect(
      screen.getByText("Candidate Understanding and Approach"),
    ).toBeInTheDocument();
    expect(screen.getByText("Code Snippet")).toBeInTheDocument();
    expect(
      screen.getByText("Should this candidate proceed to the next stage?"),
    ).toBeInTheDocument();

    // Score fields render a 1-5 button group: 5 score fields * 5 buttons = 25
    for (let n = 1; n <= 5; n += 1) {
      expect(screen.getAllByRole("button", { name: String(n) })).toHaveLength(
        5,
      );
    }

    // Notes fields (3 valueType="notes" + 1 hasNotes on "overall") = 4 textareas
    expect(screen.getAllByPlaceholderText("Notes")).toHaveLength(4);
  });

  it("toggling a pass_fail field updates local display state", async () => {
    const user = userEvent.setup();
    render(
      <EvaluationRubricForm
        stage="recruiter_screening"
        initialResponses={{}}
        onSaveDraft={vi.fn()}
        onConfirm={vi.fn()}
      />,
    );

    const passButtons = screen.getAllByRole("button", { name: "Pass" });
    const failButtons = screen.getAllByRole("button", { name: "Fail" });
    // bg_match is the first pass_fail field
    expect(passButtons[0]).toHaveAttribute("aria-pressed", "false");
    expect(failButtons[0]).toHaveAttribute("aria-pressed", "false");

    await user.click(failButtons[0]);

    expect(failButtons[0]).toHaveAttribute("aria-pressed", "true");
    expect(passButtons[0]).toHaveAttribute("aria-pressed", "false");

    await user.click(passButtons[0]);

    expect(passButtons[0]).toHaveAttribute("aria-pressed", "true");
    expect(failButtons[0]).toHaveAttribute("aria-pressed", "false");
  });

  it("toggling a score field updates local display state", async () => {
    const user = userEvent.setup();
    render(
      <EvaluationRubricForm
        stage="tech"
        initialResponses={{}}
        onSaveDraft={vi.fn()}
        onConfirm={vi.fn()}
      />,
    );

    // data_structures is the first score field -> first set of 1-5 buttons
    const fourButtons = screen.getAllByRole("button", { name: "4" });
    await user.click(fourButtons[0]);

    expect(fourButtons[0]).toHaveAttribute("aria-pressed", "true");
    const threeButtons = screen.getAllByRole("button", { name: "3" });
    expect(threeButtons[0]).toHaveAttribute("aria-pressed", "false");
  });

  it("Save draft calls onSaveDraft with the current in-progress responses", async () => {
    const user = userEvent.setup();
    const onSaveDraft = vi.fn();
    render(
      <EvaluationRubricForm
        stage="tech"
        initialResponses={{}}
        onSaveDraft={onSaveDraft}
        onConfirm={vi.fn()}
      />,
    );

    await user.click(screen.getAllByRole("button", { name: "4" })[0]);
    await user.click(screen.getByRole("button", { name: "Save draft" }));

    expect(onSaveDraft).toHaveBeenCalledWith({
      data_structures: { value: 4 },
    });
  });

  it("Confirm & Submit shows the irreversibility dialog before calling onConfirm", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    render(
      <EvaluationRubricForm
        stage="tech"
        initialResponses={{}}
        onSaveDraft={vi.fn()}
        onConfirm={onConfirm}
      />,
    );

    await user.click(screen.getAllByRole("button", { name: "5" })[0]);
    await user.click(screen.getByRole("button", { name: "Confirm & Submit" }));

    expect(
      screen.getByText("This cannot be edited after submitting."),
    ).toBeInTheDocument();
    expect(onConfirm).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "Submit" }));

    expect(onConfirm).toHaveBeenCalledWith({ data_structures: { value: 5 } });
  });

  it("readOnly disables every input and hides the action buttons", () => {
    render(
      <EvaluationRubricForm
        stage="recruiter_screening"
        initialResponses={{
          bg_match: { value: true },
          bg_strength: { value: 3, notes: "Solid." },
        }}
        readOnly
        onSaveDraft={vi.fn()}
        onConfirm={vi.fn()}
      />,
    );

    screen.getAllByRole("button").forEach((button) => {
      expect(button).toBeDisabled();
    });
    screen.getAllByPlaceholderText("Notes").forEach((textarea) => {
      expect(textarea).toBeDisabled();
    });
    expect(
      screen.queryByRole("button", { name: "Save draft" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Confirm & Submit" }),
    ).not.toBeInTheDocument();

    // Existing initialResponses reflected as pressed state (bg_match is the
    // first pass_fail field)
    expect(screen.getAllByRole("button", { name: "Pass" })[0]).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });
});
