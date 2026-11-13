"use client";

import * as React from "react";
import * as TabsPrimitive from "@radix-ui/react-tabs";

import type { PolymorphicComponentProps } from "@/utils/polymorphic";
import { cn } from "@/utils/cn";

const TabMenuVerticalContent = TabsPrimitive.Content;
TabMenuVerticalContent.displayName = "TabMenuVerticalContent";

type TabMenuVerticalRootProps = Omit<
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.Root>,
  "orientation"
>;

const TabMenuVerticalRoot = React.forwardRef<
  React.ComponentRef<typeof TabsPrimitive.Root>,
  TabMenuVerticalRootProps
>((props, forwardedRef) => (
  <TabsPrimitive.Root ref={forwardedRef} orientation="vertical" {...props} />
));
TabMenuVerticalRoot.displayName = "TabMenuVerticalRoot";

const TabMenuVerticalList = React.forwardRef<
  React.ComponentRef<typeof TabsPrimitive.List>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.List>
>(({ className, ...rest }, forwardedRef) => (
  <TabsPrimitive.List
    ref={forwardedRef}
    className={cn("w-full space-y-2", className)}
    {...rest}
  />
));
TabMenuVerticalList.displayName = "TabMenuVerticalList";

const TabMenuVerticalTrigger = React.forwardRef<
  React.ComponentRef<typeof TabsPrimitive.Trigger>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.Trigger>
>(({ className, ...rest }, forwardedRef) => (
  <TabsPrimitive.Trigger
    ref={forwardedRef}
    className={cn(
      "group/tab-item grid w-full auto-cols-auto grid-flow-col grid-cols-[auto,minmax(0,1fr)] items-center gap-1.5 rounded-lg p-2 text-left text-label-sm text-text-sub-600 outline-none",
      "transition duration-200 ease-out hover:bg-bg-weak-50 focus:outline-none",
      "data-[state=active]:bg-bg-weak-50 data-[state=active]:text-text-strong-950",
      className,
    )}
    {...rest}
  />
));
TabMenuVerticalTrigger.displayName = "TabMenuVerticalTrigger";

function TabMenuVerticalIcon<T extends React.ElementType>({
  className,
  as,
  ...rest
}: PolymorphicComponentProps<T>) {
  const Component = as || "div";

  return (
    <Component
      className={cn(
        "size-5 text-text-sub-600 transition duration-200 ease-out",
        "group-data-[state=active]/tab-item:text-primary-base",
        className,
      )}
      {...rest}
    />
  );
}
TabMenuVerticalIcon.displayName = "TabsVerticalIcon";

function TabMenuVerticalArrowIcon<T extends React.ElementType>({
  className,
  as,
  ...rest
}: PolymorphicComponentProps<T>) {
  const Component = as || "div";

  return (
    <Component
      className={cn(
        "size-5 scale-75 rounded-full bg-bg-white-0 p-px text-text-sub-600 opacity-0 shadow-regular-xs transition ease-out",
        "group-data-[state=active]/tab-item:scale-100 group-data-[state=active]/tab-item:opacity-100",
        className,
      )}
      {...rest}
    />
  );
}
TabMenuVerticalArrowIcon.displayName = "TabMenuVerticalArrowIcon";

export {
  TabMenuVerticalRoot as Root,
  TabMenuVerticalList as List,
  TabMenuVerticalTrigger as Trigger,
  TabMenuVerticalIcon as Icon,
  TabMenuVerticalArrowIcon as ArrowIcon,
  TabMenuVerticalContent as Content,
};
