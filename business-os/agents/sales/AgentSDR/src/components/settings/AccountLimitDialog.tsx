"use client";

import { useState } from "react";
import { RiDashboard3Line, RiLoader4Line } from "@remixicon/react";
import * as Button from "@/components/alignui/button";
import * as Input from "@/components/alignui/input";
import * as Modal from "@/components/alignui/modal";
import { Callout, Field } from "@/components/settings/SettingsKit";
import { ruleError, ruleWarning, type NumberRule } from "@/lib/channels/rules";

/**
 * One account's override of an organization rule (a LinkedIn account's
 * invitations a day, a WhatsApp number's new chats a day). Empty means
 * "follow the organization", so a later change there reaches this account.
 * Bounded by the same hard ceilings, and warned past the same safe edge.
 */
export function AccountLimitDialog({
  title,
  accountLabel,
  rule,
  organizationValue,
  value,
  onClose,
  onSave,
}: {
  title: string;
  accountLabel: string;
  rule: NumberRule;
  organizationValue: number;
  value: number | null;
  onClose: () => void;
  onSave: (value: number | null) => Promise<void>;
}) {
  const [text, setText] = useState(value === null ? "" : String(value));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const parsed = text.trim() === "" ? null : Number(text);
  const invalid = parsed === null ? null : ruleError(rule, parsed);
  const warning = parsed === null || invalid ? null : ruleWarning(rule, parsed);
  const id = `limit-${rule.key}`;

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      await onSave(parsed);
      onClose();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not save the limit.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal.Root open onOpenChange={(open) => !open && onClose()}>
      <Modal.Content size="max-w-md">
        <Modal.Header icon={RiDashboard3Line}>
          <Modal.Title>{title}</Modal.Title>
          <Modal.Description>For {accountLabel}. Leave it empty to follow the organization&apos;s sending rules.</Modal.Description>
        </Modal.Header>
        <Modal.Body className="space-y-4">
          <Field label={rule.label} htmlFor={id} error={invalid ?? undefined} description={`Organization: ${organizationValue} ${rule.unit}. Allowed: ${rule.min}–${rule.max}.`}>
            <div className="flex items-center gap-2">
              <Input.Root size="small" className="w-28" hasError={Boolean(invalid)}>
                <Input.Wrapper>
                  <Input.Input
                    id={id}
                    type="number"
                    inputMode="numeric"
                    placeholder={String(organizationValue)}
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    className="tabular-nums"
                  />
                </Input.Wrapper>
              </Input.Root>
              <span className="text-paragraph-xs text-text-sub-600">{rule.unit}</span>
            </div>
          </Field>
          {warning && <Callout tone="warning">{warning}</Callout>}
          {error && <Callout tone="error">{error}</Callout>}
        </Modal.Body>
        <Modal.Footer>
          {value !== null && (
            <Button.Root variant="neutral" mode="ghost" size="small" className="mr-auto" disabled={saving} onClick={() => setText("")}>
              Use organization limit
            </Button.Root>
          )}
          <Button.Root variant="neutral" mode="stroke" size="small" onClick={onClose}>
            Cancel
          </Button.Root>
          <Button.Root variant="primary" mode="filled" size="small" onClick={() => void save()} disabled={saving || Boolean(invalid)}>
            {saving && <Button.Icon as={RiLoader4Line} className="animate-spin" />}
            {saving ? "Saving…" : "Save limit"}
          </Button.Root>
        </Modal.Footer>
      </Modal.Content>
    </Modal.Root>
  );
}
