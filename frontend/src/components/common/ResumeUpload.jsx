import { useEffect, useRef, useState } from "react";
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
 * When `onFile` is provided, it's invoked synchronously with the raw
 * `File` as soon as it passes the PDF check (before parsing), so a caller
 * can kick off something else with the original file -- e.g. uploading it
 * -- independent of, and without waiting on, the in-browser parse.
 *
 * When `showPreview` is true, a valid pick replaces the dropzone with a
 * compact "<filename> · Change" row plus a same-session `<iframe>` preview
 * of the file (via `URL.createObjectURL`). Picking a new file (via Change
 * or drag-and-drop onto the row) revokes the previous blob URL before
 * building the new one; the current blob URL is also revoked on unmount.
 * Defaults to `false`, so existing render-only usages (the Profile page's
 * resume upload) are unaffected.
 *
 * When `onRemove` is provided (preview mode), a "Remove" control is offered
 * next to "Change": it revokes the blob URL, clears the preview back to the
 * empty dropzone, resets the file input (so the same file can be re-picked),
 * and calls `onRemove` — letting the caller drop its stored résumé reference.
 *
 * @param {{ onParsed: (parsed: object) => void, onFile?: (file: File) => void,
 *          onRemove?: () => void, showPreview?: boolean }} props
 * @returns {JSX.Element}
 */
export default function ResumeUpload({
  onParsed,
  onFile,
  onRemove,
  showPreview = false,
}) {
  const inputRef = useRef(null);
  const [error, setError] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const [isParsing, setIsParsing] = useState(false);
  const [preview, setPreview] = useState(null); // { url, name } | null
  const previewUrlRef = useRef(null);

  useEffect(() => {
    return () => {
      if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
    };
  }, []);

  const handleFile = async (file) => {
    if (!file || isParsing) return;
    const isPdf =
      file.type === PDF_TYPE || file.name.toLowerCase().endsWith(".pdf");
    if (!isPdf) {
      setError("Please upload a PDF file.");
      return;
    }
    setError("");
    if (showPreview) {
      if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
      const url = URL.createObjectURL(file);
      previewUrlRef.current = url;
      setPreview({ url, name: file.name });
    }
    onFile?.(file);
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

  const handleRemove = () => {
    if (previewUrlRef.current) {
      URL.revokeObjectURL(previewUrlRef.current);
      previewUrlRef.current = null;
    }
    setPreview(null);
    setError("");
    if (inputRef.current) inputRef.current.value = "";
    onRemove?.();
  };

  const dragHandlers = {
    onDragOver: (e) => {
      e.preventDefault();
      setDragOver(true);
    },
    onDragLeave: () => setDragOver(false),
    onDrop: (e) => {
      e.preventDefault();
      setDragOver(false);
      handleFile(e.dataTransfer.files?.[0]);
    },
  };

  return (
    <div className="mx-auto max-w-xl">
      {preview ? (
        <div
          className={cn(
            "rounded-lg border-2 border-dashed p-2 transition-colors",
            dragOver
              ? "border-primary bg-primary/5"
              : "border-muted-foreground/30",
          )}
          {...dragHandlers}
        >
          <div className="flex items-center gap-3">
            <button
              type="button"
              disabled={isParsing}
              onClick={() => inputRef.current?.click()}
              className="text-sm font-medium text-slate-700 hover:underline disabled:opacity-70"
            >
              {preview.name} · {isParsing ? "Parsing…" : "Change"}
            </button>
            {onRemove && (
              <button
                type="button"
                disabled={isParsing}
                onClick={handleRemove}
                className="text-sm font-medium text-destructive hover:underline disabled:opacity-70"
              >
                Remove
              </button>
            )}
          </div>
          <iframe
            src={preview.url}
            title={`Preview of ${preview.name}`}
            className="mt-2 h-[400px] w-full rounded border"
          />
        </div>
      ) : (
        <button
          type="button"
          disabled={isParsing}
          onClick={() => inputRef.current?.click()}
          {...dragHandlers}
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
              <Loader2 className="h-6 w-6 animate-spin" aria-hidden />
              <span>Parsing…</span>
            </>
          ) : (
            <>
              <UploadCloud
                className="h-6 w-6 text-muted-foreground"
                aria-hidden
              />
              <span className="font-medium">
                Click or drag a resume PDF here
              </span>
              <span className="text-sm text-muted-foreground">
                Text-based PDF only (English, single-column)
              </span>
            </>
          )}
        </button>
      )}
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
