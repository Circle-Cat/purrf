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

See: backend/common/environment_constants.py

### Init PostgreSQL Database
**Warning**: The init_db command will **drop all existing data** and recreate an empty database with only the table structure. Using the same database for tests will erase your development data.

Note: The init_db script always reads DATABASE_URL to determine which database to initialize. Be careful to avoid running tests on production or important development data, as it may be cleared.

Create and initialize the database:
```bash
export DATABASE_URL=postgresql+asyncpg://<user>:<password>@<host>:<port>/<database>
bazel run //tools:init_db
```

**Important Notes:**

* Both development and test code use the same database.

* init_db should be run before starting the backend or running unit tests to ensure a clean environment.

* Any existing data will be deleted when running init_db.

####  Running the backend project for development

- **Command** (asynchronous support):
For developing Mentorship-related modules, please use this one.
```bash
bazel run //backend:fast_app_dev_runner
```

####  Running the frontend project for development

```bash
bazel run //frontend:dev_server
```
### Development with Hot Reload (Vite + ibazel)

### Install ibazel

```bash
go install github.com/bazelbuild/bazel-watcher/cmd/ibazel@latest
```
### Run

```bash
ibazel run //frontend:dev_server
```

#### Locally preview the frontend production build

```bash
bazel build //frontend:dist
bazel run //frontend:vite_preview
```

### Before pushing code

Before pushing any frontend changes, you **must run both commands below** to build the frontend and preview it in an environment **that is consistent with production**.

This step is required to verify that the built artifacts behave **exactly as expected in production**, not just in the development server.

```bash
bazel build //frontend:dist
bazel run //frontend:vite_preview


Before running the repository unit tests under `tests/backend_test/repository_test`,
export the test database URL (replace the placeholders as needed):

```bash
export DATABASE_URL=postgresql+asyncpg://<user>:<password>@<host>:<port>/<database>
```

Run all test methods:
```bash
bazel test ...
```

Remember to check if code format is up to standard.

To check code format, run:

```bash
bazel clean
bash lint.sh --fix all_files
```
**Note:** If `lint.sh` fails with checksum verification errors (e.g., "sha256sum: command not found"), ensure you have the necessary **jq** installed.

To format the code, run:

```bash
bazel run //:format
```

### Build and Push OCI Image

### Backend
```bash
bazel build //:purrf_image
bazel run //:purrf_image_push_dynamic --action_env=BE_REPO=xxx --action_env=TAG_1=timestamp --action_env=TAG_2=latest
```

> **Deprecated:** We now deploy the frontend dist on a CDN, so these commands are no longer required.
However, we keep them here for potential future use.
### Frontend
```bash
bazel build //frontend:dist
bazel build //:frontend_image
bazel run //:frontend_image_push_dynamic --action_env=FE_REPO=xxxx --action_env=TAG=xxxx
```

### PostgreSQL Docker Setup

For local **development only**, you can spin up a PostgreSQL database using the provided script.

#### Give the script execute permission and start the PostgreSQL container
```bash
chmod +x docker/postgres_up.sh
./docker/postgres_up.sh
```

This launches a PostgreSQL 16 container on:
* Host: localhost
* Port: 5432
* User: myuser
* Password: mypassword
* Database: mydb

#### Stop and remove the container
```bash
docker stop my-postgres
docker rm my-postgres
```