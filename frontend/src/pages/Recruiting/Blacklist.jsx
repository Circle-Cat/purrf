import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Ban, Mail } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { listBlacklist, unblockUser } from "@/api/recruitingApi";

/** Org-wide blacklist admin page: view and clear blocked users. */
const Blacklist = () => {
  const [entries, setEntries] = useState([]);
  const [hasSearched, setHasSearched] = useState(false);
  const [searchDraft, setSearchDraft] = useState("");
  const [pendingUnblock, setPendingUnblock] = useState(null);

  const load = useCallback(async (search) => {
    const { data } = await listBlacklist(search || undefined);
    setEntries(data ?? []);
  }, []);

  useEffect(() => {
    load().catch((e) => toast.error(e.message));
  }, [load]);

  const runSearch = () => {
    setHasSearched(true);
    load(searchDraft).catch((e) => toast.error(e.message));
  };

  const confirmUnblock = () => {
    const target = pendingUnblock;
    setPendingUnblock(null);
    unblockUser(target.userId)
      .then(() => {
        setEntries((prev) => prev.filter((e) => e.userId !== target.userId));
        toast.success("User unblocked.");
      })
      .catch((e) => toast.error(e.message));
  };

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <div className="flex items-start gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-slate-800 text-white">
          <Ban size={18} />
        </div>
        <div>
          <h1 className="text-xl font-semibold">Blacklist</h1>
          <p className="mt-0.5 text-sm text-muted-foreground">
            Blocked users are rejected at the application entry point across
            all postings — no cooldown, no re-apply. Unblock to lift the
            block.
          </p>
        </div>
        <Badge variant="outline" className="ml-auto shrink-0">
          {entries.length} blocked
        </Badge>
      </div>

      <div className="flex gap-2">
        <Input
          placeholder="Search by name, email, or reason"
          value={searchDraft}
          onChange={(e) => setSearchDraft(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && runSearch()}
        />
        <Button variant="outline" onClick={runSearch}>
          Search
        </Button>
      </div>

      {entries.length === 0 ? (
        <Card className="p-10 text-center text-sm text-muted-foreground">
          {hasSearched
            ? "No blocked users match this search."
            : "No blocked users. Blacklist someone from the Screening Board and they will appear here."}
        </Card>
      ) : (
        <div className="space-y-3">
          {entries.map((e) => (
            <Card
              key={e.userId}
              className="flex items-start justify-between gap-4 p-4"
            >
              <div className="min-w-0 space-y-1.5">
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-slate-900">
                    {e.name}
                  </span>
                  <Badge
                    variant="outline"
                    className="border-slate-300 text-xs text-slate-500"
                  >
                    Blocked {new Date(e.blockedAt).toLocaleDateString()}
                  </Badge>
                </div>
                <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
                  <span className="flex items-center gap-1.5">
                    <Mail size={12} className="text-slate-400" />
                    {e.email}
                  </span>
                </div>
                <p className="text-sm text-slate-700">
                  <span className="text-slate-400">Reason: </span>
                  {e.reason}
                </p>
              </div>
              <Button
                variant="outline"
                size="sm"
                className="shrink-0"
                onClick={() => setPendingUnblock(e)}
              >
                Unblock
              </Button>
            </Card>
          ))}
        </div>
      )}

      <Dialog
        open={!!pendingUnblock}
        onOpenChange={(open) => !open && setPendingUnblock(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Unblock {pendingUnblock?.name}?</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-slate-600">
            They will be able to apply to every posting again.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setPendingUnblock(null)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={confirmUnblock}>
              Unblock
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default Blacklist;
