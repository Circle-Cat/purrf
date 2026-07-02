import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import RecruitingProfileForm from "@/pages/Recruiting/components/RecruitingProfileForm";

const renderForm = (profileConfig) =>
  render(<RecruitingProfileForm profileConfig={profileConfig} />);

describe("RecruitingProfileForm", () => {
  it("renders a read-only, empty contact email placeholder (filled from the applicant's account on submission)", () => {
    renderForm({});
    const email = screen.getByLabelText("Contact email");
    expect(email).toHaveValue("");
    expect(email).toHaveAttribute("readonly");
    expect(email).toHaveAttribute(
      "placeholder",
      "Auto-filled from the applicant's account",
    );
  });

  it("always renders basic info even when every section is off", () => {
    renderForm({ education: "off", workExperience: "off", resume: "off" });
    expect(screen.getByLabelText("First name")).toBeInTheDocument();
  });

  it("shows the resume quick-fill upload with prefill copy even when resume is off", () => {
    renderForm({ resume: "off" });
    // Upload is always offered as a prefill helper, regardless of config.
    expect(
      screen.getByRole("heading", { name: /resume/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/upload it to auto-fill the sections below/i),
    ).toBeInTheDocument();
    // When off, it's flagged as a time-saver that isn't collected.
    expect(screen.getByText(/doesn't collect a resume/i)).toBeInTheDocument();
  });

  it("shows the resume upload (no off-note) when resume is required", () => {
    renderForm({ resume: "required" });
    expect(
      screen.getByRole("heading", { name: /resume/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/upload it to auto-fill the sections below/i),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/doesn't collect a resume/i),
    ).not.toBeInTheDocument();
  });

  it("renders the education block with an entry and add control when required", () => {
    renderForm({ education: "required" });
    expect(
      screen.getByRole("heading", { name: /education/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Add education" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/School/)).toBeInTheDocument();
  });

  it("hides the education block when education is off", () => {
    renderForm({ education: "off" });
    expect(
      screen.queryByRole("heading", { name: /education/i }),
    ).not.toBeInTheDocument();
  });

  it("renders the work-experience block with an add control when required", () => {
    renderForm({ workExperience: "required" });
    expect(
      screen.getByRole("heading", { name: /experience/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Add experience" }),
    ).toBeInTheDocument();
  });

  it("reflects controlled value", () => {
    const onChange = vi.fn();
    const value = {
      personal: { firstName: "Zed" },
      education: [],
      experience: [],
    };
    render(
      <RecruitingProfileForm
        profileConfig={{
          education: "optional",
          workExperience: "optional",
          resume: "off",
        }}
        value={value}
        onChange={onChange}
      />,
    );
    expect(screen.getByDisplayValue("Zed")).toBeInTheDocument();
  });

  it("emits changes on field edit when controlled", () => {
    const onChange = vi.fn();
    const value = {
      personal: { firstName: "Zed" },
      education: [],
      experience: [],
    };
    render(
      <RecruitingProfileForm
        profileConfig={{
          education: "optional",
          workExperience: "optional",
          resume: "off",
        }}
        value={value}
        onChange={onChange}
      />,
    );
    fireEvent.change(screen.getByLabelText("First name"), {
      target: { value: "Ada" },
    });
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({
        personal: expect.objectContaining({ firstName: "Ada" }),
      }),
    );
  });
});
