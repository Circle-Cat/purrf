import { useState } from "react";
import { ImageOff } from "lucide-react";
import { Button } from "@/components/ui/button";
import { EMAIL_BODY_BOX_CLASS, sanitizeEmailBody } from "@/utils/emailHtml";

// Mail bodies are foreign HTML, and Tailwind's preflight zeroes <p> margins,
// drops list markers and strips link underlines; without these hooks a message
// reads as one dense block whose links look like plain text.
const HTML_BODY_CLASS = `max-w-none ${EMAIL_BODY_BOX_CLASS} [&_a]:underline [&_ol]:list-decimal [&_ol]:pl-5 [&_p]:my-3 [&_ul]:list-disc [&_ul]:pl-5`;

/**
 * The body of one stored message: its HTML when it has any, its plain text
 * otherwise.
 *
 * Remote images and backgrounds stay unloaded until the reader asks for them,
 * as mail clients do, because loading them tells the sender the message was
 * opened, when, and from which address. The choice holds for this message
 * while it stays on screen.
 *
 * @param {{html?: string | null, text?: string | null, className?: string}} props
 *   `className` is added to the body whichever form it takes.
 */
export default function EmailBody({ html, text, className = "" }) {
  const [loadRemoteContent, setLoadRemoteContent] = useState(false);

  if (!html) {
    return <p className={`whitespace-pre-wrap ${className}`}>{text ?? ""}</p>;
  }

  const sanitized = sanitizeEmailBody(html, { loadRemoteContent });
  return (
    <div className={className}>
      {sanitized.remoteContentBlocked && (
        <div
          role="status"
          className="mb-2 flex flex-wrap items-center justify-between gap-2 rounded border border-slate-200 bg-slate-50 px-2 py-1 text-xs text-slate-600"
        >
          <span className="flex items-center gap-1.5">
            <ImageOff size={12} />
            Images are hidden so the sender cannot tell this was opened.
          </span>
          <Button
            type="button"
            variant="link"
            size="sm"
            className="h-auto p-0 text-xs"
            onClick={() => setLoadRemoteContent(true)}
          >
            Show images
          </Button>
        </div>
      )}
      <div
        className={HTML_BODY_CLASS}
        dangerouslySetInnerHTML={{ __html: sanitized.html }}
      />
    </div>
  );
}
