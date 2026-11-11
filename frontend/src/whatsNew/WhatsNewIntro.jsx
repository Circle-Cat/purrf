import {
  Popover,
  PopoverAnchor,
  PopoverContent,
} from "@/components/ui/popover";
import { Button } from "@/components/ui/button";
import { useWhatsNew } from "@/whatsNew/WhatsNewContext";

/**
 * Wraps the avatar and, once per account, points at it with a small
 * non-modal popover explaining where What's new lives. Either button records
 * the pointer as done; clicking elsewhere or pressing Escape only hides it
 * until the next page load.
 *
 * @param {Object} props
 * @param {React.ReactNode} props.children - The avatar button and its dot.
 * @returns {JSX.Element}
 */
const WhatsNewIntro = ({ children }) => {
  const { showIntro, acknowledgeIntro, hideIntro, openPanel } = useWhatsNew();

  const gotIt = () => acknowledgeIntro();
  const showMe = () => {
    acknowledgeIntro();
    openPanel();
  };

  return (
    <Popover
      open={showIntro}
      onOpenChange={(open) => {
        if (!open) hideIntro();
      }}
      modal={false}
    >
      <PopoverAnchor asChild>
        <span className="relative inline-flex">{children}</span>
      </PopoverAnchor>
      <PopoverContent
        align="end"
        className="flex flex-col gap-3"
        aria-labelledby="whats-new-intro-title"
        // It appears without the user asking, so it must not take focus.
        onOpenAutoFocus={(event) => event.preventDefault()}
      >
        <h2 id="whats-new-intro-title" className="text-sm font-semibold">
          What&apos;s new
        </h2>
        <p className="text-sm text-muted-foreground">
          New features and tips for Purrf show up here. Look for the dot.
        </p>
        <div className="flex justify-end gap-2">
          <Button size="sm" variant="ghost" onClick={gotIt}>
            Got it
          </Button>
          <Button size="sm" onClick={showMe}>
            Show me
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  );
};

export default WhatsNewIntro;
