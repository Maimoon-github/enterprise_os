import { CrmRecordModal } from "@/components/crm/CrmRecordModal";

/**
 * A link to /crm/records/[id] inside the app is intercepted here and opens
 * the record as a pop-up over the current page (the Action required queue,
 * the Pipeline, Leads, the inboxes). Loading the URL directly skips this and
 * renders src/app/crm/records/[id] as a full page.
 *
 * The pop-up frame is the layout above [id], not inside it, so it stays
 * mounted both while a record streams in (instead of re-animating when
 * loading.tsx hands over) and while the pop-up steps from one lead to the
 * next; it reads the id from the URL itself.
 */
export default function CrmRecordModalLayout({ children }: { children: React.ReactNode }) {
  return <CrmRecordModal>{children}</CrmRecordModal>;
}
