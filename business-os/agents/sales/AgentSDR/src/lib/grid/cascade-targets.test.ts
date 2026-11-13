import { expect, test } from "bun:test";
import { cascadeTargets, changedCellUpdates, readyDependents, type CascadeColumn } from "./cascade-targets";

const formula = (key: string, dependsOn: string[], expression: string, autoRun = true): CascadeColumn => ({
  key,
  type: "formula",
  config: { expression },
  dependsOn,
  autoRun,
});
const ai = (key: string, dependsOn: string[], prompt: string, delaySeconds?: number): CascadeColumn => ({
  key,
  type: "ai",
  config: { prompt, delaySeconds } as unknown as CascadeColumn["config"],
  dependsOn,
  autoRun: true,
});

test("an edit queues every auto-run dependent of the changed column", () => {
  const columns = [formula("upper", ["name"], "UPPER({{name}})"), formula("manual", ["name"], "{{name}}", false)];
  expect(readyDependents(columns, "name", { name: "ada" }).map((c) => c.key)).toEqual(["upper"]);
});

test("a paid dependent waits until all its inputs have values", () => {
  const columns = [ai("intro", ["first", "last"], "Write to {{first}} {{last}}")];
  expect(readyDependents(columns, "first", { first: "Ada", last: "" })).toEqual([]);
  expect(readyDependents(columns, "first", { first: "Ada", last: "Lovelace" })).toHaveLength(1);
});

test("a formula recomputes on any change, even to blank", () => {
  const columns = [formula("full", ["first", "last"], "{{first}} {{last}}")];
  expect(readyDependents(columns, "last", { first: "Ada", last: "" })).toHaveLength(1);
  expect(readyDependents(columns, "first", {})).toHaveLength(1);
});

test("an AI column whose referenced inputs are all empty is not queued", () => {
  const columns = [ai("summary", ["bio"], "Summarise {{bio}}")];
  expect(readyDependents(columns, "bio", { bio: " " })).toEqual([]);
});

test("a batch yields one target per row and column, with the column's delay", () => {
  const columns = [ai("summary", ["bio", "role"], "{{bio}} {{role}}", 30), formula("n", ["bio"], "LEN({{bio}})")];
  const targets = cascadeTargets(columns, [
    { rowId: "r1", cells: { bio: "x", role: "y" }, changedKeys: ["bio", "role"] },
    { rowId: "r2", cells: { bio: "x", role: "" }, changedKeys: ["bio"] },
  ]);
  expect(targets).toEqual([
    { rowId: "r1", columnKey: "summary", delaySeconds: 30 },
    { rowId: "r1", columnKey: "n", delaySeconds: 0 },
    { rowId: "r2", columnKey: "n", delaySeconds: 0 },
  ]);
});

test("writing back the same value is not a change", () => {
  const previous = [
    { rowId: "r1", columnKey: "a", value: "x" },
    { rowId: "r2", columnKey: "a", value: null },
  ];
  const next = [
    { rowId: "r1", columnKey: "a", value: "x" },
    { rowId: "r2", columnKey: "a", value: "y" },
  ];
  expect(changedCellUpdates(previous, next)).toEqual([{ rowId: "r2", columnKey: "a", value: "y" }]);
  expect(changedCellUpdates([{ rowId: "r", columnKey: "a", value: undefined }], [{ rowId: "r", columnKey: "a", value: null }])).toEqual([]);
});
