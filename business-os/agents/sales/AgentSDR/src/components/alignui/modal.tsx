// AlignUI Modal v0.0.0

'use client';

import * as React from 'react';
import * as DialogPrimitive from '@radix-ui/react-dialog';

import { cn } from '@/utils/cn';

/**
 * Built on Radix Dialog rather than a hand-rolled portal, because the parts
 * that are easy to skip are the ones that matter: focus is trapped and
 * restored to the trigger on close, Escape and outside-click are wired up,
 * background scroll is locked, and the rest of the page is hidden from screen
 * readers while the modal is open.
 */
const Root = DialogPrimitive.Root;
const Trigger = DialogPrimitive.Trigger;
const Close = DialogPrimitive.Close;

const Overlay = React.forwardRef<
  React.ComponentRef<typeof DialogPrimitive.Overlay>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Overlay>
>(({ className, ...rest }, forwardedRef) => (
  <DialogPrimitive.Overlay
    ref={forwardedRef}
    className={cn(
      'fixed inset-0 z-50 bg-overlay backdrop-blur-[3px]',
      'data-[state=open]:animate-in data-[state=open]:fade-in-0',
      'data-[state=closed]:animate-out data-[state=closed]:fade-out-0',
      className,
    )}
    {...rest}
  />
));
Overlay.displayName = 'ModalOverlay';

const Content = React.forwardRef<
  React.ComponentRef<typeof DialogPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Content> & {
    /** Hides the corner close button — use for a modal that must be answered. */
    hideClose?: boolean;
    /** Tailwind max-width class. Defaults to a small prompt-sized modal. */
    size?: string;
  }
>(({ className, children, hideClose, size = 'max-w-md', ...rest }, forwardedRef) => (
  <DialogPrimitive.Portal>
    <Overlay />
    <DialogPrimitive.Content
      ref={forwardedRef}
      className={cn(
        'fixed left-1/2 top-1/2 z-50 flex max-h-[85vh] w-[calc(100%-2rem)] -translate-x-1/2 -translate-y-1/2 flex-col',
        'rounded-2xl bg-bg-white-0 shadow-regular-md ring-1 ring-inset ring-stroke-soft-200',
        'focus:outline-none',
        'data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95',
        'data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95',
        size,
        className,
      )}
      {...rest}
    >
      {children}
      {!hideClose && (
        <DialogPrimitive.Close
          aria-label="Close"
          className="absolute right-4 top-4 flex size-7 items-center justify-center rounded-full text-text-soft-400 outline-none transition duration-200 ease-out hover:bg-bg-weak-50 hover:text-text-sub-600 focus-visible:ring-2 focus-visible:ring-stroke-strong-950"
        >
          <CloseIcon />
        </DialogPrimitive.Close>
      )}
    </DialogPrimitive.Content>
  </DialogPrimitive.Portal>
));
Content.displayName = 'ModalContent';

function CloseIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" className="size-4" aria-hidden="true">
      <path
        d="M6 6l12 12M18 6L6 18"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  );
}

function Header({
  className,
  icon: Icon,
  children,
  ...rest
}: React.ComponentPropsWithoutRef<'div'> & { icon?: React.ElementType }) {
  return (
    <div
      className={cn('flex shrink-0 items-start gap-3 p-5 pb-0 pr-12', className)}
      {...rest}
    >
      {Icon && (
        <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-bg-weak-50 text-text-sub-600">
          <Icon className="size-5" />
        </span>
      )}
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}

const Title = React.forwardRef<
  React.ComponentRef<typeof DialogPrimitive.Title>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Title>
>(({ className, ...rest }, forwardedRef) => (
  <DialogPrimitive.Title
    ref={forwardedRef}
    className={cn('text-label-md text-text-strong-950', className)}
    {...rest}
  />
));
Title.displayName = 'ModalTitle';

const Description = React.forwardRef<
  React.ComponentRef<typeof DialogPrimitive.Description>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Description>
>(({ className, ...rest }, forwardedRef) => (
  <DialogPrimitive.Description
    ref={forwardedRef}
    className={cn('mt-1 text-paragraph-sm text-text-sub-600', className)}
    {...rest}
  />
));
Description.displayName = 'ModalDescription';

/** Scrolls on its own, so a long body never pushes the footer off-screen. */
function Body({ className, ...rest }: React.ComponentPropsWithoutRef<'div'>) {
  return <div className={cn('min-h-0 flex-1 overflow-y-auto p-5', className)} {...rest} />;
}

function Footer({ className, ...rest }: React.ComponentPropsWithoutRef<'div'>) {
  return (
    <div
      className={cn(
        'flex shrink-0 items-center justify-end gap-3 border-t border-stroke-soft-200 p-5',
        className,
      )}
      {...rest}
    />
  );
}

/**
 * A right-anchored sheet. Same dialog semantics as Content, but full height
 * against the edge of the screen — for reference material a person reads
 * beside their work rather than a prompt that interrupts it.
 */
const SideContent = React.forwardRef<
  React.ComponentRef<typeof DialogPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Content> & {
    /** Hides the corner close button. */
    hideClose?: boolean;
    /** Tailwind max-width class. Defaults to a reading-width sheet. */
    size?: string;
  }
>(({ className, children, hideClose, size = 'max-w-lg', ...rest }, forwardedRef) => (
  <DialogPrimitive.Portal>
    <Overlay />
    <DialogPrimitive.Content
      ref={forwardedRef}
      className={cn(
        'fixed inset-y-0 right-0 z-50 flex w-full flex-col',
        'bg-bg-white-0 shadow-regular-md ring-1 ring-inset ring-stroke-soft-200',
        'focus:outline-none',
        'data-[state=open]:animate-in data-[state=open]:slide-in-from-right',
        'data-[state=closed]:animate-out data-[state=closed]:slide-out-to-right',
        size,
        className,
      )}
      {...rest}
    >
      {children}
      {!hideClose && (
        <DialogPrimitive.Close
          aria-label="Close"
          className="absolute right-4 top-4 flex size-7 items-center justify-center rounded-full text-text-soft-400 outline-none transition duration-200 ease-out hover:bg-bg-weak-50 hover:text-text-sub-600 focus-visible:ring-2 focus-visible:ring-stroke-strong-950"
        >
          <CloseIcon />
        </DialogPrimitive.Close>
      )}
    </DialogPrimitive.Content>
  </DialogPrimitive.Portal>
));
SideContent.displayName = 'ModalSideContent';

export {
  Root,
  Trigger,
  Close,
  Overlay,
  Content,
  SideContent,
  Header,
  Title,
  Description,
  Body,
  Footer,
};
