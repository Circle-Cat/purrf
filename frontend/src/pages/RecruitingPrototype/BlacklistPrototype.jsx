import { Ban, Mail, Phone, Undo2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";

/**
 * BlacklistPrototype
 *
 * Standalone org-wide blacklist page for the Recruiting v2 demo. Lists users
 * who have been blocked (e.g. blacklisted from a screening board). Blocking is
 * a user-level, cross-posting state (mirrors `users.is_blocked`) — distinct
 * from a per-application Rejected, which only cools down re-application.
 *
 * @component
 * @param {Object} props
 * @param {Array<{id:number,name:string,email:string,phone:string,reason:string,blockedAt:string}>} props.entries
 * @param {(id:number) => void} props.onRemove - Unblock (remove from the list).
 * @returns {JSX.Element}
 */
const BlacklistPrototype = ({ entries = [], onRemove }) => {
  return (
    <div className="max-w-3xl mx-auto space-y-5">
      <div className="flex items-start gap-3">
        <div className="h-10 w-10 rounded-lg bg-slate-800 flex items-center justify-center text-white shrink-0">
          <Ban size={18} />
        </div>
        <div>
          <h2 className="text-xl font-semibold">Blacklist</h2>
          <p className="text-sm text-muted-foreground mt-0.5">
            Blocked users are rejected at the application entry point across all
            postings — no cooldown, no re-apply. Unblock to lift the block.
          </p>
        </div>
        <Badge variant="outline" className="ml-auto shrink-0">
          {entries.length} blocked
        </Badge>
      </div>

      {entries.length === 0 ? (
        <Card className="p-10 text-center text-sm text-muted-foreground">
          No blocked users. Blacklist someone from the Screening Board and they
          will appear here.
        </Card>
      ) : (
        <div className="space-y-3">
          {entries.map((e) => (
            <Card
              key={e.id}
              className="p-4 flex items-start justify-between gap-4"
            >
              <div className="min-w-0 space-y-1.5">
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-slate-900">{e.name}</span>
                  <Badge
                    variant="outline"
                    className="text-xs border-slate-300 text-slate-500"
                  >
                    Blocked {e.blockedAt}
                  </Badge>
                </div>
                <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
                  <span className="flex items-center gap-1.5">
                    <Mail size={12} className="text-slate-400" />
                    {e.email}
                  </span>
                  <span className="flex items-center gap-1.5">
                    <Phone size={12} className="text-slate-400" />
                    {e.phone}
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
                className="shrink-0 gap-1"
                onClick={() => onRemove?.(e.id)}
              >
                <Undo2 size={14} />
                Unblock
              </Button>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
};

export default BlacklistPrototype;
