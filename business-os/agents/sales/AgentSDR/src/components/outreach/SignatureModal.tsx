"use client";

import { useState } from "react";
import { RiPenNibLine } from "@remixicon/react";

import * as Button from "@/components/alignui/button";
import * as Modal from "@/components/alignui/modal";
import * as Textarea from "@/components/alignui/textarea";
import { Callout, Field } from "@/components/settings/SettingsKit";

export default function SignatureModal({
  mailboxId,
  mailboxAddress,
  initial,
  onClose,
  onSaved,
}: {
  mailboxId: string;
  mailboxAddress?: string;
  initial: string | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [value, setValue] = useState(initial ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSave() {
    setSaving(true);
    setError(null);
    try {
      const res = await fetch(`/api/outreach/mailboxes/${mailboxId}/signature`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ signatureHtml: value }),
      });
      if (!res.ok) {
        setError("The signature was not saved. Please try again.");
        return;
      }
      onSaved();
      onClose();
    } catch {
      setError("Could not reach the server. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal.Root open onOpenChange={(open) => !open && onClose()}>
      <Modal.Content size="max-w-lg">
        <Modal.Header icon={RiPenNibLine}>
          <Modal.Title>Signature</Modal.Title>
          <Modal.Description>{mailboxAddress ? `For ${mailboxAddress}.` : "For this mailbox."}</Modal.Description>
        </Modal.Header>
        <Modal.Body className="space-y-4">
          <Field
            label="Signature"
            htmlFor={`signature-${mailboxId}`}
            description={
              <>
                Appended to every send from this mailbox. Put <code className="rounded bg-bg-weak-50 px-1 font-mono text-text-strong-950">%signature%</code> in a sequence step to place it exactly where you want instead.
              </>
            }
          >
            <Textarea.Root
              id={`signature-${mailboxId}`}
              simple
              autoFocus
              value={value}
              onChange={(e) => setValue(e.target.value)}
              placeholder={"Jane Doe\nHead of Sales, Acme Inc."}
              rows={6}
            />
          </Field>
          {error && <Callout tone="error">{error}</Callout>}
        </Modal.Body>
        <Modal.Footer>
          <Button.Root variant="neutral" mode="stroke" size="small" onClick={onClose}>
            Cancel
          </Button.Root>
          <Button.Root variant="primary" mode="filled" size="small" disabled={saving} onClick={handleSave}>
            {saving ? "Saving…" : "Save signature"}
          </Button.Root>
        </Modal.Footer>
      </Modal.Content>
    </Modal.Root>
  );
}
