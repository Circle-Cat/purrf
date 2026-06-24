/**
 * ScreeningBoardPrototype.jsx
 *
 * Hero screen for the Recruiting v2 stakeholder demo.
 *
 * Renders a horizontally-scrollable Kanban swimlane board driven entirely by
 * mock data. Selecting a different job posting reshuffles the lanes and cards.
 * Clicking a card opens a Dialog with the applicant's full profile and action
 * buttons (Hire, Reject, Advance to next stage).
 *
 * All board mutations are local-state only — nothing reaches the backend.
 *
 * @module ScreeningBoardPrototype
 */

import { useState, useMemo } from "react";
import {
  Mail,
  Phone,
  FileText,
  ChevronRight,
  Ban,
  Star,
  MessageSquare,
  ArrowRight,
  Send,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
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
import { Separator } from "@/components/ui/separator";

import { JOBS, STAGES, applicationsByStage } from "./mockData";

// ---------------------------------------------------------------------------
// Static color map — every class string must appear verbatim so Tailwind v4
// includes them in the generated stylesheet.
// ---------------------------------------------------------------------------
/** @type {Record<string, { header: string; tint: string; count: string; border: string }>} */
const LANE_COLORS = {
  sky: {
    header: "bg-sky-100 text-sky-800 border-sky-200",
    tint: "bg-sky-50",
    count: "bg-sky-200 text-sky-800",
    border: "border-sky-200",
  },
  violet: {
    header: "bg-violet-100 text-violet-800 border-violet-200",
    tint: "bg-violet-50",
    count: "bg-violet-200 text-violet-800",
    border: "border-violet-200",
  },
  amber: {
    header: "bg-amber-100 text-amber-800 border-amber-200",
    tint: "bg-amber-50",
    count: "bg-amber-200 text-amber-800",
    border: "border-amber-200",
  },
  rose: {
    header: "bg-rose-100 text-rose-800 border-rose-200",
    tint: "bg-rose-50",
    count: "bg-rose-200 text-rose-800",
    border: "border-rose-200",
  },
  emerald: {
    header: "bg-emerald-100 text-emerald-800 border-emerald-200",
    tint: "bg-emerald-50",
    count: "bg-emerald-200 text-emerald-800",
    border: "border-emerald-200",
  },
  slate: {
    header: "bg-slate-200 text-slate-700 border-slate-300",
    tint: "bg-slate-100",
    count: "bg-slate-300 text-slate-700",
    border: "border-slate-300",
  },
};

// ---------------------------------------------------------------------------
// Terminal lanes (always shown after the pipeline lanes)
// ---------------------------------------------------------------------------
/** Terminal stage keys + their lane metadata. */
const TERMINAL_STAGES = {
  hired: { key: "hired", label: "Hired", color: "emerald" },
  rejected: { key: "rejected", label: "Rejected", color: "slate" },
};

/** Ordered list of terminal lane keys. */
const TERMINAL_KEYS = ["hired", "rejected"];

/** Merged lookup: pipeline stages + terminal stages. */
const STAGE_META = { ...STAGES, ...TERMINAL_STAGES };

// ---------------------------------------------------------------------------
// Per-stage evaluation status (replaces the old viewed/unviewed flag)
// ---------------------------------------------------------------------------
/**
 * A candidate's status *within* the current stage: Pending on entering the
 * stage (not started), In Progress while being assessed, Evaluated once the
 * assessment is done. Class strings are literal so Tailwind picks them up.
 */
const CARD_STATUS = {
  pending: {
    label: "Pending",
    className: "bg-slate-100 text-slate-600 border-slate-200",
  },
  in_progress: {
    label: "In Progress",
    className: "bg-amber-50 text-amber-700 border-amber-200",
  },
  evaluated: {
    label: "Evaluated",
    className: "bg-emerald-50 text-emerald-700 border-emerald-200",
  },
};

/** Lifecycle order, for the detail-view status selector. */
const CARD_STATUS_ORDER = ["pending", "in_progress", "evaluated"];

/** Monotonic id source for activity entries added during the session. */
let activitySeq = 0;
const nextActivityId = () => `act-new-${(activitySeq += 1)}`;

/**
 * Per-stage scorecard template: the criteria scored at each stage. Each
 * criterion is rated 1–5 with an optional multi-line note.
 */
const SCORECARD_TEMPLATES = {
  recruiter_screening: [
    "Basic qualifications",
    "Mandarin fluency",
    "Communication",
  ],
  behavioral: ["Motivation & alignment", "Teamwork", "Ownership"],
  tech: ["Coding", "System design", "Problem solving"],
  board_review: ["Overall recommendation"],
  offer: ["Offer fit"],
};

/** Predefined rejection reasons (a reason is required to reject). */
const REJECT_REASONS = [
  "Insufficient experience",
  "Did not meet the technical bar",
  "Communication concerns",
  "Not aligned with our mission",
  "Accepted another offer",
  "Incomplete application",
  "Other",
];

// ---------------------------------------------------------------------------
// Helper — derive next-stage label/key for a given stage within a job
// ---------------------------------------------------------------------------
/**
 * Returns the advance target for a card currently in `stageKey`:
 * - the next pipeline stage, if one exists;
 * - the `hired` terminal stage, if `stageKey` is the final pipeline stage;
 * - null, if `stageKey` is not part of this job's pipeline (already terminal).
 *
 * @param {{ stages: string[] }} job
 * @param {string} stageKey
 * @returns {{ key: string, label: string } | null}
 */
function advanceTarget(job, stageKey) {
  const idx = job.stages.indexOf(stageKey);
  if (idx === -1) return null;
  if (idx === job.stages.length - 1) {
    return { key: "hired", label: TERMINAL_STAGES.hired.label };
  }
  const key = job.stages[idx + 1];
  return { key, label: STAGES[key]?.label ?? key };
}

// ---------------------------------------------------------------------------
// ApplicantCard
// ---------------------------------------------------------------------------
/**
 * A compact card summarising one applicant. Hire / Reject are intentionally
 * absent — those actions live inside the detail Dialog.
 *
 * @param {{ application: object; showStatus: boolean; onClick: () => void }} props
 */
function ApplicantCard({ application, showStatus, onClick }) {
  const { applicant, status } = application;
  const fullName = `${applicant.firstName} ${applicant.lastName}`;
  const statusMeta = CARD_STATUS[status] ?? CARD_STATUS.pending;

  return (
    <Card
      onClick={onClick}
      className="cursor-pointer p-4 rounded-xl border border-white/80 bg-white shadow-sm hover:shadow-md hover:ring-2 hover:ring-offset-1 hover:ring-slate-300 transition-all duration-150 select-none"
    >
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex items-center gap-2 min-w-0">
          <span className="font-semibold text-slate-900 text-sm leading-tight truncate">
            {fullName}
          </span>
        </div>
        {showStatus && (
          <Badge
            className={`text-xs shrink-0 ${statusMeta.className}`}
            variant="outline"
          >
            {statusMeta.label}
          </Badge>
        )}
      </div>

      <div className="space-y-1">
        <div className="flex items-center gap-1.5 text-xs text-slate-500 truncate">
          <Mail size={11} className="shrink-0 text-slate-400" />
          <span className="truncate">{applicant.email}</span>
        </div>
        <div className="flex items-center gap-1.5 text-xs text-slate-500">
          <Phone size={11} className="shrink-0 text-slate-400" />
          <span>{applicant.phone}</span>
        </div>
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Activity feed (Evaluations / Comments / Emails / Stage changes)
// ---------------------------------------------------------------------------
/** Per-entry-type icon + accent for the activity feed and filter chips. */
const ACTIVITY_META = {
  evaluation: { label: "Evaluations", Icon: Star, color: "text-amber-500" },
  comment: { label: "Comments", Icon: MessageSquare, color: "text-sky-500" },
  email: { label: "Emails", Icon: Mail, color: "text-violet-500" },
  stage: { label: "Stage", Icon: ArrowRight, color: "text-slate-400" },
};

/** Filter chip order. */
const ACTIVITY_FILTERS = ["all", "evaluation", "comment", "email", "stage"];

/** Highlights @mentions inside a comment string. */
function renderMentions(text) {
  return text.split(/(\s+)/).map((tok, i) =>
    tok.startsWith("@") ? (
      <span key={i} className="text-sky-600 font-medium">
        {tok}
      </span>
    ) : (
      tok
    ),
  );
}

/**
 * One activity entry, rendered by type.
 *
 * @param {{ entry: object }} props
 */
function ActivityEntry({ entry }) {
  const meta = ACTIVITY_META[entry.type] ?? ACTIVITY_META.stage;
  const Icon = meta.Icon;
  return (
    <div className="flex gap-2.5">
      <Icon size={15} className={`mt-0.5 shrink-0 ${meta.color}`} />
      <div className="min-w-0 flex-1">
        {entry.type === "evaluation" && (
          <>
            <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-slate-500">
              <span className="font-medium text-slate-700">{entry.author}</span>
              <Badge variant="secondary" className="text-xs">
                {STAGES[entry.stage]?.label ?? entry.stage}
                {entry.overall ? ` · ${entry.overall}/5 avg` : ""}
              </Badge>
              <span>{entry.at}</span>
            </div>
            <ul className="mt-1 space-y-0.5">
              {(entry.criteria ?? []).map((c, i) => (
                <li key={i} className="text-sm text-slate-700">
                  <span className="text-slate-500">{c.label}:</span>{" "}
                  <span className="font-medium">{c.score}/5</span>
                  {c.note ? (
                    <span className="text-slate-600"> — {c.note}</span>
                  ) : null}
                </li>
              ))}
            </ul>
          </>
        )}
        {entry.type === "comment" && (
          <>
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <span className="font-medium text-slate-700">{entry.author}</span>
              <span>{entry.at}</span>
            </div>
            <p className="text-sm text-slate-700 mt-0.5">
              {renderMentions(entry.text)}
            </p>
          </>
        )}
        {entry.type === "email" && (
          <>
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <span className="font-medium text-slate-700">
                {entry.direction === "out" ? "Sent" : "Received"}
              </span>
              <span>{entry.at}</span>
            </div>
            <p className="text-sm text-slate-700 mt-0.5">
              <span className="font-medium">{entry.subject}</span>
              {entry.snippet ? ` — ${entry.snippet}` : ""}
            </p>
          </>
        )}
        {entry.type === "stage" && (
          <div className="text-xs text-slate-500">
            <span className="font-medium text-slate-700">{entry.author}</span>{" "}
            moved {entry.from} → {entry.to} · {entry.at}
            {entry.reason ? (
              <span className="block text-slate-600">
                Reason: {entry.reason}
              </span>
            ) : null}
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * Right-hand activity panel: one chronological feed of evaluations, comments,
 * emails, and stage changes, with filter chips and inline composers for adding
 * a comment or submitting an evaluation. Emails are read-only.
 *
 * @param {{
 *   activity: object[];
 *   stage: string;
 *   inPipeline: boolean;
 *   onAddComment: (text: string) => void;
 *   onAddEvaluation: (payload: { criteria: object[], overall: number }) => void;
 * }} props
 */
function ActivityPanel({
  activity,
  stage,
  inPipeline,
  onAddComment,
  onAddEvaluation,
}) {
  const [filter, setFilter] = useState("all");
  const [mode, setMode] = useState("comment");
  const [commentText, setCommentText] = useState("");
  const [scores, setScores] = useState({});
  const [notes, setNotes] = useState({});

  const criteria = SCORECARD_TEMPLATES[stage] ?? ["Overall"];

  const filtered =
    filter === "all" ? activity : activity.filter((a) => a.type === filter);

  const submitComment = () => {
    if (!commentText.trim()) return;
    onAddComment(commentText.trim());
    setCommentText("");
  };
  const submitEvaluation = () => {
    const results = criteria.map((label) => ({
      label,
      score: scores[label] ?? 0,
      note: (notes[label] ?? "").trim(),
    }));
    const rated = results.filter((r) => r.score > 0);
    if (!rated.length) return;
    const overall =
      Math.round((rated.reduce((s, r) => s + r.score, 0) / rated.length) * 10) /
      10;
    onAddEvaluation({ criteria: results, overall });
    setScores({});
    setNotes({});
  };

  return (
    <div className="md:w-[340px] shrink-0 bg-slate-50 flex flex-col">
      <div className="px-4 pt-4 pb-3 border-b border-slate-100 space-y-3">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
          Activity
        </h3>

        {/* Filter chips */}
        <div className="flex flex-wrap gap-1.5">
          {ACTIVITY_FILTERS.map((f) => {
            const isActive = filter === f;
            const label = f === "all" ? "All" : ACTIVITY_META[f].label;
            return (
              <button
                key={f}
                type="button"
                onClick={() => setFilter(f)}
                className={`text-xs px-2 py-0.5 rounded-full border transition-colors ${
                  isActive
                    ? "bg-slate-800 text-white border-slate-800"
                    : "bg-white text-slate-600 border-slate-200 hover:border-slate-400"
                }`}
              >
                {label}
              </button>
            );
          })}
        </div>

        {/* Composer */}
        <div className="rounded-lg border border-slate-200 bg-white p-2 space-y-2">
          <div className="flex gap-1">
            <button
              type="button"
              onClick={() => setMode("comment")}
              className={`text-xs px-2 py-1 rounded-md ${
                mode === "comment"
                  ? "bg-slate-100 font-medium text-slate-800"
                  : "text-slate-500"
              }`}
            >
              Comment
            </button>
            {inPipeline && (
              <button
                type="button"
                onClick={() => setMode("evaluation")}
                className={`text-xs px-2 py-1 rounded-md ${
                  mode === "evaluation"
                    ? "bg-slate-100 font-medium text-slate-800"
                    : "text-slate-500"
                }`}
              >
                Evaluation
              </button>
            )}
          </div>

          {mode === "comment" ? (
            <>
              <textarea
                rows={2}
                value={commentText}
                onChange={(e) => setCommentText(e.target.value)}
                placeholder="Add a comment… use @ to mention a teammate"
                className="w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm resize-none focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              />
              <Button
                size="sm"
                className="w-full gap-1"
                onClick={submitComment}
              >
                <Send size={13} /> Add comment
              </Button>
            </>
          ) : (
            <>
              <p className="text-xs text-slate-500">
                {STAGES[stage]?.label ?? stage} scorecard
              </p>
              {criteria.map((label) => (
                <div key={label} className="space-y-1">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-medium text-slate-700">
                      {label}
                    </span>
                    <div className="flex items-center gap-1">
                      {[1, 2, 3, 4, 5].map((n) => (
                        <button
                          key={n}
                          type="button"
                          onClick={() =>
                            setScores((s) => ({ ...s, [label]: n }))
                          }
                          className={`h-5 w-5 rounded text-xs border ${
                            scores[label] === n
                              ? "bg-amber-500 text-white border-amber-500"
                              : "bg-white text-slate-600 border-slate-200"
                          }`}
                        >
                          {n}
                        </button>
                      ))}
                    </div>
                  </div>
                  <textarea
                    rows={2}
                    value={notes[label] ?? ""}
                    onChange={(e) =>
                      setNotes((nn) => ({ ...nn, [label]: e.target.value }))
                    }
                    placeholder={`Notes on ${label.toLowerCase()}…`}
                    className="w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm resize-none focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                  />
                </div>
              ))}
              <Button
                size="sm"
                className="w-full gap-1 bg-amber-600 hover:bg-amber-700"
                onClick={submitEvaluation}
              >
                <Star size={13} /> Submit scorecard
              </Button>
            </>
          )}
        </div>
      </div>

      {/* Feed */}
      <div className="p-4 space-y-4 overflow-y-auto">
        {filtered.length === 0 ? (
          <p className="text-xs text-slate-400 text-center mt-4">
            No activity yet.
          </p>
        ) : (
          filtered.map((entry) => (
            <ActivityEntry key={entry.id} entry={entry} />
          ))
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// ApplicantDetail Dialog
// ---------------------------------------------------------------------------
/**
 * Full detail view for a selected applicant rendered inside a shadcn Dialog.
 *
 * @param {{
 *   application: object | null;
 *   job: object;
 *   onClose: () => void;
 *   onAdvance: (appId: number, nextKey: string) => void;
 *   onReject: (appId: number, reason: string, note: string) => void;
 *   onBlacklist: (app: object) => void;
 *   onSetStatus: (appId: number, status: string) => void;
 *   onAddComment: (appId: number, text: string) => void;
 *   onAddEvaluation: (appId: number, stage: string, payload: object) => void;
 * }} props
 */
function ApplicantDetail({
  application,
  job,
  onClose,
  onAdvance,
  onReject,
  onBlacklist,
  onSetStatus,
  onAddComment,
  onAddEvaluation,
}) {
  const [rejecting, setRejecting] = useState(false);
  const [rejectReason, setRejectReason] = useState(REJECT_REASONS[0]);
  const [rejectNote, setRejectNote] = useState("");

  const closeDetail = () => {
    setRejecting(false);
    setRejectNote("");
    onClose();
  };

  if (!application) return null;
  const { applicant, resumeUrl, experience, education, formAnswers, stage } =
    application;
  const fullName = `${applicant.firstName} ${applicant.lastName}`;
  const inPipeline = job.stages.includes(stage);
  const target = advanceTarget(job, stage);

  return (
    <Dialog
      open={!!application}
      onOpenChange={(open) => !open && closeDetail()}
    >
      <DialogContent className="z-[1100] sm:max-w-5xl max-h-[90vh] overflow-y-auto rounded-2xl p-0">
        {/* ---- Header band ---- */}
        <div className="bg-gradient-to-r from-slate-800 to-slate-700 px-6 pt-6 pb-5 rounded-t-2xl">
          <DialogHeader>
            <DialogTitle className="text-white text-xl font-bold leading-tight">
              {fullName}
            </DialogTitle>
          </DialogHeader>
          <div className="mt-2 flex flex-wrap gap-x-5 gap-y-1">
            <div className="flex items-center gap-1.5 text-slate-300 text-sm">
              <Mail size={13} />
              <span>{applicant.email}</span>
            </div>
            <div className="flex items-center gap-1.5 text-slate-300 text-sm">
              <Phone size={13} />
              <span>{applicant.phone}</span>
            </div>
            {resumeUrl && (
              <a
                href={resumeUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1.5 text-sky-300 hover:text-sky-200 text-sm underline underline-offset-2 transition-colors"
              >
                <FileText size={13} />
                <span>Resume</span>
              </a>
            )}
          </div>

          {/* Per-stage evaluation status selector */}
          {inPipeline && (
            <div className="mt-3 flex items-center gap-1.5">
              <span className="text-xs text-slate-400 mr-1">Status</span>
              {CARD_STATUS_ORDER.map((s) => {
                const isActive = (application.status ?? "pending") === s;
                return (
                  <button
                    key={s}
                    type="button"
                    onClick={() => onSetStatus(application.id, s)}
                    className={`text-xs px-2 py-1 rounded-md border transition-colors ${
                      isActive
                        ? "bg-white text-slate-800 border-white font-medium"
                        : "bg-transparent text-slate-300 border-slate-600 hover:border-slate-400"
                    }`}
                  >
                    {CARD_STATUS[s].label}
                  </button>
                );
              })}
            </div>
          )}
        </div>

        <div className="flex flex-col md:flex-row">
          <div className="flex-1 px-6 py-5 space-y-5 md:border-r border-slate-100 min-w-0">
            {/* ---- Experience ---- */}
            {experience?.length > 0 && (
              <section>
                <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
                  Experience
                </h3>
                <ul className="space-y-1.5">
                  {experience.map((exp, i) => (
                    <li key={i} className="text-sm text-slate-700">
                      <span className="font-medium">{exp.title}</span>
                      <span className="text-slate-400"> · </span>
                      <span>{exp.company}</span>
                      <span className="text-slate-400 text-xs ml-2">
                        {exp.years}
                      </span>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            {/* ---- Education ---- */}
            {education?.length > 0 && (
              <>
                <Separator />
                <section>
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
                    Education
                  </h3>
                  <ul className="space-y-1.5">
                    {education.map((edu, i) => (
                      <li key={i} className="text-sm text-slate-700">
                        <span className="font-medium">{edu.degree}</span>
                        <span className="text-slate-400"> · </span>
                        <span>{edu.school}</span>
                        <span className="text-slate-400 text-xs ml-2">
                          {edu.years}
                        </span>
                      </li>
                    ))}
                  </ul>
                </section>
              </>
            )}

            {/* ---- Form answers ---- */}
            {formAnswers && Object.keys(formAnswers).length > 0 && (
              <>
                <Separator />
                <section>
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3">
                    Application Answers
                  </h3>
                  <dl className="space-y-3">
                    {Object.entries(formAnswers).map(([label, value]) => (
                      <div key={label}>
                        <dt className="text-xs font-medium text-slate-500 mb-0.5">
                          {label}
                        </dt>
                        <dd className="text-sm text-slate-800 leading-relaxed">
                          {value}
                        </dd>
                      </div>
                    ))}
                  </dl>
                </section>
              </>
            )}
          </div>

          <ActivityPanel
            key={application.id}
            activity={application.activity ?? []}
            stage={stage}
            inPipeline={inPipeline}
            onAddComment={(text) => onAddComment(application.id, text)}
            onAddEvaluation={(payload) =>
              onAddEvaluation(application.id, stage, payload)
            }
          />
        </div>

        {/* ---- Action footer ---- */}
        <DialogFooter className="px-6 py-4 border-t border-slate-100 bg-slate-50 rounded-b-2xl flex flex-row flex-wrap gap-2 justify-end">
          {rejecting ? (
            <div className="w-full space-y-2">
              <div className="space-y-1">
                <label className="text-xs font-medium text-slate-600">
                  Rejection reason
                </label>
                <select
                  value={rejectReason}
                  onChange={(e) => setRejectReason(e.target.value)}
                  className="w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                >
                  {REJECT_REASONS.map((r) => (
                    <option key={r} value={r}>
                      {r}
                    </option>
                  ))}
                </select>
              </div>
              <textarea
                rows={2}
                value={rejectNote}
                onChange={(e) => setRejectNote(e.target.value)}
                placeholder="Optional note for the hiring team…"
                className="w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm resize-none focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              />
              <div className="flex justify-end gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setRejecting(false)}
                >
                  Cancel
                </Button>
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={() => {
                    onReject(application.id, rejectReason, rejectNote.trim());
                    closeDetail();
                  }}
                >
                  Confirm reject
                </Button>
              </div>
            </div>
          ) : (
            <>
              {/* Blacklist (拉黑) — always available; removes from board entirely */}
              <Button
                variant="outline"
                size="sm"
                className="mr-auto text-slate-700 border-slate-300 hover:bg-slate-800 hover:text-white"
                onClick={() => {
                  onBlacklist(application);
                  closeDetail();
                }}
              >
                <Ban size={14} className="mr-1" />
                Blacklist
              </Button>

              {/* Reject — opens the reason form (a reason is required) */}
              {inPipeline && (
                <Button
                  variant="outline"
                  size="sm"
                  className="text-rose-600 border-rose-200 hover:bg-rose-50 hover:border-rose-300"
                  onClick={() => setRejecting(true)}
                >
                  Reject
                </Button>
              )}

              {/* Advance — next stage, or Hired when leaving the final stage */}
              {inPipeline && target && (
                <Button
                  size="sm"
                  className="bg-slate-800 hover:bg-slate-700 text-white gap-1"
                  onClick={() => {
                    onAdvance(application.id, target.key);
                    closeDetail();
                  }}
                >
                  <span>Advance to {target.label}</span>
                  <ChevronRight size={14} />
                </Button>
              )}
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// SwimlaneLane
// ---------------------------------------------------------------------------
/**
 * One vertical lane in the Kanban board.
 *
 * @param {{
 *   stageKey: string;
 *   applications: object[];
 *   onCardClick: (app: object) => void;
 * }} props
 */
function SwimlaneLane({ stageKey, applications, onCardClick }) {
  const stage = STAGE_META[stageKey];
  const colors = LANE_COLORS[stage?.color] ?? LANE_COLORS.sky;
  const isPipelineStage = !TERMINAL_KEYS.includes(stageKey);

  return (
    <div
      className={`flex flex-col rounded-2xl border ${colors.border} ${colors.tint} min-w-[240px] w-[240px] flex-shrink-0`}
    >
      {/* Lane header */}
      <div
        className={`flex items-center justify-between px-4 py-3 rounded-t-2xl border-b ${colors.header} ${colors.border}`}
      >
        <span className="text-sm font-semibold tracking-tight">
          {stage?.label ?? stageKey}
        </span>
        <span
          className={`text-xs font-bold px-2 py-0.5 rounded-full ${colors.count}`}
        >
          {applications.length}
        </span>
      </div>

      {/* Cards */}
      <div className="flex flex-col gap-3 p-3 flex-1 overflow-y-auto">
        {applications.length === 0 ? (
          <p className="text-center text-xs text-slate-400 mt-6">
            No applicants
          </p>
        ) : (
          applications.map((app) => (
            <ApplicantCard
              key={app.id}
              application={app}
              showStatus={isPipelineStage}
              onClick={() => onCardClick(app)}
            />
          ))
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// ScreeningBoardPrototype — main export
// ---------------------------------------------------------------------------
/**
 * Hero screen for the Recruiting v2 stakeholder prototype.
 *
 * Renders a horizontally-scrollable Kanban swimlane board. The job switcher at
 * the top drives the number of lanes (Intern = 5 stages; Mentee = 1 stage).
 * Card clicks open a detail Dialog with Hire / Reject / Advance actions that
 * mutate local React state only.
 *
 * @returns {JSX.Element}
 */
export default function ScreeningBoardPrototype({ onBlacklist }) {
  // Job selection
  const [selectedJobId, setSelectedJobId] = useState(1);
  const job = useMemo(
    () => JOBS.find((j) => j.id === selectedJobId) ?? JOBS[0],
    [selectedJobId],
  );

  // Board state: { [stageKey]: Application[] }
  const [boardState, setBoardState] = useState(() => applicationsByStage(1));

  // Selected card for detail Dialog
  const [selected, setSelected] = useState(/** @type {object|null} */ (null));

  // Re-initialise board when job changes
  function handleJobChange(value) {
    const id = Number(value);
    setSelectedJobId(id);
    setBoardState(applicationsByStage(id));
    setSelected(null);
  }

  // Advance a card to the next stage
  function handleAdvance(appId, nextKey) {
    setBoardState((prev) => {
      const next = { ...prev };
      for (const [key, apps] of Object.entries(next)) {
        const idx = apps.findIndex((a) => a.id === appId);
        if (idx !== -1) {
          const updated = [...apps];
          const [app] = updated.splice(idx, 1);
          next[key] = updated;
          next[nextKey] = [
            ...(next[nextKey] ?? []),
            { ...app, stage: nextKey, status: "pending" },
          ];
          break;
        }
      }
      return next;
    });
  }

  // Update a card's per-stage evaluation status (Pending/In Progress/Evaluated).
  function handleSetStatus(appId, status) {
    setBoardState((prev) => {
      const next = { ...prev };
      for (const [key, apps] of Object.entries(next)) {
        const idx = apps.findIndex((a) => a.id === appId);
        if (idx !== -1) {
          const updated = [...apps];
          updated[idx] = { ...updated[idx], status };
          next[key] = updated;
          break;
        }
      }
      return next;
    });
  }

  // Prepend an activity entry onto a card's trail (newest first).
  function appendActivity(appId, partial) {
    setBoardState((prev) => {
      const next = { ...prev };
      for (const [key, apps] of Object.entries(next)) {
        const idx = apps.findIndex((a) => a.id === appId);
        if (idx !== -1) {
          const card = apps[idx];
          const entry = { id: nextActivityId(), at: "just now", ...partial };
          const updated = [...apps];
          updated[idx] = {
            ...card,
            activity: [entry, ...(card.activity ?? [])],
          };
          next[key] = updated;
          break;
        }
      }
      return next;
    });
  }

  // Add a teammate comment to a card's activity.
  function handleAddComment(appId, text) {
    appendActivity(appId, { type: "comment", author: "You", text });
  }

  // Submit a structured scorecard for the card's current stage; marks it Evaluated.
  function handleAddEvaluation(appId, stageKey, payload) {
    appendActivity(appId, {
      type: "evaluation",
      author: "You",
      stage: stageKey,
      criteria: payload.criteria,
      overall: payload.overall,
    });
    handleSetStatus(appId, "evaluated");
  }

  // Reject a candidate with a reason: record it on the trail, then move to the
  // Rejected lane.
  function handleReject(appId, reason, note) {
    let fromLabel = "Stage";
    for (const apps of Object.values(boardState)) {
      const card = apps.find((a) => a.id === appId);
      if (card) {
        fromLabel = STAGES[card.stage]?.label ?? card.stage;
        break;
      }
    }
    appendActivity(appId, {
      type: "stage",
      author: "You",
      from: fromLabel,
      to: "Rejected",
      reason: note ? `${reason} — ${note}` : reason,
    });
    handleAdvance(appId, "rejected");
  }

  // Blacklist (拉黑) — remove from the board entirely and report up to the
  // shared blacklist store so it appears on the Blacklist page.
  function handleBlacklist(application) {
    setBoardState((prev) => {
      const next = { ...prev };
      for (const [key, apps] of Object.entries(next)) {
        const filtered = apps.filter((a) => a.id !== application.id);
        if (filtered.length !== apps.length) {
          next[key] = filtered;
          break;
        }
      }
      return next;
    });
    onBlacklist?.(application);
  }

  // Visible stages for the selected job (only stages defined in STAGES)
  const visibleStages = job.stages.filter((s) => !!STAGES[s]);

  // Keep the dialog card reference in sync with board state (card may have moved)
  const selectedApp = useMemo(() => {
    if (!selected) return null;
    for (const apps of Object.values(boardState)) {
      const found = apps.find((a) => a.id === selected.id);
      if (found) return found;
    }
    return null;
  }, [selected, boardState]);

  const totalCount = visibleStages.reduce(
    (sum, s) => sum + (boardState[s]?.length ?? 0),
    0,
  );

  return (
    <div className="min-h-screen bg-slate-100 flex flex-col">
      {/* ---- Top bar ---- */}
      <header className="bg-white border-b border-slate-200 px-6 py-4 flex items-center justify-between shadow-sm">
        <div className="flex items-center gap-3">
          <div className="h-8 w-8 rounded-lg bg-slate-800 flex items-center justify-center">
            <svg
              width="16"
              height="16"
              viewBox="0 0 16 16"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <rect
                x="1"
                y="2"
                width="5"
                height="12"
                rx="1.5"
                fill="white"
                fillOpacity="0.9"
              />
              <rect
                x="8"
                y="2"
                width="5"
                height="8"
                rx="1.5"
                fill="white"
                fillOpacity="0.6"
              />
            </svg>
          </div>
          <div>
            <h1 className="text-base font-bold text-slate-900 leading-tight">
              Recruiting Board
            </h1>
            <p className="text-xs text-slate-400 leading-tight">
              CircleCat · v2 prototype
            </p>
          </div>
        </div>

        {/* Job switcher + count */}
        <div className="flex items-center gap-3">
          <span className="text-xs text-slate-500 font-medium">Posting</span>
          <Select value={String(selectedJobId)} onValueChange={handleJobChange}>
            <SelectTrigger className="w-64 text-sm bg-white border-slate-200 rounded-lg shadow-sm">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {JOBS.filter((j) => j.stages.length > 0).map((j) => (
                <SelectItem key={j.id} value={String(j.id)}>
                  {j.title}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <div className="flex items-center gap-1.5 bg-slate-100 rounded-full px-3 py-1">
            <span className="text-xs text-slate-500">Total</span>
            <span className="text-xs font-bold text-slate-700">
              {totalCount}
            </span>
          </div>
        </div>
      </header>

      {/* ---- Job context strip ---- */}
      <div className="bg-white border-b border-slate-100 px-6 py-2.5 flex items-center gap-4">
        <Badge
          variant="outline"
          className="text-xs border-slate-300 text-slate-600 rounded-full px-3"
        >
          {job.template}
        </Badge>
        <span className="text-xs text-slate-400 truncate max-w-xl">
          {job.description}
        </span>
      </div>

      {/* ---- Swimlane board ---- */}
      <main className="flex-1 overflow-x-auto px-6 py-6">
        {visibleStages.length === 0 ? (
          <div className="flex items-center justify-center h-64">
            <p className="text-slate-400 text-sm">
              This posting has no pipeline stages.
            </p>
          </div>
        ) : (
          <div
            className="flex gap-4 pb-6"
            style={{
              minWidth: "fit-content",
              minHeight: "calc(100vh - 180px)",
            }}
          >
            {visibleStages.map((stageKey) => (
              <SwimlaneLane
                key={stageKey}
                stageKey={stageKey}
                applications={boardState[stageKey] ?? []}
                onCardClick={(app) => setSelected(app)}
              />
            ))}

            {/* Terminal lanes — always shown after the pipeline */}
            {TERMINAL_KEYS.map((stageKey) => (
              <SwimlaneLane
                key={stageKey}
                stageKey={stageKey}
                applications={boardState[stageKey] ?? []}
                onCardClick={(app) => setSelected(app)}
              />
            ))}
          </div>
        )}
      </main>

      {/* ---- Detail Dialog ---- */}
      <ApplicantDetail
        application={selectedApp}
        job={job}
        onClose={() => setSelected(null)}
        onAdvance={handleAdvance}
        onReject={handleReject}
        onBlacklist={handleBlacklist}
        onSetStatus={handleSetStatus}
        onAddComment={handleAddComment}
        onAddEvaluation={handleAddEvaluation}
      />
    </div>
  );
}
