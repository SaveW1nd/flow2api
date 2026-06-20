import type { Metadata } from "next";
import "./globals.css";

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
      </body>
    </html>
  );
}
