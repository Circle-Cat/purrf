import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
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

/**
 * Turn the composer's plain text into safe HTML (escape, keep line breaks).
 * The body is stored/sent as HTML; authoring stays plain text for the MVP.
 */
const plainTextToHtml = (text) =>
  text
    .split("\n")
    .map((line) =>
      line.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"),
    )
    .join("<br>");

/**
 * Compose (or reply to) a candidate email. Recipients/Cc are comma-separated
 * text so the recruiter can add or drop addresses; the body is sent as HTML.
 *
 * @param {{open: boolean, onOpenChange: (open: boolean) => void,
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
  defaultTo,
  defaultCc,
  replyThread,
  onSend,
  sending,
}) => {
  const [to, setTo] = useState("");
  const [cc, setCc] = useState("");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");

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
    setBody("");
  }, [open, defaultTo, defaultCc, replyThread]);

  const handleSubmit = () => {
    if (sending) return;
    const recipients = splitAddresses(to);
    if (recipients.length === 0 || !subject.trim() || !body.trim()) return;
    onSend({
      to: recipients,
      cc: splitAddresses(cc),
      subject: subject.trim(),
      body: plainTextToHtml(body),
      threadId: replyThread?.threadId ?? null,
    }).then(
      () => onOpenChange(false),
      () => {},
    );
  };

  return (
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
            <Label htmlFor="email-body">Message</Label>
            <Textarea
              id="email-body"
              value={body}
              onChange={(e) => setBody(e.target.value)}
              rows={8}
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
          <Button type="button" onClick={handleSubmit} disabled={sending}>
            Send
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default ComposeEmailDialog;
