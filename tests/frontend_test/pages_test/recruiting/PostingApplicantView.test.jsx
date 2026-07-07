import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import PostingApplicantView from "@/pages/Recruiting/components/PostingApplicantView";
import * as api from "@/api/recruitingApi";

vi.mock("@/api/recruitingApi");
vi.mock("@/lib/resume-parser", () => ({
  parseResumeFromPdf: vi.fn().mockResolvedValue({
    user: {},
    education: [],
    workHistory: [],
    projects: [],
    unmapped: {},
  }),
}));

const questions = [
  {
    id: "q1",
    type: "single_choice",
    label: "Referred?",
    options: ["yes", "no"],
  },
  {
    id: "q2",
    type: "short_text",
    label: "Referrer name",
    showWhen: { questionId: "q1", equals: "yes" },
  },
];

describe("PostingApplicantView", () => {
  it("renders title, kind, description, profile form and the questions", () => {
    render(
      <PostingApplicantView
        title="SWE Intern"
        kind="employment"
        description="Great role."
        questions={questions}
        profileConfig={{ resume: "required" }}
      />,
    );
    expect(
      screen.getByRole("heading", { name: "SWE Intern" }),
    ).toBeInTheDocument();
    expect(screen.getByText("employment")).toBeInTheDocument();
    expect(screen.getByText("Great role.")).toBeInTheDocument();
    expect(screen.getByText("Profile")).toBeInTheDocument();
    expect(screen.getByText("Contact email")).toBeInTheDocument();
    expect(
      screen.getByRole("radiogroup", { name: "Referred?" }),
    ).toBeInTheDocument();
  });

  it("threads contactEmail into the profile form's read-only email field", () => {
    render(
      <PostingApplicantView
        title="T"
        questions={questions}
        contactEmail="cand@x.com"
      />,
    );
    const email = screen.getByLabelText("Contact email");
    expect(email).toHaveValue("cand@x.com");
    expect(email).toHaveAttribute("readonly");
  });

  it("threads onResumeStored into the profile form's resume upload", async () => {
    api.uploadResume.mockResolvedValue({
      data: { sha256: "s", objectKey: "k" },
    });
    const onResumeStored = vi.fn();
    render(
      <PostingApplicantView
        title="T"
        questions={questions}
        onResumeStored={onResumeStored}
      />,
    );
    fireEvent.change(screen.getByTestId("resume-file-input"), {
      target: {
        files: [new File(["%PDF-1.4"], "r.pdf", { type: "application/pdf" })],
      },
    });
    await waitFor(() =>
      expect(onResumeStored).toHaveBeenCalledWith({
        sha256: "s",
        objectKey: "k",
      }),
    );
  });

  it("threads existingResume into the profile form's résumé-on-file banner", () => {
    render(
      <PostingApplicantView
        title="T"
        questions={questions}
        existingResume={{ applicationId: 7 }}
      />,
    );
    expect(
      screen.getByText(/on file from your previous application/i),
    ).toBeInTheDocument();
  });

  it("reveals a showWhen question when its dependency is answered (throwaway state)", () => {
    render(<PostingApplicantView title="T" questions={questions} />);
    expect(screen.queryByLabelText("Referrer name")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("radio", { name: "yes" }));
    expect(screen.getByLabelText("Referrer name")).toBeInTheDocument();
  });

  it("lifts profile value and answers to a parent when controlled props are provided", () => {
    const onProfileChange = vi.fn();
    const onAnswerChange = vi.fn();
    const profileValue = {
      personal: { firstName: "Ada" },
      education: [],
      experience: [],
    };
    render(
      <PostingApplicantView
        title="T"
        questions={questions}
        profileValue={profileValue}
        onProfileChange={onProfileChange}
        answers={{ q1: "yes" }}
        onAnswerChange={onAnswerChange}
      />,
    );
    expect(screen.getByDisplayValue("Ada")).toBeInTheDocument();
    // Controlled `answers` already reveals the showWhen-dependent question.
    expect(screen.getByLabelText("Referrer name")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("radio", { name: "no" }));
    expect(onAnswerChange).toHaveBeenCalledWith("q1", "no");
  });

  it("emits profile changes on field edit when controlled", () => {
    const onProfileChange = vi.fn();
    const profileValue = {
      personal: { firstName: "Sam" },
      education: [],
      experience: [],
    };
    render(
      <PostingApplicantView
        title="T"
        questions={questions}
        profileValue={profileValue}
        onProfileChange={onProfileChange}
      />,
    );
    fireEvent.change(screen.getByLabelText("First name"), {
      target: { value: "Casey" },
    });
    expect(onProfileChange).toHaveBeenCalledWith(
      expect.objectContaining({
        personal: expect.objectContaining({ firstName: "Casey" }),
      }),
    );
  });
});
