"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  RiArrowRightSLine,
  RiCheckLine,
  RiDragMove2Line,
  RiFolder3Line,
  RiHome4Line,
  RiLoader4Line,
} from "@remixicon/react";
import * as Button from "@/components/alignui/button";
import * as Modal from "@/components/alignui/modal";
import type { GridFolder } from "@/lib/grid/schema";
import WorkbookIcon from "./WorkbookIcon";

type WorkbookRow = { id: string; name: string; folderId: string | null };

/**
 * Picks a destination workbook for a table, browsing the same folder tree the
 * All Files screen shows.
 *
 * Folders are containers here, not targets — a table lives in a workbook, so
 * a folder can only be expanded, never selected.
 */
export default function MoveTableDialog({
  open,
  tableName,
  currentWorkbookId,
  /** Disables every destination and explains why, e.g. the last table left. */
  blockedReason,
  onClose,
  onMove,
}: {
  open: boolean;
  tableName: string;
  currentWorkbookId: string;
  blockedReason?: string | null;
  onClose: () => void;
  onMove: (workbookId: string) => Promise<void>;
}) {
  const [loading, setLoading] = useState(false);
  const [folders, setFolders] = useState<GridFolder[]>([]);
  const [workbooks, setWorkbooks] = useState<WorkbookRow[]>([]);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [selected, setSelected] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [folderRes, workbookRes] = await Promise.all([
        fetch("/api/grid/folders"),
        fetch("/api/grid/workbooks"),
      ]);
      if (!folderRes.ok || !workbookRes.ok) throw new Error("Could not load your workbooks");
      const nextFolders: GridFolder[] = (await folderRes.json()).folders ?? [];
      const nextWorkbooks: WorkbookRow[] = (await workbookRes.json()).workbooks ?? [];
      setFolders(nextFolders);
      setWorkbooks(nextWorkbooks);

      // Open the branch holding the table's current workbook, so the user can
      // see where it is now without hunting for it.
      const home = nextWorkbooks.find((w) => w.id === currentWorkbookId);
      if (home?.folderId) {
        const byId = new Map(nextFolders.map((f) => [f.id, f]));
        const trail = new Set<string>();
        let cursor = byId.get(home.folderId);
        while (cursor && !trail.has(cursor.id)) {
          trail.add(cursor.id);
          cursor = cursor.parentId ? byId.get(cursor.parentId) : undefined;
        }
        setExpanded(trail);
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load your workbooks");
    } finally {
      setLoading(false);
    }
  }, [currentWorkbookId]);

  useEffect(() => {
    if (!open) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- intentional: effect resets/seeds local state when props or open state change; deriving during render would change timing
    setSelected(null);
    setBusy(false);
    void load();
  }, [open, load]);

  const childFolders = useMemo(() => {
    const map = new Map<string, GridFolder[]>();
    for (const folder of folders) {
      const key = folder.parentId ?? "root";
      map.set(key, [...(map.get(key) ?? []), folder]);
    }
    for (const list of map.values()) list.sort((a, b) => a.name.localeCompare(b.name));
    return map;
  }, [folders]);

  const childWorkbooks = useMemo(() => {
    const map = new Map<string, WorkbookRow[]>();
    for (const workbook of workbooks) {
      const key = workbook.folderId ?? "root";
      map.set(key, [...(map.get(key) ?? []), workbook]);
    }
    for (const list of map.values()) list.sort((a, b) => a.name.localeCompare(b.name));
    return map;
  }, [workbooks]);

  function toggle(id: string) {
    setExpanded((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function renderBranch(key: string, depth: number): React.ReactNode {
    return (
      <>
        {(childFolders.get(key) ?? []).map((folder) => (
          <div key={folder.id}>
            <button
              type="button"
              onClick={() => toggle(folder.id)}
              style={{ paddingLeft: 8 + depth * 16 }}
              className="flex w-full items-center gap-1.5 rounded-lg py-2 pr-2 text-left text-paragraph-sm text-text-strong-950 transition hover:bg-bg-weak-50"
            >
              <RiArrowRightSLine className={`size-4 shrink-0 text-text-soft-400 transition ${expanded.has(folder.id) ? "rotate-90" : ""}`} />
              <RiFolder3Line className="size-4 shrink-0 text-warning-base" />
              <span className="flex-1 truncate">{folder.name}</span>
            </button>
            {expanded.has(folder.id) && renderBranch(folder.id, depth + 1)}
          </div>
        ))}

        {(childWorkbooks.get(key) ?? []).map((workbook) => {
          const isCurrent = workbook.id === currentWorkbookId;
          const isSelected = workbook.id === selected;
          return (
            <button
              key={workbook.id}
              type="button"
              disabled={isCurrent || Boolean(blockedReason)}
              onClick={() => setSelected(workbook.id)}
              style={{ paddingLeft: 8 + depth * 16 + 22 }}
              className={`flex w-full items-center gap-2 rounded-lg py-2 pr-2 text-left text-paragraph-sm transition disabled:cursor-not-allowed disabled:opacity-45 ${
                isSelected
                  ? "bg-primary-alpha-10 text-primary-base"
                  : "text-text-strong-950 hover:bg-bg-weak-50 disabled:hover:bg-transparent"
              }`}
            >
              <WorkbookIcon className="size-4 shrink-0" />
              <span className="flex-1 truncate">{workbook.name}</span>
              {isCurrent && <span className="shrink-0 text-subheading-2xs uppercase text-text-soft-400">Current</span>}
              {isSelected && <RiCheckLine className="size-4 shrink-0" />}
            </button>
          );
        })}
      </>
    );
  }

  async function submit() {
    if (!selected || busy) return;
    setBusy(true);
    setError(null);
    try {
      await onMove(selected);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not move that table");
      setBusy(false);
    }
  }

  return (
    <Modal.Root open={open} onOpenChange={(next) => { if (!next && !busy) onClose(); }}>
      <Modal.Content size="max-w-md" className="max-h-[80vh]">
        <Modal.Header icon={RiDragMove2Line}>
          <Modal.Title>Move table</Modal.Title>
          <Modal.Description>Choose the workbook to move “{tableName}” into.</Modal.Description>
        </Modal.Header>

        <Modal.Body className="pt-4">
          {blockedReason && (
            <p className="mb-3 rounded-lg bg-warning-lighter px-3 py-2 text-paragraph-sm text-warning-dark">
              {blockedReason}
            </p>
          )}

          {loading ? (
            <p className="flex items-center justify-center gap-2 py-10 text-paragraph-sm text-text-sub-600">
              <RiLoader4Line className="size-4 animate-spin" />Loading workbooks…
            </p>
          ) : (
            <>
              <div className="flex items-center gap-1.5 px-2 py-2 text-subheading-2xs uppercase tracking-wide text-text-soft-400">
                <RiHome4Line className="size-4" />All Files
              </div>
              {renderBranch("root", 0)}
              {!folders.length && !workbooks.length && (
                <p className="px-2 py-6 text-center text-paragraph-sm text-text-sub-600">
                  No other workbooks yet.
                </p>
              )}
            </>
          )}

          {error && (
            <p className="mt-3 rounded-lg bg-red-alpha-10 px-3 py-2 text-paragraph-sm text-error-base">{error}</p>
          )}
        </Modal.Body>

        <Modal.Footer>
          <Button.Root variant="neutral" mode="stroke" size="small" disabled={busy} onClick={onClose}>
            Cancel
          </Button.Root>
          <Button.Root
            variant="primary"
            mode="filled"
            size="small"
            disabled={busy || !selected}
            onClick={() => void submit()}
          >
            {busy && <RiLoader4Line className="size-4 animate-spin" />}
            Move table
          </Button.Root>
        </Modal.Footer>
      </Modal.Content>
    </Modal.Root>
  );
}
