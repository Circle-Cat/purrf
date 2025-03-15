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
After building the target, run it using:

```bash
bazel run //path/to/submodule:specific_target
```

### Before push the code
Remember to check if code format is up to standard.

To check code format, run:

```bash
bazel clean
bash lint.sh all_files
```
**Note:** If `lint.sh` fails with checksum verification errors (e.g., "sha256sum: command not found"), ensure you have the necessary **jq** installed.

To format the code, run:

```bash
bazel build //:format
bazel run //:format
```

Here’s the updated version with Markdown formatting:

---

# Accessing Google Cloud External APIs

This project integrates with Google Cloud external APIs, such as the Google Chat API. During development, authentication and authorization are handled using a Service Account to impersonate a user login.

## Authenticating with a Service Account

To authenticate and access Google Cloud APIs, you can use a Service Account with impersonation. This allows the Service Account to act on behalf of a user。

## Steps for Development

Follow these steps to set up your development environment:

1. **Set Up a Service Account**:
   - Download the `service_secrets.json` key file into this workspace.

2. **Configure Authentication**:
   - Set the `GOOGLE_APPLICATION_CREDENTIALS` environment variable to point to your Service Account key file. Run this command in your terminal:
     ```bash
     export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service_secrets.json
     ```
     Replace `/path/to/service_secrets.json` with the actual path where you stored the file in your workspace.

3. **Run Project**:
   - Use the following command to execute your project, specifying the user email to impersonate and other optional environment variables:
     ```bash
     USER_EMAIL=<your-gmail> LOG_LEVEL=DEBUG REDIS_HOST=<redis-host> REDIS_PORT=6379 REDIS_PASSWORD=<redis-password> bazel run //path/to/your/binary:binary-name
     ```
     - **Explanation of Variables**:
       - `LOG_LEVEL=DEBUG`: Sets the logging level to `DEBUG` for detailed output during development (optional, defaults to `INFO` if omitted).
       - `REDIS_HOST=<redis-host>`, `REDIS_PORT=6379`, `REDIS_PASSWORD=<redis-password>`: Configuration for interacting with a Redis instance.
     - **Note on Redis Variables**: If your development task doesn’t involve interacting with Redis, you can skip setting `REDIS_HOST`, `REDIS_PORT`, and `REDIS_PASSWORD`. The project will still run without these variables.

## Important Notes

- **Secure Storage**: Store your `service_secrets.json` file securely and **NEVER committing it to gerrit**

- **Scopes**: Use appropriate OAuth 2.0 scopes based on the APIs you need to access (e.g., `https://www.googleapis.com/auth/chat.messages.readonly` for Google Chat). These should be configured in code.
- **Development Only**: This impersonation approach is intended for development. In production, using workload identity.