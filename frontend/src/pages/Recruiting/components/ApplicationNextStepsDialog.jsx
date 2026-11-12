import { useNavigate } from "react-router-dom";
import { Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { ROUTE_PATHS } from "@/constants/RoutePaths";

const STEPS = [
  { title: "Apply", detail: "Done.", done: true },
  {
    title: "Get admitted",
    detail: "We review your application and let you know by email.",
  },
  {
    title: "Register for a round",
    detail:
      "Once admitted, register on your Personal Dashboard each time a round opens. You're only matched with a partner after you register.",
  },
];

/**
 * Shown once a mentorship application is sent, because applying alone puts
 * nobody in a round: admission comes by email, and only a registration on
 * the Personal Dashboard gets someone matched.
 *
 * Closing it any other way counts as "View my application", so the
 * candidate is never left on a form that has already been sent.
 *
 * @param {{open: boolean, onViewApplication: () => void}} props
 */
const ApplicationNextStepsDialog = ({ open, onViewApplication }) => {
  const navigate = useNavigate();

  return (
    <Dialog open={open} onOpenChange={(next) => !next && onViewApplication()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Application submitted</DialogTitle>
          <DialogDescription>
            Applying is the first step. Here&apos;s what comes next:
          </DialogDescription>
        </DialogHeader>
        <ol className="space-y-3">
          {STEPS.map((step, index) => (
            <li key={step.title} className="flex items-start gap-3">
              <span
                className={
                  step.done
                    ? "flex size-6 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground"
                    : "flex size-6 shrink-0 items-center justify-center rounded-full border text-xs text-muted-foreground"
                }
              >
                {step.done ? (
                  <Check className="size-4" aria-label="Done" />
                ) : (
                  index + 1
                )}
              </span>
              <div>
                <p className="text-sm font-medium text-slate-900">
                  {step.title}
                </p>
                <p className="text-sm text-muted-foreground">{step.detail}</p>
              </div>
            </li>
          ))}
        </ol>
        <p className="text-sm text-muted-foreground">
          You can check where you are anytime under My Applications on your
          Personal Dashboard.
        </p>
        <DialogFooter>
          <Button variant="outline" onClick={onViewApplication}>
            View my application
          </Button>
          <Button onClick={() => navigate(ROUTE_PATHS.PERSONAL_DASHBOARD)}>
            Go to Personal Dashboard
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default ApplicationNextStepsDialog;
