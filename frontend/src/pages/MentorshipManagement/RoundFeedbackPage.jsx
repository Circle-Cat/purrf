import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import Table from "@/components/common/Table";
import { ROUTE_PATHS } from "@/constants/RoutePaths";
import { unresolvedPersonLabel } from "@/pages/Recruiting/components/personLabel";
import { useRoundFeedback } from "@/pages/MentorshipManagement/hooks/useRoundFeedback";

// In the order the feedback form asks its questions, so the two about the
// partner sit together.
const COLUMNS = [
  { header: "Name", accessor: "name" },
  { header: "Role", accessor: "role" },
  { header: "Most Valuable Aspects", accessor: "mostValuableAspects" },
  { header: "Challenges", accessor: "challenges" },
  { header: "Program Rating", accessor: "programRating" },
  { header: "Rating of Partner", accessor: "partnerRating" },
  { header: "Feedback About Partner", accessor: "partnerFeedback" },
];

const partnerLabel = (entry) =>
  entry.partnerName ?? unresolvedPersonLabel(entry.partnerId);

/**
 * One line per partner. What someone wrote about a partner sits on the
 * writer's row: it is their view of the partner, named in each line.
 */
const PartnerLines = ({ entries, render }) => {
  const lines = entries.filter((e) => render(e) != null);
  if (lines.length === 0) return "—";
  return (
    <div className="space-y-1">
      {lines.map((e) => (
        <p key={e.partnerId}>
          <span className="text-gray-500">{partnerLabel(e)}: </span>
          {render(e)}
        </p>
      ))}
    </div>
  );
};

const toRow = (p) => ({
  name: (
    <div>
      <div className="font-medium">{p.name}</div>
      <div className="text-xs text-gray-500">ID {p.userId}</div>
    </div>
  ),
  role: p.role ?? "—",
  mostValuableAspects: p.mostValuableAspects || "—",
  challenges: p.challenges || "—",
  programRating: p.programRating != null ? `${p.programRating}/5` : "—",
  partnerRating: (
    <PartnerLines
      entries={p.partnerFeedback ?? []}
      render={(e) => (e.rating != null ? `${e.rating}/5` : null)}
    />
  ),
  partnerFeedback: (
    <PartnerLines
      entries={p.partnerFeedback ?? []}
      render={(e) => (e.feedback ? <>&ldquo;{e.feedback}&rdquo;</> : null)}
    />
  ),
});

/**
 * RoundFeedbackPage
 *
 * Everyone a round's feedback is asked of, with what each of them sent, opened
 * from the Feedback column of the rounds table. Someone who has not sent it is
 * a row of dashes; "Not sent only" narrows the list to them.
 *
 * Route: /mentorship-management/rounds/:roundId/feedback
 *
 * @returns {JSX.Element}
 */
const RoundFeedbackPage = () => {
  const { roundId } = useParams();
  const { feedback, isLoading, error } = useRoundFeedback(roundId);
  const [role, setRole] = useState("all");
  const [notSentOnly, setNotSentOnly] = useState(false);

  const rows = (feedback?.participants ?? [])
    .filter((p) => role === "all" || p.role === role)
    .filter((p) => !notSentOnly || !p.hasSubmitted)
    .sort((a, b) => a.name.localeCompare(b.name));

  let body;
  if (isLoading) {
    body = (
      <div className="py-10 text-center text-gray-500">Loading feedback...</div>
    );
  } else if (error || !feedback) {
    body = (
      <div className="py-10 text-center text-gray-500">
        Could not load this round&apos;s feedback.
      </div>
    );
  } else {
    body = (
      <>
        <div className="mb-4 flex flex-wrap items-center gap-4 text-sm text-gray-700">
          <label className="flex items-center gap-2">
            Role
            <select
              aria-label="Role"
              value={role}
              onChange={(e) => setRole(e.target.value)}
              className="h-9 rounded-md border border-gray-300 px-2"
            >
              <option value="all">All roles</option>
              <option value="mentor">Mentor</option>
              <option value="mentee">Mentee</option>
            </select>
          </label>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={notSentOnly}
              onChange={(e) => setNotSentOnly(e.target.checked)}
            />
            Not sent only
          </label>
        </div>
        {rows.length > 0 ? (
          <Table columns={COLUMNS} data={rows.map(toRow)} />
        ) : (
          <div className="py-8 text-center text-gray-500">Nobody here.</div>
        )}
      </>
    );
  }

  return (
    <Card className="border-gray-200">
      <CardHeader className="space-y-2">
        <Link
          to={ROUTE_PATHS.MENTORSHIP_MANAGEMENT}
          className="flex w-fit items-center gap-1 text-sm text-gray-600 hover:text-gray-900"
        >
          <ArrowLeft className="h-4 w-4" />
          Mentorship Management
        </Link>
        <div className="flex flex-wrap items-baseline gap-3">
          <CardTitle>
            Feedback{feedback ? ` — ${feedback.roundName}` : ""}
          </CardTitle>
          {feedback ? (
            <span className="text-sm text-gray-500">
              {feedback.sent} of {feedback.owed} sent
            </span>
          ) : null}
        </div>
      </CardHeader>
      <CardContent>{body}</CardContent>
    </Card>
  );
};

export default RoundFeedbackPage;
