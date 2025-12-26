import React, { useState, useEffect } from "react";
import "@/pages/Profile/modals/Modal.css";
import {
  TimezoneEnum,
  formatTimezoneLabel,
  CommunicationMethodEnum,
  isValidEmail,
} from "@/pages/Profile/utils";
import { useAuth } from "@/context/auth/AuthContext";
import { USER_ROLES } from "@/constants/UserRoles";
import { Button } from "@/components/ui/button";

/**
 * EmailFormItem renders a single email input with label, error handling, and delete option.
 *
 * @param {object} item - Email data { id, email, isPrimary }
 * @param {object} errors - Object mapping field keys to error messages
 * @param {function} onChange - Callback for input change
 * @param {function} onDelete - Callback for deleting this email
 */
const EmailFormItem = ({ item, errors, onChange, onDelete }) => {
  const errorKey = `${item.id}-email`;
  const hasError = errors[errorKey];

  return (
    <div className="email-edit-item-container">
      <div className="email-edit-item">
        <input
          type="text"
          value={item.email || ""}
          onChange={(e) => onChange(item.id, "email", e.target.value)}
          readOnly={item.isPrimary}
          disabled={item.isPrimary}
          style={item.isPrimary ? { backgroundColor: "#f0f0f0" } : {}}
          title={item.isPrimary ? "Primary email, cannot be modified" : ""}
          className={`${item.isPrimary ? "primary-input" : ""} ${hasError ? "input-error" : ""}`}
          placeholder={item.isPrimary ? "Primary email" : "Alternative email"}
        />

        <div className="email-type-label">
          {item.isPrimary ? (
            <span className="email-tag primary">Primary</span>
          ) : (
            <span className="email-tag alternative">Alternative</span>
          )}
        </div>

        {!item.isPrimary && (
          <Button
            variant="destructive"
            size="sm"
            onClick={() => onDelete(item.id)}
          >
            -
          </Button>
        )}
      </div>

      {/* Display validation error for this email if exists */}
      {hasError && <span className="error-text">{hasError}</span>}
    </div>
  );
};

/**
 * PersonalEditModal allows editing personal profile information including
 * name, timezone, LinkedIn, emails, and communication method.
 *
 * @param {boolean} isOpen - Controls modal visibility
 * @param {function} onClose - Callback to close the modal
 * @param {object} initialData - Initial form data
 * @param {function} onSave - Callback for saving data
 * @param {boolean} canEditTimezone - Whether the user can edit timezone
 * @param {string} nextEditableDate - Next allowed timezone update date
 */
