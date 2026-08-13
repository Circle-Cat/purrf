import React, { useState, useEffect, useRef } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { MentorshipParticipantRoles } from "@/constants/MentorshipParticipantRoles";
import {
  getMyMentorshipFeedback,
  getMyMentorshipPartners,
  postMyMentorshipFeedback,
} from "@/api/mentorshipApi";
import { toast } from "sonner";

const RATING_OPTIONS = [1, 2, 3, 4, 5];

const PARTNER_RATING_OPTIONS = [
  { value: 1, label: "Poor" },
  { value: 2, label: "Below Average" },
  { value: 3, label: "Average" },
  { value: 4, label: "Good" },
  { value: 5, label: "Excellent" },
];

const EMPTY_FORM = {
  mostValuableAspects: "",
  challenges: "",
  programRating: "",
  partnerFeedback: {},
};

/** Convert a feedback API payload into the dialog's form state. */
function toFormState(data) {
  const partnerFeedback = {};
  (data.partnerFeedback ?? []).forEach((entry) => {
    partnerFeedback[entry.partnerId] = {
      rating: entry.rating?.toString() ?? "",
      feedback: entry.feedback ?? "",
    };
  });
  return {
    mostValuableAspects: data.mostValuableAspects ?? "",
    challenges: data.challenges ?? "",
    programRating: data.programRating?.toString() ?? "",
    partnerFeedback,
  };
}

function TextArea({ value, onChange, placeholder, maxLength, disabled }) {
  return (
    <div className="relative">
      <textarea
        disabled={disabled}
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        maxLength={maxLength}
        className="w-full p-2 border rounded-md text-sm min-h-[80px] focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50 disabled:cursor-not-allowed"
      />
      <div className="absolute bottom-2 right-2 text-xs text-muted-foreground pointer-events-none">
        {(value || "").length} / {maxLength}
      </div>
    </div>
  );
}

/**
 * Dialog for submitting, editing, or viewing mentorship program feedback.
 *
 * Answers stay editable for as long as the feedback window is open, so the
 * trigger reads "Submit Feedback", "Edit Feedback", or -- once the deadline has
 * passed -- "View Feedback" over a fully disabled form. After the deadline a
 * participant who never submitted has nothing to look at, so nothing renders at
 * all. The trigger is also withheld until the initial status fetch resolves, to
 * avoid a "Submit" → "Edit" flash on page load.
 *
 * `programRating` and a rating per partner are required; the free-text answers
 * are optional.
 *
 * Partners are fetched by `roundId` rather than reused from the participant
 * card, so this dialog owns every field it renders.
 *
 * Inline field-level errors are shown on submit; each clears as soon as the
 * user interacts with that field. Closing the dialog discards anything typed
 * since the last successful save.
 *
 * @param {object}  props
 * @param {string}  props.roundId              - ID of the mentorship round.
 * @param {string}  props.roundName            - Display name of the round (used in the dialog title).
 * @param {boolean} props.isEditable           - When false the form is read-only.
 * @param {string|null} props.feedbackDeadlineText - Preformatted deadline shown in the hint, or null when unknown.
 */
