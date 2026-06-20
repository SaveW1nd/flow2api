"use client";

import { Activity, Film, ImageIcon, Layers, Server, Users } from "lucide-react";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { Dashboard } from "@/lib/types";

export default function AdminDashboard() {
  const [data, setData] = useState<Dashboard | null>(null);

  useEffect(() => {
    const load = () => api<Dashboard>("/admin/dashboard").then(setData).catch(() => {});
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, []);

  return (
    <div>
      <h1 className="page-title">数据概览</h1>
      <p className="page-sub">实时监控平台运行状态(每 5 秒刷新)</p>

      <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Stat icon={<Users />} label="总用户" value={data?.total_users} accent="from-brand-500/20" />
        <Stat icon={<Layers />} label="总任务" value={data?.total_tasks} accent="from-cyanx-500/20" />
        <Stat icon={<Server />} label="活跃账号" value={data?.active_accounts} accent="from-emerald-500/20" />
        <Stat icon={<Activity />} label="进行中" value={data?.running} accent="from-amber-500/20" />
      </div>

      <div className="mt-4 grid gap-3 lg:grid-cols-3">
        <div className="card p-4 lg:col-span-2">
          <h3 className="mb-3 text-[13px] text-slate-300">近 24 小时生成量</h3>
          <div className="grid grid-cols-3 gap-3">
            <MiniStat icon={<Layers className="h-4 w-4" />} label="任务总数" value={data?.last_24h_tasks} />
            <MiniStat icon={<ImageIcon className="h-4 w-4" />} label="出图" value={data?.last_24h_images} />
            <MiniStat icon={<Film className="h-4 w-4" />} label="出视频" value={data?.last_24h_videos} />
          </div>
        </div>

        <div className="card p-4">
          <h3 className="mb-3 text-[13px] text-slate-300">任务状态分布</h3>
          <div className="space-y-3">
            {data &&
              Object.entries(data.tasks_by_status).map(([k, v]) => (
                <StatusRow
                  key={k}
                  label={k}
                  value={v}
                  total={data.total_tasks}
                />
              ))}
            {(!data || Object.keys(data.tasks_by_status).length === 0) && (
              <p className="text-xs text-slate-500">暂无数据</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function Stat({
  icon,
  label,
  value,
  accent,
}: {
  icon: React.ReactNode;
  label: string;
  value?: number;
  accent: string;
}) {
  return (
    <div className="card relative overflow-hidden p-4">
      <div className={`absolute -right-6 -top-6 h-24 w-24 rounded-full bg-gradient-to-br ${accent} to-transparent blur-2xl`} />
      <div className="mb-2.5 grid h-9 w-9 place-items-center rounded-md bg-white/5 text-brand-300">
        {icon}
      </div>
      <div className="text-2xl text-white">{value ?? "—"}</div>
      <div className="mt-0.5 text-xs text-slate-400">{label}</div>
    </div>
  );
}

function MiniStat({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value?: number;
}) {
  return (
    <div className="rounded-md bg-ink-900/50 p-3.5">
      <div className="mb-2 flex items-center gap-2 text-slate-400">{icon}</div>
      <div className="text-xl text-white">{value ?? 0}</div>
      <div className="text-xs text-slate-500">{label}</div>
    </div>
  );
}

const STATUS_COLORS: Record<string, string> = {
  succeeded: "bg-emerald-400",
  failed: "bg-red-400",
  running: "bg-brand-400",
  queued: "bg-amber-400",
  cancelled: "bg-slate-400",
};

function StatusRow({ label, value, total }: { label: string; value: number; total: number }) {
  const pct = total ? (value / total) * 100 : 0;
  return (
    <div>
      <div className="mb-1 flex justify-between text-xs text-slate-400">
        <span className="capitalize">{label}</span>
        <span className="text-slate-300">{value}</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-white/10">
        <div
          className={`h-full rounded-full ${STATUS_COLORS[label] ?? "bg-brand-400"}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
