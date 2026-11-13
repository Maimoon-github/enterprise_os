/**
 * What a person has to do about a record in the Action required queue, in the
 * five groups the queue filters by. Each row still names its exact action
 * ("Follow-up review", "Due follow-up", …); the filter used to list all nine
 * of those, several of which never occur or repeat another filter.
 *
 * Client-safe: the SQL that assigns a record its group is the `.server`
 * sibling, so a client component can import the labels.
 */
export const CRM_ACTION_GROUPS = ["reply", "follow_up", "classification", "next_step", "problem"] as const;

export type CrmActionGroup = typeof CRM_ACTION_GROUPS[number];

export const CRM_ACTION_GROUP_LABELS: Readonly<Record<CrmActionGroup, string>> = {
  reply: "Immediate reply",
  follow_up: "Follow-up due",
  classification: "Confirm classification",
  next_step: "Needs a next step",
  problem: "Error or failed",
};

export function isCrmActionGroup(value: string): value is CrmActionGroup {
  return (CRM_ACTION_GROUPS as readonly string[]).includes(value);
}
