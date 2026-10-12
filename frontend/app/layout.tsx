import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PIBCivil",
  description: "Summarised PIB releases for exam prep",
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
