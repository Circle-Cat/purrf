import React, { useState } from "react";
import "@/pages/Profile/Profile.css";

import { useProfileData } from "@/pages/Profile/hooks/useProfileData";

import ProfileHeader from "@/pages/Profile/components/ProfileHeader";
import ContactSection from "@/pages/Profile/components/ContactSection";
import ExperienceSection from "@/pages/Profile/components/ExperienceSection";
import EducationSection from "@/pages/Profile/components/EducationSection";
import TrainingSection from "@/pages/Profile/components/TrainingSection";

import PersonalEditModal from "@/pages/Profile/modals/PersonalEditModal";
import ExperienceEditModal from "@/pages/Profile/modals/ExperienceEditModal";
import EducationEditModal from "@/pages/Profile/modals/EducationEditModal";
import { Card, CardHeader, CardContent } from "@/components/ui/card";

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
    personalInfo,
    experienceList,
    educationList,
    canEditTimezone,
    nextEditableDate,
    handleUpdateProfile,
  } = useProfileData();

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
    return <div className="profile-page-container">Loading profile...</div>;
  }

  return (
    <div className="profile-page-container">
      <div className="profile-content-area">
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
            <ContactSection info={personalInfo} />
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
            <TrainingSection list={personalInfo.completedTraining} />
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
