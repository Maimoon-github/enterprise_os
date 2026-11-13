import * as Badge from "@/components/alignui/badge";
import type { CallStatus } from "@/lib/calls/contract";
import { CALL_STATUS_LABEL, CALL_STATUS_TONE } from "./callStatus";

const COLOR = { neutral: "gray", success: "green", info: "blue", danger: "red", warning: "orange" } as const;

/** One call's status ("Recorded", "Not connected") as a dot badge; the label carries the meaning. */
export function CallSessionBadge({ status }: { status: CallStatus }) {
  return (
    <Badge.Root variant="lighter" size="medium" color={COLOR[CALL_STATUS_TONE[status]]} className="shrink-0 whitespace-nowrap">
      <Badge.Dot />
      {CALL_STATUS_LABEL[status]}
    </Badge.Root>
  );
}
