import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Toaster } from "react-hot-toast";

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Sensex Edge Telugu | Sensex Options Intraday Trading",
  description:
    "Sensex Edge Telugu provides Sensex Options Intraday Trading levels, market analysis, premium signals and educational content in Telugu.",
  keywords: [
    "Sensex Options",
    "Sensex Intraday",
    "Bank Nifty",
    "Stock Market Telugu",
    "Options Trading Telugu",
    "Sensex Edge Telugu"
  ],
  authors: [
    {
      name: "Sensex Edge Telugu",
    },
  ],
  creator: "Sensex Edge Telugu",
  publisher: "Sensex Edge Telugu",

  openGraph: {
    title: "Sensex Edge Telugu",
    description:
      "Professional Sensex Options Intraday Trading Updates in Telugu",
    type: "website",
    locale: "en_US",
  },

  icons: {
    icon: "/favicon.ico",
  },

  robots: {
    index: true,
    follow: true,
  },
};

export const viewport = {
  themeColor: "#FFD700",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="te">
      <body className={inter.className}>
        {children}

        <Toaster
          position="top-right"
          reverseOrder={false}
        />
      </body>
    </html>
  );
}