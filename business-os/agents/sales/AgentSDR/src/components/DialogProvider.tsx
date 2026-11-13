"use client";

import * as React from "react";
import { RiAlertLine, RiErrorWarningLine, RiInformationLine, RiLoader4Line } from "@remixicon/react";

import * as Button from "@/components/alignui/button";
import * as Input from "@/components/alignui/input";
import * as Modal from "@/components/alignui/modal";

/**
 * Promise-based replacements for window.alert / confirm / prompt.
 *
 * Deliberately imperative. Nearly every call site is mid-flow inside an async
 * handler — `if (!window.confirm(...)) return;` — and converting each of those
 * into open/onConfirm state would turn a one-line guard into a state machine
 * per handler. An awaited promise keeps the control flow exactly as it reads,
 * while the thing on screen is ours rather than Chrome's.
 */
export type ConfirmOptions = {
  title: string;
  description?: React.ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  /** "error" for anything destructive — red button, warning icon. */
  variant?: "primary" | "error";
};

export type AlertOptions = {
  title: string;
  description?: React.ReactNode;
  closeLabel?: string;
  variant?: "info" | "error";
};

export type PromptOptions = {
  title: string;
  description?: React.ReactNode;
  label?: string;
  defaultValue?: string;
  placeholder?: string;
  confirmLabel?: string;
  /** Allows submitting an empty string — used for clearing a description. */
  allowEmpty?: boolean;
};

type Request =
  | { kind: "confirm"; options: ConfirmOptions; resolve: (v: boolean) => void }
  | { kind: "alert"; options: AlertOptions; resolve: (v: void) => void }
  | { kind: "prompt"; options: PromptOptions; resolve: (v: string | null) => void };

type DialogApi = {
  confirm: (options: ConfirmOptions) => Promise<boolean>;
  alert: (options: AlertOptions) => Promise<void>;
  prompt: (options: PromptOptions) => Promise<string | null>;
};

const DialogContext = React.createContext<DialogApi | null>(null);

export function useDialogs(): DialogApi {
  const api = React.useContext(DialogContext);
  if (!api) throw new Error("useDialogs must be used inside <DialogProvider>");
  return api;
}

export default function DialogProvider({ children }: { children: React.ReactNode }) {
  const [request, setRequest] = React.useState<Request | null>(null);
  const [value, setValue] = React.useState("");

  const api = React.useMemo<DialogApi>(
    () => ({
      confirm: (options) =>
        new Promise<boolean>((resolve) => setRequest({ kind: "confirm", options, resolve })),
      alert: (options) =>
        new Promise<void>((resolve) => setRequest({ kind: "alert", options, resolve })),
      prompt: (options) =>
        new Promise<string | null>((resolve) => {
          setValue(options.defaultValue ?? "");
          setRequest({ kind: "prompt", options, resolve });
        }),
    }),
    [],
  );

  /**
   * Settles the open request and clears it.
   *
   * Every exit path routes through here — the buttons, Escape, the overlay,
   * the corner X. A dismissal that failed to resolve would leave the caller's
   * await hanging forever, which is the one way this can be worse than the
   * native dialogs it replaces.
   */
  const settle = React.useCallback(
    (outcome: "confirm" | "dismiss") => {
      setRequest((current) => {
        if (!current) return null;
        if (current.kind === "confirm") current.resolve(outcome === "confirm");
        else if (current.kind === "alert") current.resolve();
        else current.resolve(outcome === "confirm" ? value : null);
        return null;
      });
    },
    [value],
  );

  const options = request?.options;
  const isDestructive =
    request?.kind === "confirm" && request.options.variant === "error";
  const isErrorAlert = request?.kind === "alert" && request.options.variant === "error";

  const submitDisabled =
    request?.kind === "prompt" && !request.options.allowEmpty && !value.trim();

  return (
    <DialogContext.Provider value={api}>
      {children}

      <Modal.Root
        open={request !== null}
        onOpenChange={(open) => {
          if (!open) settle("dismiss");
        }}
      >
        {request && options && (
          <Modal.Content size="max-w-[420px]">
            <Modal.Header
              icon={
                isDestructive || isErrorAlert
                  ? isDestructive
                    ? RiAlertLine
                    : RiErrorWarningLine
                  : request.kind === "alert"
                    ? RiInformationLine
                    : undefined
              }
            >
              <Modal.Title>{options.title}</Modal.Title>
              {options.description && <Modal.Description>{options.description}</Modal.Description>}
            </Modal.Header>

            {request.kind === "prompt" && (
              <div className="px-5 pt-4">
                {request.options.label && (
                  <label
                    htmlFor="dialog-prompt-input"
                    className="mb-1.5 block text-subheading-2xs uppercase tracking-wide text-text-soft-400"
                  >
                    {request.options.label}
                  </label>
                )}
                <Input.Root size="medium">
                  <Input.Wrapper>
                    <Input.Input
                      id="dialog-prompt-input"
                      autoFocus
                      value={value}
                      placeholder={request.options.placeholder}
                      onChange={(event) => setValue(event.target.value)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" && !submitDisabled) {
                          event.preventDefault();
                          settle("confirm");
                        }
                      }}
                    />
                  </Input.Wrapper>
                </Input.Root>
              </div>
            )}

            <Modal.Footer className="mt-5 border-t-0 pt-0">
              {request.kind !== "alert" && (
                <Button.Root
                  variant="neutral"
                  mode="stroke"
                  size="small"
                  onClick={() => settle("dismiss")}
                >
                  {request.kind === "confirm"
                    ? (request.options.cancelLabel ?? "Cancel")
                    : "Cancel"}
                </Button.Root>
              )}
              <Button.Root
                variant={isDestructive ? "error" : "primary"}
                mode="filled"
                size="small"
                autoFocus={request.kind !== "prompt"}
                disabled={submitDisabled}
                onClick={() => settle("confirm")}
              >
                {request.kind === "confirm"
                  ? (request.options.confirmLabel ?? "Confirm")
                  : request.kind === "prompt"
                    ? (request.options.confirmLabel ?? "Save")
                    : (request.options.closeLabel ?? "OK")}
              </Button.Root>
            </Modal.Footer>
          </Modal.Content>
        )}
      </Modal.Root>
    </DialogContext.Provider>
  );
}

/** Re-exported so busy states in consumer dialogs share one spinner. */
export { RiLoader4Line as DialogSpinner };
