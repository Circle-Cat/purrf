import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { describe, it, expect, vi, afterEach } from "vitest";
import "@testing-library/jest-dom/vitest";
import ConfirmationForm from "@/pages/ResumeParserDemo/components/ConfirmationForm";

// react-timezone-select is heavy in jsdom — replace with a plain input.
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

const seed = {
  user: {
    firstName: "Jane",
    lastName: "Doe",
    phone: "(123) 456-7890",
    linkedinLink: "linkedin.com/in/janedoe",
    timezoneSuggestion: "America/Los_Angeles",
  },
  education: [
    {
      school: "Stanford University",
      degree: "Bachelor",
      fieldOfStudy: "CS",
      startDate: "2016-01-01",
      endDate: "2020-01-01",
    },
  ],
  workHistory: [
    {
      title: "Engineer",
      companyOrOrganization: "Acme",
      startDate: "2020-01-01",
      endDate: null,
      isCurrentJob: true,
    },
  ],
  projects: [{ name: "Resume Parser", startDate: "2024-01-01", endDate: null }],
  unmapped: { summary: "A summary." },
};

describe("ConfirmationForm", () => {
  it("pre-fills fields from the parsed result", () => {
    render(<ConfirmationForm initial={seed} onConfirm={() => {}} />);
    expect(screen.getByLabelText(/First name/)).toHaveValue("Jane");
    expect(screen.getByLabelText(/Last name/)).toHaveValue("Doe");
    expect(screen.getByDisplayValue("Stanford University")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Acme")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Resume Parser")).toBeInTheDocument();
  });

  it("emits edited data on confirm, with no _key and no email", () => {
    const onConfirm = vi.fn();
    render(<ConfirmationForm initial={seed} onConfirm={onConfirm} />);
    fireEvent.change(screen.getByLabelText(/First name/), {
      target: { value: "Janet" },
    });
    fireEvent.click(screen.getByRole("button", { name: "确认" }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
    const data = onConfirm.mock.calls[0][0];
    expect(data.user.firstName).toBe("Janet");
    expect(data.education[0].school).toBe("Stanford University");
    expect(JSON.stringify(data)).not.toContain("_key");
    expect(JSON.stringify(data)).not.toContain("@");
  });

  it("adds and removes an education row", () => {
    render(<ConfirmationForm initial={seed} onConfirm={() => {}} />);
    expect(screen.getAllByLabelText("学校")).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: "添加教育" }));
    expect(screen.getAllByLabelText("学校")).toHaveLength(2);
    fireEvent.click(screen.getAllByRole("button", { name: "删除" })[0]);
    expect(screen.getAllByLabelText("学校")).toHaveLength(1);
  });

  it("shows a hint when the parsed result is empty", () => {
    render(
      <ConfirmationForm
        initial={{ user: {}, education: [], workHistory: [], unmapped: {} }}
        onConfirm={() => {}}
      />,
    );
    expect(screen.getByText(/请手动填写/)).toBeInTheDocument();
  });
});
