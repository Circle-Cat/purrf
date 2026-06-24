import { useState } from "react";
import { LayoutGrid, FileText, SquarePlus, Ban } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import ScreeningBoardPrototype from "@/pages/RecruitingPrototype/ScreeningBoardPrototype";
import ApplyPrototype from "@/pages/RecruitingPrototype/ApplyPrototype";
import JobModalPrototype from "@/pages/RecruitingPrototype/JobModalPrototype";
import BlacklistPrototype from "@/pages/RecruitingPrototype/BlacklistPrototype";

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

/** Left-nav sections. */
const NAV = [
  { key: "board", label: "Screening Board", icon: LayoutGrid },
  { key: "apply", label: "Apply Form", icon: FileText },
  { key: "create", label: "Create Posting", icon: SquarePlus },
  { key: "blacklist", label: "Blacklist", icon: Ban },
];

/**
 * RecruitingPrototype
 *
 * A self-contained, mock-data prototype of the Recruiting v2 design, built for a
 * stakeholder demo. No backend calls — everything renders from
 * `@/pages/RecruitingPrototype/mockData`. A left sidebar navigates the four
 * sections: the screening swimlane board (with Hired/Rejected terminal lanes),
 * the candidate apply form, the job-creation modal, and the org-wide blacklist.
 *
 * The blacklist is lifted here so blacklisting a candidate on the board shows
 * up immediately on the Blacklist section.
 *
 * Route: /recruiting/prototype (no permission gate, for demo convenience)
 *
 * @returns {JSX.Element}
 */
const RecruitingPrototype = () => {
  const [active, setActive] = useState("board");
  const [blacklist, setBlacklist] = useState(INITIAL_BLACKLIST);

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
        {active === "apply" && <ApplyPrototype />}
        {active === "create" && (
          <div className="p-6">
            <JobModalPrototype />
          </div>
        )}
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
