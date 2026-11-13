"use client";

import { useEffect, useMemo, useState } from "react";
import { RiCheckLine, RiFolder3Line, RiFolderTransferLine, RiHome4Line, RiLoader4Line } from "@remixicon/react";
import * as Button from "@/components/alignui/button";
import * as Modal from "@/components/alignui/modal";
import type { GridFolder } from "@/lib/grid/schema";

/** Root-first path for a folder, used to render the flat list as a tree. */
function pathOf(folder: GridFolder, byId: Map<string, GridFolder>): GridFolder[] {
  const trail: GridFolder[] = [];
  const guard = new Set<string>();
  let current: GridFolder | undefined = folder;
  while (current && !guard.has(current.id)) {
    guard.add(current.id);
    trail.unshift(current);
    current = current.parentId ? byId.get(current.parentId) : undefined;
  }
  return trail;
}

export default function MoveToFolderDialog({
  open,
  title,
  itemName,
  currentFolderId,
  folders,
  /** Folders that cannot receive the item — a folder's own subtree. */
  excludeIds = [],
  onClose,
  onMove,
}: {
  open: boolean;
  title: string;
  itemName: string;
  currentFolderId: string | null;
  folders: GridFolder[];
  excludeIds?: string[];
  onClose: () => void;
  onMove: (folderId: string | null) => Promise<void> | void;
}) {
  const [selected, setSelected] = useState<string | null>(currentFolderId);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- intentional: effect resets/seeds local state when props or open state change; deriving during render would change timing
    setSelected(currentFolderId);
    setError(null);
    setBusy(false);
  }, [open, currentFolderId]);

  const options = useMemo(() => {
    const byId = new Map(folders.map((f) => [f.id, f]));
    const blocked = new Set(excludeIds);
    return folders
      .filter((f) => !blocked.has(f.id))
      .map((f) => ({ folder: f, trail: pathOf(f, byId) }))
      // Sort by full path so children sit directly under their parent.
      .sort((a, b) =>
        a.trail.map((t) => t.name.toLowerCase()).join("/") <
        b.trail.map((t) => t.name.toLowerCase()).join("/")
          ? -1
          : 1,
      );
  }, [folders, excludeIds]);

  async function submit() {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await onMove(selected);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not move that item");
      setBusy(false);
    }
  }

  return (
    <Modal.Root open={open} onOpenChange={(next) => { if (!next && !busy) onClose(); }}>
      <Modal.Content size="max-w-md" className="max-h-[80vh]">
        <Modal.Header icon={RiFolderTransferLine}>
          <Modal.Title>{title}</Modal.Title>
          <Modal.Description>Choose a destination for “{itemName}”.</Modal.Description>
        </Modal.Header>

        <Modal.Body className="pt-4">
          <button
            type="button"
            onClick={() => setSelected(null)}
            className={`flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left text-paragraph-sm transition ${
              selected === null
                ? "bg-primary-alpha-10 text-primary-base"
                : "text-text-strong-950 hover:bg-bg-weak-50"
            }`}
          >
            <RiHome4Line className="size-4 shrink-0 text-text-soft-400" />
            <span className="flex-1 truncate font-medium">All Files</span>
            {selected === null && <RiCheckLine className="size-4 shrink-0" />}
          </button>

          {options.map(({ folder, trail }) => (
            <button
              key={folder.id}
              type="button"
              onClick={() => setSelected(folder.id)}
              style={{ paddingLeft: 8 + (trail.length - 1) * 16 }}
              className={`flex w-full items-center gap-2 rounded-lg py-2 pr-2 text-left text-paragraph-sm transition ${
                selected === folder.id
                  ? "bg-primary-alpha-10 text-primary-base"
                  : "text-text-strong-950 hover:bg-bg-weak-50"
              }`}
            >
              <RiFolder3Line className="size-4 shrink-0 text-warning-base" />
              <span className="flex-1 truncate">{folder.name}</span>
              {selected === folder.id && <RiCheckLine className="size-4 shrink-0" />}
            </button>
          ))}

          {!options.length && (
            <p className="px-2 py-6 text-center text-paragraph-sm text-text-sub-600">
              No folders yet — use New &gt; Folder to create one.
            </p>
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
            disabled={busy || selected === currentFolderId}
            onClick={() => void submit()}
          >
            {busy && <RiLoader4Line className="size-4 animate-spin" />}
            Move
          </Button.Root>
        </Modal.Footer>
      </Modal.Content>
    </Modal.Root>
  );
}
