import { createContext, useContext, useMemo } from "react";
import { Joyride } from "react-joyride";
import GuideTooltip from "@/guides/GuideTooltip";

// The only file that knows about react-joyride. The GuideProvider decides
// which step shows and what every button does; this just draws it.

// Above the header (z-[100]), the sidebar (z-[90]) and the Contact Us dialog
// (z-[1000]).
const TOUR_Z_INDEX = 1200;

const TourControlsContext = createContext(null);

/**
 * Bridges react-joyride's tooltip slot to GuideTooltip. Defined at module
 * level so its identity is stable across renders.
 */
const JoyrideTooltip = ({ step, tooltipProps }) => {
  const controls = useContext(TourControlsContext);
  return (
    <GuideTooltip
      title={step.title}
      body={step.content}
      showBack={controls.showBack}
      isLastStep={controls.isLastStep}
      showDismiss={controls.showDismiss}
      onBack={controls.onBack}
      onNext={controls.onNext}
      onDone={controls.onDone}
      onClose={controls.onClose}
      onDismiss={controls.onDismiss}
      containerProps={tooltipProps}
    />
  );
};

/**
 * Draws one step of a running tour: the overlay, the spotlight on the
 * step's `[data-tour]` element and a GuideTooltip beside it. Navigation is
 * fully controlled by the caller.
 *
 * @param {Object} props
 * @param {Array<{anchor: string, title: string, body: string}>} props.steps -
 *   Every step of the guide.
 * @param {number} props.stepIndex - The step to show.
 * @param {boolean} props.showBack - Whether Back is offered.
 * @param {boolean} props.isLastStep - Whether Done replaces Next.
 * @param {boolean} props.showDismiss - Whether "Don't show again" is offered.
 * @param {() => void} props.onBack - Back was clicked.
 * @param {() => void} props.onNext - Next was clicked.
 * @param {() => void} props.onDone - Done was clicked.
 * @param {() => void} props.onClose - The close button was clicked.
 * @param {() => void} props.onDismiss - "Don't show again" was clicked.
 * @returns {JSX.Element}
 */
const GuideTourRenderer = ({
  steps,
  stepIndex,
  showBack,
  isLastStep,
  showDismiss,
  onBack,
  onNext,
  onDone,
  onClose,
  onDismiss,
}) => {
  const joyrideSteps = useMemo(
    () =>
      steps.map((step) => ({
        target: `[data-tour="${step.anchor}"]`,
        title: step.title,
        content: step.body,
      })),
    [steps],
  );

  const controls = useMemo(
    () => ({
      showBack,
      isLastStep,
      showDismiss,
      onBack,
      onNext,
      onDone,
      onClose,
      onDismiss,
    }),
    [
      showBack,
      isLastStep,
      showDismiss,
      onBack,
      onNext,
      onDone,
      onClose,
      onDismiss,
    ],
  );

  return (
    <TourControlsContext.Provider value={controls}>
      <Joyride
        run
        continuous
        stepIndex={stepIndex}
        steps={joyrideSteps}
        tooltipComponent={JoyrideTooltip}
        options={{
          zIndex: TOUR_Z_INDEX,
          skipBeacon: true,
          blockTargetInteraction: true,
          overlayClickAction: false,
          // Escape is handled by the GuideProvider, so it means the same as
          // the close button.
          dismissKeyAction: false,
          arrowColor: "var(--popover)",
        }}
      />
    </TourControlsContext.Provider>
  );
};

export default GuideTourRenderer;
