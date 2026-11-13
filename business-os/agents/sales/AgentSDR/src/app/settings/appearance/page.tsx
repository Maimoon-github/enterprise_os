import AppearanceSettings from "@/components/settings/AppearanceSettings";
import { SettingsPage } from "@/components/settings/SettingsPage";

export const metadata = { title: "Appearance" };

export default function AppearancePage() {
  return (
    <SettingsPage title="Appearance" description="Light, dark, or matched to your system." width="narrow">
      <AppearanceSettings />
    </SettingsPage>
  );
}
