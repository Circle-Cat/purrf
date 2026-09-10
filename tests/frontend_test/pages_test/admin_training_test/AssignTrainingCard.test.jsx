import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { toast } from "sonner";
import AssignTrainingCard from "@/pages/AdminTraining/components/AssignTrainingCard";
import {
  searchAudience,
  listAudienceIds,
  assignCourseBulk,
  listUserAssignments,
} from "@/api/trainingApi";

vi.mock("@/api/trainingApi", () => ({
  searchAudience: vi.fn(),
  listAudienceIds: vi.fn(),
  assignCourseBulk: vi.fn(),
  listUserAssignments: vi.fn(),
}));

const LIVE = {
  courseId: 1,
  name: "Corporate Culture",
  liveState: "live",
  isActive: true,
};
const PACKAGELESS = {
  courseId: 2,
  name: "Residency Onboarding",
  liveState: "no_package",
  isActive: true,
};
const DEACTIVATED = {
  courseId: 3,
  name: "Old Safety Briefing",
  liveState: "live",
  isActive: false,
};
const COURSES = [LIVE, PACKAGELESS, DEACTIVATED];

const row = (over = {}) => ({
  userId: 11,
  firstName: "Ada",
  lastName: "Internal",
  preferredName: null,
  contactEmail: "ada@circlecat.org",
  isInternal: true,
  courseStatus: null,
  assignedCourseCount: 0,
  doneCourseCount: 0,
  ...over,
});

const page = (rows, total) => ({
  data: { rows, total: total ?? rows.length },
});

const renderCard = () => render(<AssignTrainingCard courses={COURSES} />);

const pickCourse = async (user, name) =>
  user.selectOptions(screen.getByLabelText("Target course"), name);

const submitSearch = async (user) =>
  user.click(screen.getByRole("button", { name: "Search" }));

