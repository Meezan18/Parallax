import type { Metadata } from "next";
import "./globals.css";
import { Intro } from "@/components/Intro";

export const metadata: Metadata = {
  title: "Parallax: AI pit wall",
  description: "Pick a race and a driver. The AI runs its own strategy against the real one, lap by lap.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@500;600;700&family=Barlow:wght@400;500;600&display=swap"
        />
      </head>
      <body>
        <Intro />
        {children}
      </body>
    </html>
  );
}
