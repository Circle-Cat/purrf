import { useState } from "react";
import { LayoutGrid, FileText, Briefcase, ClipboardCheck, Ban } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import ScreeningBoardPrototype from "@/pages/RecruitingPrototype/ScreeningBoardPrototype";
import ApplyPrototype from "@/pages/RecruitingPrototype/ApplyPrototype";
import BlacklistPrototype from "@/pages/RecruitingPrototype/BlacklistPrototype";
import PostingsListPrototype from "@/pages/RecruitingPrototype/PostingsListPrototype";
import ReviewQueuePrototype from "@/pages/RecruitingPrototype/ReviewQueuePrototype";
import { INITIAL_POSTINGS, CURRENT_USER_ID } from "@/pages/RecruitingPrototype/mockData";

/** One pre-seeded blocked user so the Blacklist page isn't empty at demo start. */
const INITIAL_BLACKLIST = [
  {
    id: 9001,
    name: "Sam Rivera",
    email: "sam.rivera@example.com",
    phone: "+1 (212) 555-0101",
    reason: "Submitted AI-generated answers after explicit warning.",
    blockedAt: "2026-06-10",
  },
];

/** Left-nav sections. Flat list (Create Posting now lives inside Postings). */
const NAV = [
  { key: "board", label: "Screening 看板", icon: LayoutGrid },
  { key: "postings", label: "Postings", icon: Briefcase },
  { key: "review", label: "待我审核", icon: ClipboardCheck },
  { key: "apply", label: "申请表单", icon: FileText },
  { key: "blacklist", label: "黑名单", icon: Ban },
];

/** The reviewer whose queue "待我审核" shows (demo: Alice Kim, id 1). */
const DEMO_REVIEWER_ID = 1;

/**
 * RecruitingPrototype
 *
 * Self-contained, mock-data prototype of the Recruiting v2 design. A left
 * sidebar navigates the sections: the screening swimlane board, the postings
 * list (job lifecycle + review gate), the reviewer's "待我审核" queue, the
 * candidate apply form, and the org-wide blacklist.
 *
 * Two slices of state are lifted here so they stay consistent across sections:
 * the blacklist (board → Blacklist page) and the postings (Postings list →
 * 待我审核 queue share the same posting objects, so approving in the queue
 * updates the list).
 *
 * Route: /recruiting/prototype (no permission gate, for demo convenience)
 *
 * @returns {JSX.Element}
 */
const RecruitingPrototype = () => {
  const [active, setActive] = useState("board");
  const [blacklist, setBlacklist] = useState(INITIAL_BLACKLIST);
  const [postings, setPostings] = useState(INITIAL_POSTINGS);

  /** Add a blacklisted applicant (from the board) to the shared list. */
  const handleBlacklist = (application) => {
    const { applicant } = application;
    const record = {
      id: application.id,
      name: `${applicant.firstName} ${applicant.lastName}`,
      email: applicant.email,
      phone: applicant.phone,
      reason: "Flagged during screening.",
      blockedAt: new Date().toISOString().slice(0, 10),
    };
    setBlacklist((prev) => [record, ...prev.filter((e) => e.id !== record.id)]);
  };

  /** Remove (unblock) a user from the blacklist. */
  const handleUnblock = (id) => {
    setBlacklist((prev) => prev.filter((e) => e.id !== id));
  };

  /** Move a draft posting into review, recording reviewer + optional message. */
  const submitForReview = (id, reviewerId, message) =>
    setPostings((prev) =>
      prev.map((p) =>
        p.id === id
          ? {
              ...p,
              status: "pending_review",
              reviewerId,
              submitMessage: message,
              rejectComment: "",
              rejectedBy: null,
            }
          : p,
      ),
    );

  /** Approve a posting (or its pending revision) → published. */
  const approve = (id) =>
    setPostings((prev) =>
      prev.map((p) =>
        p.id === id ? { ...p, status: "published", pendingRevision: null } : p,
      ),
    );

  /** Send a posting back to draft with a required reviewer comment. */
  const sendBack = (id, comment) =>
    setPostings((prev) =>
      prev.map((p) =>
        p.id === id
          ? {
              ...p,
              status: "draft",
              rejectComment: comment,
              rejectedBy: p.reviewerId,
              reviewerId: null,
              pendingRevision: null,
            }
          : p,
      ),
    );

  /** Append a newly created posting (always starts as draft). */
  const createPosting = (jobLike) =>
    setPostings((prev) => [
      {
        id: Math.max(0, ...prev.map((p) => p.id)) + 1,
        status: "draft",
        reviewerId: null,
        submitMessage: "",
        rejectComment: "",
        rejectedBy: null,
        pendingRevision: null,
        ...jobLike,
      },
      ...prev,
    ]);

  return (
    <div className="flex min-h-screen bg-slate-50">
      {/* Prototype sidebar nav */}
      <aside className="w-56 shrink-0 border-r border-slate-200 bg-white flex flex-col">
        <div className="px-4 py-4 border-b border-slate-100">
          <div className="flex items-center gap-2">
            <span className="text-lg font-semibold text-slate-900">
              Recruiting
            </span>
            <Badge variant="outline" className="text-xs">
              v2
            </Badge>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">Prototype · mock data</p>
        </div>
        <nav className="p-2 space-y-1">
          {NAV.map((item) => {
            const Icon = item.icon;
            const isActive = active === item.key;
            return (
              <button
                key={item.key}
                type="button"
                onClick={() => setActive(item.key)}
                className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors ${
                  isActive
                    ? "bg-slate-800 text-white"
                    : "text-slate-600 hover:bg-slate-100"
                }`}
              >
                <Icon size={16} />
                {item.label}
              </button>
            );
          })}
        </nav>
      </aside>

      {/* Content */}
      <main className="flex-1 min-w-0">
        {active === "board" && (
          <ScreeningBoardPrototype onBlacklist={handleBlacklist} />
        )}
        {active === "postings" && (
          <PostingsListPrototype
            postings={postings}
            currentUserId={CURRENT_USER_ID}
            onSubmitForReview={submitForReview}
            onCreate={createPosting}
          />
        )}
        {active === "review" && (
          <ReviewQueuePrototype
            postings={postings}
            reviewerId={DEMO_REVIEWER_ID}
            onApprove={approve}
            onSendBack={sendBack}
          />
        )}
        {active === "apply" && <ApplyPrototype />}
        {active === "blacklist" && (
          <div className="p-6">
            <BlacklistPrototype entries={blacklist} onRemove={handleUnblock} />
          </div>
        )}
      </main>
    </div>
  );
};

export default RecruitingPrototype;
