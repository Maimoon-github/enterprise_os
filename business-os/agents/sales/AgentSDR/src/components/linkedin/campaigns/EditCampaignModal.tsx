"use client";

import { useState } from "react";
import { RiErrorWarningLine, RiLoader4Line, RiPencilLine, RiSaveLine } from "@remixicon/react";
import * as Button from "@/components/alignui/button";
import * as Checkbox from "@/components/alignui/checkbox";
import * as Input from "@/components/alignui/input";
import * as Modal from "@/components/alignui/modal";
import * as Textarea from "@/components/alignui/textarea";
import { LinkedInAccountTag } from "@/components/linkedin/LinkedInAccountTag";
import { cn } from "@/utils/cn";

export type SenderAccount = { id: string; username: string; name: string | null; profilePictureUrl: string | null };

export type EditableCampaign = {
  id: string;
  name: string;
  description: string | null;
  type?: "REGULAR" | "PERSONAL";
  accounts: SenderAccount[];
};

/**
 * Rename a campaign, change its description, and choose its senders. The
 * list page and the detail page share it; each applies `onSaved` to its own
 * copy. Campaign type is fixed after creation, so it is shown, not edited.
 */
export function EditCampaignModal({
  campaign,
  accounts,
  open,
  onOpenChange,
  onSaved,
}: {
  campaign: EditableCampaign | null;
  accounts: SenderAccount[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSaved: (updated: { name: string; description: string | null; accounts: SenderAccount[] }) => void;
}) {
  return (
    <Modal.Root open={open} onOpenChange={onOpenChange}>
      <Modal.Content size="max-w-lg">
        {campaign && (
          // Keyed so each open starts from the campaign's current values.
          <EditForm key={campaign.id} campaign={campaign} accounts={accounts} onCancel={() => onOpenChange(false)} onSaved={onSaved} />
        )}
      </Modal.Content>
    </Modal.Root>
  );
}

function EditForm({
  campaign,
  accounts,
  onCancel,
  onSaved,
}: {
  campaign: EditableCampaign;
  accounts: SenderAccount[];
  onCancel: () => void;
  onSaved: (updated: { name: string; description: string | null; accounts: SenderAccount[] }) => void;
}) {
  const [name, setName] = useState(campaign.name);
  const [description, setDescription] = useState(campaign.description ?? "");
  const [selectedIds, setSelectedIds] = useState<string[]>(campaign.accounts.map((a) => a.id));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save() {
    const trimmed = name.trim();
    if (!trimmed) { setError("Campaign name is required"); return; }
    setSaving(true);
    setError(null);
    try {
      const res = await fetch(`/api/linkedin/campaigns/${campaign.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: trimmed, description: description.trim() || null, linkedinAccountIds: selectedIds }),
      });
      const data = await res.json();
      if (!data.ok) { setError(data.error ?? "Failed"); return; }
      onSaved({
        name: trimmed,
        description: description.trim() || null,
        accounts: accounts.filter((a) => selectedIds.includes(a.id)),
      });
    } catch {
      setError("Network error");
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <Modal.Header icon={RiPencilLine}>
        <Modal.Title>Edit campaign</Modal.Title>
        <Modal.Description>
          {campaign.type
            ? `${campaign.type === "PERSONAL" ? "Personal" : "Regular"} campaign. The type can't be changed after creation.`
            : "Rename it, or change which accounts send."}
        </Modal.Description>
      </Modal.Header>
      <Modal.Body className="space-y-4">
        <label className="block">
          <span className="mb-1.5 block text-label-sm text-text-strong-950">Campaign name</span>
          <Input.Root hasError={Boolean(error && !name.trim())}>
            <Input.Wrapper>
              <Input.Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") void save(); }}
                placeholder="e.g. Q2 Tech Founders Outreach"
                autoFocus
              />
            </Input.Wrapper>
          </Input.Root>
        </label>
        <label className="block">
          <span className="mb-1.5 block text-label-sm text-text-strong-950">
            Description <span className="text-text-soft-400">(optional)</span>
          </span>
          <Textarea.Root simple rows={2} value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Optional notes about this campaign…" />
        </label>
        <div>
          <span className="mb-1.5 block text-label-sm text-text-strong-950">LinkedIn senders</span>
          {accounts.length === 0 ? (
            <p className="rounded-xl bg-bg-weak-50 p-3 text-paragraph-sm text-text-sub-600">No connected accounts.</p>
          ) : (
            <div className="max-h-48 space-y-1 overflow-y-auto rounded-xl p-1 ring-1 ring-inset ring-stroke-soft-200">
              {accounts.map((a) => {
                const checked = selectedIds.includes(a.id);
                return (
                  <label key={a.id} className={cn("flex cursor-pointer items-center gap-2.5 rounded-lg px-2 py-1.5 transition", checked ? "bg-bg-weak-50" : "hover:bg-bg-weak-50")}>
                    <Checkbox.Root
                      checked={checked}
                      onCheckedChange={() => setSelectedIds((prev) => (checked ? prev.filter((id) => id !== a.id) : [...prev, a.id]))}
                    />
                    <LinkedInAccountTag account={a} size="sm" />
                  </label>
                );
              })}
            </div>
          )}
        </div>
        {error && (
          <p role="alert" className="flex items-center gap-1.5 text-paragraph-sm text-error-base">
            <RiErrorWarningLine className="size-4 shrink-0" />{error}
          </p>
        )}
      </Modal.Body>
      <Modal.Footer>
        <Button.Root variant="neutral" mode="stroke" size="small" onClick={onCancel}>Cancel</Button.Root>
        <Button.Root variant="primary" mode="filled" size="small" onClick={() => void save()} disabled={saving}>
          <Button.Icon as={saving ? RiLoader4Line : RiSaveLine} className={cn(saving && "animate-spin")} />
          Save changes
        </Button.Root>
      </Modal.Footer>
    </>
  );
}
