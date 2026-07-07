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

  it("forwards the raw file to onFile as soon as it passes the PDF check", async () => {
    parseResumeFromPdf.mockResolvedValue(PARSED);
    const onParsed = vi.fn();
    const onFile = vi.fn();
    const file = pdfFile();
    render(<ResumeUpload onParsed={onParsed} onFile={onFile} />);

    selectFile(file);

    expect(onFile).toHaveBeenCalledWith(file);
    await waitFor(() => expect(onParsed).toHaveBeenCalledWith(PARSED));
  });

  it("does not call onFile for a rejected non-PDF file", () => {
    const onFile = vi.fn();
    render(<ResumeUpload onParsed={vi.fn()} onFile={onFile} />);

    selectFile(txtFile());

    expect(onFile).not.toHaveBeenCalled();
  });
});

describe("ResumeUpload with showPreview", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    parseResumeFromPdf.mockResolvedValue(PARSED);
  });

  it("shows a compact filename row and an iframe preview after a valid pick", async () => {
    render(<ResumeUpload onParsed={vi.fn()} showPreview />);
    selectFile(pdfFile());

    const iframe = screen.getByTitle("Preview of resume.pdf");
    expect(iframe.getAttribute("src")).toMatch(/^blob:/);
    await waitFor(() =>
      expect(screen.getByText(/resume\.pdf · Change/)).toBeInTheDocument(),
    );
  });

  it("does not show a preview when showPreview is unset (default behavior unchanged)", async () => {
    render(<ResumeUpload onParsed={vi.fn()} />);
    selectFile(pdfFile());
    await waitFor(() => expect(parseResumeFromPdf).toHaveBeenCalled());
    expect(screen.queryByTitle(/Preview of/)).not.toBeInTheDocument();
  });

  it("shows 'Parsing…' next to the filename while the parse is in flight, then 'Change'", async () => {
    let resolveParse;
    parseResumeFromPdf.mockReturnValue(
      new Promise((resolve) => {
        resolveParse = resolve;
      }),
    );
    render(<ResumeUpload onParsed={vi.fn()} showPreview />);
    selectFile(pdfFile());

    expect(screen.getByText(/resume\.pdf · Parsing…/)).toBeInTheDocument();
    resolveParse(PARSED);
    await waitFor(() =>
      expect(screen.getByText(/resume\.pdf · Change/)).toBeInTheDocument(),
    );
  });

  it("revokes the previous blob URL and shows the new file when replaced", async () => {
    const revokeSpy = vi.spyOn(URL, "revokeObjectURL");
    render(<ResumeUpload onParsed={vi.fn()} showPreview />);
    selectFile(pdfFile());
    await waitFor(() =>
      expect(screen.getByText(/resume\.pdf · Change/)).toBeInTheDocument(),
    );
    const firstSrc = screen
      .getByTitle("Preview of resume.pdf")
      .getAttribute("src");

    const secondFile = new File(["%PDF-1.4"], "other.pdf", {
      type: "application/pdf",
    });
    selectFile(secondFile);

    await waitFor(() =>
      expect(screen.getByText(/other\.pdf · Change/)).toBeInTheDocument(),
    );
    expect(revokeSpy).toHaveBeenCalledWith(firstSrc);
    expect(
      screen.getByTitle("Preview of other.pdf").getAttribute("src"),
    ).not.toBe(firstSrc);
  });

  it("keeps the existing preview and shows the error when a later pick is not a PDF", async () => {
    render(<ResumeUpload onParsed={vi.fn()} showPreview />);
    selectFile(pdfFile());
    await waitFor(() =>
      expect(screen.getByText(/resume\.pdf · Change/)).toBeInTheDocument(),
    );

    selectFile(txtFile());

    expect(screen.getByText("Please upload a PDF file.")).toBeInTheDocument();
    expect(screen.getByText(/resume\.pdf · Change/)).toBeInTheDocument();
  });

  it("ignores a second file dropped onto the preview row while a parse is already in flight", async () => {
    let resolveFirstParse;
    parseResumeFromPdf.mockReturnValue(
      new Promise((resolve) => {
        resolveFirstParse = resolve;
      }),
    );
    const onParsed = vi.fn();
    render(<ResumeUpload onParsed={onParsed} showPreview />);
    selectFile(pdfFile());
    expect(screen.getByText(/resume\.pdf · Parsing…/)).toBeInTheDocument();

    const secondFile = new File(["%PDF-1.4"], "other.pdf", {
      type: "application/pdf",
    });
    selectFile(secondFile);

    // The second pick was ignored: still showing the first file, and
    // parseResumeFromPdf was never called a second time.
    expect(screen.getByText(/resume\.pdf · Parsing…/)).toBeInTheDocument();
    expect(parseResumeFromPdf).toHaveBeenCalledTimes(1);

    resolveFirstParse(PARSED);
    await waitFor(() => expect(onParsed).toHaveBeenCalledTimes(1));
  });

  it("revokes the current blob URL on unmount", async () => {
    const revokeSpy = vi.spyOn(URL, "revokeObjectURL");
    const { unmount } = render(<ResumeUpload onParsed={vi.fn()} showPreview />);
    selectFile(pdfFile());
    await waitFor(() =>
      expect(screen.getByText(/resume\.pdf · Change/)).toBeInTheDocument(),
    );
    const src = screen.getByTitle("Preview of resume.pdf").getAttribute("src");

    unmount();

    expect(revokeSpy).toHaveBeenCalledWith(src);
  });
});