describe("AssignTrainingCard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    searchAudience.mockResolvedValue(page([row()]));
    listAudienceIds.mockResolvedValue({ data: { userIds: [11], total: 1 } });
    assignCourseBulk.mockResolvedValue({
      message: "Assigned to 1 people. 0 already had this course.",
      data: { courseId: 1, createdCount: 1, alreadyAssignedCount: 0 },
    });
    listUserAssignments.mockResolvedValue({
      data: { userId: 11, rows: [] },
    });
    vi.spyOn(toast, "error").mockImplementation(() => {});
    vi.spyOn(toast, "success").mockImplementation(() => {});
  });

  it("waits to be asked before it searches anybody", async () => {
    renderCard();

    expect(
      screen.getByText("Search to find the people to assign a course to."),
    ).toBeInTheDocument();
    expect(searchAudience).not.toHaveBeenCalled();
  });

  it("lists every course, deactivated and packageless included", async () => {
    renderCard();

    const options = within(screen.getByLabelText("Target course"))
      .getAllByRole("option")
      .map((option) => option.textContent);

    expect(options).toEqual([
      "All courses",
      "Corporate Culture",
      "Residency Onboarding",
      "Old Safety Briefing",
    ]);
  });

  it("cannot assign before a course is named", async () => {
    renderCard();

    const assign = screen.getByRole("button", { name: "Assign" });
    expect(assign).toBeDisabled();
    expect(assign).toHaveAttribute("title", "Pick a course to assign");
  });

  it("cannot assign a course with nothing published", async () => {
    const user = userEvent.setup();
    renderCard();

    await pickCourse(user, "Residency Onboarding");

    expect(screen.getByRole("button", { name: "Assign" })).toHaveAttribute(
      "title",
      "Publish a package to this course first",
    );
  });

  it("cannot assign a deactivated course", async () => {
    const user = userEvent.setup();
    renderCard();

    await pickCourse(user, "Old Safety Briefing");

    expect(screen.getByRole("button", { name: "Assign" })).toHaveAttribute(
      "title",
      "This course is deactivated. Turn it back on to assign it.",
    );
  });

  it("assigns the ticked people once a live course is named", async () => {
    const user = userEvent.setup();
    renderCard();
    await pickCourse(user, "Corporate Culture");
    await submitSearch(user);

    await user.click(await screen.findByLabelText("Select Ada Internal"));
    await user.click(screen.getByRole("button", { name: "Assign" }));

    await waitFor(() =>
      expect(assignCourseBulk).toHaveBeenCalledWith({
        courseId: LIVE.courseId,
        userIds: [11],
      }),
    );
  });

  it("only offers the group facet to internal accounts", async () => {
    const user = userEvent.setup();
    renderCard();

    expect(screen.getByLabelText("Group")).toBeDisabled();
    await user.selectOptions(screen.getByLabelText("Type"), "Internal");
    expect(screen.getByLabelText("Group")).toBeEnabled();
  });

  it("only offers the course-status facet once a course is named", async () => {
    const user = userEvent.setup();
    renderCard();

    expect(screen.getByLabelText("On this course")).toBeDisabled();
    await pickCourse(user, "Corporate Culture");
    expect(screen.getByLabelText("On this course")).toBeEnabled();
  });

  it("shows what a person holds overall while no course is named", async () => {
    const user = userEvent.setup();
    searchAudience.mockResolvedValue(
      page([
        row({ assignedCourseCount: 4, doneCourseCount: 2 }),
        row({ userId: 12, firstName: "Bo", assignedCourseCount: 0 }),
      ]),
    );
    renderCard();

    await submitSearch(user);

    expect(await screen.findByText("4 courses · 2 done")).toBeInTheDocument();
    expect(screen.getByText("No courses")).toBeInTheDocument();
  });

  it("shows the status on the course once one is named", async () => {
    const user = userEvent.setup();
    searchAudience.mockResolvedValue(
      page([row({ courseStatus: "in_progress" })]),
    );
    renderCard();

    await pickCourse(user, "Corporate Culture");
    await submitSearch(user);

    expect(await screen.findByText("In progress")).toBeInTheDocument();
  });

  it("reads Not assigned off a person with no row for the course", async () => {
    const user = userEvent.setup();
    searchAudience.mockResolvedValue(page([row({ courseStatus: null })]));
    renderCard();

    await pickCourse(user, "Corporate Culture");
    await submitSearch(user);

    // Scoped to the row: "Not assigned" is also one of the facet's options.
    const person = await screen.findByTestId("audience-row-11");
    expect(within(person).getByText("Not assigned")).toBeInTheDocument();
  });

  it("selects everyone matching through the separate ids request", async () => {
    const user = userEvent.setup();
    searchAudience.mockResolvedValue(page([row()], 40));
    listAudienceIds.mockResolvedValue({
      data: { userIds: [11, 12, 13], total: 3 },
    });
    renderCard();
    await submitSearch(user);

    // Waiting on the label, not the call: the button only names the total
    // once the first page has landed.
    await user.click(
      await screen.findByRole("button", { name: "Select all 40 matching" }),
    );

    expect(listAudienceIds).toHaveBeenCalled();
    expect(await screen.findByText("3 selected")).toBeInTheDocument();
  });

  it("drops the ticks when a facet changes", async () => {
    const user = userEvent.setup();
    renderCard();
    await submitSearch(user);
    await user.click(await screen.findByLabelText("Select Ada Internal"));
    expect(screen.getByText("1 selected")).toBeInTheDocument();

    await user.type(screen.getByLabelText("Name or email"), "a");

    expect(screen.queryByText("1 selected")).not.toBeInTheDocument();
  });

  it("pages without losing the count", async () => {
    const user = userEvent.setup();
    searchAudience.mockResolvedValue(page([row()], 40));
    renderCard();
    await submitSearch(user);

    expect(await screen.findByText("1–20 of 40")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Next" }));

    await waitFor(() =>
      expect(searchAudience).toHaveBeenLastCalledWith(
        expect.objectContaining({ offset: 20 }),
      ),
    );
  });

  it("says so when nobody matches", async () => {
    const user = userEvent.setup();
    searchAudience.mockResolvedValue(page([], 0));
    renderCard();

    await submitSearch(user);

    expect(
      await screen.findByText("Nobody matches this search."),
    ).toBeInTheDocument();
  });
  it("lists what a person holds when their row is expanded", async () => {
    const user = userEvent.setup();
    listUserAssignments.mockResolvedValue({
      data: {
        userId: 11,
        rows: [
          {
            trainingId: 900,
            courseId: 1,
            courseName: "Corporate Culture",
            category: "corporate_culture_course",
            status: "in_progress",
            deadline: "2026-10-01T00:00:00Z",
            completedTimestamp: null,
            lessonStatus: "incomplete",
            scoreRaw: "82.50",
            scoreMax: "100.00",
            sessionTimeSeconds: 940,
            lastAccessedAt: "2026-09-01T10:00:00Z",
          },
        ],
      },
    });
    renderCard();
    await submitSearch(user);

    await user.click(
      await screen.findByRole("button", {
        name: "Show courses for Ada Internal",
      }),
    );

    // Scoped to the sub-row: the course names are also dropdown options.
    const held = within(await screen.findByTestId("user-assignments-11"));
    expect(held.getByText("Corporate Culture")).toBeInTheDocument();
    expect(held.getByText("82.50")).toBeInTheDocument();
    expect(held.getByText("15m 40s")).toBeInTheDocument();
    expect(listUserAssignments).toHaveBeenCalledWith(11);
  });

  it("says so for a person holding nothing at all", async () => {
    const user = userEvent.setup();
    renderCard();
    await submitSearch(user);

    await user.click(
      await screen.findByRole("button", {
        name: "Show courses for Ada Internal",
      }),
    );

    expect(await screen.findByText("No courses assigned.")).toBeInTheDocument();
  });

  it("reads a person's courses once, not on every expand", async () => {
    const user = userEvent.setup();
    renderCard();
    await submitSearch(user);
    const toggle = await screen.findByRole("button", {
      name: "Show courses for Ada Internal",
    });

    await user.click(toggle);
    await screen.findByText("No courses assigned.");
    await user.click(
      screen.getByRole("button", { name: "Hide courses for Ada Internal" }),
    );
    await user.click(
      screen.getByRole("button", { name: "Show courses for Ada Internal" }),
    );

    expect(listUserAssignments).toHaveBeenCalledTimes(1);
  });

  it("reports a failed read of a person's courses", async () => {
    const user = userEvent.setup();
    listUserAssignments.mockRejectedValue(new Error("could not read the list"));
    renderCard();
    await submitSearch(user);

    await user.click(
      await screen.findByRole("button", {
        name: "Show courses for Ada Internal",
      }),
    );

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith("could not read the list"),
    );
  });
  it("does not claim a course status for rows fetched without a course", async () => {
    const user = userEvent.setup();
    searchAudience.mockResolvedValue(
      page([row({ assignedCourseCount: 4, doneCourseCount: 2 })]),
    );
    renderCard();
    await submitSearch(user);
    await screen.findByText("4 courses · 2 done");

    // Picking a course does not refetch, so the rows on screen were never
    // asked about it. Reading "Not assigned" off them would be a lie.
    await pickCourse(user, "Corporate Culture");

    const person = within(screen.getByTestId("audience-row-11"));
    expect(person.queryByText("Not assigned")).not.toBeInTheDocument();
    expect(person.getByText("4 courses · 2 done")).toBeInTheDocument();
  });

  it("will not select everyone against a search that has moved on", async () => {
    const user = userEvent.setup();
    searchAudience.mockResolvedValue(page([row()], 40));
    renderCard();
    await submitSearch(user);
    const selectAll = await screen.findByRole("button", {
      name: "Select all 40 matching",
    });
    expect(selectAll).toBeEnabled();

    await user.selectOptions(screen.getByLabelText("Type"), "External");

    expect(
      screen.getByRole("button", { name: "Select all 40 matching" }),
    ).toBeDisabled();
    expect(listAudienceIds).not.toHaveBeenCalled();
  });
});
