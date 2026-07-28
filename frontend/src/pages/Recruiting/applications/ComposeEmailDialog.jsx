import { useEffect, useRef, useState } from "react";
import DOMPurify from "dompurify";
import { getApplicationEmailTemplates } from "@/api/recruitingApi";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const splitAddresses = (value) =>
  value
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);

/**
 * Markup a candidate email body may carry. Deliberately narrow: the composer
 * authors rich text, and what leaves here has to survive Gmail's own
 * sanitizing anyway, so anything structural (tables, images, styles) or
 * active (script, iframe, event handlers) is dropped rather than sent.
 */
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

/** Attributes kept on the allowed tags — enough for a working hyperlink. */
const EMAIL_ALLOWED_ATTR = ["href", "target", "rel"];

/** Sanitize composer HTML down to the tags Gmail bodies are allowed to carry. */
const sanitizeEmailHtml = (html) =>
  DOMPurify.sanitize(html, {
    ALLOWED_TAGS: EMAIL_ALLOWED_TAGS,
    ALLOWED_ATTR: EMAIL_ALLOWED_ATTR,
  });

/**
 * Compose (or reply to) a candidate email. Recipients/Cc are comma-separated
 * text so the recruiter can add or drop addresses; the body is sent as HTML.
 *
 * @param {{open: boolean, onOpenChange: (open: boolean) => void,
 *          applicationId: number|string,
 *          defaultTo: string|null, defaultCc: string[]|null,
 *          replyThread: {threadId: number, subject: string,
 *                        defaultCc?: string[]}|null,
 *          onSend: (payload: {to: string[], cc: string[], subject: string,
 *                             body: string, threadId: number|null})
 *                  => Promise<unknown>,
 *          sending: boolean}} props
 */
const ComposeEmailDialog = ({
  open,
  onOpenChange,
  applicationId,
  defaultTo,
  defaultCc,
  replyThread,
  onSend,
  sending,
}) => {
  const [to, setTo] = useState("");
  const [cc, setCc] = useState("");
  const [subject, setSubject] = useState("");
  const editorRef = useRef(null);
  // Whether the editor holds any text, tracked in state so the Send button
  // can react to it — an uncontrolled contenteditable gives us no other
  // render-time signal.
  const [hasText, setHasText] = useState(false);
  const [templates, setTemplates] = useState([]);
  // A template the sender picked while the body already had text — held
  // here until the overwrite confirmation is resolved.
  const [pendingTemplate, setPendingTemplate] = useState(null);
  // Drives the Select as a controlled component so its displayed label only
  // ever reflects a template that was actually applied — not merely clicked.
  // Left stale (i.e. never speculatively set) while a pick is pending
  // confirmation, so Cancel needs no extra reset and re-picking the same
  // template after a Cancel still registers as a value change to Radix.
  const [selectedTemplateKey, setSelectedTemplateKey] = useState("");

  useEffect(() => {
    if (!open) return;
    setTo(defaultTo ?? "");
    // Prefill (but keep editable) Cc: the thread's prior Cc on a reply,
    // otherwise the recruiter's own address for a new email.
    const prefillCc = replyThread?.defaultCc ?? defaultCc ?? [];
    setCc(prefillCc.join(", "));
    const base = replyThread?.subject ?? "";
    setSubject(
      replyThread ? (base.startsWith("Re:") ? base : `Re: ${base}`) : "",
    );
    // The body is uncontrolled on purpose: re-rendering a contenteditable
    // from state on every keystroke resets the caret. We write into it
    // imperatively (dialog open, and later a template) and read innerHTML
    // back on send.
    if (editorRef.current) editorRef.current.innerHTML = "";
    setHasText(false);
    setPendingTemplate(null);
    setSelectedTemplateKey("");
  }, [open, defaultTo, defaultCc, replyThread]);

  useEffect(() => {
    if (!open) return;
    getApplicationEmailTemplates(applicationId).then(
      (res) => setTemplates(res?.data ?? []),
      () => setTemplates([]),
    );
  }, [open, applicationId]);

  /** Write a template into the composer. Reply keeps its `Re:` subject (B4). */
  const applyTemplate = (template) => {
    if (!replyThread) setSubject(template.subject);
    if (editorRef.current) {
      editorRef.current.innerHTML = sanitizeEmailHtml(template.bodyHtml);
      setHasText(Boolean(editorRef.current.textContent?.trim()));
    }
    setSelectedTemplateKey(template.key);
  };

  const handleTemplatePick = (key) => {
    const template = templates.find((t) => t.key === key);
    if (!template) return;
    if (editorRef.current?.textContent?.trim()) {
      setPendingTemplate(template);
      return;
    }
    applyTemplate(template);
  };

  const handleSubmit = () => {
    if (sending) return;
    const recipients = splitAddresses(to);
    const html = sanitizeEmailHtml(editorRef.current?.innerHTML ?? "");
    if (recipients.length === 0 || !subject.trim() || !hasText) return;
    onSend({
      to: recipients,
      cc: splitAddresses(cc),
      subject: subject.trim(),
      body: html,
      threadId: replyThread?.threadId ?? null,
    }).then(
      () => onOpenChange(false),
      () => {},
    );
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
            <Select
              value={selectedTemplateKey}
              onValueChange={handleTemplatePick}
            >
              <SelectTrigger id="email-template" aria-label="Template">
                <SelectValue placeholder="Start from a template (optional)" />
              </SelectTrigger>
              <SelectContent>
                {templates.map((t) => (
                  <SelectItem key={t.key} value={t.key}>
                    {t.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
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
              className="min-h-40 max-h-96 overflow-y-auto rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring [&_a]:underline [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5"
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
            disabled={sending || !hasText}
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
    </>
  );
};

export default ComposeEmailDialog;
