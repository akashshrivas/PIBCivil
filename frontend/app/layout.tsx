import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PIBCivil",
  description: "Summarised PIB releases for exam prep",
};

// NEW: tells phones to use the full screen, so the bottom padding for
// the iPhone home bar (env(safe-area-inset-bottom) in globals.css) works.
export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

export default function RootLayout({
  children,
  modal,
}: {
  children: React.ReactNode;
  modal: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        {children}
        {modal}
      </body>
    </html>
  );
}
