import { SettingsPage } from "@/components/settings/SettingsPage";
import InstructionsSettings from "@/components/settings/InstructionsSettings";

export const metadata = { title: "Instructions" };
export const dynamic = "force-dynamic";

export default function InstructionsPage() {
  return (
    <SettingsPage
      title="Instructions"
      description="Guidance added to every AI draft and classification. Each instruction is sent to the AI as its own titled section."
    >
      <InstructionsSettings />
    </SettingsPage>
  );
}
