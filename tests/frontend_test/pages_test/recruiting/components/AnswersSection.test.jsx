import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import AnswersSection from "@/pages/Recruiting/components/AnswersSection";

const QUESTIONS = [
  { id: "q1", type: "short_text", label: "Authorized to work?" },
  { id: "q2", type: "long_text", label: "Why us?" },
];

describe("AnswersSection", () => {
  it("renders nothing when there are no questions and no answers", () => {
    const { container } = render(
      <AnswersSection submission={{ answers: {} }} liveQuestions={[]} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("prefers the snapshot schema over the live schema", () => {
    render(
      <AnswersSection
        submission={{
          answers: { q1: "Yes" },
          formSchema: {
            questions: [
              { id: "q1", type: "short_text", label: "Snapshot label" },
            ],
          },
        }}
        liveQuestions={[{ id: "q1", type: "short_text", label: "Live label" }]}
      />,
    );
    expect(screen.getByText("Snapshot label")).toBeInTheDocument();
    expect(screen.queryByText("Live label")).not.toBeInTheDocument();
  });

  it("does not warn when the snapshot schema was used", () => {
    render(
      <AnswersSection
        submission={{
          answers: { q1: "Yes" },
          formSchema: { questions: QUESTIONS },
        }}
        liveQuestions={QUESTIONS}
      />,
    );
    expect(screen.queryByText(/current form/)).not.toBeInTheDocument();
  });

  it("warns when it falls back to the live schema", () => {
    render(
      <AnswersSection
        submission={{ answers: { q1: "Yes" } }}
        liveQuestions={QUESTIONS}
      />,
    );
    expect(
      screen.getByText(
        "Labels are from the job's current form, not the version this candidate filled in.",
      ),
    ).toBeInTheDocument();
  });

  it("keeps line breaks in a long answer", () => {
    render(
      <AnswersSection
        submission={{
          answers: { q2: "One.\n\nTwo." },
          formSchema: { questions: QUESTIONS },
        }}
      />,
    );
    expect(screen.getByText(/One\./).textContent).toBe("One.\n\nTwo.");
  });

  it("marks an unanswered question", () => {
    render(
      <AnswersSection
        submission={{ answers: {}, formSchema: { questions: QUESTIONS } }}
      />,
    );
    expect(screen.getAllByText("Not answered")).toHaveLength(2);
  });

  it("keeps an answer whose question was removed from the form", () => {
    render(
      <AnswersSection
        submission={{
          answers: { q1: "Yes", q7: "Orphaned value" },
          formSchema: { questions: QUESTIONS },
        }}
      />,
    );
    expect(screen.getByText("Other recorded answers")).toBeInTheDocument();
    expect(
      screen.getByText(
        "These questions were removed from the form, or are hidden by a conditional rule.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("q7")).toBeInTheDocument();
    expect(screen.getByText("Orphaned value")).toBeInTheDocument();
  });

  it("renders a live question's array answer inline, not as an orphan", () => {
    // The key-level coverage claim in unmatchedEntries only holds because the
    // renderer shows a value of any shape: q1 counts as rendered, so it must
    // actually appear under its question.
    render(
      <AnswersSection
        submission={{
          answers: { q1: ["Remote", "Hybrid"] },
          formSchema: { questions: QUESTIONS },
        }}
      />,
    );
    expect(screen.getByText("Remote")).toBeInTheDocument();
    expect(screen.getByText("Hybrid")).toBeInTheDocument();
    expect(
      screen.queryByText("Other recorded answers"),
    ).not.toBeInTheDocument();
  });

  it("hides both reviewer notices from the applicant, keeping their answers", () => {
    render(
      <AnswersSection
        submission={{ answers: { q1: "Yes", q7: "Orphaned value" } }}
        liveQuestions={QUESTIONS}
        viewerIsApplicant
      />,
    );
    expect(screen.queryByText(/current form/)).not.toBeInTheDocument();
    expect(screen.queryByText(/removed from the form/)).not.toBeInTheDocument();
    // Everything else still renders, including the recorded answers.
    expect(screen.getByText("Authorized to work?")).toBeInTheDocument();
    expect(screen.getByText("Other recorded answers")).toBeInTheDocument();
    expect(screen.getByText("q7")).toBeInTheDocument();
    expect(screen.getByText("Orphaned value")).toBeInTheDocument();
  });

  it("keeps an answer whose question is hidden by a conditional rule", () => {
    render(
      <AnswersSection
        submission={{
          answers: { q1: "no", q3: "stale" },
          formSchema: {
            questions: [
              { id: "q1", type: "short_text", label: "Base" },
              {
                id: "q3",
                type: "short_text",
                label: "Conditional",
                showWhen: { questionId: "q1", equals: "yes" },
              },
            ],
          },
        }}
      />,
    );
    expect(screen.queryByText("Conditional")).not.toBeInTheDocument();
    expect(screen.getByText("q3")).toBeInTheDocument();
    expect(screen.getByText("stale")).toBeInTheDocument();
  });

  it("renders an orphaned array answer item by item", () => {
    render(
      <AnswersSection
        submission={{
          answers: { q1: "Yes", q8: ["Remote", "Hybrid"] },
          formSchema: { questions: QUESTIONS },
        }}
      />,
    );
    expect(screen.getByText("q8")).toBeInTheDocument();
    expect(screen.getByText("Remote")).toBeInTheDocument();
    expect(screen.getByText("Hybrid")).toBeInTheDocument();
  });

  it("renders an orphaned object answer as JSON, not [object Object]", () => {
    render(
      <AnswersSection
        submission={{
          answers: { q1: "Yes", q8: { nested: true } },
          formSchema: { questions: QUESTIONS },
        }}
      />,
    );
    expect(screen.getByText("q8")).toBeInTheDocument();
    expect(screen.getByText(/"nested": true/)).toBeInTheDocument();
    expect(screen.queryByText(/\[object Object\]/)).not.toBeInTheDocument();
  });

  it("groups an other-option free text with its own question", () => {
    render(
      <AnswersSection
        submission={{
          answers: { q4: "Other", q4__other: "One day on-site" },
          formSchema: {
            questions: [
              {
                id: "q4",
                type: "single_choice",
                label: "Work mode",
                options: ["Remote", "Other"],
                otherOption: "Other",
              },
            ],
          },
        }}
      />,
    );
    expect(screen.getByText("One day on-site")).toBeInTheDocument();
    expect(screen.queryByText("q4__other")).not.toBeInTheDocument();
    expect(
      screen.queryByText("Other recorded answers"),
    ).not.toBeInTheDocument();
  });

  it("keeps a stale other-option answer visible after the selection moves away", () => {
    render(
      <AnswersSection
        submission={{
          answers: { q4: "Remote", q4__other: "One day on-site" },
          formSchema: {
            questions: [
              {
                id: "q4",
                type: "single_choice",
                label: "Work mode",
                options: ["Remote", "Other"],
                otherOption: "Other",
              },
            ],
          },
        }}
      />,
    );
    expect(screen.getByText("Other recorded answers")).toBeInTheDocument();
    expect(screen.getByText("q4__other")).toBeInTheDocument();
    expect(screen.getByText("One day on-site")).toBeInTheDocument();
  });

  it("renders nothing when submission is null", () => {
    const { container } = render(
      <AnswersSection submission={null} liveQuestions={[]} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("namespaces DOM ids with idPrefix", () => {
    const { container } = render(
      <AnswersSection
        submission={{
          answers: { q5: "Remote" },
          formSchema: {
            questions: [
              {
                id: "q5",
                type: "single_choice",
                label: "Work mode",
                options: ["Remote"],
              },
            ],
          },
        }}
        idPrefix="other-201-"
      />,
    );
    expect(
      container.querySelector('input[name="other-201-q5"]'),
    ).toBeInTheDocument();
  });
});