export default function MentorshipFeedbackDialog({
  roundId,
  roundName,
  isEditable,
  feedbackDeadlineText,
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  const [participantRole, setParticipantRole] = useState(null);
  const [hasSubmitted, setHasSubmitted] = useState(null);
  const [fetchError, setFetchError] = useState(false);
  const [errors, setErrors] = useState({});

  const [mostValuableAspects, setMostValuableAspects] = useState("");
  const [challenges, setChallenges] = useState("");
  const [programRating, setProgramRating] = useState("");
  const [partners, setPartners] = useState([]);
  const [partnerFeedback, setPartnerFeedback] = useState({});

  // Last state persisted on the server. Closing the dialog rewinds to it so
  // abandoned edits never masquerade as saved answers on the next open.
  const savedFormRef = useRef(EMPTY_FORM);

  const isMentee = participantRole === MentorshipParticipantRoles.MENTEE;
  const partnerRoleLabel = isMentee ? "mentor" : "mentee";

  const applyFormState = (form) => {
    setMostValuableAspects(form.mostValuableAspects);
    setChallenges(form.challenges);
    setProgramRating(form.programRating);
    setPartnerFeedback(form.partnerFeedback);
  };

  const clearError = (field) => {
    setErrors((prev) => {
      if (!prev[field]) return prev;
      const next = { ...prev };
      delete next[field];
      return next;
    });
  };

  const updatePartnerField = (partnerId, field, value) => {
    setPartnerFeedback((prev) => ({
      ...prev,
      [partnerId]: { ...prev[partnerId], [field]: value },
    }));
  };

  useEffect(() => {
    // Without a round there is nothing to fetch; render a disabled trigger.
    if (!roundId) {
      setHasSubmitted(false);
      return;
    }
    let cancelled = false;
    Promise.all([
      getMyMentorshipFeedback(roundId),
      getMyMentorshipPartners(roundId),
    ])
      .then(([{ data }, { data: partnersData }]) => {
        if (cancelled) return;
        setParticipantRole(data.participantRole);
        setHasSubmitted(Boolean(data.hasSubmitted));
        setPartners(partnersData ?? []);
        if (data.hasSubmitted) {
          savedFormRef.current = toFormState(data);
          applyFormState(savedFormRef.current);
        }
      })
      .catch((err) => {
        if (cancelled) return;
        console.error(
          "[MentorshipFeedbackDialog] failed to fetch feedback status",
          err,
        );
        setHasSubmitted(false);
        setFetchError(true);
      });
    return () => {
      cancelled = true;
    };
  }, [roundId]);

  const validate = () => {
    const newErrors = {};
    if (!programRating) newErrors.programRating = "This field is required.";
    partners.forEach((partner) => {
      if (!partnerFeedback[partner.id]?.rating) {
        newErrors[`partnerRating-${partner.id}`] = "This field is required.";
      }
    });
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSave = async () => {
    if (!validate()) return;
    setIsSaving(true);
    try {
      await postMyMentorshipFeedback(roundId, {
        mostValuableAspects: mostValuableAspects || null,
        challenges: challenges || null,
        programRating: programRating ? parseInt(programRating, 10) : null,
        partnerFeedback: partners.map((partner) => ({
          partnerId: partner.id,
          rating: parseInt(partnerFeedback[partner.id]?.rating, 10),
          feedback: partnerFeedback[partner.id]?.feedback || null,
        })),
      });
      savedFormRef.current = {
        mostValuableAspects,
        challenges,
        programRating,
        partnerFeedback,
      };
      const wasUpdate = hasSubmitted;
      setHasSubmitted(true);
      setIsOpen(false);
      toast.success(wasUpdate ? "Feedback Updated" : "Feedback Submitted", {
        description: `Thank you for sharing feedback on ${roundName || "this round"}.`,
        duration: 4000,
      });
    } catch {
      toast.error("Submission Failed", {
        description:
          "We couldn't submit your feedback. Please try again in a moment.",
        duration: 4000,
      });
    } finally {
      setIsSaving(false);
    }
  };

  if (hasSubmitted === null) return null;
  // Past the deadline there is nothing to show someone who never submitted.
  if (!isEditable && !hasSubmitted) return null;

  const handleOpenChange = (open) => {
    if (!open) {
      applyFormState(savedFormRef.current);
      setErrors({});
    }
    setIsOpen(open);
  };

  const triggerLabel = !isEditable
    ? "View Feedback"
    : hasSubmitted
      ? "Edit Feedback"
      : "Submit Feedback";

  const deadlineNote = isEditable
    ? feedbackDeadlineText
      ? `You can update your responses until ${feedbackDeadlineText}.`
      : "You can update your responses until the feedback deadline."
    : feedbackDeadlineText
      ? `The feedback deadline passed on ${feedbackDeadlineText}. Your responses are read-only.`
      : "The feedback deadline has passed. Your responses are read-only.";

  return (
    <Dialog open={isOpen} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm" disabled={!roundId || fetchError}>
          {triggerLabel}
        </Button>
      </DialogTrigger>

      <DialogContent className="sm:max-w-[500px] top-[64px] translate-y-0">
        <DialogHeader>
          <DialogTitle>
            {roundName ? `${roundName} Feedback` : "Feedback"}
          </DialogTitle>
          <p className="text-[11px] text-muted-foreground italic mt-1">
            {deadlineNote}
          </p>
        </DialogHeader>

        <div className="py-4 space-y-6 max-h-[70vh] overflow-y-auto px-1">
          {/* Most valuable aspects (All) */}
          <div className="space-y-3">
            <Label className="text-sm font-semibold">
              What were the most valuable aspects of the mentorship?
            </Label>
            <TextArea
              value={mostValuableAspects}
              onChange={setMostValuableAspects}
              placeholder="Share what you found most valuable..."
              maxLength={300}
              disabled={!isEditable}
            />
          </div>

          {/* Challenges (All) */}
          <div className="space-y-3">
            <Label className="text-sm font-semibold">
              What challenges did you encounter during the mentorship, if any?
            </Label>
            <TextArea
              value={challenges}
              onChange={setChallenges}
              placeholder="Describe any challenges you faced..."
              maxLength={300}
              disabled={!isEditable}
            />
          </div>

          {/* Overall effectiveness rating (All) */}
          <div className="space-y-3">
            <Label className="text-sm font-semibold">
              How would you rate the overall effectiveness of the mentorship?{" "}
              <span className="text-destructive">*</span>
            </Label>
            <RadioGroup
              value={programRating}
              onValueChange={(val) => {
                setProgramRating(val);
                clearError("programRating");
              }}
              className="flex gap-4"
            >
              {RATING_OPTIONS.map((n) => (
                <div key={n} className="flex items-center space-x-1">
                  <RadioGroupItem
                    value={n.toString()}
                    id={`program-rating-${n}`}
                    disabled={!isEditable}
                  />
                  <Label
                    htmlFor={`program-rating-${n}`}
                    className="font-normal cursor-pointer"
                  >
                    {n}
                  </Label>
                </div>
              ))}
            </RadioGroup>
            <p className="text-[11px] text-muted-foreground italic">
              1 = Not effective, 5 = Very effective
            </p>
            {errors.programRating && (
              <p className="text-xs text-destructive">{errors.programRating}</p>
            )}
          </div>

          {/* Every participant rates and leaves feedback for each of their partners */}
          {partners.flatMap((partner) => {
            const entry = partnerFeedback[partner.id] || {};
            const ratingError = errors[`partnerRating-${partner.id}`];
            return [
              <div key={`${partner.id}-rating`} className="space-y-3">
                <Label className="text-sm font-semibold">
                  How was your overall experience working with your{" "}
                  {partnerRoleLabel} {partner.preferredName}?{" "}
                  <span className="text-destructive">*</span>
                </Label>
                <RadioGroup
                  value={entry.rating || ""}
                  onValueChange={(val) => {
                    updatePartnerField(partner.id, "rating", val);
                    clearError(`partnerRating-${partner.id}`);
                  }}
                  className="flex flex-wrap gap-4"
                >
                  {PARTNER_RATING_OPTIONS.map((option) => (
                    <div
                      key={option.value}
                      className="flex items-center space-x-1"
                    >
                      <RadioGroupItem
                        value={option.value.toString()}
                        id={`partner-rating-${partner.id}-${option.value}`}
                        disabled={!isEditable}
                      />
                      <Label
                        htmlFor={`partner-rating-${partner.id}-${option.value}`}
                        className="font-normal cursor-pointer"
                      >
                        {option.label}
                      </Label>
                    </div>
                  ))}
                </RadioGroup>
                {ratingError && (
                  <p className="text-xs text-destructive">{ratingError}</p>
                )}
              </div>,
              <div key={`${partner.id}-feedback`} className="space-y-3">
                <Label className="text-sm font-semibold">
                  What feedback would you like to share about your{" "}
                  {partnerRoleLabel} {partner.preferredName}?
                </Label>
                <TextArea
                  value={entry.feedback || ""}
                  onChange={(val) =>
                    updatePartnerField(partner.id, "feedback", val)
                  }
                  placeholder={`Share feedback about ${partner.preferredName}...`}
                  maxLength={300}
                  disabled={!isEditable}
                />
              </div>,
            ];
          })}
        </div>

        <DialogFooter>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => handleOpenChange(false)}>
              Close
            </Button>
            {isEditable && (
              <Button onClick={handleSave} disabled={isSaving}>
                {isSaving
                  ? "Saving..."
                  : hasSubmitted
                    ? "Save Changes"
                    : "Submit"}
              </Button>
            )}
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
