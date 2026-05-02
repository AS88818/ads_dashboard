import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { ClerkProvider } from "@clerk/nextjs";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "YCK Ads Dashboard",
  description: "YCK advertising performance dashboard for Google Ads and Meta Ads.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <ClerkProvider
      appearance={{
        variables: {
          colorPrimary: "#1E3F36", // Forest Green
          colorBackground: "#FFFFFF",
          colorText: "#1A202C",
        },
        elements: {
          formButtonPrimary: 
            "bg-accent-primary hover:bg-accent-primary/90 text-white transition-all",
          card: "shadow-soft border border-border",
        }
      }}
    >
      <html
        lang="en"
        className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
      >
        <body className="min-h-full flex flex-col bg-background text-foreground selection:bg-accent-primary/10 selection:text-accent-primary">
          {children}
        </body>
      </html>
    </ClerkProvider>
  );
}
