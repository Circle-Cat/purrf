import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { RouterProvider, createMemoryRouter } from "react-router-dom";
import WorkGuidePage from "@/pages/WorkGuide";
import EmailFlowDiagram from "@/pages/WorkGuide/EmailFlowDiagram";
import GuideBlocks from "@/pages/WorkGuide/GuideBlocks";
import { useAuth } from "@/context/auth";
import { useFeatureFlags } from "@/hooks/useFeatureFlags";
import { useFeatureFlagsReady } from "@/hooks/useFeatureFlagsReady";
import { highlightAnchor } from "@/whatsNew/highlightAnchor";
import { FEATURE_FLAGS } from "@/constants/FeatureFlags";
import { INBOX_PERMISSIONS, PERMISSIONS } from "@/constants/Permissions";
import { GUIDE_PERMISSIONS } from "@/pages/WorkGuide/guideModel";

vi.mock("@/context/auth", () => ({ useAuth: vi.fn() }));
vi.mock("@/hooks/useFeatureFlags", () => ({ useFeatureFlags: vi.fn() }));
vi.mock("@/hooks/useFeatureFlagsReady", () => ({
  useFeatureFlagsReady: vi.fn(),
}));
vi.mock("@/whatsNew/highlightAnchor", () => ({ highlightAnchor: vi.fn() }));

const chapters = [
  {
    id: "start-here",
    title: "Start here",
    description: "How email and approvals work across Purrf.",
    permissions: GUIDE_PERMISSIONS,
    flows: [
      {
        id: "fixture-basics",
        title: "Fixture email basics",
        intro: "One mailbox for everything.",
        blocks: [{ type: "text", text: "Addresses decide where mail lands." }],
      },
    ],
  },
  {
    id: "inbox",
    title: "Inbox",
    description: "Answer fixture email.",
    permissions: INBOX_PERMISSIONS,
    flows: [
      {
        id: "fixture-reply",
        title: "Reply to a fixture email",
        whoFor: "anyone who can see the inbox",
        intro: "The Inbox holds fixture conversations.",
        blocks: [
          {
            type: "steps",
            steps: [
              {
                text: "Open **Inbox** in the sidebar.",
                imageAlt: "Screenshot: sidebar",
                route: "/inbox",
                anchor: "inbox-nav",
              },
              {
                text: "Click **Send reply**.",
                image: "/guide/fixture-reply.png",
                imageAlt: "Screenshot: the reply box",
              },
            ],
          },
          { type: "goodToKnow", items: ["Your **draft** is kept."] },
        ],
      },
    ],
  },
  {
    id: "recruiting",
    title: "Recruiting",
    description: "Move fixture applications.",
    permissions: [PERMISSIONS.RECRUITING_APPLICATION_ADVANCE],
    flows: [
      {
        id: "recruiting-advance",
        title: "Advance a fixture application",
        blocks: [{ type: "text", text: "Use the board." }],
      },
    ],
  },
];

const viewer = ({
  permissions = [
    PERMISSIONS.MENTORSHIP_ADMIN_WRITE,
    PERMISSIONS.RECRUITING_APPLICATION_ADVANCE,
  ],
  flag = true,
  ready = true,
  loading = false,
} = {}) => {
  useAuth.mockReturnValue({ permissions, loading });
  useFeatureFlags.mockReturnValue({ [FEATURE_FLAGS.WORK_GUIDE]: flag });
  useFeatureFlagsReady.mockReturnValue(ready);
};

const renderAt = (url) => {
  const page = <WorkGuidePage chapters={chapters} />;
  const router = createMemoryRouter(
    [
      { path: "/guide", element: page },
      { path: "/guide/:flowId", element: page },
      { path: "/access-denied", element: <p>Access denied page</p> },
      { path: "/inbox", element: <p>Inbox page</p> },
    ],
    { initialEntries: [url] },
  );
  const result = render(<RouterProvider router={router} />);
  return { ...result, router };
};

