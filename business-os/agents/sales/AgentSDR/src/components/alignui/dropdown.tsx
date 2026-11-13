// AlignUI Dropdown v0.0.0

'use client';

import * as React from 'react';
import * as DropdownMenuPrimitive from '@radix-ui/react-dropdown-menu';
import { Slot } from '@radix-ui/react-slot';

import { cn } from '@/utils/cn';

const Root = DropdownMenuPrimitive.Root;
const Trigger = DropdownMenuPrimitive.Trigger;
const Group = DropdownMenuPrimitive.Group;

const Content = React.forwardRef<
  React.ComponentRef<typeof DropdownMenuPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.Content>
>(({ className, align = 'end', sideOffset = 8, ...rest }, forwardedRef) => (
  <DropdownMenuPrimitive.Portal>
    <DropdownMenuPrimitive.Content
      ref={forwardedRef}
      align={align}
      sideOffset={sideOffset}
      className={cn(
        'z-50 min-w-[180px] overflow-hidden rounded-2xl bg-bg-white-0 p-2 shadow-regular-md ring-1 ring-inset ring-stroke-soft-200',
        'data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0',
        className,
      )}
      {...rest}
    />
  </DropdownMenuPrimitive.Portal>
));
Content.displayName = 'DropdownContent';

const Item = React.forwardRef<
  React.ComponentRef<typeof DropdownMenuPrimitive.Item>,
  React.ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.Item> & {
    /** Destructive actions read in red and get a red hover, per AlignUI's error tokens. */
    destructive?: boolean;
  }
>(({ className, destructive, ...rest }, forwardedRef) => (
  <DropdownMenuPrimitive.Item
    ref={forwardedRef}
    className={cn(
      'group flex cursor-pointer select-none items-center gap-2 rounded-lg p-2 text-paragraph-sm outline-none transition duration-200 ease-out',
      'data-[disabled]:pointer-events-none data-[disabled]:text-text-disabled-300',
      destructive
        ? 'text-error-base data-[highlighted]:bg-error-lighter'
        : 'text-text-strong-950 data-[highlighted]:bg-bg-weak-50',
      className,
    )}
    {...rest}
  />
));
Item.displayName = 'DropdownItem';

function ItemIcon({
  className,
  as,
  ...rest
}: React.ComponentPropsWithoutRef<'div'> & {
  as?: React.ElementType;
}) {
  const Component = as || Slot;
  return <Component className={cn('size-5 shrink-0', className)} {...rest} />;
}
ItemIcon.displayName = 'DropdownItemIcon';

const Separator = React.forwardRef<
  React.ComponentRef<typeof DropdownMenuPrimitive.Separator>,
  React.ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.Separator>
>(({ className, ...rest }, forwardedRef) => (
  <DropdownMenuPrimitive.Separator
    ref={forwardedRef}
    className={cn('-mx-2 my-1 h-px bg-stroke-soft-200', className)}
    {...rest}
  />
));
Separator.displayName = 'DropdownSeparator';

export { Root, Trigger, Content, Item, ItemIcon, Group, Separator };
