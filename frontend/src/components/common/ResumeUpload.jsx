import { useRef, useState } from "react";
import { UploadCloud, Loader2 } from "lucide-react";

import { cn } from "@/lib/utils";
import { parseResumeFromPdf } from "@/lib/resume-parser";

const PDF_TYPE = "application/pdf";

/** Shape handed back when parsing fails, so callers always get a ParsedResume. */
const EMPTY_PARSED = {
  user: {},
  education: [],
  workHistory: [],
  projects: [],
  unmapped: {},
};

/**
 * Reusable click-or-drag area to pick a single PDF resume, parse it in the
 * browser, and hand the raw `ParsedResume` to the caller via `onParsed`. It
 * owns only upload + parse + a parsing indicator — mapping/merging the result
 * into a form is the caller's concern (see `parsedResumeToProfile`).
 *
 * Non-PDF input is rejected inline without parsing. Parsing never surfaces an
 * error to the caller: a failure yields an empty `ParsedResume`.
 *
 * @param {{ onParsed: (parsed: object) => void }} props
 * @returns {JSX.Element}
 */
export default function ResumeUpload({ onParsed }) {
  const inputRef = useRef(null);
  const [error, setError] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const [isParsing, setIsParsing] = useState(false);

  const handleFile = async (file) => {
    if (!file) return;
    const isPdf =
      file.type === PDF_TYPE || file.name.toLowerCase().endsWith(".pdf");
    if (!isPdf) {
      setError("Please upload a PDF file.");
      return;
    }
    setError("");
    setIsParsing(true);
    let result;
    try {
      result = await parseResumeFromPdf(file);
    } catch {
      result = EMPTY_PARSED;
    }
    setIsParsing(false);
    onParsed(result ?? EMPTY_PARSED);
  };

  return (
    <div className="mx-auto max-w-xl">
      <button
        type="button"
        disabled={isParsing}
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          handleFile(e.dataTransfer.files?.[0]);
        }}
        className={cn(
          "flex w-full flex-col items-center gap-3 rounded-lg border-2 border-dashed p-10 text-center transition-colors",
          dragOver
            ? "border-primary bg-primary/5"
            : "border-muted-foreground/30",
          isParsing && "pointer-events-none opacity-70",
        )}
      >
        {isParsing ? (
          <>
            <Loader2 className="h-8 w-8 animate-spin" aria-hidden />
            <span>Parsing…</span>
          </>
        ) : (
          <>
            <UploadCloud
              className="h-8 w-8 text-muted-foreground"
              aria-hidden
            />
            <span className="font-medium">Click or drag a resume PDF here</span>
            <span className="text-sm text-muted-foreground">
              Text-based PDF only (English, single-column)
            </span>
          </>
        )}
      </button>
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf,.pdf"
        className="hidden"
        data-testid="resume-file-input"
        onChange={(e) => handleFile(e.target.files?.[0])}
      />
      {error && <p className="mt-2 text-sm text-destructive">{error}</p>}
    </div>
  );
}
