# Training e2e: side effects audit

What each training write does outside its own rows on test, who it reaches,
and whether the suite lets it out. Read from the backend at the commit the
suite was written against (main as of 2026-10-15). Paths are under
`backend/`.

## Mail, notifications, cron

- **No training write sends anything.** Nothing under `training/`,
  `repository/training_*` or the profile training read calls `record_event`,
  Gmail, Kit, Calendar or Pub/Sub. Assigning a course (single or bulk),
  starting a trial, publishing, discarding and deactivating notify nobody, the
  learner included.
- **No scheduled job reads training.** The cronjobs in
  `helm/purrf/values.yaml` (LDAP, Jira, Calendar pull, leave accrual and
  close, Gmail watch, Meet attendance) never touch `training*` tables. There
  is no deadline reminder or overdue sweep; `training.deadline` is only shown.
- **Auto-assignment never picks a suite course.** `ensure_for_admitted`
  (`mentorship/onboarding_training_service.py`) and the first-login employee
  courses (`user_identity/internal_onboarding_training.py`) resolve the
  course by `category` (`TrainingCourseRepository.get_course_by_category`).
  Suite courses are created through `POST /api/training/courses`, which takes
  `{name, description}` only, so their `category` is always NULL.

## Object storage

- An upload unpacks the zip into `gs://<prefix>-training/training/<course_id>/<32 hex>/…`
  (test: `purrf-test-training`, `terraform/modules/purrf_instance/training.tf`;
  key built in `training/training_package_service.py:_read_and_store`).
  The suite's packages are four files, under 10 KB in all.
- Purrf deletes a prefix itself when its row goes: discarding a staged
  package, uploading over a staged one, and publishing over a live one
  (`_delete_prefix_quietly`, after commit). A rejected upload (not a zip, or
  a damaged member) is refused before or while storing and drops whatever it
  wrote (`_drop_prefix_quietly`).
- What is left is the last live package of each suite course, plus a staged
  one when a test failed between upload and publish or discard. Global
  teardown discards every staged package of a suite course through the API
  (so Purrf deletes those files), then the SQL cleanup removes the rows; the
  live prefixes cannot be removed through Purrf and gcloud is not signed in
  here, so they stay. Teardown prints each one it leaves
  (`[teardown] left in the training bucket: training/<id>/<hex>/`).
- Yuji accepted this residue (2026-10-15): the prefixes stay, nothing cleans
  them.
- Content is served from `test-training-content.purrf.io/p/<token>/…`, which
  has no Access application in front (a bad token gets the backend's 401);
  that is the design, the signed token is the credential.

## Mentorship gates and what real people see

- Mentorship registration, matching eligibility and the console's onboarding
  column read `training.category` in `MENTORSHIP_ONBOARDING_CATEGORIES`
  (`mentorship/matching_eligibility_service.py`,
  `mentorship/mentorship_admin_service.py`,
  `repository/mentorship_round_participants_repository.py`). A row on a suite
  course has `category` NULL (`TrainingAssignmentService._new_row` copies the
  course's), so assigning, finishing or resetting it moves none of them.
  e2e-member's mentee onboarding row (course 1, done) is never written:
  the guard refuses any session, progress or trial on a training row that is
  not on a suite course, and assignment only creates rows on the course named.
- Bulk assignment adopts an existing row by category only when the course
  has one, so a suite course never takes over anybody's onboarding row.
- **Visible to real admins while a run lasts:** the suite's `E2E …` courses
  are listed in the Training Administration catalogue and in its Target
  course picker (every course is listed, no filter). Nothing else
  aggregates over all courses: the profile lists only the viewer's own rows,
  the personal dashboard's onboarding reminder is category based, and the
  audience table's "Courses" count only counts rows a person holds (seed
  trainees and test accounts).
- The trial run creates e2e-admin's own assignment on the course being
  tried (`start_trial`), so e2e-admin holds every suite course; the cleanup
  removes it with the course.

## What the suite lets out

`lib/guard.js` allows a training write only when:

| Write                                                                          | Let out when                                                                               |
| ------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------ |
| `POST /api/training/courses`                                                   | named `E2E …`                                                                              |
| `PATCH /api/training/courses/{id}`                                             | a suite course (created by the suite this run, or `E2E …` with no category in the DB)      |
| upload / publish / discard / trial / preview on `/api/training/courses/{id}/…` | a suite course                                                                             |
| `POST /api/training/assignments/bulk`                                          | a suite course, and every user id a seed trainee (990201–990299) or a test account         |
| `POST /api/training/{id}/session`, `trial-session`, `progress`                 | the training row is on a suite course (checked in the DB, owner a test account or trainee) |

Everything else under `/api/training/` is refused and fails the test; the
four seed courses (`category` set) can never pass the suite-course check.
Nothing is ever mailed, so there is no mail rule.

Teardown fingerprints every real course (`category` set or not named
`E2E …`): id, name, active flag, live and staged package id, version and
verification, and how many assignments and finished assignments it has, and
warns if anything moved.

## Not tested, and why

- **The four real courses**: no upload, publish, discard, trial, preview,
  deactivate or assignment on them; the guard blocks it. Yuji allowed using
  them (no mail or notification goes to their learners: none of these writes
  notifies anybody, see above), on condition that teardown puts their live
  package back. That cannot be done: publishing deletes the outgoing live
  package's row and then its files (`publish_package` →
  `_delete_prefix_quietly`), so the original package is gone from the bucket
  and no SQL can make it live again; and an upload to courses 3 and 4 would
  also delete the package staged on them now (`DMGDdmgd`, `9K8IMOal`). The
  course–category–mentorship-gate link is covered from the other side
  instead: e2e-member's mentee onboarding row is checked unchanged around
  every learner test.
- **Assigning to a real person** from the bulk page: the guard aborts it;
  one spec proves the abort.
- **A learner on an external-link course** (`training.link` / a category
  with an onboarding link): only the real mentorship courses have one.
- **Deleting a course**: there is no endpoint; the suite deactivates.
