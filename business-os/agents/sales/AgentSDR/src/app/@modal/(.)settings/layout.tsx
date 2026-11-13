import { SettingsModal } from "@/components/settings/SettingsShell";

/**
 * A link to /settings/* inside the app is intercepted here and opens Settings
 * as a pop-up over the current page. Loading a /settings URL directly skips
 * this and renders src/app/settings as a full page. Each section below reuses
 * that page's module, so the two cannot drift.
 */
export default function SettingsModalLayout({ children }: { children: React.ReactNode }) {
  return <SettingsModal>{children}</SettingsModal>;
}
