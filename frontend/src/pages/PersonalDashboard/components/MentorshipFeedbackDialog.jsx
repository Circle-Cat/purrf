import React, { useState, useEffect } from "react";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { MentorshipParticipantRoles } from "@/constants/MentorshipParticipantRoles";
import { useFeatureFlags } from "@/hooks/useFeatureFlags";
import { FEATURE_FLAGS } from "@/constants/FeatureFlags";
import {
  getMyMentorshipFeedback,
  postMyMentorshipFeedback,
} from "@/api/mentorshipApi";
import { toast } from "sonner";

const SESSION_COUNT_OPTIONS = Array.from({ length: 10 }, (_, i) => i + 1);

const RATING_OPTIONS = [1, 2, 3, 4, 5];

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
 * Dialog for submitting or viewing mentorship program feedback for a round.
 *
 * Renders a trigger button whose label reflects the user's prior submission
 * status. The button is hidden until the initial status fetch resolves to
 * avoid a "Submit Feedback" → "View Feedback" flash on page load.
 *
 * Required fields vary by participant role:
 * - All roles: `programRating`, `mostValuableAspects` (optional), `challenges` (optional)
 * - Mentee only: `sessionsCompleted`
 *
 * Inline field-level errors are shown on submit; each clears as soon as the
 * user interacts with that field.
 *
 * @param {object}  props
 * @param {string}  props.roundId           - ID of the mentorship round.
 * @param {string}  props.roundName         - Display name of the round (used in the dialog title).
 * @param {boolean} props.isFeedbackEnabled - When false the trigger button is disabled.
 */
export default function MentorshipFeedbackDialog({
  roundId,
  roundName,
  isFeedbackEnabled,
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  const [participantRole, setParticipantRole] = useState(null);
  const [hasSubmitted, setHasSubmitted] = useState(null);
  const [fetchError, setFetchError] = useState(false);
  const [errors, setErrors] = useState({});

  const [sessionsCompleted, setSessionsCompleted] = useState("");
  const [mostValuableAspects, setMostValuableAspects] = useState("");
  const [challenges, setChallenges] = useState("");
  const [programRating, setProgramRating] = useState("");

  const flags = useFeatureFlags();
  // When Google Meetings is enabled, mentee session attendance is captured
  // automatically, so the manual sessions-completed question is hidden.
  const isCreateGoogleMeetingsEnabled =
    flags[FEATURE_FLAGS.CREATE_GOOGLE_MEETING];

  const isMentee = participantRole === MentorshipParticipantRoles.MENTEE;

  const populateForm = (data) => {
    setSessionsCompleted(data.sessionsCompleted?.toString() ?? "");
    setMostValuableAspects(data.mostValuableAspects ?? "");
    setChallenges(data.challenges ?? "");
    setProgramRating(data.programRating?.toString() ?? "");
  };

  const clearError = (field) => {
    setErrors((prev) => {
      if (!prev[field]) return prev;
      const next = { ...prev };
      delete next[field];
      return next;
    });
  };

  useEffect(() => {
    // When feedback isn't available for this round, render a disabled trigger
    // button without hitting the API.
    if (!isFeedbackEnabled || !roundId) {
      setHasSubmitted(false);
      return;
    }
    let cancelled = false;
    getMyMentorshipFeedback(roundId)
      .then(({ data }) => {
        if (cancelled) return;
        setParticipantRole(data.participantRole);
        setHasSubmitted(Boolean(data.hasSubmitted));
        if (data.hasSubmitted) populateForm(data);
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
  }, [roundId, isFeedbackEnabled]);

  const validate = () => {
    const newErrors = {};
    if (isMentee && !isCreateGoogleMeetingsEnabled && !sessionsCompleted)
      newErrors.sessionsCompleted = "This field is required.";
    if (!programRating) newErrors.programRating = "This field is required.";
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSave = async () => {
    if (!validate()) return;
    setIsSaving(true);
    try {
      await postMyMentorshipFeedback(roundId, {
        sessionsCompleted: sessionsCompleted
          ? parseInt(sessionsCompleted, 10)
          : null,
        mostValuableAspects: mostValuableAspects || null,
        challenges: challenges || null,
        programRating: programRating ? parseInt(programRating, 10) : null,
      });
      setHasSubmitted(true);
      setIsOpen(false);
      toast.success("Feedback Submitted", {
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

  const handleOpenChange = (open) => {
    if (!open && !hasSubmitted) {
      setSessionsCompleted("");
      setMostValuableAspects("");
      setChallenges("");
      setProgramRating("");
      setErrors({});
    }
    setIsOpen(open);
  };

  return (
    <Dialog open={isOpen} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button
          variant="outline"
          className="border-[#6035F3] text-[#6035F3] hover:bg-purple-50 disabled:opacity-50"
          disabled={!isFeedbackEnabled || fetchError}
        >
          {hasSubmitted ? "View Feedback" : "Submit Feedback"}
        </Button>
      </DialogTrigger>

      <DialogContent className="sm:max-w-[500px] top-[64px] translate-y-0">
        <DialogHeader>
          <DialogTitle>
            {roundName ? `${roundName} Feedback` : "Feedback"}
          </DialogTitle>
          {hasSubmitted ? (
            <p className="text-[11px] text-muted-foreground italic mt-1">
              Thank you for sharing feedback with us!
            </p>
          ) : (
            <p className="text-[11px] text-destructive mt-1">
              Please review your responses carefully. Feedback cannot be edited
              after submission.
            </p>
          )}
        </DialogHeader>

        <div className="py-4 space-y-6 max-h-[70vh] overflow-y-auto px-1">
          {/* Sessions completed (Mentee only, hidden when Google Meetings is enabled) */}
          {isMentee && !isCreateGoogleMeetingsEnabled && (
            <div className="space-y-3">
              <Label className="text-sm font-semibold">
                How many sessions have you completed during this past round and
                logged in Moodle? <span className="text-destructive">*</span>
              </Label>
              <Select
                value={sessionsCompleted}
                onValueChange={(val) => {
                  setSessionsCompleted(val);
                  clearError("sessionsCompleted");
                }}
                disabled={hasSubmitted}
              >
                <SelectTrigger
                  className={`w-full${errors.sessionsCompleted ? " border-destructive" : ""}`}
                >
                  <SelectValue placeholder="Select number of sessions" />
                </SelectTrigger>
                <SelectContent>
                  {SESSION_COUNT_OPTIONS.map((n) => (
                    <SelectItem key={n} value={n.toString()}>
                      {n}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {errors.sessionsCompleted && (
                <p className="text-xs text-destructive">
                  {errors.sessionsCompleted}
                </p>
              )}
            </div>
          )}

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
              disabled={hasSubmitted}
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
              disabled={hasSubmitted}
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
                    disabled={hasSubmitted}
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
        </div>

        <DialogFooter>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => handleOpenChange(false)}>
              Close
            </Button>
            {!hasSubmitted && (
              <Button onClick={handleSave} disabled={isSaving}>
                {isSaving ? "Saving..." : "Submit"}
              </Button>
            )}
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
