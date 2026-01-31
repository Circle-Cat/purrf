# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- New features added since the last release.

### Changed
- Changes in existing functionality.

### Deprecated
- Features marked for removal in future releases.

### Removed
- Features removed in this release.

### Fixed
- Bug fixes.

### Security
- Security-related fixes.


## [1.0.0] - 2026-01-30

### Added

#### Backend (Tag: 20260130-141900)
- **Initial Release:** Core backend services for the Purrf application.
- **FastAPI Infrastructure:** High-performance asynchronous API built with FastAPI and SQLAlchemy (asyncpg).
- **Data Synchronization:** Robust synchronization engine for third-party platforms:
  - **JIRA:** Ticket status tracking, count aggregation, and historical data sync.
  - **Gerrit:** Statistics for code reviews, commits, and CL sync.
  - **Google Workspace:**
    - **Google Meet & Calendar:** Attendance records and session summaries.
    - **Google Chat:** Message history and participation logs.
  - **Microsoft Teams:**
    - **Teams Chat:** Participation data and message history.
    - **Member Sync:** Synchronization of organization member.
- **Database Management:** Alembic-based migration system for PostgreSQL.
- **Authentication & Identity:** Secure user authentication and identity management services.
- **Mentorship Module:**
    - **Registration** Viewing and managing mentorship registrations.
    - **Profile** Viewing and managing mentorship user profiles.
- **Notification Management:** System for handling application-wide notifications.

#### Frontend (Tag: 3224520)
- **Initial Release:** React-based single-page application (SPA) built with Vite.
- **Key Pages & Features:**
  - **Interactive Dashboard:** Comprehensive visualization of member activities across various platforms.
  - **Personal Dashboard:** Tailored view for individual member activity and progress.
  - **Data Search:** Advanced search capabilities across aggregated platform data.
  - **Profile Management:** User profile viewing and management.
- **Modern UI/UX:**
  - Adoption of **Shadcn UI** and **Tailwind CSS** for a clean, responsive interface.
  - Strategic isolation of legacy styles during the UI migration process.
- **Build System:** Integration with Bazel for consistent builds and production asset management.
- **State & Routing:** Global routing context using `BrowserRouter` and centralized state management.
- **API Integration:** Seamless communication with the FastAPI backend.

