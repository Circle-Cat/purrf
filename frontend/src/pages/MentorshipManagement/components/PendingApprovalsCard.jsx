import { useNavigate } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { formatDateWithZone, resolveViewerTimezone } from "@/utils/dateTime";
import {
  approvalActionLabel,
  approvalPairLabel,
  approvalPersonLabel,
  approvalReviewLink,
} from "@/pages/MentorshipManagement/utils/approvalLabels";

/**
 * The mentorship approval requests waiting on the signed-in reviewer, at the
 * top of Mentorship Management. Renders nothing when there are none.
 *
 * Decisions are not taken here: each row's Review opens the page of what the
 * request is about -- the round's matching results, the person in the
 * Needs exemption list, or (ending a pair) the mentee's page -- and the
 * reviewer decides there, with the thing in front of them.
 *
 * @param {object} props
 * @param {object[]} props.requests Pending requests, oldest first.
 * @returns {JSX.Element|null}
 */
const PendingApprovalsCard = ({ requests }) => {
  const navigate = useNavigate();
  if (!requests?.length) return null;
  const timezone = resolveViewerTimezone();

  return (
    <Card className="mb-6 border-gray-200">
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Pending approvals</CardTitle>
        <span className="text-xs text-muted-foreground">
          {requests.length} waiting
        </span>
      </CardHeader>
      <CardContent>
        <ul className="divide-y divide-border">
          {requests.map((r) => (
            <li key={r.requestId} className="flex flex-wrap gap-3 py-3">
              <div className="min-w-64 flex-1 space-y-1 text-sm">
                <p className="font-medium">
                  {approvalActionLabel(r.action)}
                  {r.round?.name ? ` · ${r.round.name}` : ""}
                  {r.person ? ` · ${approvalPersonLabel(r.person)}` : ""}
                  {r.pair ? ` · ${approvalPairLabel(r.pair)}` : ""}
                </p>
                <p className="text-muted-foreground">
                  From {approvalPersonLabel(r.raisedBy)}
                  {r.createdAt
                    ? `, ${formatDateWithZone(r.createdAt, timezone)}`
                    : ""}
                </p>
                {r.reason ? <p>{r.reason}</p> : null}
              </div>
              <div className="flex items-start">
                <Button
                  size="sm"
                  onClick={() => navigate(approvalReviewLink(r))}
                >
                  Review
                </Button>
              </div>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
};

export default PendingApprovalsCard;
