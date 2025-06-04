# Purrf

## Overview

**Purrf** is a web application designed to provide a comprehensive summary of CircleCat organization members' activity across various platforms. It aggregates data from JIRA, Google Meet, Google Chat, Microsoft Teams, and Gerrit to offer insights into individual contributions, such as the number of messages sent, code changes (CLs) submitted, and more.  Purrf helps team members track progress, assess contributions.

## Features

* **JIRA Ticket Tracking:**  Displays JIRA ticket counts and related status for each member.
* **Google Meet Session Summary:**  Shows attendance records for Google Meet sessions.
* **Google Chat Participation:**  Visualizes participation in Google Chat.
* **Microsoft Teams Activity:**  Visualizes participation in Microsoft Teams Chat.
* **Gerrit Statistics:**  Provides summaries of Gerrit contributions.
* **Interactive Dashboard:**  A web-based dashboard for viewing aggregated reports.
* **User Authentication:**  Secure access to the application.

## Getting Started

This project uses Bazel for build and dependency management.

### Prerequisites

- Bazel 8.1.0
- Python 3.12.3

### Building

Python dependencies are managed within the Bazel workspace.

To build all targets in the project:

```bash
bazel build //...
```

To build specific target in the submodule in the project:

```bash
bazel build //path/to/submodule:specific_target
```

### Running the project

#### Authenticating with Google ADC

```bash
gcloud auth application-default login
gcloud config set project {google_project_id}
```
####  Export Environment Variables
- USER_EMAIL
- SERVICE_ACCOUNT_EMAIL
- LOG_LEVEL
- REDIS_HOST
- REDIS_PORT
- REDIS_PASSWORD
- GERRIT_URL
- GERRIT_USER
- GERRIT_HTTP_PASS
- AZURE_CLIENT_ID
- AZURE_CLIENT_SECRET
- AZURE_TENANT_ID

####  Running the project

```bash
bazel run //src:purrf
```

### Before push the code
Run all test methods:
```bash
bazel test ...
```

Remember to check if code format is up to standard.

To check code format, run:

```bash
bazel clean
bash lint.sh all_files
```
**Note:** If `lint.sh` fails with checksum verification errors (e.g., "sha256sum: command not found"), ensure you have the necessary **jq** installed.

To format the code, run:

```bash
bazel run //:format
```

### Build and Push OCI Image

```bash
bazel build //:purrf_image
bazel run //:flask_image_push_dynamic --action_env=REPO=xxxx --action_env=TAG=xxxx
```
