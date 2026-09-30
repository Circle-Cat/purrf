import { useMemo, useRef, useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import ComposeEmailDialog from "@/pages/ApplicationEmailsPrototype/ComposeEmailDialog";
import EmailsPanel from "@/pages/ApplicationEmailsPrototype/EmailsPanel";
import {
  needsReply,
  replyCcOf,
  senderAliasOf,
  templatesFor,
} from "@/pages/ApplicationEmailsPrototype/emailState";
import { INITIAL_APPLICATIONS } from "@/pages/ApplicationEmailsPrototype/mockData";

/** Stable, so the composer's prefill effect doesn't rerun on every render. */
const NO_DEFAULT_CC = [];

const CHANGES = [
  {
    title: "From line in the composer",
    detail:
      "Compose and Reply show a read-only From: mentor and mentee postings send from mentorship@circlecat.org, employment postings from recruiting@circlecat.org.",
  },
  {
    title: "No default Cc to yourself",
    detail:
      "A new email starts with an empty Cc. A reply still prefills the thread's earlier Cc, without the candidate or our aliases.",
  },
  {
    title: "From and To on every message",
    detail:
      "Each message names the address it came from and the one it went to, so you can see which alias was used.",
  },
  {
    title: "Auto-replies and bounces",
    detail:
      "Out-of-office replies and delivery failures are tagged and dimmed. A bounce raises a banner until something is sent after it.",
  },
  {
    title: "Needs reply",
    detail:
      "A thread whose last message from a person is newer than our last reply says Needs reply, and so does the Emails tab. Replying clears it.",
  },
];

const WhatChanged = () => {
  const [open, setOpen] = useState(true);
  const Icon = open ? ChevronDown : ChevronRight;
  return (
    <section className="rounded-lg border border-violet-200 bg-violet-50">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 px-4 py-2 text-left text-sm font-medium text-violet-900"
      >
        <Icon size={16} />
        What changed vs today
      </button>
      {open && (
        <ol className="list-decimal space-y-1 px-4 pb-3 pl-9 text-sm text-violet-900">
          {CHANGES.map((c) => (
            <li key={c.title}>
              <span className="font-medium">{c.title}.</span> {c.detail}
            </li>
          ))}
        </ol>
      )}
    </section>
  );
};

/**
 * ApplicationEmailsPrototype
 *
 * The Emails tab of an application's detail page and its compose/reply
 * dialog, reproduced from the real page with five proposed changes applied.
 * The frame around it is only enough to switch between applications. Sending
 * appends to local state; refreshing the page resets everything.
 *
 * @returns {JSX.Element}
 */
const ApplicationEmailsPrototype = () => {
  const [applications, setApplications] = useState(INITIAL_APPLICATIONS);
  const [currentId, setCurrentId] = useState(INITIAL_APPLICATIONS[0].id);
  const [composeOpen, setComposeOpen] = useState(false);
  const [replyThread, setReplyThread] = useState(null);
  const [refreshed, setRefreshed] = useState(false);
  const nextId = useRef(1);

  const application = applications.find((a) => a.id === currentId);
  const anyNeedsReply = application.threads.some(needsReply);
  const { templates, signatureHtml } = useMemo(
    () => templatesFor(application),
    [application],
  );
  const fromAlias = senderAliasOf(application.job);

  const openCompose = () => {
    setReplyThread(null);
    setComposeOpen(true);
  };

  const openReply = (thread) => {
    setReplyThread({
      threadId: thread.threadId,
      subject: thread.subject,
      defaultCc: replyCcOf(thread, application.applicant.email),
    });
    setComposeOpen(true);
  };

  const handleSend = (payload) => {
    const n = nextId.current++;
    const message = {
      messageId: `local-${n}`,
      direction: "outbound",
      fromAddress: payload.from,
      to: payload.to,
      cc: payload.cc,
      kind: "human",
      gmailInternalDate: new Date(
        Date.parse("2026-09-30T17:00:00Z") + n * 60000,
      ).toISOString(),
      bodyHtml: payload.body,
    };
    setApplications((prev) =>
      prev.map((a) => {
        if (a.id !== currentId) return a;
        if (payload.threadId != null) {
          return {
            ...a,
            threads: a.threads.map((t) =>
              t.threadId === payload.threadId
                ? { ...t, messages: [...t.messages, message] }
                : t,
            ),
          };
        }
        return {
          ...a,
          threads: [
            {
              threadId: Number(`9${a.id}${n}`),
              subject: payload.subject,
              archivedAt: null,
              messages: [message],
            },
            ...a.threads,
          ],
        };
      }),
    );
    return Promise.resolve();
  };

  return (
    <div className="min-h-full bg-slate-50">
      <main className="mx-auto max-w-4xl space-y-4 p-4 sm:p-6">
        <WhatChanged />

        <div className="flex flex-wrap items-center gap-2">
          <label
            htmlFor="application-switcher"
            className="text-xs uppercase tracking-wide text-slate-400"
          >
            Application
          </label>
          <select
            id="application-switcher"
            value={currentId}
            onChange={(e) => {
              setCurrentId(Number(e.target.value));
              setRefreshed(false);
            }}
            className="h-9 rounded-md border border-slate-300 bg-white px-2 text-sm text-slate-700"
          >
            {applications.map((a) => (
              <option key={a.id} value={a.id}>
                {a.applicant.name} · {a.job.title} (#{a.id})
              </option>
            ))}
          </select>
        </div>

        <div className="space-y-4 rounded-lg border border-slate-200 bg-white p-4">
          <header className="space-y-1">
            <h1 className="text-xl font-semibold text-slate-900">
              {application.applicant.name}
            </h1>
            <p className="flex flex-wrap items-center gap-2 text-sm text-slate-600">
              {application.job.title}
              <Badge
                variant="outline"
                className="border-slate-300 text-slate-600"
              >
                {application.job.kind === "ACTIVITY"
                  ? "Activity posting"
                  : "Employment posting"}
              </Badge>
              <span className="text-slate-400">·</span>
              {application.stage}
            </p>
          </header>

          <Tabs defaultValue="emails">
            <TabsList>
              <TabsTrigger value="evaluations">Evaluations</TabsTrigger>
              <TabsTrigger value="timeline">Timeline</TabsTrigger>
              <TabsTrigger value="comments">Comments</TabsTrigger>
              <TabsTrigger value="emails" className="gap-1.5">
                Emails
                {anyNeedsReply && (
                  <span
                    aria-label="Needs reply"
                    title="Needs reply"
                    className="h-2 w-2 rounded-full bg-orange-500"
                  />
                )}
              </TabsTrigger>
            </TabsList>
            {["evaluations", "timeline", "comments"].map((key) => (
              <TabsContent key={key} value={key}>
                <p className="text-sm text-slate-400">
                  Not part of this prototype.
                </p>
              </TabsContent>
            ))}
            <TabsContent value="emails">
              {refreshed && (
                <p className="mb-2 text-xs text-slate-500">
                  Refreshed. Mock data, so nothing new arrived.
                </p>
              )}
              <EmailsPanel
                threads={application.threads}
                onCompose={openCompose}
                onReply={openReply}
                onRefresh={() => setRefreshed(true)}
              />
              <ComposeEmailDialog
                open={composeOpen}
                onOpenChange={setComposeOpen}
                fromAlias={fromAlias}
                defaultTo={application.applicant.email}
                defaultCc={NO_DEFAULT_CC}
                replyThread={replyThread}
                templates={templates}
                signatureHtml={signatureHtml}
                onSend={handleSend}
                sending={false}
              />
            </TabsContent>
          </Tabs>
        </div>
      </main>
    </div>
  );
};

export default ApplicationEmailsPrototype;
