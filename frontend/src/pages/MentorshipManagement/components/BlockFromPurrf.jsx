import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import ApprovalRequestDialog from "@/components/approval/ApprovalRequestDialog";
import BlockDialog from "@/pages/AdminAccounts/components/BlockDialog";
import {
  createBlockRequest,
  getBlockPreflight,
  getRaisedBlockRequests,
  getUserAdmins,
  reassignBlockRequest,
  withdrawBlockRequest,
} from "@/api/adminAccountsApi";
import { useAuth } from "@/context/auth";
import { approvalPersonLabel } from "@/pages/MentorshipManagement/utils/approvalLabels";

// Shown to the reviewer as where the request came from; the backend accepts
// it only from holders of mentorship write access.
const RAISED_FROM = "mentorship_participant";

const REQUEST_DESCRIPTION =
  "This does not block anyone yet. It goes to the reviewer you name below, and nothing changes for this person until they approve it. You can reassign or withdraw it while it waits.";

/**
 * Ask a user admin to block this person from Purrf, from their mentorship
 * page. While a request waits, says who it waits on instead; when the caller
 * raised it, they can reassign or withdraw it. Blocking is
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
  // The caller's own open request about this person, and which person the
  // read last settled for (success or failure).
  const [ownRequest, setOwnRequest] = useState(null);
  const [settledFor, setSettledFor] = useState(null);
  const [reassignOpen, setReassignOpen] = useState(false);
  const [reassigning, setReassigning] = useState(false);
  const [withdrawing, setWithdrawing] = useState(false);

  const personId = person.userId;
  useEffect(() => {
    // Without write access the read is a guaranteed 403.
    if (!canWrite) return;
    let current = true;
    getRaisedBlockRequests()
      .then(({ data }) => {
        if (!current) return;
        setOwnRequest(
          (data ?? []).find((r) => r.targetUserId === personId) ?? null,
        );
      })
      .catch(() => {
        if (current) setOwnRequest(null);
      })
      .finally(() => {
        if (current) setSettledFor(personId);
      });
    return () => {
      current = false;
    };
  }, [canWrite, personId]);
  const settled = !canWrite || settledFor === personId;

  const loadHolders = () => {
    setHoldersError(false);
    getUserAdmins()
      .then(({ data }) => setHolders(data ?? []))
      .catch(() => setHoldersError(true));
  };

  const reassign = (reviewerId) => {
    if (reassigning) return;
    setReassigning(true);
    reassignBlockRequest(ownRequest.id, reviewerId)
      .then(({ data }) => {
        setOwnRequest(data);
        setReassignOpen(false);
        toast.success(`Reassigned to ${data.reviewerName}.`);
        onRequested();
      })
      .catch((e) => toast.error(e?.response?.data?.message ?? e.message))
      .finally(() => setReassigning(false));
  };

  const withdraw = () => {
    if (withdrawing) return;
    setWithdrawing(true);
    withdrawBlockRequest(ownRequest.id)
      .then(() => {
        setOwnRequest(null);
        toast.success("Block request withdrawn.");
        onRequested();
      })
      .catch((e) => toast.error(e?.response?.data?.message ?? e.message))
      .finally(() => setWithdrawing(false));
  };

  if (pendingBlockRequest) {
    if (!settled) return null;
    if (ownRequest) {
      return (
        <>
          <span className="text-sm text-amber-800">
            {`Block requested — sent to ${ownRequest.reviewerName}`}
            <Button
              variant="link"
              className="px-2"
              onClick={() => {
                setReassignOpen(true);
                loadHolders();
              }}
            >
              Reassign
            </Button>
            <Button
              variant="link"
              className="px-2"
              onClick={withdraw}
              disabled={withdrawing}
            >
              Withdraw
            </Button>
          </span>
          <ApprovalRequestDialog
            open={reassignOpen}
            onOpenChange={setReassignOpen}
            title="Reassign this block request"
            description="The request stays open and nothing about it changes except who decides it. Both the old and the new reviewer are told."
            reviewers={holders}
            reviewersError={holdersError}
            excludeUserIds={[ownRequest.reviewerId, user?.userId, personId]}
            reviewerHint="The reviewer who has it now, you, and the person this is about are all left out of this list."
            confirmLabel="Reassign"
            onConfirm={({ reviewerId }) => reassign(reviewerId)}
            submitting={reassigning}
          />
        </>
      );
    }
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
    setOpen(true);
    getBlockPreflight(person.userId)
      .then(({ data }) => setPreflight(data))
      .catch(() => setPreflightError(true));
    loadHolders();
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