describe("WorkGuidePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    viewer();
  });

  it("shows the home page with the Start here card", () => {
    renderAt("/guide");

    expect(
      screen.getByRole("heading", { level: 1, name: "Work guide" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "How to do your work in Purrf, step by step. You only see the parts that match your permissions.",
      ),
    ).toBeInTheDocument();
    const card = screen.getByRole("link", { name: /Read this first →/ });
    expect(within(card).getByText("Start here")).toBeInTheDocument();
    expect(card).toHaveAttribute("href", "/guide/fixture-basics");
    expect(
      screen.getByRole("heading", { level: 2, name: "Recruiting" }),
    ).toBeInTheDocument();
  });

  it("shows a flow with its sections and neighbours", () => {
    renderAt("/guide/fixture-reply");

    const breadcrumb = screen.getByRole("navigation", { name: "Breadcrumb" });
    expect(
      within(breadcrumb).getByRole("link", { name: "Work guide" }),
    ).toHaveAttribute("href", "/guide");
    expect(
      screen.getByRole("heading", {
        level: 1,
        name: "Reply to a fixture email",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("For: anyone who can see the inbox"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { level: 2, name: "Steps" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { level: 2, name: "Good to know" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /Previous.*Fixture email basics/ }),
    ).toHaveAttribute("href", "/guide/fixture-basics");
    expect(
      screen.getByRole("link", { name: /Next.*Advance a fixture application/ }),
    ).toHaveAttribute("href", "/guide/recruiting-advance");

    const onThisPage = screen.getByRole("navigation", {
      name: "On this page",
    });
    expect(
      within(onThisPage).getByRole("link", { name: "Steps" }),
    ).toHaveAttribute("href", "#steps");
    expect(
      within(onThisPage).getByRole("link", { name: "Good to know" }),
    ).toHaveAttribute("href", "#good-to-know");
  });

  it("marks the current flow in the guide nav", () => {
    renderAt("/guide/fixture-reply");

    const nav = screen.getByRole("navigation", { name: "Work guide contents" });
    expect(
      within(nav).getByRole("link", { name: "Reply to a fixture email" }),
    ).toHaveAttribute("aria-current", "page");
    expect(
      within(nav).getByRole("link", { name: "Fixture email basics" }),
    ).not.toHaveAttribute("aria-current");
  });

  it("renders a screenshot only for a step that has one, loaded lazily", () => {
    renderAt("/guide/fixture-reply");

    const images = screen.getAllByRole("img");
    expect(images).toHaveLength(1);
    expect(images[0]).toHaveAttribute("src", "/guide/fixture-reply.png");
    expect(images[0]).toHaveAttribute("alt", "Screenshot: the reply box");
    expect(images[0]).toHaveAttribute("loading", "lazy");
    expect(images[0]).toHaveAttribute("decoding", "async");
    expect(screen.queryByAltText("Screenshot: sidebar")).toBeNull();
  });

  it("opens the step's page and highlights its anchor", async () => {
    const { router } = renderAt("/guide/fixture-reply");

    const links = screen.getAllByRole("button", { name: "Open in Purrf →" });
    expect(links).toHaveLength(1);
    fireEvent.click(links[0]);

    expect(await screen.findByText("Inbox page")).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/inbox");
    expect(highlightAnchor).toHaveBeenCalledWith("inbox-nav");
  });

  it("says an unknown flow isn't in the guide", () => {
    renderAt("/guide/nope");

    expect(
      screen.getByText("This page isn't in the guide."),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Back to the Work guide" }),
    ).toHaveAttribute("href", "/guide");
  });

  it("treats a flow hidden by permission as unknown", () => {
    viewer({ permissions: [PERMISSIONS.MENTORSHIP_ADMIN_READ] });
    renderAt("/guide/recruiting-advance");

    expect(
      screen.getByText("This page isn't in the guide."),
    ).toBeInTheDocument();
    expect(screen.queryByText("Advance a fixture application")).toBeNull();
  });

  it("searches only the visible flows and says when nothing matches", () => {
    renderAt("/guide");

    const search = screen.getByLabelText("Search the guide");
    expect(search).toHaveAttribute(
      "placeholder",
      "e.g. reply, reject, approve",
    );

    fireEvent.change(search, { target: { value: "zzz" } });
    expect(screen.getByText("No matches")).toBeInTheDocument();

    fireEvent.change(search, { target: { value: "reply (" } });
    expect(screen.getByText("No matches")).toBeInTheDocument();

    fireEvent.change(search, { target: { value: "SEND REPLY" } });
    const nav = screen.getByRole("navigation", { name: "Work guide contents" });
    expect(
      within(nav).getByRole("link", { name: "Reply to a fixture email" }),
    ).toBeInTheDocument();
    expect(within(nav).queryByText("Fixture email basics")).toBeNull();
  });

  it("renders nothing until the flags are ready", () => {
    viewer({ ready: false, flag: false });
    const { container } = renderAt("/guide");

    expect(container).toBeEmptyDOMElement();
    expect(screen.queryByText("Access denied page")).toBeNull();
  });

  it("renders nothing while auth is loading", () => {
    viewer({ loading: true, permissions: [] });
    const { container } = renderAt("/guide");

    expect(container).toBeEmptyDOMElement();
  });

  it("redirects to Access denied when the flag is off", async () => {
    viewer({ flag: false });
    renderAt("/guide");

    expect(await screen.findByText("Access denied page")).toBeInTheDocument();
  });

  it("redirects to Access denied when no chapter is visible", async () => {
    viewer({ permissions: [PERMISSIONS.LEAVE_ADMIN] });
    renderAt("/guide/fixture-basics");

    expect(await screen.findByText("Access denied page")).toBeInTheDocument();
  });
});

describe("GuideBlocks", () => {
  it("renders text, headings and tables with bold labels", () => {
    render(
      <GuideBlocks
        blocks={[
          { type: "heading", text: "Addresses" },
          { type: "text", text: "Use **Send email**." },
          {
            type: "table",
            columns: ["Where", "Use it to"],
            rows: [["**Inbox**", "Answer people"]],
          },
        ]}
        headingIds={["addresses"]}
        onOpen={vi.fn()}
      />,
    );

    expect(
      screen.getByRole("heading", { level: 2, name: "Addresses" }),
    ).toHaveAttribute("id", "addresses");
    expect(screen.getByText("Send email").tagName).toBe("STRONG");
    expect(
      screen.getByRole("columnheader", { name: "Use it to" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "Inbox" })).toBeInTheDocument();
  });

  it("uses a steps block's own title", () => {
    render(
      <GuideBlocks
        blocks={[
          {
            type: "steps",
            title: "Rules of thumb",
            steps: [{ text: "Look where you sent from." }],
          },
        ]}
        headingIds={["rules-of-thumb"]}
        onOpen={vi.fn()}
      />,
    );

    expect(
      screen.getByRole("heading", { level: 2, name: "Rules of thumb" }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Steps" })).toBeNull();
    expect(screen.getByText("1")).toBeInTheDocument();
  });

  it("renders the email flow diagram block", () => {
    render(
      <GuideBlocks
        blocks={[{ type: "diagram", name: "emailFlow" }]}
        headingIds={[]}
        onOpen={vi.fn()}
      />,
    );

    expect(screen.getByText("Inbox: Unsorted")).toBeInTheDocument();
  });
});

describe("EmailFlowDiagram", () => {
  it("shows where each kind of incoming email lands", () => {
    render(<EmailFlowDiagram />);

    const figure = screen.getByRole("figure");
    expect(within(figure).getAllByRole("listitem")).toHaveLength(4);
    for (const text of [
      "Application: Emails tab / Participant page: Timeline",
      "Inbox: Mentorship, Recruiting or Contact",
      "Inbox: Unsorted",
      "Not collected in Purrf",
    ]) {
      expect(within(figure).getByText(text)).toBeInTheDocument();
    }
  });
});
