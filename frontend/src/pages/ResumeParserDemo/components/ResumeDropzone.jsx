import { useRef, useState } from "react";
import { UploadCloud, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

const PDF_TYPE = "application/pdf";

/**
 * Click-or-drag area to pick a single PDF resume. Validates the file is a PDF
 * and calls onFile(file); otherwise shows an inline error. While isParsing is
 * true it shows a spinner and ignores input.
 *
 * @param {{ onFile: (file: File) => void, isParsing?: boolean }} props
 */
export default function ResumeDropzone({ onFile, isParsing = false }) {
  const inputRef = useRef(null);
  const [error, setError] = useState("");
  const [dragOver, setDragOver] = useState(false);

  const handleFile = (file) => {
    if (!file) return;
    const isPdf =
      file.type === PDF_TYPE || file.name.toLowerCase().endsWith(".pdf");
    if (!isPdf) {
      setError("请上传 PDF 文件。");
      return;
    }
    setError("");
    onFile(file);
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
            <span>解析中…</span>
          </>
        ) : (
          <>
            <UploadCloud
              className="h-8 w-8 text-muted-foreground"
              aria-hidden
            />
            <span className="font-medium">点击或拖拽简历 PDF 到这里</span>
            <span className="text-sm text-muted-foreground">
              仅支持文本型 PDF（英文、单栏）
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
