import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  cancelEmailSend,
  confirmEmailSend,
  createEmailSend,
  listKitDrafts,
  refreshEmailPreview,
} from "@/api/mentorshipEmailApi";
import { formatInTz } from "@/utils/dateTime";
import { MEETING_TIMEZONE } from "../../utils/attendanceIssues";
import PreviewFrame from "./PreviewFrame";
import { pacificToUtcIso } from "./sendTime";
import { STAGE_OPTIONS, stageLabel } from "./emailLabels";

const MIN_LEAD_MS = 30 * 60 * 1000;
const fieldClass = "h-9 rounded-md border bg-background px-2 text-sm";

const defaultSendTime = () => {
  const iso = new Date(Date.now() + 60 * 60 * 1000).toISOString();
  return {
    date: formatInTz(iso, MEETING_TIMEZONE, "yyyy-MM-dd"),
    time: formatInTz(iso, MEETING_TIMEZONE, "HH:mm"),
  };
};

const errorText = (e) => e?.response?.data?.message ?? e?.message;

function SendTimeInputs({ sendAt, setSendAt, tooSoon }) {
  return (
    <div className="space-y-1">
      <div className="flex flex-wrap items-center gap-2">
        <input
          type="date"
          aria-label="Send date"
          className={fieldClass}
          value={sendAt.date}
          onChange={(e) => setSendAt((s) => ({ ...s, date: e.target.value }))}
        />
        <input
          type="time"
          aria-label="Send time"
          className={fieldClass}
          value={sendAt.time}
          onChange={(e) => setSendAt((s) => ({ ...s, time: e.target.value }))}
        />
        <span className="text-sm text-muted-foreground">
          Pacific Time (America/Los_Angeles)
        </span>
      </div>
      {tooSoon && (
        <p className="text-sm text-red-600">
          Pick a time at least 30 minutes from now.
        </p>
      )}
    </div>
  );
}

function PreviewSection({ preview, stage }) {
  return (
    <div className="space-y-2">
      <div className="text-sm">
        <div>
          <span className="font-medium">Subject:</span> {preview.subject}
        </div>
        <div>
          <span className="font-medium">From:</span> {preview.senderAddress}
        </div>
        <div>{preview.recipientCount} recipients</div>
      </div>
      {preview.noEmail.length > 0 && (
        <p className="text-sm text-muted-foreground">
          No email address for user{preview.noEmail.length > 1 ? "s" : ""}{" "}
          {preview.noEmail.map((r) => r.userId).join(", ")}.
        </p>
      )}
      {preview.recentlySentUserIds.length > 0 && (
        <p className="text-sm text-amber-700">
          {preview.recentlySentUserIds.length} of them already got a{" "}
          {stageLabel(stage)} email for this round in the last 7 days.
        </p>
      )}
      {preview.invalidHrefs.length > 0 && (
        <div className="text-sm text-red-600">
          <p>These links in the draft are not valid:</p>
          <ul className="list-disc pl-5">
            {preview.invalidHrefs.map((h) => (
              <li key={h}>{h}</li>
            ))}
          </ul>
        </div>
      )}
      {!preview.filterOk && (
        <p className="text-sm text-red-600">
          The recipients or sender of this draft were changed in Kit.
        </p>
      )}
      <PreviewFrame html={preview.html} />
    </div>
  );
}

/**
 * Sends a Kit notification to people picked in the Participants card. The
 * first step picks the stage and the Kit draft and creates the send; the
 * second shows the preview with its checks and schedules it for a Pacific
 * time at least 30 minutes ahead. Closing the dialog after the send was
 * created but before it was confirmed cancels the send (failures are only
 * logged). The dialog starts over every time it opens.
 *
 * @param {{
 *   open: boolean,
 *   onOpenChange: (open: boolean) => void,
 *   roundId: number|string, the round the people were listed in
 *   recipients: Array<{userId: number, name: string}>,
 *   defaultStage?: string, the stage selected when the dialog opens
 *   onScheduled: (sendAtIso: string) => void, called after Confirm succeeds, before closing
 * }} props
 */
