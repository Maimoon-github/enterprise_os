import { CrmLayout } from "@/components/crm/CrmLayout";
import CrmRecordClient from "@/components/crm/CrmRecordClient";

export default async function CrmRecordPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <CrmLayout><CrmRecordClient recordId={id} /></CrmLayout>;
}
