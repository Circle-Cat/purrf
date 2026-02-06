import React, { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { User, Mail, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { MatchStatus } from "@/constants/matchStatus";

/**
 * MatchingResultDialog
 *
 * A controlled dialog component used to display mentorship matching results
 * for a specific round.
 *
 * The dialog renders different status messages and partner details based on
 * the provided match data. The trigger button is enabled when either:
 * - the matching results are in the announcement period, or
 * - the user has already been successfully matched.
 *
 * @param {Object} props
 * @param {string} props.roundName
 *   The display name of the mentorship round.
 * @param {boolean} props.canViewMatch
 *   Whether the matching results are currently in the announcement period.
 * @param {Object|null} props.matchData
 *   Preloaded matching result data. If null or invalid, the dialog falls back
 *   to an "unknown" status.
 */

export default function MatchingResultDialog({
  roundName,
  canViewMatch,
  matchData,
}) {
  const [open, setOpen] = useState(false);

  // Destructure values from the provided matchData
  const { currentStatus = MatchStatus.UNKNOWN, partners = [] } =
    matchData || {};

  // Core logic:
  // The button is clickable if the announcement period is active OR the user is already matched
  const isMatched = currentStatus === MatchStatus.MATCHED;
  const isDisabled = !canViewMatch && !isMatched;

  /**
   * Status message configuration
   */
  const statusConfig = {
    [MatchStatus.MATCHED]: {
      title: "Congratulations!",
      description: "Here are your partner details for this round.",
      color: "text-green-600",
    },
    [MatchStatus.UNMATCHED]: {
      title: "No Match Found",
      description:
        "We're sorry that we couldn't find a suitable match for you in this round.",
      color: "text-amber-600",
    },
    [MatchStatus.REJECTED]: {
      title: "Application Update",
      description:
        "Thank you for applying. Unfortunately, we couldn't include you in this round.",
      color: "text-destructive",
    },
    [MatchStatus.PENDING]: {
      title: "Matching Has Not Started",
      description: "The matching process for this round hasn't begun yet.",
      color: "text-blue-600",
    },
    [MatchStatus.UNKNOWN]: {
      title: "Status Unknown",
      description:
        "We're having trouble determining your match status. Please contact our support team for assistance.",
      color: "text-muted-foreground",
    },
  };

  const currentConfig =
    statusConfig[currentStatus] || statusConfig[MatchStatus.UNKNOWN];

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button
          variant="outline"
          disabled={isDisabled}
          className="border-[#6035F3] text-[#6035F3] hover:bg-purple-50 disabled:opacity-50"
        >
          View Matching Result
        </Button>
      </DialogTrigger>

      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle>{roundName} Matching Results</DialogTitle>
          <DialogDescription asChild>
            <div className="space-y-1">
              <p className={`font-semibold ${currentConfig.color}`}>
                {currentConfig.title}
              </p>
              <p className="text-muted-foreground">
                {currentConfig.description}
              </p>
            </div>
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 py-4 max-h-[60vh] overflow-y-auto pr-2">
          {partners.length > 0 ? (
            partners.map((partner) => (
              <div
                key={partner.id}
                className="flex flex-col gap-3 p-4 border rounded-lg bg-card hover:bg-accent/5 transition-colors"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center text-primary">
                      <User className="h-5 w-5" />
                    </div>
                    <div>
                      <h4 className="font-semibold text-foreground">
                        {partner.preferredName ||
                          `${partner.firstName} ${partner.lastName}`}
                      </h4>
                      <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
                        <Mail className="h-3.5 w-3.5" />
                        <span>{partner.primaryEmail}</span>
                      </div>
                    </div>
                  </div>
                  <Badge variant="secondary" className="capitalize">
                    {partner.participantRole}
                  </Badge>
                </div>

                {partner.recommendationReason && (
                  <div className="mt-2 bg-muted/50 p-3 rounded-md text-sm">
                    <div className="flex items-start gap-2">
                      <Sparkles className="h-4 w-4 text-amber-500 mt-0.5 flex-shrink-0" />
                      <div>
                        <span className="font-medium text-foreground">
                          Why you matched:{" "}
                        </span>
                        <span className="text-muted-foreground">
                          {partner.recommendationReason}
                        </span>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            ))
          ) : (
            <div className="text-center py-8 text-muted-foreground border rounded-lg bg-muted/20 text-sm">
              No matching details available.
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
