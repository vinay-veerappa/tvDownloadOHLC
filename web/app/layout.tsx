import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { AppSidebar } from "@/components/app-sidebar";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "TradeNote - Trading Platform",
  description: "Advanced Trading Journal and Backtesting Platform",
};

import { TradeProvider } from "@/components/journal/trade-context";
import { Toaster } from "@/components/ui/sonner";
import { ThemeProvider } from "@/components/theme-provider";
import { ThemeProvider as ChartThemeProvider } from "@/context/theme-context";

if (typeof window === "undefined") {
  const originalWarn = console.warn;
  console.warn = (...args: unknown[]) => {
    const message = args
      .filter((arg): arg is string => typeof arg === "string")
      .join(" ");

    if (message.includes("The width(-1) and height(-1) of chart should be greater than 0")) {
      return;
    }

    originalWarn(...args);
  };
}

// ...

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body
        suppressHydrationWarning
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <ThemeProvider
          attribute="class"
          defaultTheme="system"
          enableSystem
          disableTransitionOnChange
        >
          <ChartThemeProvider>
            <TradeProvider>
              <div className="flex h-screen overflow-hidden">
                <AppSidebar />
                <div className="flex flex-col flex-1 overflow-hidden">
                  <main className="flex-1 overflow-auto p-4 bg-muted/10">
                    {children}
                  </main>
                </div>
              </div>
              <Toaster />
            </TradeProvider>
          </ChartThemeProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
