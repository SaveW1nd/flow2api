"use client";

import { Check, Pencil, Plus, Wallet, X } from "lucide-react";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { toast } from "@/components/ui/Toast";
import type { AdminUser } from "@/lib/types";
import { cn } from "@/lib/utils";

export default function AdminUsersPage() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [editing, setEditing] = useState<number | null>(null);
  const [draft, setDraft] = useState<{ image: number; video: number }>({ image: 0, video: 0 });
  const [editingUser, setEditingUser] = useState<AdminUser | null>(null);
  const [userDraft, setUserDraft] = useState({
    email: "",
    full_name: "",
    role: "user" as "user" | "admin",
    is_active: true,
  });
  const [recharging, setRecharging] = useState<AdminUser | null>(null);
  const [rechargeDraft, setRechargeDraft] = useState({ image: 0, video: 0 });

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

  function startEditUser(u: AdminUser) {
    setEditingUser(u);
    setUserDraft({
      email: u.email,
      full_name: u.full_name || "",
      role: u.role,
      is_active: u.is_active,
    });
  }

  async function saveUser() {
    if (!editingUser) return;
    await api(`/admin/users/${editingUser.id}`, {
      method: "PATCH",
      body: JSON.stringify(userDraft),
    });
    setEditingUser(null);
    load();
    toast.success("用户信息已更新");
  }

  function startRecharge(u: AdminUser) {
    setRecharging(u);
    setRechargeDraft({ image: 0, video: 0 });
  }

  async function saveRecharge() {
    if (!recharging) return;
    await api(`/admin/users/${recharging.id}/recharge`, {
      method: "POST",
      body: JSON.stringify({
        image_quota: rechargeDraft.image,
        video_quota: rechargeDraft.video,
      }),
    });
    setRecharging(null);
    load();
    toast.success("额度已充值");
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

      {editingUser && (
        <div className="card mt-4 space-y-3 p-4">
          <div className="text-sm text-white">编辑用户</div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <label className="label">邮箱</label>
              <input
                className="input"
                value={userDraft.email}
                onChange={(e) => setUserDraft({ ...userDraft, email: e.target.value })}
              />
            </div>
            <div>
              <label className="label">名称</label>
              <input
                className="input"
                value={userDraft.full_name}
                onChange={(e) => setUserDraft({ ...userDraft, full_name: e.target.value })}
              />
            </div>
            <div>
              <label className="label">角色</label>
              <select
                className="input"
                value={userDraft.role}
                onChange={(e) => setUserDraft({ ...userDraft, role: e.target.value as "user" | "admin" })}
              >
                <option value="user">用户</option>
                <option value="admin">管理员</option>
              </select>
            </div>
            <div>
              <label className="label">状态</label>
              <select
                className="input"
                value={userDraft.is_active ? "active" : "disabled"}
                onChange={(e) => setUserDraft({ ...userDraft, is_active: e.target.value === "active" })}
              >
                <option value="active">正常</option>
                <option value="disabled">禁用</option>
              </select>
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <button onClick={() => setEditingUser(null)} className="btn-ghost">
              取消
            </button>
            <button onClick={saveUser} className="btn-primary">
              保存用户
            </button>
          </div>
        </div>
      )}

      {recharging && (
        <div className="card mt-4 space-y-3 p-4">
          <div className="text-sm text-white">充值额度: {recharging.email}</div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label className="label">增加出图额度</label>
              <input
                type="number"
                className="input"
                value={rechargeDraft.image}
                onChange={(e) => setRechargeDraft({ ...rechargeDraft, image: Number(e.target.value) })}
              />
            </div>
            <div>
              <label className="label">增加出视频额度</label>
              <input
                type="number"
                className="input"
                value={rechargeDraft.video}
                onChange={(e) => setRechargeDraft({ ...rechargeDraft, video: Number(e.target.value) })}
              />
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <button onClick={() => setRecharging(null)} className="btn-ghost">
              取消
            </button>
            <button onClick={saveRecharge} className="btn-primary">
              充值
            </button>
          </div>
        </div>
      )}

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
                      <div className="flex justify-end gap-2">
                        <button onClick={() => startEditUser(u)} className="btn-ghost btn-sm">
                          <Pencil className="h-3.5 w-3.5" />
                          编辑用户
                        </button>
                        <button onClick={() => startRecharge(u)} className="btn-ghost btn-sm text-emerald-300">
                          <Wallet className="h-3.5 w-3.5" />
                          充值额度
                        </button>
                        <button onClick={() => startEdit(u)} className="btn-ghost btn-sm">
                          <Plus className="h-3.5 w-3.5" />
                          改每日额度
                        </button>
                      </div>
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
