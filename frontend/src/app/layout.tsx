import type { Metadata } from "next";
import { Playfair_Display, Lora, Courier_Prime } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/lib/auth";

const playfair = Playfair_Display({
  subsets: ["latin"],
  weight: ["400", "600", "700"],
  style: ["normal", "italic"],
  variable: "--font-playfair",
  display: "swap",
});

const lora = Lora({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  style: ["normal", "italic"],
  variable: "--font-lora",
  display: "swap",
});

const courier = Courier_Prime({
  subsets: ["latin"],
  weight: ["400", "700"],
  variable: "--font-courier",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Copilot Investor",
  description: "You already invest. We help you do it intentionally.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${playfair.variable} ${lora.variable} ${courier.variable} antialiased`}>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
