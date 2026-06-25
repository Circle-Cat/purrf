import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { describe, it, expect, vi, afterEach } from "vitest";
import "@testing-library/jest-dom/vitest";
import ResumeDropzone from "@/pages/ResumeParserDemo/components/ResumeDropzone";

afterEach(cleanup);

const pdfFile = (name = "resume.pdf") =>
  new File(["%PDF-1.4"], name, { type: "application/pdf" });

describe("ResumeDropzone", () => {
  it("calls onFile when a PDF is chosen", () => {
    const onFile = vi.fn();
    render(<ResumeDropzone onFile={onFile} />);
    fireEvent.change(screen.getByTestId("resume-file-input"), {
      target: { files: [pdfFile()] },
    });
    expect(onFile).toHaveBeenCalledTimes(1);
  });

  it("rejects a non-PDF and shows an error", () => {
    const onFile = vi.fn();
    render(<ResumeDropzone onFile={onFile} />);
    const txt = new File(["x"], "resume.txt", { type: "text/plain" });
    fireEvent.change(screen.getByTestId("resume-file-input"), {
      target: { files: [txt] },
    });
    expect(onFile).not.toHaveBeenCalled();
    expect(screen.getByText(/请上传 PDF/)).toBeInTheDocument();
  });

  it("shows a spinner while parsing", () => {
    render(<ResumeDropzone onFile={() => {}} isParsing />);
    expect(screen.getByText("解析中…")).toBeInTheDocument();
  });
});
