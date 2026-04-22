import React, { useState, useEffect, useMemo } from "react";
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
import { toast } from "sonner";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import MultipleSelector from "@/components/common/MultipleSelector";
import { Info } from "lucide-react";
import { MentorshipParticipantRoles } from "@/constants/MentorshipParticipantRoles";
import SurveyRadioQuestion from "@/pages/PersonalDashboard/components/SurveyRadioQuestion";
import {
  INDUSTRY_CONFIG,
  SKILLSET_CONFIG,
  CAREER_TRANSITION_OPTIONS,
  REGION_OPTIONS,
  EXTERNAL_MENTORING_OPTIONS,
  CURRENT_BACKGROUND_OPTIONS,
  CURRENT_STAGE_OPTIONS,
  TIME_URGENCY_OPTIONS,
  TARGET_REGION_OPTIONS,
  mapRegistrationToForm,
  mapFormToApi,
} from "@/pages/PersonalDashboard/utils/mentorshipRegistration";

/**
 * MentorshipRegistrationDialog
 *
 * Dialog component for creating or viewing mentorship registration preferences.
 * It supports both mentor and mentee flows and handles preference initialization,
 * form state management, and submission.
 */
export default function MentorshipRegistrationDialog({
  currentRegistration,
  allPastPartners = [],
  isPartnersLoading,
  loadPastPartners,
  refreshRegistration,
  isLocked,
  onSave,
}) {
  const [isOpen, setIsOpen] = useState(false);

  // Determine participant role from current registration
  const participantRole =
    currentRegistration?.roundPreferences?.participantRole;
  const isMentor = participantRole === MentorshipParticipantRoles.MENTOR;
  const isUpdating = currentRegistration?.isRegistered;

  // Form state
  const [selectedIndustries, setSelectedIndustries] = useState([]);
  const [selectedSkillsets, setSelectedSkillsets] = useState([]);
  const [partnerCapacity, setPartnerCapacity] = useState(1);
  const [goal, setGoal] = useState("");
  const [selectedPartners, setSelectedPartners] = useState([]);
  const [excludedPartners, setExcludedPartners] = useState([]);
  // Mentor survey
  const [careerTransition, setCareerTransition] = useState("");
  const [careerTransitionOther, setCareerTransitionOther] = useState("");
  const [region, setRegion] = useState("");
  const [regionOther, setRegionOther] = useState("");
  const [externalMentoringExp, setExternalMentoringExp] = useState("");
  // Mentee survey
  const [currentBackground, setCurrentBackground] = useState("");
  const [currentBackgroundOther, setCurrentBackgroundOther] = useState("");
  const [targetRegion, setTargetRegion] = useState("");
  const [targetRegionOther, setTargetRegionOther] = useState("");
  const [currentStage, setCurrentStage] = useState("");
  const [timeUrgency, setTimeUrgency] = useState("");
  const [errors, setErrors] = useState({});

  const clearError = (field) =>
    setErrors((prev) => {
      if (!prev[field]) return prev;
      const rest = { ...prev };
      delete rest[field];
      return rest;
    });

  // Initialize form state when dialog opens
  useEffect(() => {
    if (!isOpen || !currentRegistration) return;
    setErrors({});

    const formData = mapRegistrationToForm(
      currentRegistration,
      allPastPartners,
    );

    setSelectedIndustries(formData.industries);
    setSelectedSkillsets(formData.skillsets);
    setPartnerCapacity(formData.partnerCapacity);
    setGoal(formData.goal);
    setSelectedPartners(formData.selectedPartners);
    setExcludedPartners(formData.excludedPartners);
    // Mentor survey
    setCareerTransition(formData.careerTransition);
    setCareerTransitionOther(formData.careerTransitionOther);
    setRegion(formData.region);
    setRegionOther(formData.regionOther);
    setExternalMentoringExp(formData.externalMentoringExp);
    // Mentee survey
    setCurrentBackground(formData.currentBackground);
    setCurrentBackgroundOther(formData.currentBackgroundOther);
    setTargetRegion(formData.targetRegion);
    setTargetRegionOther(formData.targetRegionOther);
    setCurrentStage(formData.currentStage);
    setTimeUrgency(formData.timeUrgency);
  }, [currentRegistration, allPastPartners, isOpen]);

  /**
   * Handle dialog open/close changes.
   * When opening, refresh registration data and load past partners.
   */
  const handleOpenChange = (open) => {
    setIsOpen(open);
    if (open) {
      refreshRegistration();
      loadPastPartners();
    }
  };

  const validate = () => {
    const newErrors = {};
    if (!isMentor && selectedIndustries.length === 0)
      newErrors.selectedIndustries = "Please select an industry.";
    if (selectedSkillsets.length === 0)
      newErrors.selectedSkillsets = "Please select at least one skillset.";
    if (isMentor) {
      if (!careerTransition)
        newErrors.careerTransition = "This field is required.";
      if (careerTransition === "other" && !careerTransitionOther.trim())
        newErrors.careerTransitionOther =
          "Please describe your career transition background.";
      if (!region) newErrors.region = "This field is required.";
      if (region === "other" && !regionOther.trim())
        newErrors.regionOther = "Please specify your region.";
      if (!externalMentoringExp)
        newErrors.externalMentoringExp = "This field is required.";
    } else {
      if (!currentBackground)
        newErrors.currentBackground = "This field is required.";
      if (currentBackground === "other" && !currentBackgroundOther.trim())
        newErrors.currentBackgroundOther =
          "Please describe your current background.";
      if (!currentStage) newErrors.currentStage = "This field is required.";
      if (!timeUrgency) newErrors.timeUrgency = "This field is required.";
      if (!targetRegion) newErrors.targetRegion = "This field is required.";
      if (targetRegion === "other" && !targetRegionOther.trim())
        newErrors.targetRegionOther = "Please specify your target job market.";
    }
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  /**
   * Build API payload from form state and submit it.
   */
  const handleSave = async () => {
    if (!validate()) return;
    const payload = mapFormToApi(
      {
        industries: selectedIndustries,
        skillsets: selectedSkillsets,
        partnerCapacity,
        goal,
        selectedPartners,
        excludedPartners,
        careerTransition,
        careerTransitionOther,
        region,
        regionOther,
        externalMentoringExp,
        currentBackground,
        currentBackgroundOther,
        targetRegion,
        targetRegionOther,
        currentStage,
        timeUrgency,
      },
      currentRegistration,
    );

    await onSave(payload);
    setIsOpen(false);

    toast.success(
      isUpdating ? "Registration Updated" : "Registration Completed",
      {
        description: `Your preferences for ${currentRegistration?.roundName || "this round"} have been ${isUpdating ? "updated" : "submitted"} successfully.`,
        duration: 4000,
      },
    );
  };

  // Cross-filtered partner options
  /**
   * Options for preferred partners ("want to continue with").
   * Excludes partners already selected in the exclusion list.
   */
  const wantOptions = useMemo(() => {
    const excludedIds = excludedPartners.map((p) => p.id);
    return allPastPartners
      .map((p) => ({
        id: p.id,
        name: p.preferredName || `${p.firstName} ${p.lastName}`,
      }))
      .filter((opt) => !excludedIds.includes(opt.id));
  }, [allPastPartners, excludedPartners]);

  /**
   * Options for excluded partners ("do not want to continue with").
   * Excludes partners already selected in the preferred list.
   */
  const notWantOptions = useMemo(() => {
    const selectedIds = selectedPartners.map((p) => p.id);
    return allPastPartners
      .map((p) => ({
        id: p.id,
        name: p.preferredName || `${p.firstName} ${p.lastName}`,
      }))
      .filter((opt) => !selectedIds.includes(opt.id));
  }, [allPastPartners, selectedPartners]);

  return (
    <Dialog open={isOpen} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button variant="default" disabled={isPartnersLoading}>
          {isLocked ? "View Registration" : "Register for Next Round"}
        </Button>
      </DialogTrigger>

      <DialogContent className="sm:max-w-[450px] top-[64px] translate-y-0">
        <DialogHeader>
          <DialogTitle>
            {" "}
            {currentRegistration?.roundName} Registration
          </DialogTitle>
          {isUpdating && (
            <p className="text-[11px] text-destructive italic mt-1">
              You are already registered for this round.
            </p>
          )}
        </DialogHeader>

        <div className="py-4 space-y-6 max-h-[70vh] overflow-y-auto px-1">
          {/* Industry selection (visible to mentees only) */}
          {!isMentor && (
            <div className="space-y-3">
              <Label className="text-sm font-semibold">
                Which industry are you interested in?{" "}
                <span className="text-destructive">*</span>
              </Label>
              <MultipleSelector
                className="w-full"
                options={INDUSTRY_CONFIG}
                value={selectedIndustries}
                onChange={(val) => {
                  setSelectedIndustries(val);
                  clearError("selectedIndustries");
                }}
                maxSelected={1}
                placeholder="Select industries..."
                disabled={isLocked}
              />
              {errors.selectedIndustries && (
                <span className="text-destructive text-xs">
                  {errors.selectedIndustries}
                </span>
              )}
            </div>
          )}

          {/* Skillset selection */}
          <div className="space-y-3">
            <Label className="text-sm font-semibold">
              {isMentor
                ? "Which skills can you provide guidance on?"
                : "Which skills do you hope to gain guidance on?"}{" "}
              <span className="text-destructive">*</span>
            </Label>
            <MultipleSelector
              className="w-full"
              options={SKILLSET_CONFIG}
              value={selectedSkillsets}
              onChange={(val) => {
                setSelectedSkillsets(val);
                clearError("selectedSkillsets");
              }}
              maxSelected={3}
              placeholder="Search and select up to 3 skills..."
              disabled={isLocked}
            />
            {errors.selectedSkillsets && (
              <span className="text-destructive text-xs">
                {errors.selectedSkillsets}
              </span>
            )}
            <p className="text-[11px] text-muted-foreground italic">
              * Select up to 3 key skillsets.
            </p>
          </div>

          {/* Time commitment (mentor only) */}
          {isMentor && (
            <div className="space-y-3">
              <Label className="text-sm font-semibold">
                How much time do you want to invest in this round?{" "}
                <span className="text-destructive">*</span>
              </Label>
              <RadioGroup
                disabled={isLocked}
                value={partnerCapacity.toString()}
                onValueChange={(val) => setPartnerCapacity(parseInt(val))}
                className="flex flex-col gap-2"
              >
                {[1, 2, 3].map((num) => (
                  <div key={num} className="flex items-center space-x-2">
                    <RadioGroupItem value={num.toString()} id={`c${num}`} />
                    <Label
                      htmlFor={`c${num}`}
                      className="font-normal cursor-pointer text-sm"
                    >
                      {num} {num === 1 ? "mentee" : "mentees"} – around{" "}
                      {num * 3} hours
                    </Label>
                  </div>
                ))}
              </RadioGroup>
            </div>
          )}

          {/* Mentor survey questions */}
          {isMentor && (
            <>
              <SurveyRadioQuestion
                label="Do you have experience transitioning into CS / tech from another field?"
                required
                options={CAREER_TRANSITION_OPTIONS}
                value={careerTransition}
                onValueChange={(val) => {
                  setCareerTransition(val);
                  if (val !== "other") setCareerTransitionOther("");
                  clearError("careerTransition");
                }}
                idPrefix="ct"
                disabled={isLocked}
                error={errors.careerTransition}
                otherValue={careerTransitionOther}
                onOtherChange={(val) => {
                  setCareerTransitionOther(val);
                  clearError("careerTransitionOther");
                }}
                otherError={errors.careerTransitionOther}
                otherMaxLength={200}
                otherPlaceholder="Please briefly describe..."
              />

              <SurveyRadioQuestion
                label="Which region are you currently primarily based in for career development?"
                required
                options={REGION_OPTIONS}
                value={region}
                onValueChange={(val) => {
                  setRegion(val);
                  if (val !== "other") setRegionOther("");
                  clearError("region");
                }}
                idPrefix="r"
                disabled={isLocked}
                error={errors.region}
                otherValue={regionOther}
                onOtherChange={(val) => {
                  setRegionOther(val);
                  clearError("regionOther");
                }}
                otherError={errors.regionOther}
              />

              <SurveyRadioQuestion
                label="Do you have experience mentoring others outside of the CircleCat Mentorship Program?"
                required
                options={EXTERNAL_MENTORING_OPTIONS}
                value={externalMentoringExp}
                onValueChange={(val) => {
                  setExternalMentoringExp(val);
                  clearError("externalMentoringExp");
                }}
                idPrefix="em"
                disabled={isLocked}
                error={errors.externalMentoringExp}
              />
            </>
          )}

          {/* Mentee survey questions */}
          {!isMentor && (
            <>
              <SurveyRadioQuestion
                label="Which of the following best describes your current situation?"
                required
                options={CURRENT_BACKGROUND_OPTIONS}
                value={currentBackground}
                onValueChange={(val) => {
                  setCurrentBackground(val);
                  if (val !== "other") setCurrentBackgroundOther("");
                  clearError("currentBackground");
                }}
                idPrefix="cb"
                disabled={isLocked}
                error={errors.currentBackground}
                otherValue={currentBackgroundOther}
                onOtherChange={(val) => {
                  setCurrentBackgroundOther(val);
                  clearError("currentBackgroundOther");
                }}
                otherError={errors.currentBackgroundOther}
                otherPlaceholder="Please briefly describe..."
              />

              <SurveyRadioQuestion
                label="Which stage are you currently in?"
                required
                options={CURRENT_STAGE_OPTIONS}
                value={currentStage}
                onValueChange={(val) => {
                  setCurrentStage(val);
                  clearError("currentStage");
                }}
                idPrefix="cs"
                disabled={isLocked}
                error={errors.currentStage}
              />

              <SurveyRadioQuestion
                label="How urgent is your timeline?"
                required
                options={TIME_URGENCY_OPTIONS}
                value={timeUrgency}
                onValueChange={(val) => {
                  setTimeUrgency(val);
                  clearError("timeUrgency");
                }}
                idPrefix="tu"
                disabled={isLocked}
                error={errors.timeUrgency}
              />

              <SurveyRadioQuestion
                label="Which job market region are you targeting?"
                required
                options={TARGET_REGION_OPTIONS}
                value={targetRegion}
                onValueChange={(val) => {
                  setTargetRegion(val);
                  if (val !== "other") setTargetRegionOther("");
                  clearError("targetRegion");
                }}
                idPrefix="tr"
                disabled={isLocked}
                error={errors.targetRegion}
                otherValue={targetRegionOther}
                onOtherChange={(val) => {
                  setTargetRegionOther(val);
                  clearError("targetRegionOther");
                }}
                otherError={errors.targetRegionOther}
              />
            </>
          )}

          {/* Goal input */}
          <div className="space-y-3">
            <Label className="text-sm font-semibold">
              Goal for Current Round
            </Label>
            <div className="relative">
              <textarea
                disabled={isLocked}
                placeholder="What do you hope to achieve?"
                value={goal}
                onChange={(e) => setGoal(e.target.value)}
                maxLength={300}
                className="w-full p-2 border rounded-md text-sm min-h-[80px] focus:outline-none focus:ring-2 focus:ring-ring"
              />
              <div className="absolute bottom-2 right-2 text-xs text-muted-foreground pointer-events-none">
                {(goal || "").length} / 300
              </div>
            </div>
          </div>

          {/* Preference section hint */}
          <div className="pt-2 space-y-1">
            <h2 className="font-bold">
              {isMentor ? "Mentee Preferences" : "Mentor Preferences"}
            </h2>
            <div className="flex gap-3 p-3 rounded-lg border bg-muted/40 text-muted-foreground">
              <Info className="h-4 w-4 mt-0.5 shrink-0 text-primary/80" />
              <p className="text-[13px] leading-relaxed">
                Leaving these fields empty indicates you have no preference and
                are open to matching with any suitable{" "}
                {isMentor ? "mentee" : "mentor"}.
              </p>
            </div>
          </div>

          {/* Preferred partners (limited by partner capacity) */}
          <div className="space-y-3">
            <Label className="text-sm font-semibold">
              Who would you like to continue with?
            </Label>
            <MultipleSelector
              className="w-full"
              options={wantOptions}
              value={selectedPartners}
              onChange={setSelectedPartners}
              disabled={isLocked || isPartnersLoading}
              maxSelected={partnerCapacity}
              placeholder="Select ..."
            />
            <p className="text-[11px] text-muted-foreground italic">
              * Select up to {partnerCapacity}{" "}
              {partnerCapacity > 1
                ? "partners. These individuals"
                : "partner. This individual"}{" "}
              will be prioritized in matching.
            </p>
          </div>

          {/* Excluded partners (no hard limit) */}
          <div className="space-y-3">
            <Label className="text-sm font-semibold text-destructive">
              Who would you prefer not to continue with?
            </Label>
            <MultipleSelector
              className="w-full"
              options={notWantOptions}
              value={excludedPartners}
              onChange={setExcludedPartners}
              disabled={isLocked || isPartnersLoading}
              showSelectAll
              placeholder="Select ..."
            />
            <p className="text-[11px] text-muted-foreground italic">
              * These individuals will be excluded from matching.
            </p>
          </div>
        </div>

        <DialogFooter>
          <DialogTrigger asChild>
            <Button variant="outline" onClick={() => setIsOpen(false)}>
              Close
            </Button>
          </DialogTrigger>
          {!isLocked && (
            <Button onClick={handleSave}>
              {isUpdating ? "Update Registration" : "Register"}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
