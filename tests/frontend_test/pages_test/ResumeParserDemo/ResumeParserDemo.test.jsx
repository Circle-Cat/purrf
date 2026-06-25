import {
  render,
  screen,
  fireEvent,
  cleanup,
  waitFor,
} from "@testing-library/react";
import { describe, it, expect, vi, afterEach } from "vitest";
import "@testing-library/jest-dom/vitest";
import ResumeParserDemo from "@/pages/ResumeParserDemo";

vi.mock("@/lib/resume-parser", () => ({
  parseResumeFromPdf: vi.fn(async () => ({
    user: {
      firstName: "Jane",
      lastName: "Doe",
      timezoneSuggestion: "America/Los_Angeles",
    },
    education: [
      { school: "Stanford University", degree: "Bachelor", fieldOfStudy: "CS" },
    ],
    workHistory: [
      { title: "Engineer", companyOrOrganization: "Acme", isCurrentJob: true },
    ],
    unmapped: { summary: "A summary." },
  })),
}));

// Heavy leaf — stub it (the form imports it).
vi.mock("@/components/common/TimezoneSelector", () => ({
  default: ({ value, onChange }) => (
    <input
      data-testid="tz"
      value={value || ""}
      onChange={(e) => onChange({ value: e.target.value })}
    />
  ),
}));

afterEach(cleanup);

describe("ResumeParserDemo (integration)", () => {
  it("walks upload → confirm → result", async () => {
    render(<ResumeParserDemo />);
    const file = new File(["%PDF-1.4"], "resume.pdf", {
      type: "application/pdf",
    });
    fireEvent.change(screen.getByTestId("resume-file-input"), {
      target: { files: [file] },
    });
    // After parse, the confirm form pre-fills.
    await waitFor(() =>
      expect(screen.getByLabelText(/First name/)).toHaveValue("Jane"),
    );
    fireEvent.click(screen.getByRole("button", { name: "确认" }));
    // Result view shows the name and JSON.
    expect(screen.getByText("Jane Doe")).toBeInTheDocument();
    expect(screen.getByTestId("result-json")).toHaveTextContent(
      "Stanford University",
    );
  });
});
