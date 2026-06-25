import { useState } from "react";
import { parseResumeFromPdf } from "@/lib/resume-parser";
import ResumeDropzone from "./components/ResumeDropzone";
import ConfirmationForm from "./components/ConfirmationForm";
import ParsedResultView from "./components/ParsedResultView";

const EMPTY = {
  user: { firstName: "", lastName: "" },
  education: [],
  workHistory: [],
  unmapped: {},
};

/**
 * Standalone demo page: upload a resume PDF, confirm the parsed fields, then
 * view the confirmed structured result. Front-end only; nothing is persisted.
 */
export default function ResumeParserDemo() {
  const [phase, setPhase] = useState("upload"); // "upload" | "confirm" | "result"
  const [isParsing, setIsParsing] = useState(false);
  const [parsed, setParsed] = useState(EMPTY);
  const [confirmed, setConfirmed] = useState(null);

  const handleFile = async (file) => {
    setIsParsing(true);
    let result;
    try {
      result = await parseResumeFromPdf(file);
    } catch {
      result = EMPTY;
    }
    setParsed(result ?? EMPTY);
    setIsParsing(false);
    setPhase("confirm");
  };

  const handleConfirm = (data) => {
    setConfirmed(data);
    setPhase("result");
  };

  const reset = () => {
    setParsed(EMPTY);
    setConfirmed(null);
    setPhase("upload");
  };

  return (
    <div className="p-6">
      <h1 className="mb-2 text-2xl font-semibold">简历解析演示</h1>
      <p className="mb-6 text-sm text-muted-foreground">
        上传一份英文、单栏、文本型 PDF
        简历，系统会尝试预填下面的表单。全程在浏览器本地完成，不上传服务器。
      </p>
      {phase === "upload" && (
        <ResumeDropzone onFile={handleFile} isParsing={isParsing} />
      )}
      {phase === "confirm" && (
        <ConfirmationForm initial={parsed} onConfirm={handleConfirm} />
      )}
      {phase === "result" && (
        <ParsedResultView data={confirmed} onReset={reset} />
      )}
    </div>
  );
}
