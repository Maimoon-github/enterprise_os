import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/linkedin/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full px-2.5 py-0.5 text-label-xs transition-colors ring-1 ring-inset",
  {
    variants: {
      variant: {
        default: "bg-primary-lighter text-primary-base ring-primary-alpha-16",
        secondary: "bg-bg-weak-50 text-text-strong-950 ring-stroke-soft-200",
        destructive: "bg-error-lighter text-error-base ring-error-light",
        outline: "bg-bg-white-0 text-text-strong-950 ring-stroke-soft-200",
        success: "bg-success-lighter text-success-base ring-success-light",
        warning: "bg-warning-lighter text-warning-base ring-warning-light",
        muted: "bg-bg-weak-50 text-text-soft-400 ring-stroke-soft-200",
        blue: "bg-information-lighter text-information-base ring-information-light",
        purple: "bg-away-lighter text-away-base ring-away-light",
      },
    },
    defaultVariants: { variant: "default" },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };
