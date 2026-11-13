"use client";

import { useState } from "react";
import { RiStickyNoteLine, RiTaskLine } from "@remixicon/react";
import * as Button from "@/components/alignui/button";
import * as Input from "@/components/alignui/input";
import * as Modal from "@/components/alignui/modal";
import * as Textarea from "@/components/alignui/textarea";

/** "+ Task" / "+ Note" from an open thread: creates one tied to that lead. */
export default function QuickCreateModal({
  type,
  leadId,
  leadName,
  onClose,
  onCreated,
}: {
  type: "task" | "note";
  leadId: string;
  /** Who it is for, shown in the description. */
  leadName?: string;
  onClose: () => void;
  onCreated: () => void;
}) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [saving, setSaving] = useState(false);
  const isTask = type === "task";

  async function handleSave() {
    if (!name.trim()) return;
    setSaving(true);
    try {
      const endpoint = isTask ? "/api/outreach/inbox/tasks" : "/api/outreach/inbox/notes";
      await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(isTask ? { name, description, leadId } : { title: name, description, leadId }),
      });
      onCreated();
      onClose();
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal.Root open onOpenChange={(open) => !open && onClose()}>
      <Modal.Content>
        <Modal.Header icon={isTask ? RiTaskLine : RiStickyNoteLine}>
          <Modal.Title>{isTask ? "New task" : "New note"}</Modal.Title>
          <Modal.Description>
            {leadName ? `For ${leadName}. ` : ""}
            {isTask ? "It shows up under Tasks." : "It shows up under Notes."}
          </Modal.Description>
        </Modal.Header>
        <form
          className="contents"
          onSubmit={(e) => {
            e.preventDefault();
            void handleSave();
          }}
        >
          <Modal.Body className="space-y-3">
            <Input.Root>
              <Input.Wrapper>
                <Input.Input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder={isTask ? "Task name" : "Note title"}
                  aria-label={isTask ? "Task name" : "Note title"}
                  autoFocus
                />
              </Input.Wrapper>
            </Input.Root>
            <Textarea.Root simple rows={4} value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Description…" aria-label="Description" />
          </Modal.Body>
          <Modal.Footer>
            <Button.Root type="button" variant="neutral" mode="stroke" size="small" onClick={onClose}>
              Cancel
            </Button.Root>
            <Button.Root type="submit" variant="primary" mode="filled" size="small" disabled={saving || !name.trim()}>
              {saving ? "Saving…" : isTask ? "Create task" : "Create note"}
            </Button.Root>
          </Modal.Footer>
        </form>
      </Modal.Content>
    </Modal.Root>
  );
}
