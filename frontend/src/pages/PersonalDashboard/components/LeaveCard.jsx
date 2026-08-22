import { useNavigate } from "react-router-dom";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ROUTE_PATHS } from "@/constants/RoutePaths";

/**
 * LeaveCard
 *
 * The way in to the viewer's own leave.
 *
 * Shown only to somebody the feature applies to. It carries no figure of its
 * own on purpose: a balance here would be a second place for the same number
 * to live, and the one screen that owns it is a page away.
 *
 * A sibling of the approvals card, never a parent of it. The two answer
 * different questions -- whether you get leave, and whether anybody needs you
 * to decide theirs -- and either can be true on its own. A manager outside the
 * leave population has the second and not the first.
 *
 * The caller decides whether to render it at all.
 */
const LeaveCard = () => {
  const navigate = useNavigate();

  return (
    <Card className="border-gray-200 shadow-sm">
      <CardHeader>
        <CardTitle className="text-lg font-semibold">My Leave</CardTitle>
      </CardHeader>
      <CardContent className="flex items-center justify-between gap-4">
        <p className="text-sm text-muted-foreground">
          Ask for leave and see what you have asked for.
        </p>
        <Button onClick={() => navigate(ROUTE_PATHS.LEAVE_REQUESTS)}>
          Open
        </Button>
      </CardContent>
    </Card>
  );
};

export default LeaveCard;
