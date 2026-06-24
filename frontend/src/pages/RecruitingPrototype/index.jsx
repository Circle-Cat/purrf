import { useState } from "react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
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

/**
 * RecruitingPrototype
 *
 * A self-contained, mock-data prototype of the Recruiting v2 design, built for a
 * stakeholder demo. No backend calls — everything renders from
 * `@/pages/RecruitingPrototype/mockData`. Four tabs walk through the vision:
 * the screening swimlane board (with Hired/Rejected terminal lanes), the
 * candidate apply form, the job-creation modal, and the org-wide blacklist.
 *
 * The blacklist is lifted here so blacklisting a candidate on the board shows
 * up immediately on the Blacklist tab.
 *
 * Route: /recruiting/prototype (no permission gate, for demo convenience)
 *
 * @returns {JSX.Element}
 */
const RecruitingPrototype = () => {
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
    <div className="p-6">
      <div className="mb-6 flex items-center gap-3">
        <h1 className="text-2xl font-semibold">Recruiting v2</h1>
        <Badge variant="outline">Prototype · mock data</Badge>
      </div>

      <Tabs defaultValue="board">
        <TabsList>
          <TabsTrigger value="board">Screening Board</TabsTrigger>
          <TabsTrigger value="apply">Apply Form</TabsTrigger>
          <TabsTrigger value="create">Create Posting</TabsTrigger>
          <TabsTrigger value="blacklist">Blacklist</TabsTrigger>
        </TabsList>

        <TabsContent value="board" className="pt-4">
          <ScreeningBoardPrototype onBlacklist={handleBlacklist} />
        </TabsContent>
        <TabsContent value="apply" className="pt-4">
          <ApplyPrototype />
        </TabsContent>
        <TabsContent value="create" className="pt-4">
          <JobModalPrototype />
        </TabsContent>
        <TabsContent value="blacklist" className="pt-4">
          <BlacklistPrototype entries={blacklist} onRemove={handleUnblock} />
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default RecruitingPrototype;
