import CrmRecordClient from "@/components/crm/CrmRecordClient";

export const dynamic = "force-dynamic";

/** The record workspace inside the pop-up; see ../layout.tsx. */
export default async function CrmRecordModalPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <CrmRecordClient key={id} recordId={id} variant="modal" />;
}
