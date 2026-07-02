import { Button } from "@/components/ui/button";

/**
 * Pre-content state for a page whose data hasn't rendered yet: a muted
 * "Loading…" placeholder while the fetch is in flight, or an inline error
 * message with a Retry button once it has failed (so a failed load is never
 * mistaken for an empty page and can be recovered without a reload).
 *
 * @param {{error: boolean, errorMessage: string, onRetry: () => void}} props
 */
const LoadGate = ({ error, errorMessage, onRetry }) => {
  if (!error) {
    return <p className="p-6 text-sm text-muted-foreground">Loading…</p>;
  }
  return (
    <div className="flex flex-col items-start gap-3 p-6">
      <p className="text-sm text-muted-foreground">{errorMessage}</p>
      <Button onClick={onRetry}>Retry</Button>
    </div>
  );
};

export default LoadGate;
