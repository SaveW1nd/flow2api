import type { Metadata } from "next";
import "./globals.css";

import { ConfirmHost } from "@/components/ui/Confirm";
import { Toaster } from "@/components/ui/Toast";

export const metadata: Metadata = {
  title: "Flow2API · 智能出图出视频平台",
  description: "高端 AIGC 多用户出图 / 出视频平台",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN">
      <body>
        <div className="aurora" />
        {children}
        <Toaster />
        <ConfirmHost />
      </body>
    </html>
  );
}
