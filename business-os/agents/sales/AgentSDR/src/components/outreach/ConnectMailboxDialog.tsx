"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { RiCheckLine, RiLoader4Line, RiMailAddLine } from "@remixicon/react";

import * as Button from "@/components/alignui/button";
import * as Input from "@/components/alignui/input";
import * as Modal from "@/components/alignui/modal";
import * as Textarea from "@/components/alignui/textarea";
import { DocsLink } from "@/components/page/DocsLink";
import { Callout, Field } from "@/components/settings/SettingsKit";

type Stage = "form" | "testing" | "success" | "failed";

/**
 * Adds a mailbox and tests it in one step. An AlignUI (Radix) modal, so it
 * stacks correctly over the Settings pop-up: focus, Escape and outside-click
 * all belong to the top dialog.
 */
export default function ConnectMailboxDialog({ onClose }: { onClose: () => void }) {
  const router = useRouter();
  const [emailAddress, setEmailAddress] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [signatureHtml, setSignatureHtml] = useState("");
  const [stage, setStage] = useState<Stage>("form");
  const [error, setError] = useState<string | null>(null);

  async function handleConnect(e: React.FormEvent) {
    e.preventDefault();
    setStage("testing");
    setError(null);
    try {
      const res = await fetch("/api/outreach/mailboxes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          emailAddress,
          displayName: displayName || undefined,
          signatureHtml: signatureHtml || undefined,
        }),
      });
      const data = await res.json();
      if (!res.ok || data.ok === false) {
        setError(data.error ?? "Failed to connect mailbox");
        setStage("failed");
        return;
      }
      setStage("success");
      router.refresh();
    } catch {
      setError("Network error — please try again");
      setStage("failed");
    }
  }

  const testing = stage === "testing";

  return (
    <Modal.Root open onOpenChange={(open) => { if (!open && !testing) onClose(); }}>
      <Modal.Content size="max-w-lg" hideClose={testing} onEscapeKeyDown={(event) => testing && event.preventDefault()}>
        <Modal.Header icon={RiMailAddLine}>
          <Modal.Title>Add a mailbox</Modal.Title>
          <Modal.Description>A Google Workspace address already authorised for sending. It is tested before it is saved.</Modal.Description>
          <DocsLink page="email/connect#add-a-mailbox" appearance="inline" className="mt-1.5 text-paragraph-xs" />
        </Modal.Header>

        {(stage === "form" || stage === "failed") && (
          <form onSubmit={handleConnect} className="flex min-h-0 flex-col">
            <Modal.Body className="space-y-4">
              <Field
                label="Email address"
                htmlFor="mailbox-email"
                required
                description="Must be authorised for our app's client ID in the Workspace admin console (domain-wide delegation)."
              >
                <Input.Root size="medium">
                  <Input.Wrapper>
                    <Input.Input
                      id="mailbox-email"
                      type="email"
                      required
                      autoFocus
                      value={emailAddress}
                      onChange={(e) => setEmailAddress(e.target.value)}
                      placeholder="rep@yourcompany.com"
                    />
                  </Input.Wrapper>
                </Input.Root>
              </Field>

              <Field label="Display name" htmlFor="mailbox-name" optional description="The name recipients see beside the address.">
                <Input.Root size="medium">
                  <Input.Wrapper>
                    <Input.Input
                      id="mailbox-name"
                      type="text"
                      value={displayName}
                      onChange={(e) => setDisplayName(e.target.value)}
                      placeholder="Jane from Acme"
                    />
                  </Input.Wrapper>
                </Input.Root>
              </Field>

              <Field
                label="Signature"
                htmlFor="mailbox-signature"
                optional
                description="Appended to every send from this mailbox. You can change it later from the mailbox's Signature action."
              >
                <Textarea.Root
                  id="mailbox-signature"
                  simple
                  value={signatureHtml}
                  onChange={(e) => setSignatureHtml(e.target.value)}
                  placeholder={"Jane Doe\nHead of Sales, Acme Inc."}
                  rows={4}
                />
              </Field>

              {stage === "failed" && error && (
                <Callout tone="error" title="The connection test failed">
                  {error}
                </Callout>
              )}
            </Modal.Body>

            <Modal.Footer>
              <Button.Root type="button" variant="neutral" mode="stroke" size="small" onClick={onClose}>
                Cancel
              </Button.Root>
              <Button.Root type="submit" variant="primary" mode="filled" size="small" disabled={!emailAddress}>
                {stage === "failed" ? "Try again" : "Connect & test"}
              </Button.Root>
            </Modal.Footer>
          </form>
        )}

        {testing && (
          <Modal.Body>
            <div role="status" className="flex flex-col items-center justify-center gap-3 py-10 text-center">
              <RiLoader4Line className="size-6 animate-spin text-text-sub-600" aria-hidden="true" />
              <p className="text-paragraph-sm text-text-sub-600">Testing the connection to {emailAddress}…</p>
            </div>
          </Modal.Body>
        )}

        {stage === "success" && (
          <>
            <Modal.Body>
              <div role="status" className="flex flex-col items-center justify-center gap-3 py-6 text-center">
                <span className="flex size-12 items-center justify-center rounded-full bg-success-lighter">
                  <RiCheckLine className="size-6 text-success-base" aria-hidden="true" />
                </span>
                <div>
                  <p className="text-label-sm text-text-strong-950">Mailbox connected</p>
                  <p className="mt-0.5 text-paragraph-sm text-text-sub-600">{emailAddress} is ready to send.</p>
                </div>
              </div>
            </Modal.Body>
            <Modal.Footer>
              <Button.Root variant="primary" mode="filled" size="small" onClick={onClose}>
                Done
              </Button.Root>
            </Modal.Footer>
          </>
        )}
      </Modal.Content>
    </Modal.Root>
  );
}
