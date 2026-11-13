/** 0 = Sunday … 6 = Saturday (matches JavaScript Date.getDay() in local parsing; we use Intl weekday) */
export const WEEKDAY_LABELS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"] as const;

export type WorkingHoursFields = {
  workTimezone: string | null;
  workStartTime: string | null;
  workEndTime: string | null;
  workDays: string | null;
};

const WEEKDAY_FROM_SHORT: Record<string, number> = {
  Sun: 0,
  Mon: 1,
  Tue: 2,
  Wed: 3,
  Thu: 4,
  Fri: 5,
  Sat: 6,
};

/** Mon–Sat (1–6), 9:00–18:00 India (IST) */
export const DEFAULT_WORK_TIMEZONE = "Asia/Kolkata";
export const DEFAULT_WORK_DAYS = "1,2,3,4,5,6";
export const DEFAULT_WORK_START = "09:00";
export const DEFAULT_WORK_END = "18:00";

export const hasWorkingHoursConfigured = (account: WorkingHoursFields): boolean =>
  !!account.workTimezone && !!account.workStartTime && !!account.workEndTime;

export const parseWorkDays = (workDays: string | null | undefined): number[] => {
  const raw = workDays?.trim() || DEFAULT_WORK_DAYS;
  const days = raw
    .split(",")
    .map((d) => Number(d.trim()))
    .filter((d) => d >= 0 && d <= 6);
  return days.length > 0 ? days : [1, 2, 3, 4, 5, 6];
};

export const parseHHmmToMinutes = (value: string): number => {
  const [h, m] = value.split(":").map((part) => Number(part));
  if (!Number.isFinite(h) || !Number.isFinite(m)) return 0;
  return h * 60 + m;
};

const getZonedTimeInfo = (date: Date, timeZone: string) => {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone,
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    weekday: "short",
  }).formatToParts(date);

  const hour = Number(parts.find((p) => p.type === "hour")?.value ?? 0);
  const minute = Number(parts.find((p) => p.type === "minute")?.value ?? 0);
  const weekday = parts.find((p) => p.type === "weekday")?.value ?? "Mon";

  return {
    day: WEEKDAY_FROM_SHORT[weekday] ?? 1,
    minutes: hour * 60 + minute,
  };
};

/** Returns true when no working-hours window is configured, or `at` falls inside the window. */
export const isWithinWorkingHours = (
  account: WorkingHoursFields,
  at: Date = new Date()
): boolean => {
  if (!hasWorkingHoursConfigured(account)) return true;

  const timeZone = account.workTimezone!;
  const startM = parseHHmmToMinutes(account.workStartTime ?? DEFAULT_WORK_START);
  const endM = parseHHmmToMinutes(account.workEndTime ?? DEFAULT_WORK_END);
  const allowedDays = parseWorkDays(account.workDays);

  const { day, minutes } = getZonedTimeInfo(at, timeZone);
  if (!allowedDays.includes(day)) return false;

  if (startM === endM) return true;
  if (startM < endM) return minutes >= startM && minutes < endM;
  return minutes >= startM || minutes < endM;
};

/**
 * The hours an account runs in: its own when it has them, otherwise the
 * organization's (Settings → LinkedIn → Sending rules), otherwise any time.
 */
export const withOrganizationHours = (
  account: WorkingHoursFields,
  organization: { timezone: string; days: number[]; start: string; end: string } | null,
): WorkingHoursFields => {
  if (hasWorkingHoursConfigured(account) || !organization) return account;
  return {
    workTimezone: organization.timezone,
    workStartTime: organization.start,
    workEndTime: organization.end,
    workDays: organization.days.join(","),
  };
};

export const formatWorkingHoursSummary = (account: WorkingHoursFields): string => {
  if (!hasWorkingHoursConfigured(account)) return "24/7 (no restriction)";

  const days = parseWorkDays(account.workDays)
    .sort((a, b) => a - b)
    .map((d) => WEEKDAY_LABELS[d])
    .join(", ");

  return `${days} ${account.workStartTime}–${account.workEndTime} (${account.workTimezone})`;
};
