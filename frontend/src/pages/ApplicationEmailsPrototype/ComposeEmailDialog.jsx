import { useEffect, useRef, useState } from "react";
import DOMPurify from "dompurify";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";

const splitAddresses = (value) =>
  value
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);

const EMAIL_ALLOWED_TAGS = [
  "p",
  "br",
  "b",
  "strong",
  "i",
  "em",
  "u",
  "ul",
  "ol",
  "li",
  "a",
];

const EMAIL_ALLOWED_ATTR = ["href", "target", "rel"];

const sanitizeEmailHtml = (html) =>
  DOMPurify.sanitize(html, {
    ALLOWED_TAGS: EMAIL_ALLOWED_TAGS,
    ALLOWED_ATTR: EMAIL_ALLOWED_ATTR,
  });

const BRACKET_RE = /\[[A-Z0-9][A-Z0-9 /]*\]/g;

/**
 * `mark` is absent from EMAIL_ALLOWED_TAGS, so sanitizing on send drops the
 * highlight and keeps the text.
 */
const highlightBrackets = (html) =>
  html.replace(BRACKET_RE, (marker) => `<mark>${marker}</mark>`);

const countUnfilledBrackets = (text) => (text.match(BRACKET_RE) ?? []).length;

/**
 * ComposeEmailDialog
 *
 * The real compose/reply dialog, reproduced: To and Cc as comma-separated
 * text, a template picker, a rich-text body with `[UPPERCASE]` markers
 * highlighted, and the overwrite and unfilled-placeholder confirmations. This
 * prototype adds a read-only From line naming the alias the mail goes out
 * from. Cc is prefilled from `replyThread.defaultCc` on a reply, otherwise
 * from `defaultCc`.
 *
 * The template picker is a native select here (the product uses a Radix
 * Select), so it can be driven in jsdom; it is held at "" so every pick is an
 * action, exactly like the real one.
 *
 * @param {{open: boolean, onOpenChange: Function, fromAlias: string,
 *   defaultTo: string|null, defaultCc: string[]|null,
 *   replyThread: {threadId: number, subject: string, defaultCc?: string[]}|null,
 *   templates: object[], signatureHtml: string,
 *   onSend: Function, sending: boolean}} props
 * @returns {JSX.Element}
 */
