import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  flattenGoogleCalendarScheduleData,
  flattenMicrosoftChatData,
  flattenGoogleChatData,
} from "@/utils/flattenScheduleData";

let toLocaleDateStringSpy;
let toLocaleTimeStringSpy;

const restoreDatePrototypes = () => {
  toLocaleDateStringSpy?.mockRestore();
  toLocaleTimeStringSpy?.mockRestore();
};

describe("flattenGoogleCalendarScheduleData", () => {
  beforeEach(() => {
    const dateMap = {
      "2025-09-20T09:00": "9/20/2025",
      "2025-09-20T10:00": "9/20/2025",
      "2025-09-20T14:30": "9/20/2025",
      "2025-09-20T15:00": "9/20/2025",
      "2025-09-21T11:00": "9/21/2025",
      "2025-09-21T12:00": "9/21/2025",
      "2025-09-21T15:30": "9/21/2025",
      "2025-09-21T16:00": "9/21/2025",
    };

    const timeMap = {
      "2025-09-20T09:00": "9:00 AM",
      "2025-09-20T10:00": "10:00 AM",
      "2025-09-20T14:30": "2:30 PM",
      "2025-09-20T15:00": "3:00 PM",
      "2025-09-21T11:00": "11:00 AM",
      "2025-09-21T12:00": "12:00 PM",
      "2025-09-21T15:30": "3:30 PM",
      "2025-09-21T16:00": "4:00 PM",
    };

    toLocaleDateStringSpy = vi
      .spyOn(Date.prototype, "toLocaleDateString")
      .mockImplementation(function () {
        const isoPrefix = this.toISOString().slice(0, 16); // 'YYYY-MM-DDTHH:MM'
        return dateMap[isoPrefix] ?? "9/20/2025";
      });

    toLocaleTimeStringSpy = vi
      .spyOn(Date.prototype, "toLocaleTimeString")
      .mockImplementation(function () {
        const isoPrefix = this.toISOString().slice(0, 16);
        return (
          timeMap[isoPrefix] ??
          new Intl.DateTimeFormat([], {
            hour: "2-digit",
            minute: "2-digit",
          }).format(this)
        );
      });
  });

  afterEach(() => {
    restoreDatePrototypes();
  });

  it("should return an empty array for null or undefined input", () => {
    expect(flattenGoogleCalendarScheduleData(null)).toEqual([]);
    expect(flattenGoogleCalendarScheduleData(undefined)).toEqual([]);
  });

  it("should return an empty array for an empty object", () => {
    expect(flattenGoogleCalendarScheduleData({})).toEqual([]);
  });

  it("should flatten nested data correctly", () => {
    const mockBackendData = {
      ldap1: [
        {
          calendar_name: "Calendar A",
          summary: "Meeting 1",
          event_id: "e1",
          attendance: [
            {
              join_time: "2025-09-20T09:00:00Z",
              leave_time: "2025-09-20T10:00:00Z",
            },

            {
              join_time: "2025-09-21T11:00:00Z",
              leave_time: "2025-09-21T12:00:00Z",
            },
          ],
        },
        {
          calendar_name: "Calendar A",
          summary: "Meeting 2",
          event_id: "e2",
          attendance: [
            {
              join_time: "2025-09-20T14:30:00Z",
              leave_time: "2025-09-20T15:00:00Z",
            },
          ],
        },
      ],
      ldap2: [
        {
          calendar_name: "Calendar B",
          summary: "Sync Up",
          event_id: "e3",
          attendance: [
            {
              join_time: "2025-09-21T15:30:00Z",
              leave_time: "2025-09-21T16:00:00Z",
            },
          ],
        },
      ],
    };

    const expected = [
      {
        ldap: "ldap1",
        calendarName: "Calendar A",
        summary: "Meeting 1",
        date: "9/20/2025",
        joinTime: "9:00 AM",
        leaveTime: "10:00 AM",
        key: "ldap1-e1-0",
      },
      {
        ldap: "ldap1",
        calendarName: "Calendar A",
        summary: "Meeting 1",
        date: "9/21/2025",
        joinTime: "11:00 AM",
        leaveTime: "12:00 PM",
        key: "ldap1-e1-1",
      },
      {
        ldap: "ldap1",
        calendarName: "Calendar A",
        summary: "Meeting 2",
        date: "9/20/2025",
        joinTime: "2:30 PM",
        leaveTime: "3:00 PM",
        key: "ldap1-e2-0",
      },
      {
        ldap: "ldap2",
        calendarName: "Calendar B",
        summary: "Sync Up",
        date: "9/21/2025",
        joinTime: "3:30 PM",
        leaveTime: "4:00 PM",
        key: "ldap2-e3-0",
      },
    ];

    const result = flattenGoogleCalendarScheduleData(mockBackendData);
    expect(result).toEqual(expected);
  });

  it("should handle missing events or attendance arrays gracefully", () => {
    const mockBackendData = {
      ldap1: [
        {
          calendar_name: "Calendar A",
          summary: "Meeting 1",
          event_id: "e1",
          attendance: null,
        },
      ],
      ldap2: null,
      ldap3: [
        {
          calendar_name: "Calendar C",
          summary: "Meeting 3",
          event_id: "e4",
        },
      ],
    };
    expect(flattenGoogleCalendarScheduleData(mockBackendData)).toEqual([]);
  });

  describe("flattenMicrosoftChatData", () => {
    it("should return an empty array for null or undefined data", () => {
      expect(
        flattenMicrosoftChatData({ data: null, defaultChatSpace: "test" }),
      ).toEqual([]);
      expect(
        flattenMicrosoftChatData({ data: undefined, defaultChatSpace: "test" }),
      ).toEqual([]);
    });

    it("should return an empty array for an empty object", () => {
      expect(
        flattenMicrosoftChatData({ data: {}, defaultChatSpace: "test" }),
      ).toEqual([]);
    });

    it("should flatten data correctly with a default chat space", () => {
      const mockData = {
        alice: 15,
        bob: 10,
        charlie: 22,
      };
      const defaultChatSpace = "General Channel";
      const expected = [
        { ldap: "alice", chatSpace: "General Channel", counts: 15 },
        { ldap: "bob", chatSpace: "General Channel", counts: 10 },
        { ldap: "charlie", chatSpace: "General Channel", counts: 22 },
      ];
      expect(
        flattenMicrosoftChatData({ data: mockData, defaultChatSpace }),
      ).toEqual(expected);
    });

    it("should handle a count of zero correctly", () => {
      const mockData = {
        dave: 0,
      };
      const defaultChatSpace = "Test Space";
      const expected = [{ ldap: "dave", chatSpace: "Test Space", counts: 0 }];
      expect(
        flattenMicrosoftChatData({ data: mockData, defaultChatSpace }),
      ).toEqual(expected);
    });
  });
  describe("flattenGoogleChatData", () => {
    it("should return an empty array for null or undefined data", () => {
      expect(flattenGoogleChatData({ data: null, spaceMap: {} })).toEqual([]);
      expect(flattenGoogleChatData({ data: undefined, spaceMap: {} })).toEqual(
        [],
      );
    });

    it("should return an empty array for an empty data object", () => {
      expect(flattenGoogleChatData({ data: {}, spaceMap: {} })).toEqual([]);
    });

    it("should flatten nested data correctly and use the spaceMap for names", () => {
      const mockData = {
        alice: { space1: 25, space2: 5 },
        bob: { space1: 11, space2: 0 },
      };
      const mockSpaceMap = {
        space1: "Team-Alpha",
        space2: "Project-Omega",
      };
      const expected = [
        { ldap: "alice", chatSpace: "Team-Alpha", counts: 25 },
        { ldap: "alice", chatSpace: "Project-Omega", counts: 5 },
        { ldap: "bob", chatSpace: "Team-Alpha", counts: 11 },
        { ldap: "bob", chatSpace: "Project-Omega", counts: 0 },
      ];
      expect(
        flattenGoogleChatData({ data: mockData, spaceMap: mockSpaceMap }),
      ).toEqual(expected);
    });

    it("should handle a count of zero correctly", () => {
      const mockData = {
        charlie: { space3: 0 },
      };
      const mockSpaceMap = {
        space3: "Support-Chat",
      };
      const expected = [
        { ldap: "charlie", chatSpace: "Support-Chat", counts: 0 },
      ];
      expect(
        flattenGoogleChatData({ data: mockData, spaceMap: mockSpaceMap }),
      ).toEqual(expected);
    });

    it("should use the spaceId as a fallback if not found in the spaceMap", () => {
      const mockData = {
        dave: { space4: 50 },
      };
      const mockSpaceMap = {}; // Empty map
      const expected = [{ ldap: "dave", chatSpace: "space4", counts: 50 }];
      expect(
        flattenGoogleChatData({ data: mockData, spaceMap: mockSpaceMap }),
      ).toEqual(expected);
    });
  });
});
