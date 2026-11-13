// AlignUI Select v0.0.0

'use client';

import * as React from 'react';
import * as SelectPrimitive from '@radix-ui/react-select';
import { RiArrowDownSLine, RiCheckLine } from '@remixicon/react';

import { cn } from '@/utils/cn';
import { tv, type VariantProps } from '@/utils/tv';

// Radix reserves `value=""` for "nothing selected" and refuses an item with
// it, but our filters use "" for "All …" the way a native <select> could.
// Root and Item swap "" for this sentinel on the way in and back on the way
// out, so call sites keep `value=""` — and an empty value with no "" item
// still shows the placeholder.
const EMPTY = '__alignui_select_empty__';

type SelectContextValue = { size: SelectSize; registerEmpty: () => () => void };
const SelectContext = React.createContext<SelectContextValue>({ size: 'medium', registerEmpty: () => () => {} });

type SelectSize = 'medium' | 'small' | 'xsmall';

const selectVariants = tv({
  slots: {
    trigger: [
      'group/trigger inline-flex w-full min-w-0 items-center gap-2 bg-bg-white-0 text-left text-paragraph-sm text-text-strong-950 shadow-regular-xs outline-none',
      'ring-1 ring-inset ring-stroke-soft-200 transition duration-200 ease-out',
      'hover:bg-bg-weak-50 hover:shadow-none',
      'focus-visible:shadow-button-important-focus focus-visible:ring-stroke-strong-950',
      'data-[state=open]:ring-stroke-strong-950',
      'data-[placeholder]:text-text-soft-400',
      'disabled:pointer-events-none disabled:bg-bg-weak-50 disabled:text-text-disabled-300 disabled:shadow-none disabled:ring-transparent',
    ],
    item: [
      'relative flex cursor-pointer select-none items-center gap-2 rounded-lg py-2 pl-2 pr-8 text-paragraph-sm text-text-strong-950 outline-none',
      'transition duration-200 ease-out',
      'data-[highlighted]:bg-bg-weak-50',
      'data-[disabled]:pointer-events-none data-[disabled]:text-text-disabled-300',
    ],
  },
  variants: {
    size: {
      medium: { trigger: 'h-10 rounded-10 px-3' },
      small: { trigger: 'h-9 rounded-lg px-2.5' },
      xsmall: { trigger: 'h-8 rounded-lg px-2.5' },
    },
    hasError: {
      true: { trigger: 'ring-error-base hover:ring-error-base focus-visible:ring-error-base' },
    },
  },
  defaultVariants: { size: 'medium' },
});

type RootProps = React.ComponentPropsWithoutRef<typeof SelectPrimitive.Root> & { size?: SelectSize };

function Root({ size = 'medium', value, defaultValue, onValueChange, ...rest }: RootProps) {
  const [emptyItems, setEmptyItems] = React.useState(0);
  const registerEmpty = React.useCallback(() => {
    setEmptyItems((count) => count + 1);
    return () => setEmptyItems((count) => count - 1);
  }, []);
  const toRadix = (next: string | undefined) => (next === '' && emptyItems > 0 ? EMPTY : next);
  const context = React.useMemo(() => ({ size, registerEmpty }), [size, registerEmpty]);
  return (
    <SelectContext.Provider value={context}>
      <SelectPrimitive.Root
        value={toRadix(value)}
        defaultValue={toRadix(defaultValue)}
        onValueChange={onValueChange ? (next) => onValueChange(next === EMPTY ? '' : next) : undefined}
        {...rest}
      />
    </SelectContext.Provider>
  );
}
Root.displayName = 'SelectRoot';

const Trigger = React.forwardRef<
  React.ComponentRef<typeof SelectPrimitive.Trigger>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitive.Trigger> & Pick<VariantProps<typeof selectVariants>, 'hasError'>
>(({ className, children, hasError, ...rest }, forwardedRef) => {
  const { size } = React.useContext(SelectContext);
  const { trigger } = selectVariants({ size, hasError });
  return (
    <SelectPrimitive.Trigger ref={forwardedRef} className={trigger({ class: className })} {...rest}>
      <span className="flex min-w-0 flex-1 items-center gap-2 truncate [&>span]:truncate">{children}</span>
      <SelectPrimitive.Icon asChild>
        <RiArrowDownSLine className="size-5 shrink-0 text-text-soft-400 transition duration-200 ease-out group-hover/trigger:text-text-sub-600 group-data-[state=open]/trigger:rotate-180 group-disabled/trigger:text-text-disabled-300" />
      </SelectPrimitive.Icon>
    </SelectPrimitive.Trigger>
  );
});
Trigger.displayName = 'SelectTrigger';

const Value = SelectPrimitive.Value;

const Content = React.forwardRef<
  React.ComponentRef<typeof SelectPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitive.Content>
>(({ className, children, position = 'popper', sideOffset = 8, ...rest }, forwardedRef) => (
  <SelectPrimitive.Portal>
    <SelectPrimitive.Content
      ref={forwardedRef}
      position={position}
      sideOffset={sideOffset}
      className={cn(
        'z-50 overflow-hidden rounded-2xl bg-bg-white-0 shadow-regular-md ring-1 ring-inset ring-stroke-soft-200',
        position === 'popper' && 'max-h-[min(var(--radix-select-content-available-height),22rem)] min-w-[max(var(--radix-select-trigger-width),10rem)]',
        'data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0',
        className,
      )}
      {...rest}
    >
      <SelectPrimitive.Viewport className="p-2">{children}</SelectPrimitive.Viewport>
    </SelectPrimitive.Content>
  </SelectPrimitive.Portal>
));
Content.displayName = 'SelectContent';

const Item = React.forwardRef<
  React.ComponentRef<typeof SelectPrimitive.Item>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitive.Item>
>(({ className, children, value, ...rest }, forwardedRef) => {
  const { registerEmpty } = React.useContext(SelectContext);
  const isEmpty = value === '';
  React.useLayoutEffect(() => (isEmpty ? registerEmpty() : undefined), [isEmpty, registerEmpty]);
  const { item } = selectVariants();
  return (
    <SelectPrimitive.Item ref={forwardedRef} value={isEmpty ? EMPTY : value} className={item({ class: className })} {...rest}>
      <SelectPrimitive.ItemText>{children}</SelectPrimitive.ItemText>
      <SelectPrimitive.ItemIndicator className="absolute right-2 flex items-center">
        <RiCheckLine className="size-4 text-text-sub-600" />
      </SelectPrimitive.ItemIndicator>
    </SelectPrimitive.Item>
  );
});
Item.displayName = 'SelectItem';

const Group = SelectPrimitive.Group;

const GroupLabel = React.forwardRef<
  React.ComponentRef<typeof SelectPrimitive.Label>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitive.Label>
>(({ className, ...rest }, forwardedRef) => (
  <SelectPrimitive.Label
    ref={forwardedRef}
    className={cn('px-2 pb-1 pt-2 text-subheading-xs uppercase text-text-soft-400', className)}
    {...rest}
  />
));
GroupLabel.displayName = 'SelectGroupLabel';

const Separator = React.forwardRef<
  React.ComponentRef<typeof SelectPrimitive.Separator>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitive.Separator>
>(({ className, ...rest }, forwardedRef) => (
  <SelectPrimitive.Separator ref={forwardedRef} className={cn('-mx-2 my-1 h-px bg-stroke-soft-200', className)} {...rest} />
));
Separator.displayName = 'SelectSeparator';

export { Root, Trigger, Value, Content, Item, Group, GroupLabel, Separator };
