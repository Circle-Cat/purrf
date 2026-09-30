import { useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ROUTE_PATHS } from "@/constants/RoutePaths";
import { unresolvedPersonLabel } from "@/pages/Recruiting/components/personLabel";
import { useRoundFeedback } from "@/pages/MentorshipManagement/hooks/useRoundFeedback";

// Columns take a share of the table's width and everything wraps inside its
// column, so answers of up to 300 characters do not stretch the row. Below
// the table's minimum width it scrolls sideways inside its card rather than
// squeezing the columns. The shares add up to 100%.
const CELL = "align-top whitespace-normal break-words";

// In the order the feedback form asks its questions, so the two about the
// partner sit together.
const COLUMNS = [
  { header: "User ID", accessor: "userId", width: "w-[7%]" },
  { header: "Name", accessor: "name", width: "w-[12%]" },
  { header: "Role", accessor: "role", width: "w-[7%]" },
  {
    header: "Most Valuable Aspects",
    accessor: "mostValuableAspects",
    width: "w-[20%]",
  },
  { header: "Challenges", accessor: "challenges", width: "w-[20%]" },
  { header: "Program Rating", accessor: "programRating", width: "w-[7%]" },
  { header: "Rating of Partner", accessor: "partnerRating", width: "w-[7%]" },
  {
    header: "Feedback About Partner",
    accessor: "partnerFeedback",
    width: "w-[20%]",
  },
];

// The ID goes beside the name, as everywhere in the console: two partners
// can share a name.
const partnerLabel = (entry) =>
  entry.partnerName
    ? `${entry.partnerName} (ID ${entry.partnerId})`
    : unresolvedPersonLabel(entry.partnerId);

/**
 * One line per partner. What someone wrote about a partner sits on the
 * writer's row: it is their view of the partner, named in each line.
 */
const PartnerLines = ({ entries, render }) => {
  const lines = entries.filter((e) => render(e) != null);
  if (lines.length === 0) return "—";
  return (
    <div className="space-y-1">
      {lines.map((e, i) => (
        // Nothing on the write side stops a partner appearing twice.
        <div key={`${e.partnerId}-${i}`}>
          <span className="text-gray-500">{partnerLabel(e)}: </span>
          {render(e)}
        </div>
      ))}
    </div>
  );
};

/** What someone wrote about each partner, each line wrapped. */
const PartnerFeedbackLines = ({ entries }) => {
  const lines = entries.filter((e) => e.feedback);
  if (lines.length === 0) return "—";
  return (
    <div className="space-y-2">
      {lines.map((e, i) => (
        <div key={`${e.partnerId}-${i}`}>
          <span className="text-gray-500">{partnerLabel(e)}: </span>
          &ldquo;{e.feedback}&rdquo;
        </div>
      ))}
    </div>
  );
};

const toRow = (p) => ({
  userId: p.userId,
  name: <span className="font-medium">{p.name}</span>,
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
  partnerFeedback: <PartnerFeedbackLines entries={p.partnerFeedback ?? []} />,
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
  const location = useLocation();
  const returnSearch = location.state?.returnSearch;
  const { feedback, isLoading, error } = useRoundFeedback(roundId);
  const [role, setRole] = useState("all");
  const [notSentOnly, setNotSentOnly] = useState(false);

  const rows = (feedback?.participants ?? [])
    .filter((p) => role === "all" || p.role === role)
    .filter((p) => !notSentOnly || !p.hasSubmitted);

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
          <div className="rounded-lg border">
            <Table className="min-w-[960px] table-fixed">
              <TableHeader>
                <TableRow>
                  {COLUMNS.map((col) => (
                    <TableHead
                      key={col.accessor}
                      className={`${col.width} whitespace-normal`}
                    >
                      {col.header}
                    </TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((p) => {
                  const row = toRow(p);
                  return (
                    <TableRow key={p.userId}>
                      {COLUMNS.map((col) => (
                        <TableCell key={col.accessor} className={CELL}>
                          {row[col.accessor]}
                        </TableCell>
                      ))}
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
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
          to={{
            pathname: ROUTE_PATHS.MENTORSHIP_MANAGEMENT,
            search: typeof returnSearch === "string" ? returnSearch : "",
          }}
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
