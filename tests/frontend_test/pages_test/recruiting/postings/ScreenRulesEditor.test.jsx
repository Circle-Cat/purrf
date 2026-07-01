import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ScreenRulesEditor from "@/pages/Recruiting/postings/ScreenRulesEditor";

const QUESTIONS = [
  { id: "q1", type: "single_choice", label: "Fluent?", options: ["Yes", "No"] },
  { id: "q2", type: "short_text", label: "Name" },
];

describe("ScreenRulesEditor", () => {
  it("emits an email_domain=equals rule for a single domain", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <ScreenRulesEditor
        value={{ rules: [] }}
        questions={[]}
        onChange={onChange}
      />,
    );
    await user.click(
      screen.getByRole("checkbox", { name: "Screen by email domain" }),
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

  it("emits an email_domain=in rule for multiple comma-separated domains", () => {
    const onChange = vi.fn();
    render(
      <ScreenRulesEditor
        value={{
          rules: [
            {
              id: "r1",
              condition: {
                source: "email_domain",
                operator: "equals",
                value: "google.com",
              },
              action: "qualify",
            },
          ],
        }}
        questions={[]}
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

  it("adds an answer rule limited to single_choice questions and their options", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <ScreenRulesEditor
        value={{ rules: [] }}
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
