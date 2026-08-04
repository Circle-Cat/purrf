import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { toast } from "sonner";
import RecruitingProfileForm from "@/pages/Recruiting/components/RecruitingProfileForm";
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
vi.spyOn(toast, "error").mockImplementation(() => {});

beforeEach(() => vi.clearAllMocks());

const renderForm = (profileConfig, extraProps) =>
  render(
    <RecruitingProfileForm profileConfig={profileConfig} {...extraProps} />,
  );

const pdfFile = () =>
  new File(["%PDF-1.4"], "resume.pdf", { type: "application/pdf" });

const selectResumeFile = (file) =>
  fireEvent.change(screen.getByTestId("resume-file-input"), {
    target: { files: [file] },
  });

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

  it("fills the contact email field from the contactEmail prop", () => {
    renderForm({}, { contactEmail: "cand@x.com" });
    const email = screen.getByLabelText("Contact email");
    expect(email).toHaveValue("cand@x.com");
    expect(email).toHaveAttribute("readonly");
  });

  it("uploads a chosen resume and forwards {sha256, objectKey} via onResumeStored", async () => {
    api.uploadResume.mockResolvedValue({
      data: { sha256: "abc123", objectKey: "resumes/abc123.pdf" },
    });
    const onResumeStored = vi.fn();
    renderForm({}, { onResumeStored });

    selectResumeFile(pdfFile());

    await waitFor(() =>
      expect(onResumeStored).toHaveBeenCalledWith({
        sha256: "abc123",
        objectKey: "resumes/abc123.pdf",
      }),
    );
  });

  it("shows a résumé preview after picking a file (showPreview wired through)", async () => {
    renderForm({});
    selectResumeFile(pdfFile());
    await waitFor(() =>
      expect(screen.getByTitle("Preview of resume.pdf")).toBeInTheDocument(),
    );
  });

  it("does not render the résumé-on-file banner when existingResume is not provided", () => {
    renderForm({});
    expect(
      screen.queryByText(/on file from your previous application/i),
    ).not.toBeInTheDocument();
  });

  it("renders the résumé-on-file banner and expands to show the iframe", () => {
    api.resumeUrl.mockImplementation(
      (id) => `/api/recruiting/applications/${id}/resume`,
    );
    renderForm({}, { existingResume: { applicationId: 7 } });

    expect(
      screen.getByText(/on file from your previous application/i),
    ).toBeInTheDocument();
    expect(screen.queryByTitle("Your résumé on file")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Expand" }));
    expect(screen.getByTitle("Your résumé on file")).toHaveAttribute(
      "src",
      "/api/recruiting/applications/7/resume",
    );

    fireEvent.click(screen.getByRole("button", { name: "Collapse" }));
    expect(screen.queryByTitle("Your résumé on file")).not.toBeInTheDocument();
  });

  it("clears the stored résumé via onResumeStored(nulls) when the on-file résumé is removed", () => {
    api.resumeUrl.mockImplementation(
      (id) => `/api/recruiting/applications/${id}/resume`,
    );
    const onResumeStored = vi.fn();
    renderForm({}, { existingResume: { applicationId: 7 }, onResumeStored });

    fireEvent.click(screen.getByRole("button", { name: "Remove" }));

    expect(onResumeStored).toHaveBeenCalledWith({
      sha256: null,
      objectKey: null,
    });
  });

  it("clears the stored résumé via onResumeStored(nulls) when a session-uploaded résumé is removed", async () => {
    api.uploadResume.mockResolvedValue({
      data: { sha256: "abc123", objectKey: "resumes/abc123.pdf" },
    });
    const onResumeStored = vi.fn();
    renderForm({}, { onResumeStored });

    selectResumeFile(pdfFile());
    await waitFor(() =>
      expect(screen.getByText(/resume\.pdf · Change/)).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByRole("button", { name: "Remove" }));

    expect(onResumeStored).toHaveBeenLastCalledWith({
      sha256: null,
      objectKey: null,
    });
  });

  it("toasts an error and does not call onResumeStored when the resume upload fails", async () => {
    api.uploadResume.mockRejectedValue(new Error("upload failed"));
    const onResumeStored = vi.fn();
    renderForm({}, { onResumeStored });

    selectResumeFile(pdfFile());

    await waitFor(() => expect(api.uploadResume).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(toast.error).toHaveBeenCalled());
    expect(onResumeStored).not.toHaveBeenCalled();
  });

  it("does not call uploadResume when onResumeStored is not provided", async () => {
    renderForm({});
    selectResumeFile(pdfFile());
    expect(api.uploadResume).not.toHaveBeenCalled();
    // Let the (mocked) parse settle so its state update lands inside `act`.
    await waitFor(() =>
      expect(screen.queryByText(/Parsing/i)).not.toBeInTheDocument(),
    );
  });

  it("does not upload the resume when the posting does not collect one", async () => {
    const onResumeStored = vi.fn();
    renderForm({ resume: "off" }, { onResumeStored });

    selectResumeFile(pdfFile());

    // Let the (mocked) parse settle so its state update lands inside `act`.
    await waitFor(() =>
      expect(screen.queryByText(/Parsing/i)).not.toBeInTheDocument(),
    );
    expect(api.uploadResume).not.toHaveBeenCalled();
    expect(onResumeStored).not.toHaveBeenCalled();
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

  it("tells optional-resume applicants the upload is saved", () => {
    renderForm({ resume: "optional" });
    expect(
      screen.getByText(/the file you upload is saved with your application/i),
    ).toBeInTheDocument();
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
