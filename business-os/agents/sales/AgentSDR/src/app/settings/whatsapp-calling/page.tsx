import { redirect } from "next/navigation";

/** Call recordings moved onto WhatsApp → Integrations; this keeps old links working. */
export default function Page() {
  redirect("/settings/whatsapp-connection");
}
