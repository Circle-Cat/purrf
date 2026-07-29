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

/**
 * The value the template Select is permanently held at. Radix documents "" as
 * "no selection, show the placeholder" (react-select@2.2.6 forbids it as an
 * item value for exactly that reason), and because the committed value never
 * moves off "", every pick — including re-picking the template already
 * applied — differs from it and so survives the controlled-setter guard in
 * react-use-controllable-state@1.2.2 that only forwards onValueChange when
 * `next !== prop`. Picking a template is an action, not a value; what was
 * applied is reported as adjacent text instead.
 */
const TEMPLATE_PICKER_VALUE = "";

/** Sanitize composer HTML down to the tags Gmail bodies are allowed to carry. */
const sanitizeEmailHtml = (html) =>
  DOMPurify.sanitize(html, {
    ALLOWED_TAGS: EMAIL_ALLOWED_TAGS,
    ALLOWED_ATTR: EMAIL_ALLOWED_ATTR,
  });

/**
 * Matches the free-text `[UPPERCASE]` markers templates leave for the sender
 * to fill in. Every character inside the brackets must be an uppercase
 * letter, digit, space, or `/` (the only punctuation real markers use) —
 * requiring the whole marker to be uppercase, not just its first letter,
 * keeps ordinary bracketed prose like "[See attached resume]" or
 * "[Re: interview]" from tripping the unfilled-placeholder warning.
 */
const BRACKET_RE = /\[[A-Z0-9][A-Z0-9 /]*\]/g;

/**
 * Wrap `[UPPERCASE]` markers in <mark> so the sender can see what still needs
 * filling in. `mark` is deliberately absent from EMAIL_ALLOWED_TAGS, so
 * sanitizing on send drops the tag and keeps the text — the candidate never
 * sees highlight markup.
 */
const highlightBrackets = (html) =>
  html.replace(BRACKET_RE, (marker) => `<mark>${marker}</mark>`);

/** How many `[UPPERCASE]` markers the sender has not replaced yet. */
const countUnfilledBrackets = (text) => (text.match(BRACKET_RE) ?? []).length;

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
  // Label of the template last actually applied, shown as text beside the
  // picker. It is NOT the Select's value: the Select is held at "" so that
  // picking is a pure action (see TEMPLATE_PICKER_VALUE above), which leaves
  // the trigger permanently on its placeholder and no way for it to claim a
  // template that was only clicked — or one whose overwrite prompt was
  // cancelled — was applied.
  const [appliedTemplateLabel, setAppliedTemplateLabel] = useState("");
  // Count of unfilled `[UPPERCASE]` markers found at Send time; >0 opens the
  // soft-warning confirmation dialog below.
  const [unfilledCount, setUnfilledCount] = useState(0);
  // Exactly the HTML we prefilled the body with, or "". An untouched prefill is
  // not the sender's draft: picking a template over it must not ask to
  // overwrite, and Send must not treat a lone signature as a written message.
  const prefilledRef = useRef("");

  /** Whether the body still holds nothing but the signature we put there. */
  const isUntouchedPrefill = () =>
    prefilledRef.current !== "" &&
    editorRef.current?.innerHTML === prefilledRef.current;

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
    prefilledRef.current = "";
    setHasText(false);
    setPendingTemplate(null);
    setAppliedTemplateLabel("");
    setUnfilledCount(0);
  }, [open, defaultTo, defaultCc, replyThread]);

  useEffect(() => {
    if (!open) return;
    getApplicationEmailTemplates(applicationId).then(
      (res) => {
        setTemplates(res?.data?.templates ?? []);
        // Prefill the signature so a message written from scratch — or any
        // reply, which never applies a template — still goes out signed. The
        // fetch is async, so only prefill a body the sender has not started
        // writing in; otherwise a slow response would wipe their draft.
        const signature = res?.data?.signatureHtml ?? "";
        if (!signature || !editorRef.current) return;
        if (editorRef.current.textContent?.trim()) return;
        editorRef.current.innerHTML = signature;
        prefilledRef.current = signature;
      },
      () => setTemplates([]),
    );
  }, [open, applicationId]);

  /** Write a template into the composer. Reply keeps its `Re:` subject (B4). */
  const applyTemplate = (template) => {
    if (!replyThread) setSubject(template.subject);
    if (editorRef.current) {
      editorRef.current.innerHTML = highlightBrackets(
        sanitizeEmailHtml(template.bodyHtml),
      );
      setHasText(Boolean(editorRef.current.textContent?.trim()));
    }
    // The template carries its own signature, so the prefill is gone.
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

  /**
   * Send the message as-is. Called directly, or after the unfilled-marker
   * warning is confirmed — guarded on `sending` itself (not just at its two
   * call sites) so a fast double-click on "Send anyway" can't fire a second
   * send while the first is still in flight.
   */
  const doSend = () => {
    if (sending) return;
    const recipients = splitAddresses(to);
    onSend({
      to: recipients,
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

  /**
   * Everything `handleSubmit` requires. It is the Send button's `disabled`
   * condition too: handleSubmit returns silently — no toast, no field error —
   * so anything it rejects has to read as a disabled button rather than a dead
   * click. A candidate with no contact email (`defaultTo: null`) is the real
   * case: a template fills the body and subject and leaves To empty.
   */
  const canSend =
    splitAddresses(to).length > 0 && Boolean(subject.trim()) && hasText;

  const handleSubmit = () => {
    if (sending) return;
    if (!canSend) return;
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
                value={TEMPLATE_PICKER_VALUE}
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
              {appliedTemplateLabel ? (
                <p className="text-xs text-muted-foreground">
                  {`Applied: ${appliedTemplateLabel}`}
                </p>
              ) : null}
            </div>
            <div className="space-y-1">
              <Label htmlFor="email-body">Message</Label>
              {/* [&_p] is load-bearing: Tailwind's preflight zeroes p margins,
                  so without it an applied template collapses into a single
                  block here even though the mail goes out correctly spaced. */}
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
                className="min-h-40 max-h-96 overflow-y-auto rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring [&_a]:underline [&_ol]:list-decimal [&_ol]:pl-5 [&_p]:my-3 [&_ul]:list-disc [&_ul]:pl-5"
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
          // Escape / backdrop click route through here too, not just the
          // footer buttons — block dismissal the same way while a send from
          // "Send anyway" is in flight, so it can't be sidestepped.
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
