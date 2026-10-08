import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import BlockDialog from "@/pages/AdminAccounts/components/BlockDialog";
import {
  createBlockRequest,
  getBlockPreflight,
  getUserAdmins,
} from "@/api/adminAccountsApi";
import { useAuth } from "@/context/auth";
import { approvalPersonLabel } from "@/pages/MentorshipManagement/utils/approvalLabels";

// Shown to the reviewer as where the request came from; the backend accepts
// it only from holders of mentorship write access.
const RAISED_FROM = "mentorship_participant";

// This page offers no reassign or withdraw, so the dialog does not promise it.
const REQUEST_DESCRIPTION =
  "This does not block anyone yet. It goes to the reviewer you name below, and nothing changes for this person until they approve it.";

/**
 * Ask a user admin to block this person from Purrf, from their mentorship
 * page. While a request waits, says who it waits on instead. Blocking is
 * about the account, not the round, so it is offered in any round.
 *
 * @param {{person: Object, pendingBlockRequest: Object|null,
 *          canWrite: boolean, onRequested: () => void}} props
 */
const BlockFromPurrf = ({
  person,
  pendingBlockRequest,
  canWrite,
  onRequested,
}) => {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const [preflight, setPreflight] = useState(null);
  const [preflightError, setPreflightError] = useState(false);
  const [holders, setHolders] = useState([]);
  const [holdersError, setHoldersError] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  if (pendingBlockRequest) {
    return (
      <p className="text-sm text-amber-800">
        Block requested — waiting on{" "}
        {approvalPersonLabel(pendingBlockRequest.reviewer)}
      </p>
    );
  }
  if (!canWrite || person.isBlocked) return null;

  // Read on every open: the counts and the reviewers can change between.
  const openDialog = () => {
    setPreflight(null);
    setPreflightError(false);
    setHoldersError(false);
    setOpen(true);
    getBlockPreflight(person.userId)
      .then(({ data }) => setPreflight(data))
      .catch(() => setPreflightError(true));
    getUserAdmins()
      .then(({ data }) => setHolders(data ?? []))
      .catch(() => setHoldersError(true));
  };

  const confirm = ({ reason, reviewerId }) => {
    if (submitting) return;
    setSubmitting(true);
    createBlockRequest(
      { userId: person.userId, reason, reviewerId },
      RAISED_FROM,
    )
      .then(({ data }) => {
        setOpen(false);
        toast.success(`Block requested — sent to ${data.reviewerName}.`);
        onRequested();
      })
      .catch((e) => toast.error(e?.response?.data?.message ?? e.message))
      .finally(() => setSubmitting(false));
  };

  return (
    <>
      <Button variant="destructive" size="sm" onClick={openDialog}>
        Block from Purrf
      </Button>
      <BlockDialog
        open={open}
        onOpenChange={setOpen}
        mode="request"
        account={person}
        preflight={preflight}
        preflightError={preflightError}
        holders={holders}
        holdersError={holdersError}
        currentUserId={user?.userId}
        onConfirm={confirm}
        submitting={submitting}
        requestDescription={REQUEST_DESCRIPTION}
      />
    </>
  );
};

export default BlockFromPurrf;
