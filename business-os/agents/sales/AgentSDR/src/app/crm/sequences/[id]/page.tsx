import { CrmLayout } from "@/components/crm/CrmLayout";
import CrmSequenceEditor from "@/components/crm/CrmSequenceEditor";

export default async function CrmSequencePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <CrmLayout><CrmSequenceEditor sequenceId={id} /></CrmLayout>;
}
