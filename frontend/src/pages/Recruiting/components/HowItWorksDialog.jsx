import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogTrigger,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";

/**
 * A "How it works" help button that opens a modal explaining a workflow.
 * Presentational and data-driven: pass one of the guide constants from
 * guideContent.js.
 *
 * @param {object} props
 * @param {string} props.title  Dialog heading.
 * @param {string} [props.description]  One-line summary under the title.
 * @param {{title: string, detail: string}[]} props.steps  Ordered workflow steps.
 * @param {{name: string, description: string}[]} [props.statuses]  Badge +
 *          description legend, e.g. a status legend or a key-concepts glossary.
 * @param {string} [props.statusesTitle]  Heading for the legend section.
 * @param {string[]} [props.notes]  Gate/rule notes.
 * @returns {JSX.Element}
 */
const HowItWorksDialog = ({
  title,
  description,
  steps,
  statuses,
  statusesTitle = "Statuses",
  notes,
}) => {
  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          How it works
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          {description && <DialogDescription>{description}</DialogDescription>}
        </DialogHeader>

        <ol className="list-decimal space-y-2 pl-5 text-sm">
          {steps.map((step) => (
            <li key={step.title}>
              <span className="font-medium text-slate-900">{step.title}</span>
              <span className="text-slate-600"> — {step.detail}</span>
            </li>
          ))}
        </ol>

        {statuses?.length > 0 && (
          <div className="space-y-2">
            <h3 className="text-sm font-semibold text-slate-900">
              {statusesTitle}
            </h3>
            <ul className="space-y-1.5">
              {statuses.map((status) => (
                <li key={status.name} className="flex items-start gap-2">
                  <Badge variant="secondary" className="shrink-0">
                    {status.name}
                  </Badge>
                  <span className="text-sm text-slate-600">
                    {status.description}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {notes?.length > 0 && (
          <div className="space-y-2">
            <h3 className="text-sm font-semibold text-slate-900">
              Good to know
            </h3>
            <ul className="list-disc space-y-1 pl-5 text-sm text-slate-600">
              {notes.map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};

export default HowItWorksDialog;