const ComposeEmailDialog = ({
  open,
  onOpenChange,
  fromAlias,
  defaultTo,
  defaultCc,
  replyThread,
  templates,
  signatureHtml,
  onSend,
  sending,
}) => {
  const [to, setTo] = useState("");
  const [cc, setCc] = useState("");
  const [subject, setSubject] = useState("");
  const editorRef = useRef(null);
  const [hasText, setHasText] = useState(false);
  const [pendingTemplate, setPendingTemplate] = useState(null);
  const [appliedTemplateLabel, setAppliedTemplateLabel] = useState("");
  const [unfilledCount, setUnfilledCount] = useState(0);
  const prefilledRef = useRef("");

  const isUntouchedPrefill = () =>
    prefilledRef.current !== "" &&
    editorRef.current?.innerHTML === prefilledRef.current;

  useEffect(() => {
    if (!open) return;
    setTo(defaultTo ?? "");
    const prefillCc = replyThread?.defaultCc ?? defaultCc ?? [];
    setCc(prefillCc.join(", "));
    const base = replyThread?.subject ?? "";
    setSubject(
      replyThread ? (base.startsWith("Re:") ? base : `Re: ${base}`) : "",
    );
    if (editorRef.current) {
      editorRef.current.innerHTML = signatureHtml
        ? highlightBrackets(signatureHtml)
        : "";
      prefilledRef.current = editorRef.current.innerHTML;
    } else {
      prefilledRef.current = "";
    }
    setHasText(false);
    setPendingTemplate(null);
    setAppliedTemplateLabel("");
    setUnfilledCount(0);
  }, [open, defaultTo, defaultCc, replyThread, signatureHtml]);

  const applyTemplate = (template) => {
    if (!replyThread) setSubject(template.subject);
    if (editorRef.current) {
      editorRef.current.innerHTML = highlightBrackets(
        sanitizeEmailHtml(template.bodyHtml),
      );
      setHasText(Boolean(editorRef.current.textContent?.trim()));
    }
    prefilledRef.current = "";
    setAppliedTemplateLabel(template.label);
  };

  const handleTemplatePick = (key) => {
    const template = templates.find((t) => t.key === key);
    if (!template) return;
    if (editorRef.current?.textContent?.trim() && !isUntouchedPrefill()) {
      setPendingTemplate(template);
      return;
    }
    applyTemplate(template);
  };

  const doSend = () => {
    if (sending) return;
    onSend({
      from: fromAlias,
      to: splitAddresses(to),
      cc: splitAddresses(cc),
      subject: subject.trim(),
      body: sanitizeEmailHtml(editorRef.current?.innerHTML ?? ""),
      threadId: replyThread?.threadId ?? null,
    }).then(
      () => {
        setUnfilledCount(0);
        onOpenChange(false);
      },
      () => {},
    );
  };

  const canSend =
    splitAddresses(to).length > 0 && Boolean(subject.trim()) && hasText;

  const handleSubmit = () => {
    if (sending || !canSend) return;
    const remaining = countUnfilledBrackets(
      editorRef.current?.textContent ?? "",
    );
    if (remaining > 0) {
      setUnfilledCount(remaining);
      return;
    }
    doSend();
  };

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{replyThread ? "Reply" : "Send email"}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1">
              <div className="text-sm font-medium">From</div>
              <p
                aria-label="From"
                className="rounded-md border border-slate-200 bg-slate-50 px-3 py-1.5 text-sm text-slate-700"
              >
                {fromAlias}
              </p>
            </div>
            <div className="space-y-1">
              <Label htmlFor="email-to">To</Label>
              <Input
                id="email-to"
                value={to}
                onChange={(e) => setTo(e.target.value)}
                placeholder="candidate@example.com"
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="email-cc">Cc</Label>
              <Input
                id="email-cc"
                value={cc}
                onChange={(e) => setCc(e.target.value)}
                placeholder="Comma-separated (optional)"
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="email-subject">Subject</Label>
              <Input
                id="email-subject"
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="email-template">Template</Label>
              <select
                id="email-template"
                aria-label="Template"
                value=""
                onChange={(e) => handleTemplatePick(e.target.value)}
                className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm text-muted-foreground"
              >
                <option value="">Start from a template (optional)</option>
                {templates.map((t) => (
                  <option key={t.key} value={t.key}>
                    {t.label}
                  </option>
                ))}
              </select>
              {appliedTemplateLabel ? (
                <p className="text-xs text-muted-foreground">
                  {`Applied: ${appliedTemplateLabel}`}
                </p>
              ) : null}
            </div>
            <div className="space-y-1">
              <Label htmlFor="email-body">Message</Label>
              <div
                id="email-body"
                ref={editorRef}
                role="textbox"
                aria-label="Message"
                aria-multiline="true"
                contentEditable
                suppressContentEditableWarning
                onInput={() =>
                  setHasText(Boolean(editorRef.current?.textContent?.trim()))
                }
                className="min-h-40 max-h-96 overflow-y-auto rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring [&_a]:underline [&_mark]:bg-yellow-200 [&_ol]:list-decimal [&_ol]:pl-5 [&_p]:my-3 [&_ul]:list-disc [&_ul]:pl-5"
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button
              type="button"
              onClick={handleSubmit}
              disabled={sending || !canSend}
            >
              Send
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <Dialog
        open={pendingTemplate !== null}
        onOpenChange={() => setPendingTemplate(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Replace the current message?</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Applying this template will replace what you have written.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setPendingTemplate(null)}>
              Cancel
            </Button>
            <Button
              onClick={() => {
                applyTemplate(pendingTemplate);
                setPendingTemplate(null);
              }}
            >
              Replace
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <Dialog
        open={unfilledCount > 0}
        onOpenChange={(next) => {
          if (!next && sending) return;
          setUnfilledCount(0);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Unfilled placeholders</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            {`This message still has ${unfilledCount} ${
              unfilledCount === 1 ? "placeholder" : "placeholders"
            } in square brackets. Send it anyway?`}
          </p>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setUnfilledCount(0)}
              disabled={sending}
            >
              Keep editing
            </Button>
            <Button onClick={doSend} disabled={sending}>
              Send anyway
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
};

export default ComposeEmailDialog;
