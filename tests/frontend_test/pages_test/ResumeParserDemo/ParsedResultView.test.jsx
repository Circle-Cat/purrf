import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { describe, it, expect, vi, afterEach } from "vitest";
import "@testing-library/jest-dom/vitest";
import ParsedResultView from "@/pages/ResumeParserDemo/components/ParsedResultView";

afterEach(cleanup);

const data = {
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
};

describe("ParsedResultView", () => {
  it("renders the confirmed data", () => {
    render(<ParsedResultView data={data} onReset={() => {}} />);
    expect(screen.getByText("Jane Doe")).toBeInTheDocument();
    // Exact strings match only the summary <li>, not the JSON <pre> blob.
    expect(
      screen.getByText("Stanford University · Bachelor · CS"),
    ).toBeInTheDocument();
    expect(screen.getByText("Engineer @ Acme")).toBeInTheDocument();
    expect(screen.getByTestId("result-json")).toHaveTextContent(
      "Stanford University",
    );
  });

  it("fires onReset when 重新上传 is clicked", () => {
    const onReset = vi.fn();
    render(<ParsedResultView data={data} onReset={onReset} />);
    fireEvent.click(screen.getByRole("button", { name: "重新上传" }));
    expect(onReset).toHaveBeenCalledTimes(1);
  });
});
