/** Calendar date as YYYY-MM-DD (no time component). */
export type CalendarDate = string;

const readZonedParts = (date: Date, timeZone: string) => {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).formatToParts(date);

  const get = (type: string) => Number(parts.find((p) => p.type === type)?.value ?? 0);
  return {
    year: get("year"),
    month: get("month"),
    day: get("day"),
    hour: get("hour"),
    minute: get("minute"),
    second: get("second"),
  };
};

/** Map a UTC instant to the hour (0–23) in `timeZone`. */
export const getZonedHour = (date: Date, timeZone: string) =>
  readZonedParts(date, timeZone).hour;

export const formatHourBucketLabel = (hour: number) => {
  const d = new Date();
  d.setHours(hour, 0, 0, 0);
  return d.toLocaleTimeString("en-US", { hour: "numeric", hour12: true });
};

export const formatZonedDayLabel = (date: Date, timeZone: string) =>
  new Intl.DateTimeFormat("en-US", {
    timeZone,
    day: "2-digit",
    month: "short",
  }).format(date);

const zonedLocalToUtc = (
  year: number,
  month: number,
  day: number,
  hour: number,
  minute: number,
  second: number,
  timeZone: string
): Date => {
  let ts = Date.UTC(year, month - 1, day, hour, minute, second);
  for (let i = 0; i < 4; i++) {
    const got = readZonedParts(new Date(ts), timeZone);
    ts += Date.UTC(year, month - 1, day, hour, minute, second) -
      Date.UTC(got.year, got.month - 1, got.day, got.hour, got.minute, got.second);
  }
  return new Date(ts);
};

/** Inclusive UTC bounds for one calendar day in `timeZone`. */
export const calendarDayBoundsInZone = (
  dateStr: CalendarDate,
  timeZone: string
): { start: Date; end: Date } => {
  const [year, month, day] = dateStr.split("-").map((n) => Number(n));
  const start = zonedLocalToUtc(year, month, day, 0, 0, 0, timeZone);
  const end = zonedLocalToUtc(year, month, day, 23, 59, 59, timeZone);
  end.setMilliseconds(999);
  return { start, end };
};

export const addCalendarDays = (dateStr: CalendarDate, days: number): CalendarDate => {
  const [year, month, day] = dateStr.split("-").map((n) => Number(n));
  const d = new Date(year, month - 1, day + days);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${dd}`;
};

export const eachCalendarDay = (startStr: CalendarDate, endStr: CalendarDate): CalendarDate[] => {
  const days: CalendarDate[] = [];
  let cur = startStr;
  while (cur <= endStr) {
    days.push(cur);
    cur = addCalendarDays(cur, 1);
  }
  return days;
};
