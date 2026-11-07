import { X } from "lucide-react";
import { Button } from "@/components/ui/button";

/**
 * The card shown beside a highlighted element during an onboarding tour.
 *
 * @param {Object} props
 * @param {React.ReactNode} props.title - The step's heading.
 * @param {React.ReactNode} props.body - The step's text.
 * @param {boolean} props.showBack - Whether a previous step exists.
 * @param {boolean} props.isLastStep - Shows Done instead of Next.
 * @param {boolean} props.showDismiss - Shows the "Don't show again" link.
 * @param {() => void} props.onBack - Back was clicked.
 * @param {() => void} props.onNext - Next was clicked.
 * @param {() => void} props.onDone - Done was clicked.
 * @param {() => void} props.onClose - The close button was clicked.
 * @param {() => void} props.onDismiss - "Don't show again" was clicked.
 * @param {Object} [props.containerProps] - Extra attributes for the card,
 *   such as the dialog role the tour library supplies.
 *   The forward button carries `data-action="primary"`, which is where the
 *   tour library puts focus when a step opens.
 * @returns {JSX.Element}
 */
const GuideTooltip = ({
  title,
  body,
  showBack,
  isLastStep,
  showDismiss,
  onBack,
  onNext,
  onDone,
  onClose,
  onDismiss,
  containerProps = {},
}) => (
  <div
    {...containerProps}
    aria-label={typeof title === "string" ? title : undefined}
    className="relative w-80 max-w-[calc(100vw-32px)] rounded-lg border bg-popover p-4 text-popover-foreground shadow-md"
  >
    <Button
      type="button"
      variant="ghost"
      size="icon-sm"
      aria-label="Close tour"
      className="absolute right-2 top-2 text-muted-foreground"
      onClick={onClose}
    >
      <X />
    </Button>
    <h2 className="pr-8 text-base font-semibold">{title}</h2>
    <p className="mt-2 text-sm text-muted-foreground">{body}</p>
    <div className="mt-4 flex items-center gap-2">
      {showDismiss && (
        <button
          type="button"
          className="cursor-pointer text-xs text-muted-foreground underline-offset-4 hover:underline"
          onClick={onDismiss}
        >
          Don&apos;t show again
        </button>
      )}
      <div className="ml-auto flex gap-2">
        {showBack && (
          <Button type="button" variant="outline" size="sm" onClick={onBack}>
            Back
          </Button>
        )}
        {isLastStep ? (
          <Button
            type="button"
            size="sm"
            data-action="primary"
            onClick={onDone}
          >
            Done
          </Button>
        ) : (
          <Button
            type="button"
            size="sm"
            data-action="primary"
            onClick={onNext}
          >
            Next
          </Button>
        )}
      </div>
    </div>
  </div>
);

export default GuideTooltip;
