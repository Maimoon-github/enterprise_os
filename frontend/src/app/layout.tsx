import type { Metadata } from "next";
import "@/styles/globals.css";

export const metadata: Metadata = {
  title: "Agentic Brand Marketing OS",
  description: "Self-hosted agentic platform for brand marketing orchestration and publishing",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-bloodstone-canvas text-bloodstone-text antialiased min-h-screen selection:bg-bloodstone-mint/30 selection:text-bloodstone-text">
        {children}
      </body>
    </html>
  );
}