export default function SendNotificationDialog({
  open,
  onOpenChange,
  roundId,
  recipients,
  defaultStage = "",
  onScheduled,
}) {
  const [drafts, setDrafts] = useState([]);
  const [stage, setStage] = useState(defaultStage);
  const [draftId, setDraftId] = useState("");
  const [send, setSend] = useState(null);
  const [preview, setPreview] = useState(null);
  const [sendAt, setSendAt] = useState(defaultSendTime); // Pacific Time
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!open) return undefined;
    let cancelled = false;
    setDrafts([]);
    setStage(defaultStage);
    setDraftId("");
    setSend(null);
    setPreview(null);
    setSendAt(defaultSendTime());
    setBusy(false);
    setError(null);
    listKitDrafts()
      .then((rows) => {
        if (!cancelled) setDrafts(rows ?? []);
      })
      .catch((e) => {
        if (!cancelled) setError(errorText(e));
      });
    return () => {
      cancelled = true;
    };
    // defaultStage only seeds the form when the dialog opens.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const loadPreview = async (sendId) => {
    setBusy(true);
    setError(null);
    try {
      setPreview(await refreshEmailPreview(sendId));
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  const create = async () => {
    setBusy(true);
    setError(null);
    let created;
    try {
      created = await createEmailSend({
        roundId: Number(roundId),
        stage,
        kitDraftId: drafts.find((d) => String(d.id) === draftId).id,
        userIds: recipients.map((r) => r.userId),
      });
      setSend(created);
    } catch (e) {
      setError(errorText(e));
      setBusy(false);
      return;
    }
    await loadPreview(created.sendId);
  };

  const sendAtIso = useMemo(() => {
    try {
      return pacificToUtcIso(sendAt.date, sendAt.time);
    } catch {
      return null;
    }
  }, [sendAt]);
  const tooSoon =
    !sendAtIso || new Date(sendAtIso).getTime() < Date.now() + MIN_LEAD_MS;

  // An error from Create belongs to the stage and draft it was made with, so
  // it stays, and Create stays off, until one of them changes.
  const canCreate =
    stage && draftId && recipients.length > 0 && !busy && !error;
  const canConfirm =
    !!preview &&
    preview.filterOk &&
    preview.invalidHrefs.length === 0 &&
    !tooSoon &&
    !busy;

  const confirm = async () => {
    setBusy(true);
    setError(null);
    try {
      await confirmEmailSend(send.sendId, {
        sendAt: sendAtIso,
        previewToken: preview.previewToken,
      });
    } catch (e) {
      setError(errorText(e));
      setBusy(false);
      return;
    }
    setBusy(false);
    onScheduled(sendAtIso);
    onOpenChange(false);
  };

  const close = () => {
    if (send) {
      cancelEmailSend(send.sendId).catch((e) =>
        console.error("Failed to cancel the notification send", e),
      );
    }
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={(next) => !next && !busy && close()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-4xl">
        <DialogHeader>
          <DialogTitle>Send notification</DialogTitle>
          <DialogDescription>
            To {recipients.length}{" "}
            {recipients.length === 1 ? "person" : "people"}
          </DialogDescription>
        </DialogHeader>
        <p className="max-h-24 overflow-y-auto text-sm">
          {recipients.map((r) => r.name).join(", ")}
        </p>

        {send == null ? (
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1">
              <label
                htmlFor="notification-stage"
                className="text-sm font-medium"
              >
                Stage
              </label>
              <select
                id="notification-stage"
                className={fieldClass}
                value={stage}
                onChange={(e) => {
                  setStage(e.target.value);
                  setError(null);
                }}
              >
                <option value="">Select a stage</option>
                {STAGE_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1">
              <label
                htmlFor="notification-draft"
                className="text-sm font-medium"
              >
                Kit draft
              </label>
              <select
                id="notification-draft"
                className={fieldClass}
                value={draftId}
                onChange={(e) => {
                  setDraftId(e.target.value);
                  setError(null);
                }}
              >
                <option value="">Select a draft</option>
                {drafts.map((d) => (
                  <option
                    key={d.id}
                    value={String(d.id)}
                    disabled={Boolean(d.problem)}
                  >
                    {d.problem
                      ? `${d.subject || "(no subject)"} — can't send: ${d.problem}`
                      : d.subject}
                  </option>
                ))}
              </select>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="text-sm text-muted-foreground">
              {stageLabel(send.stage)} · {send.kitDraftSubject}
            </div>
            {preview ? (
              <PreviewSection preview={preview} stage={send.stage} />
            ) : busy ? (
              <p className="text-sm text-muted-foreground">Loading preview…</p>
            ) : (
              <Button
                variant="outline"
                onClick={() => loadPreview(send.sendId)}
              >
                Try the preview again
              </Button>
            )}
            <SendTimeInputs
              sendAt={sendAt}
              setSendAt={setSendAt}
              tooSoon={tooSoon}
            />
          </div>
        )}

        {error && (
          <p role="alert" className="text-sm text-red-600">
            {error}
          </p>
        )}

        <div className="flex justify-end gap-2">
          <Button variant="outline" disabled={busy} onClick={close}>
            Cancel
          </Button>
          {send == null ? (
            <Button onClick={create} disabled={!canCreate}>
              {busy ? "Creating…" : "Create"}
            </Button>
          ) : (
            <Button onClick={confirm} disabled={!canConfirm}>
              Confirm
            </Button>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
