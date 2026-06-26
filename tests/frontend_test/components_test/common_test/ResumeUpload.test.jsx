import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

import ResumeUpload from "@/components/common/ResumeUpload";
import { parseResumeFromPdf } from "@/lib/resume-parser";

vi.mock("@/lib/resume-parser", () => ({
  parseResumeFromPdf: vi.fn(),
}));

const PARSED = {
  user: { firstName: "Ann", lastName: "Liu" },
  education: [],
  workHistory: [],
  projects: [],
  unmapped: {},
};

const EMPTY = {
  user: {},
  education: [],
  workHistory: [],
  projects: [],
  unmapped: {},
};

const pdfFile = () =>
  new File(["%PDF-1.4"], "resume.pdf", { type: "application/pdf" });
const txtFile = () => new File(["hi"], "note.txt", { type: "text/plain" });

const selectFile = (file) =>
  fireEvent.change(screen.getByTestId("resume-file-input"), {
    target: { files: [file] },
  });

describe("ResumeUpload", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the upload prompt", () => {
    render(<ResumeUpload onParsed={vi.fn()} />);
    expect(screen.getByText(/drag a resume PDF/i)).toBeInTheDocument();
  });

  it("rejects a non-PDF file without parsing or calling onParsed", () => {
    const onParsed = vi.fn();
    render(<ResumeUpload onParsed={onParsed} />);

    selectFile(txtFile());

    expect(parseResumeFromPdf).not.toHaveBeenCalled();
    expect(onParsed).not.toHaveBeenCalled();
    expect(screen.getByText("Please upload a PDF file.")).toBeInTheDocument();
  });

  it("parses a PDF and forwards the parsed result to onParsed", async () => {
    parseResumeFromPdf.mockResolvedValue(PARSED);
    const onParsed = vi.fn();
    const file = pdfFile();
    render(<ResumeUpload onParsed={onParsed} />);

    selectFile(file);

    expect(parseResumeFromPdf).toHaveBeenCalledWith(file);
    await waitFor(() => expect(onParsed).toHaveBeenCalledWith(PARSED));
  });

  it("shows a parsing indicator while the parse is in flight", async () => {
    let resolveParse;
    parseResumeFromPdf.mockReturnValue(
      new Promise((resolve) => {
        resolveParse = resolve;
      }),
    );
    const onParsed = vi.fn();
    render(<ResumeUpload onParsed={onParsed} />);

    selectFile(pdfFile());

    expect(screen.getByText(/Parsing/)).toBeInTheDocument();
    resolveParse(PARSED);
    await waitFor(() => expect(onParsed).toHaveBeenCalledWith(PARSED));
  });

  it("falls back to an empty parsed result when parsing fails", async () => {
    parseResumeFromPdf.mockRejectedValue(new Error("worker failed"));
    const onParsed = vi.fn();
    render(<ResumeUpload onParsed={onParsed} />);

    selectFile(pdfFile());

    await waitFor(() => expect(onParsed).toHaveBeenCalledWith(EMPTY));
  });
});
