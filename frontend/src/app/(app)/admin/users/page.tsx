"use client";

import { Check, X } from "lucide-react";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { toast } from "@/components/ui/Toast";
import type { AdminUser } from "@/lib/types";
import { cn } from "@/lib/utils";

export default function AdminUsersPage() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [editing, setEditing] = useState<number | null>(null);
  const [draft, setDraft] = useState<{ image: number; video: number }>({ image: 0, video: 0 });

  const load = () => api<AdminUser[]>("/admin/users").then(setUsers).catch(() => {});

  useEffect(() => {
    load();
  }, []);

  async function toggleActive(u: AdminUser) {
    await api(`/admin/users/${u.id}`, {
      method: "PATCH",
      body: JSON.stringify({ is_active: !u.is_active }),
    });
    load();
  }

  function startEdit(u: AdminUser) {
    setEditing(u.id);
    setDraft({ image: u.daily_image_quota, video: u.daily_video_quota });
  }

  async function saveQuota(id: number) {
    await api(`/admin/users/${id}`, {
      method: "PATCH",
      body: JSON.stringify({
        daily_image_quota: draft.image,
        daily_video_quota: draft.video,
      }),
    });
    setEditing(null);
    load();
    toast.success("额度已更新");
  }

  return (
    <div>
      <h1 className="page-title">用户与额度</h1>
      <p className="page-sub">管理用户状态与每日生成额度</p>

      <div className="card mt-4 overflow-x-auto">
        <table className="w-full min-w-[680px] text-[13px]">
          <thead className="border-b border-white/[0.06] text-left text-xs uppercase text-slate-500">
            <tr>
              <th className="px-4 py-2.5">用户</th>
              <th className="px-4 py-2.5">角色</th>
              <th className="px-4 py-2.5">状态</th>
              <th className="px-4 py-2.5">出图额度</th>
              <th className="px-4 py-2.5">出视频额度</th>
              <th className="px-4 py-2.5 text-right">操作</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id} className="border-b border-white/[0.03] hover:bg-white/[0.02]">
                <td className="px-4 py-2.5">
                  <div className="text-white">{u.full_name || "—"}</div>
                  <div className="text-xs text-slate-500">{u.email}</div>
                </td>
                <td className="px-4 py-2.5">
                  <span
                    className={cn(
                      "badge",
                      u.role === "admin"
                        ? "bg-brand-500/15 text-brand-300"
                        : "bg-white/5 text-slate-300"
                    )}
                  >
                    {u.role === "admin" ? "管理员" : "用户"}
                  </span>
                </td>
                <td className="px-4 py-2.5">
                  <button
                    onClick={() => toggleActive(u)}
                    className={cn(
                      "badge",
                      u.is_active
                        ? "bg-emerald-500/15 text-emerald-300"
                        : "bg-red-500/15 text-red-300"
                    )}
                  >
                    {u.is_active ? <Check className="h-3 w-3" /> : <X className="h-3 w-3" />}
                    {u.is_active ? "正常" : "禁用"}
                  </button>
                </td>
                {editing === u.id ? (
                  <>
                    <td className="px-4 py-2.5">
                      <input
                        type="number"
                        className="input w-24"
                        value={draft.image}
                        onChange={(e) => setDraft({ ...draft, image: Number(e.target.value) })}
                      />
                    </td>
                    <td className="px-4 py-2.5">
                      <input
                        type="number"
                        className="input w-24"
                        value={draft.video}
                        onChange={(e) => setDraft({ ...draft, video: Number(e.target.value) })}
                      />
                    </td>
                    <td className="px-4 py-2.5">
                      <div className="flex justify-end gap-2">
                        <button onClick={() => saveQuota(u.id)} className="btn-primary btn-sm">
                          保存
                        </button>
                        <button onClick={() => setEditing(null)} className="btn-ghost btn-sm">
                          取消
                        </button>
                      </div>
                    </td>
                  </>
                ) : (
                  <>
                    <td className="px-4 py-2.5 text-slate-300">{u.daily_image_quota}</td>
                    <td className="px-4 py-2.5 text-slate-300">{u.daily_video_quota}</td>
                    <td className="px-4 py-2.5 text-right">
                      <button onClick={() => startEdit(u)} className="btn-ghost btn-sm">
                        编辑额度
                      </button>
                    </td>
                  </>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
