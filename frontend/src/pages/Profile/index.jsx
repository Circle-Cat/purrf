import React, { useState } from "react";

import { useProfileData } from "@/pages/Profile/hooks/useProfileData";
import { useProfileCompletenessReminder } from "@/pages/Profile/hooks/useProfileCompletenessReminder";

import ProfileHeader from "@/pages/Profile/components/ProfileHeader";
import LinkedInSection from "@/pages/Profile/components/LinkedInSection";
import EmailSection from "@/pages/Profile/components/EmailSection";
import ExperienceSection from "@/pages/Profile/components/ExperienceSection";
import EducationSection from "@/pages/Profile/components/EducationSection";
import TrainingSection from "@/pages/Profile/components/TrainingSection";

import PersonalEditModal from "@/pages/Profile/modals/PersonalEditModal";
import ExperienceEditModal from "@/pages/Profile/modals/ExperienceEditModal";
import EducationEditModal from "@/pages/Profile/modals/EducationEditModal";
import { Card, CardHeader, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

/**
 * Profile page component.
 *
 * Handles display of profile info, experience, education, training,
 * and modal state management for editing sections.
 */
const Profile = () => {
  /** Fetch profile data and core logic from the hook */
  const {
    isLoading,
    loadError,
    personalInfo,
    experienceList,
    educationList,
    canEditTimezone,
    nextEditableDate,
    handleUpdateProfile,
    refresh,
  } = useProfileData();

  useProfileCompletenessReminder({
    isLoading,
    loadError,
    personalInfo,
    experienceList,
    educationList,
  });

  /**
   * Modal visibility state for personal, experience, and education edit sections.
   */
  const [modalState, setModalState] = useState({
    personal: false,
    experience: false,
    education: false,
  });

  /**
   * Toggle modal visibility for a given section.
   * @param {string} key - The modal key ('personal', 'experience', 'education')
   * @param {boolean} isOpen - True to open, false to close
   */
  const toggleModal = (key, isOpen) => {
    setModalState((prev) => ({ ...prev, [key]: isOpen }));
  };

  /** Display loading state while fetching profile data */
  if (isLoading) {
    return <div className="min-h-screen px-6 py-8">Loading profile...</div>;
  }

  /**
   * Display a retry state on load failure, so a failed fetch is not mistaken
   * for an empty profile.
   */
  if (loadError) {
    return (
      <div className="min-h-screen px-6 py-8">
        <div className="mx-auto flex max-w-[1000px] flex-col items-center gap-4 py-16 text-center">
          <p className="text-muted-foreground">
            We couldn&apos;t load your profile. Please try again.
          </p>
          <Button onClick={refresh}>Retry</Button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen px-6 py-8">
      <div className="mx-auto flex max-w-[1000px] flex-col gap-4">
        {/** Top section with personal info */}
        <Card>
          <CardHeader>
            <ProfileHeader
              info={personalInfo}
              onEditClick={() => toggleModal("personal", true)}
            />
          </CardHeader>
          {/* ContactSection */}
          <CardContent>
            <LinkedInSection info={personalInfo} />
          </CardContent>
        </Card>

        {/* Email Card */}
        <Card>
          <CardContent>
            <EmailSection info={personalInfo} />
          </CardContent>
        </Card>

        {/* Experience Card */}
        <Card>
          <CardContent>
            <ExperienceSection
              list={experienceList}
              onEditClick={() => toggleModal("experience", true)}
            />
          </CardContent>
        </Card>

        {/* Education Card */}
        <Card>
          <CardContent>
            <EducationSection
              list={educationList}
              onEditClick={() => toggleModal("education", true)}
            />
          </CardContent>
        </Card>

        {/* Training Card */}
        <Card>
          <CardContent>
            <TrainingSection
              list={personalInfo.completedTraining}
              timezone={personalInfo.timezone}
            />
          </CardContent>
        </Card>
      </div>

      {/** Modal components */}
      <PersonalEditModal
        isOpen={modalState.personal}
        onClose={() => toggleModal("personal", false)}
        initialData={personalInfo}
        onSave={handleUpdateProfile}
        canEditTimezone={canEditTimezone}
        nextEditableDate={nextEditableDate}
      />

      <ExperienceEditModal
        isOpen={modalState.experience}
        onClose={() => toggleModal("experience", false)}
        initialData={experienceList}
        onSave={handleUpdateProfile}
      />

      <EducationEditModal
        isOpen={modalState.education}
        onClose={() => toggleModal("education", false)}
        initialData={educationList}
        onSave={handleUpdateProfile}
      />
    </div>
  );
};

export default Profile;
