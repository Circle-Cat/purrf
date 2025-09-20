import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { flattenGoogleCalendarScheduleData } from "@/utils/flattenScheduleData";

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
});
