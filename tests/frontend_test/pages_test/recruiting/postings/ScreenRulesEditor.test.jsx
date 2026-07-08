import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import ScreenRulesEditor from "@/pages/Recruiting/postings/ScreenRulesEditor";

const QUESTIONS = [
  { id: "q1", type: "single_choice", label: "Fluent?", options: ["Yes", "No"] },
  { id: "q2", type: "short_text", label: "Name" },
];

/**
 * Stateful wrapper so onChange feeds the next value back into the (controlled)
 * editor — mirroring how PostingEditor owns the draft.
 */
function ControlledScreenRules({
  initialRules = [],
  questions = [],
  onChange,
}) {
  const [value, setValue] = useState({ rules: initialRules });
  return (
    <ScreenRulesEditor
      value={value}
      questions={questions}
      onChange={(next) => {
        setValue(next);
        onChange?.(next);
      }}
    />
  );
}

describe("ScreenRulesEditor", () => {
  it("reflects rules supplied via the value prop after mount (no stale wipe)", () => {
    // Regression: the editor used to snapshot value.rules into local state at
    // mount and never resync, so rules that arrived after mount (an edited
    // posting loading async) were invisible and wiped on the next edit.
    const rule = {
      id: "r1",
      condition: {
        source: "email_domain",
        operator: "equals",
        value: "google.com",
      },
      action: "qualify",
    };
    const { rerender } = render(
      <ScreenRulesEditor
        value={{ rules: [] }}
        questions={[]}
        onChange={vi.fn()}
      />,
    );
    expect(screen.queryByLabelText("Email domains")).not.toBeInTheDocument();

    rerender(
      <ScreenRulesEditor
        value={{ rules: [rule] }}
        questions={[]}
        onChange={vi.fn()}
      />,
    );
    expect(screen.getByLabelText("Email domains")).toHaveValue("google.com");
  });

  it("adds an email domain rule defaulting to Include mode", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<ControlledScreenRules initialRules={[]} onChange={onChange} />);
    await user.click(
      screen.getByRole("button", { name: "Add email domain rule" }),
    );
    fireEvent.change(screen.getByLabelText("Email domains"), {
      target: { value: "google.com" },
    });
    await user.click(
      screen.getByRole("combobox", { name: "Email domain action" }),
    );
    await user.click(screen.getByRole("option", { name: "qualify" }));
    const last = onChange.mock.calls.at(-1)[0];
    expect(last.rules).toEqual([
      {
        id: "r1",
        condition: {
          source: "email_domain",
          operator: "equals",
          value: "google.com",
        },
        action: "qualify",
      },
    ]);
  });

  it("offers auto_hire as an email-domain rule action", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<ControlledScreenRules initialRules={[]} onChange={onChange} />);
    await user.click(
      screen.getByRole("button", { name: "Add email domain rule" }),
    );
    fireEvent.change(screen.getByLabelText("Email domains"), {
      target: { value: "circlecat.org" },
    });
    await user.click(
      screen.getByRole("combobox", { name: "Email domain action" }),
    );
    await user.click(screen.getByRole("option", { name: "auto_hire" }));
    const last = onChange.mock.calls.at(-1)[0];
    expect(last.rules).toEqual([
      {
        id: "r1",
        condition: {
          source: "email_domain",
          operator: "equals",
          value: "circlecat.org",
        },
        action: "auto_hire",
      },
    ]);
  });

  it("emits an email_domain=in rule for multiple comma-separated domains", () => {
    const onChange = vi.fn();
    render(
      <ControlledScreenRules
        initialRules={[
          {
            id: "r1",
            condition: {
              source: "email_domain",
              operator: "equals",
              value: "google.com",
            },
            action: "qualify",
          },
        ]}
        onChange={onChange}
      />,
    );
    fireEvent.change(screen.getByLabelText("Email domains"), {
      target: { value: "google.com, circlecat.org" },
    });
    const last = onChange.mock.calls.at(-1)[0];
    expect(last.rules[0].condition).toEqual({
      source: "email_domain",
      operator: "in",
      value: ["google.com", "circlecat.org"],
    });
  });

  it("switches a row to Exclude mode and emits a not_in rule", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <ControlledScreenRules
        initialRules={[
          {
            id: "r1",
            condition: {
              source: "email_domain",
              operator: "equals",
              value: "google.com",
            },
            action: "reject",
          },
        ]}
        onChange={onChange}
      />,
    );
    await user.click(
      screen.getByRole("combobox", { name: "Email domain mode" }),
    );
    await user.click(screen.getByRole("option", { name: "Exclude" }));
    const last = onChange.mock.calls.at(-1)[0];
    expect(last.rules[0].condition).toEqual({
      source: "email_domain",
      operator: "not_in",
      value: ["google.com"],
    });
  });

  it("loads an existing not_in rule with its mode showing Exclude", () => {
    render(
      <ControlledScreenRules
        initialRules={[
          {
            id: "r1",
            condition: {
              source: "email_domain",
              operator: "not_in",
              value: ["google.com"],
            },
            action: "reject",
          },
        ]}
        onChange={vi.fn()}
      />,
    );
    expect(
      screen.getByRole("combobox", { name: "Email domain mode" }),
    ).toHaveTextContent("Exclude");
  });

  it("supports two independent email domain rules at once", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <ControlledScreenRules
        initialRules={[
          {
            id: "r1",
            condition: {
              source: "email_domain",
              operator: "in",
              value: ["circlecat.org"],
            },
            action: "auto_hire",
          },
        ]}
        onChange={onChange}
      />,
    );
    await user.click(
      screen.getByRole("button", { name: "Add email domain rule" }),
    );
    const domainInputs = screen.getAllByLabelText("Email domains");
    expect(domainInputs).toHaveLength(2);
    fireEvent.change(domainInputs[1], {
      target: { value: "circlecat.org" },
    });
    const modeSelects = screen.getAllByRole("combobox", {
      name: "Email domain mode",
    });
    await user.click(modeSelects[1]);
    await user.click(screen.getByRole("option", { name: "Exclude" }));
    const last = onChange.mock.calls.at(-1)[0];
    expect(last.rules).toEqual([
      {
        id: "r1",
        condition: {
          source: "email_domain",
          operator: "in",
          value: ["circlecat.org"],
        },
        action: "auto_hire",
      },
      {
        id: "r2",
        condition: {
          source: "email_domain",
          operator: "not_in",
          value: ["circlecat.org"],
        },
        action: "qualify",
      },
    ]);
  });

  it("removes only the targeted email domain rule", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <ControlledScreenRules
        initialRules={[
          {
            id: "r1",
            condition: {
              source: "email_domain",
              operator: "equals",
              value: "google.com",
            },
            action: "qualify",
          },
          {
            id: "r2",
            condition: {
              source: "email_domain",
              operator: "not_in",
              value: ["google.com"],
            },
            action: "reject",
          },
        ]}
        onChange={onChange}
      />,
    );
    const removeButtons = screen.getAllByRole("button", {
      name: "Remove email domain rule",
    });
    expect(removeButtons).toHaveLength(2);
    await user.click(removeButtons[0]);
    const last = onChange.mock.calls.at(-1)[0];
    expect(last.rules).toEqual([
      {
        id: "r2",
        condition: {
          source: "email_domain",
          operator: "not_in",
          value: ["google.com"],
        },
        action: "reject",
      },
    ]);
  });

  it("adds an answer rule limited to single_choice questions and their options", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <ControlledScreenRules
        initialRules={[]}
        questions={QUESTIONS}
        onChange={onChange}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Add answer rule" }));
    // question dropdown lists q1 (single_choice) but not q2 (short_text)
    await user.click(
      screen.getByRole("combobox", { name: "Answer rule question" }),
    );
    expect(screen.getByRole("option", { name: "Fluent?" })).toBeInTheDocument();
    expect(
      screen.queryByRole("option", { name: "Name" }),
    ).not.toBeInTheDocument();
    await user.click(screen.getByRole("option", { name: "Fluent?" }));
    // option dropdown limited to q1 options
    await user.click(
      screen.getByRole("combobox", { name: "Answer rule value" }),
    );
    await user.click(screen.getByRole("option", { name: "No" }));
    await user.click(
      screen.getByRole("combobox", { name: "Answer rule action" }),
    );
    await user.click(screen.getByRole("option", { name: "reject" }));
    const last = onChange.mock.calls.at(-1)[0];
    expect(last.rules.at(-1)).toEqual({
      id: "r1",
      condition: {
        source: "answer",
        operator: "equals",
        questionId: "q1",
        value: "No",
      },
      action: "reject",
    });
  });
});
