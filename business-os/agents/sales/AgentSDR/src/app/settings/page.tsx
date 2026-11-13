import { redirect } from "next/navigation";
import { SETTINGS_HOME } from "@/components/settings/settingsNav";

export default function SettingsIndexPage() {
  redirect(SETTINGS_HOME);
}