const PersonalEditModal = ({
  isOpen,
  onClose,
  initialData,
  onSave,
  canEditTimezone,
  nextEditableDate,
}) => {
  const { roles, loading } = useAuth();
  const [formData, setFormData] = useState({});
  const [errors, setErrors] = useState({});
  const [isSaving, setIsSaving] = useState(false);

  // Initialize form state when modal opens
  useEffect(() => {
    if (isOpen && initialData) {
      setFormData(structuredClone(initialData));
      setErrors({});
      setIsSaving(false);
    }
  }, [isOpen, initialData]);

  if (!isOpen) return null;

  /** Handle changes for regular input fields */
  const handleChange = (name, value) => {
    setFormData((prev) => ({ ...prev, [name]: value }));
    setErrors((prev) => {
      const next = { ...prev };
      delete next[name];
      return next;
    });
  };

  /** Handle changes for email inputs */
  const handleEmailChange = (id, field, value) => {
    setFormData((prev) => ({
      ...prev,
      emails: prev.emails.map((item) =>
        item.id === id ? { ...item, [field]: value } : item,
      ),
    }));

    // Remove email validation error for this field
    setErrors((prev) => {
      const next = { ...prev };
      delete next[`${id}-${field}`];
      return next;
    });
  };

  /** Add a new alternative email row */
  const handleAddEmail = () => {
    const newEmail = {
      id: `new-${Date.now()}`,
      email: "",
      isPrimary: false,
    };
    setFormData((prev) => ({
      ...prev,
      emails: [...(prev.emails || []), newEmail],
    }));
  };

  /** Delete an alternative email */
  const handleDeleteEmail = (id) => {
    setFormData((prev) => ({
      ...prev,
      emails: prev.emails.filter((item) => item.id !== id),
    }));
  };

  /** Validate the entire form */
  const validate = () => {
    const newErrors = {};

    // Required field validation
    if (!formData.firstName?.trim())
      newErrors.firstName = "First name is required";
    if (!formData.lastName?.trim())
      newErrors.lastName = "Last name is required";
    if (!formData.timezone) newErrors.timezone = "Timezone is required";

    // Validate all alternative emails
    formData.emails?.forEach((item) => {
      if (!item.isPrimary) {
        const emailValue = item.email?.trim();
        if (emailValue && !isValidEmail(emailValue)) {
          newErrors[`${item.id}-email`] = "Invalid email format";
        }
      }
    });

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  /** Submit form data */
  const handleSubmit = async () => {
    if (!validate()) return;

    setIsSaving(true);
    try {
      const validAltEmails = (formData.emails || [])
        .filter((e) => !e.isPrimary && e.email?.trim())
        .map((e) => e.email.trim());

      const payload = {
        user: {
          firstName: formData.firstName,
          lastName: formData.lastName,
          preferredName: formData.preferredName,
          timezone: formData.timezone,
          linkedinLink: formData.linkedin,
          alternativeEmails: validAltEmails,
          communicationMethod: formData.communicationMethod,
        },
      };

      await onSave(payload);
      onClose();
    } catch (e) {
      console.error("Save failed", e);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="modal-overlay">
      <div className="modal-content">
        <div className="section-header">
          <h3>Edit Personal Information</h3>
        </div>

        <div className="scrollable-form-area">
          {/* First Name */}
          <div className="form-group">
            <label>
              First Name <span className="required">*</span>
            </label>
            <input
              type="text"
              className={errors.firstName ? "input-error" : ""}
              value={formData.firstName || ""}
              onChange={(e) => handleChange("firstName", e.target.value)}
            />
            {errors.firstName && (
              <span className="error-text">{errors.firstName}</span>
            )}
          </div>

          {/* Last Name */}
          <div className="form-group">
            <label>
              Last Name <span className="required">*</span>
            </label>
            <input
              type="text"
              className={errors.lastName ? "input-error" : ""}
              value={formData.lastName || ""}
              onChange={(e) => handleChange("lastName", e.target.value)}
            />
            {errors.lastName && (
              <span className="error-text">{errors.lastName}</span>
            )}
          </div>

          {/* Preferred Name */}
          <div className="form-group">
            <label>Preferred Name</label>
            <input
              type="text"
              value={formData.preferredName || ""}
              onChange={(e) => handleChange("preferredName", e.target.value)}
            />
          </div>

          {/* Timezone */}
          <div className="form-group">
            <label>
              Current Timezone <span className="required">*</span>
            </label>
            <select
              className={errors.timezone ? "input-error" : ""}
              value={formData.timezone || ""}
              onChange={(e) => handleChange("timezone", e.target.value)}
              disabled={!canEditTimezone}
            >
              <option value="">Select a timezone</option>
              {Object.values(TimezoneEnum).map((tz) => (
                <option key={tz} value={tz}>
                  {formatTimezoneLabel(tz)}
                </option>
              ))}
            </select>
            {errors.timezone && (
              <span className="error-text">{errors.timezone}</span>
            )}
            <span className="timezone-info-text">
              Timezone can only be updated once every 30 days.
              <br />
              {!canEditTimezone && `Next editable date: ${nextEditableDate}.`}
            </span>
          </div>

          {/* LinkedIn */}
          <div className="form-group">
            <label>LinkedIn</label>
            <input
              type="text"
              value={formData.linkedin || ""}
              onChange={(e) => handleChange("linkedin", e.target.value)}
            />
          </div>

          {/* Email Section */}
          <div className="email-edit-section border-t border-gray-200 mt-4 pt-4">
            <div className="section-header">
              <h3>Emails</h3>
              <Button size="sm" onClick={handleAddEmail}>
                +
              </Button>
            </div>
            <p className="modal-info-text">
              <strong>Primary Email:</strong> This is the email administrators
              will use to contact you.
              <br />
              <strong>Alternative Email:</strong> Additional contacts.
            </p>

            <div className="email-list">
              {formData.emails?.map((item) => (
                <EmailFormItem
                  key={item.id}
                  item={item}
                  errors={errors}
                  onChange={handleEmailChange}
                  onDelete={handleDeleteEmail}
                />
              ))}
            </div>
          </div>

          {/* Communication Method */}
          {!loading && roles.includes(USER_ROLES.CONTACT_GOOGLE_CHAT) && (
            <div className="form-group">
              <label>Preferred Communication Method</label>
              <div className="radio-group">
                <input
                  type="radio"
                  name="communicationMethod"
                  value={CommunicationMethodEnum.Email}
                  checked={
                    formData.communicationMethod ===
                    CommunicationMethodEnum.Email
                  }
                  onChange={(e) =>
                    handleChange("communicationMethod", e.target.value)
                  }
                />
                Email
                <input
                  type="radio"
                  name="communicationMethod"
                  value={CommunicationMethodEnum.GoogleChat}
                  checked={
                    formData.communicationMethod ===
                    CommunicationMethodEnum.GoogleChat
                  }
                  onChange={(e) =>
                    handleChange("communicationMethod", e.target.value)
                  }
                />
                Google Chat
              </div>
            </div>
          )}
        </div>

        {/* Modal Actions */}
        <div className="modal-actions">
          <Button variant="outline" onClick={onClose} disabled={isSaving}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={isSaving}>
            {isSaving ? "Saving..." : "Save"}
          </Button>
        </div>
      </div>
    </div>
  );
};

export default PersonalEditModal;
