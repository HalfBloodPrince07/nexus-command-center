import type { Metadata, Viewport } from "next";
import { Inter, Space_Grotesk } from "next/font/google";
import ThemeApplier from "@/components/ThemeApplier";
import SmoothScrollProvider from "@/components/system/SmoothScrollProvider";
import CustomCursor from "@/components/system/CustomCursor";
import ScrollProgressBar from "@/components/system/ScrollProgressBar";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const spaceGrotesk = Space_Grotesk({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
  variable: "--font-space-grotesk",
  display: "swap",
});

export const metadata: Metadata = {
  title: "NEXUS OS — Your Local Intelligence Layer",
  description:
    "A premium command center for personal AI agents. Research, memory, and orchestration — all local.",
  keywords: ["AI", "agents", "command center", "local AI", "NEXUS"],
};

export const viewport: Viewport = {
  themeColor: "#FAFAFA",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${inter.variable} ${spaceGrotesk.variable}`}>
      <head>
        {/* Prevent dark mode flash on reload */}
        <script
          dangerouslySetInnerHTML={{
            __html: `
              try {
                var s = localStorage.getItem('nexus-app-storage');
                if (s) {
                  var p = JSON.parse(s);
                  if (p && p.state && p.state.isDarkMode) {
                    document.documentElement.classList.add('dark');
                  }
                }
              } catch(e) {}
            `,
          }}
        />
      </head>
      <body className="font-sans antialiased text-ink bg-surface-primary">
        <ThemeApplier />
        <ScrollProgressBar />
        <CustomCursor />
        <SmoothScrollProvider>{children}</SmoothScrollProvider>
      </body>
    </html>
  );
}
