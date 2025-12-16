import { useState, useEffect, useCallback, useMemo } from "react";

import { getMyProfile, updateMyProfile } from "@/api/profileApi";
import {
  parseDateParts,
  getDaysSince,
  sortExperienceOrEducationList,
} from "@/pages/Profile/utils";
import { ProfileFields } from "@/constants/ApiEndpoints";

export const useProfileData = () => {
  const [isLoading, setIsLoading] = useState(true);

  /**
   * Personal information state.
   * Initialized with safe defaults to avoid undefined access in UI.
   */
  const [personalInfo, setPersonalInfo] = useState({
    emails: [],
    completedTraining: [],
    updatedTimestamp: null,
  });

  /**
   * Work experience list state.
   */
  const [experienceList, setExperienceList] = useState([]);

  /**
   * Education list state.
   */
  const [educationList, setEducationList] = useState([]);

  /**
   * Core mapping logic that transforms the backend Profile response
   * into frontend-friendly state structures.
   *
   * Wrapped with useCallback to avoid unnecessary re-renders.
   */
  const mapDataToState = useCallback((profile) => {
    if (!profile?.user) return;

    const { user, experience = [], education = [], training = [] } = profile;
    const currentJob = experience.find((exp) => exp.isCurrentJob) || {};

    /**
     * Map user data to personalInfo state.
     */
    const emailList = [];

    if (user.primaryEmail) {
      emailList.push({
        id: "primary",
        email: user.primaryEmail,
        isPrimary: true,
      });
    }

    if (Array.isArray(user.alternativeEmails)) {
      user.alternativeEmails.forEach((email, idx) => {
        emailList.push({
          id: `alt-${idx}`,
          email,
          isPrimary: false,
        });
      });
    }

    setPersonalInfo((prev) => ({
      ...prev,
      id: user.id,
      firstName: user.firstName || "",
      lastName: user.lastName || "",
      preferredName: user.preferredName || "",
      timezone: user.timezone || "",
      linkedin: user.linkedinLink || "",
      preferredCommunication: user.communicationMethod,
      updatedTimestamp: user.updatedTimestamp,
      emails: emailList,
      title: currentJob.title || "",
      company: currentJob.companyOrOrganization || "",
      completedTraining: training.map((t) => {
        const compParts = parseDateParts(t.completedTimestamp);
        const dueParts = parseDateParts(t.deadline);

        return {
          id: t.id,
          name: t.name,
          status: t.status,
          completionMonth: compParts.month,
          completionYear: compParts.year,
          dueMonth: dueParts.month,
          dueYear: dueParts.year,
          link: t.link,
        };
      }),
    }));

    /**
     * Map experience list.
     */
    const mappedExperience = experience
      .map((exp) => {
        const startParts = parseDateParts(exp.startDate);
        const endParts = parseDateParts(exp.endDate);

        return {
          id: exp.id,
          title: exp.title,
          company: exp.companyOrOrganization,
          startMonth: startParts.month,
          startYear: startParts.year,
          endMonth: endParts.month,
          endYear: endParts.year,
          isCurrentlyWorking: exp.isCurrentJob,
        };
      })
      .sort(sortExperienceOrEducationList);

    setExperienceList(mappedExperience);

    /**
     * Map education list.
     */
    const mappedEducation = education
      .map((edu) => {
        const startParts = parseDateParts(edu.startDate);
        const endParts = parseDateParts(edu.endDate);

        return {
          id: edu.id,
          institution: edu.school,
          degree: edu.degree,
          field: edu.fieldOfStudy,
          startMonth: startParts.month,
          startYear: startParts.year,
          endMonth: endParts.month,
          endYear: endParts.year,
        };
      })
      .sort(sortExperienceOrEducationList);

    setEducationList(mappedEducation);
  }, []);

  /**
   * Fetch profile data from backend.
   */
  const fetchProfileData = useCallback(async () => {
    setIsLoading(true);
    try {
      const {
        data: { profile },
      } = await getMyProfile({
        fields: [
          ProfileFields.USER,
          ProfileFields.EXPERIENCE,
          ProfileFields.EDUCATION,
          ProfileFields.TRAINING,
        ],
      });

      if (profile) {
        mapDataToState(profile);
      } else {
        console.warn("Profile data structure is unexpected:", profile);
      }
    } catch (error) {
      console.error("Failed to fetch profile:", error);
    } finally {
      setIsLoading(false);
    }
  }, [mapDataToState]);

  /**
   * Generic update handler for profile-related updates.
   * Used by edit modals. Updates local state on success
   * without requiring a full refresh.
   */
  const handleUpdateProfile = async (payload) => {
    const {
      data: { profile },
    } = await updateMyProfile(payload);

    if (profile) {
      mapDataToState(profile);
    }

    return profile;
  };

  /**
   * Computed flag indicating whether personal info can be edited.
   * Editing is restricted to once every 30 days.
   */
  const canEditPersonalInfo = useMemo(() => {
    if (!personalInfo.updatedTimestamp) return true;

    const days = getDaysSince(personalInfo.updatedTimestamp);
    return days >= 30;
  }, [personalInfo.updatedTimestamp]);

  /**
   * Computed string representing the next available edit date.
   */
  const nextEditableDate = useMemo(() => {
    if (!personalInfo.updatedTimestamp) return "";

    const date = new Date(personalInfo.updatedTimestamp);
    date.setDate(date.getDate() + 30);

    return date.toLocaleDateString();
  }, [personalInfo.updatedTimestamp]);

  /**
   * Initial data load.
   */
  useEffect(() => {
    fetchProfileData();
  }, [fetchProfileData]);

  /**
   * Public hook API.
   */
  return {
    isLoading,
    personalInfo,
    experienceList,
    educationList,
    canEditPersonalInfo,
    nextEditableDate,
    handleUpdateProfile,
    refresh: fetchProfileData,
  };
};
