import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "UAgent Chat",
  description: "Chat with UAgent AI",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">
        {children}
      </body>
    </html>
  );
}

