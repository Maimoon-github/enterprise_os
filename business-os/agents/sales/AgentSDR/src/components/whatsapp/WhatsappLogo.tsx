import { RiWhatsappFill } from "@remixicon/react";
import { cn } from "@/utils/cn";

/** WhatsApp's own mark in its brand green — where a lead's channel is WhatsApp. */
export const WHATSAPP_GREEN = "#25D366";

export function WhatsappLogo({ className }: { className?: string }) {
  return <RiWhatsappFill className={cn("size-4 shrink-0 text-[#25D366]", className)} aria-hidden="true" />;
}
