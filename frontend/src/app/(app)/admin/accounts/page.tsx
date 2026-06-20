"use client";

import { Plus, Power, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { FlowAccount } from "@/lib/types";
import { cn } from "@/lib/utils";

const STATUS_STYLE: Record<string, string> = {
  active: "bg-emerald-500/15 text-emerald-300",
  disabled: "bg-slate-500/15 text-slate-300",
  cooldown: "bg-amber-500/15 text-amber-300",
  invalid: "bg-red-500/15 text-red-300",
};

export default function AccountsPage() {
  const [accounts, setAccounts] = useState<FlowAccount[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    label: "",
    auth_token: "",
    cookie: "",
    weight: 1,
    max_concurrency: 2,
  });

  const load = () => api<FlowAccount[]>("/admin/accounts").then(setAccounts).catch(() => {});

  useEffect(() => {
    load();
  }, []);

  async function create() {
    if (!form.label || !form.auth_token) return;
    await api("/admin/accounts", { method: "POST", body: JSON.stringify(form) });
    setForm({ label: "", auth_token: "", cookie: "", weight: 1, max_concurrency: 2 });
    setShowForm(false);
    load();
  }

  async function toggle(a: FlowAccount) {
    const status = a.status === "active" ? "disabled" : "active";
    await api(`/admin/accounts/${a.id}`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    });
    load();
  }

  async function remove(id: number) {
    if (!confirm("确认删除该账号?")) return;
    await api(`/admin/accounts/${id}`, { method: "DELETE" });
    load();
  }

  return (
    <div>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">FLOW 账号池</h1>
          <p className="mt-1 text-sm text-slate-400">
            管理上游账号 / Token,系统按权重与并发自动调度
          </p>
        </div>
        <button onClick={() => setShowForm((s) => !s)} className="btn-primary">
          <Plus className="h-4 w-4" />
          新增账号
        </button>
      </div>

      {showForm && (
        <div className="card mt-6 space-y-4 p-6">
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="label">名称</label>
              <input
                className="input"
                value={form.label}
                onChange={(e) => setForm({ ...form, label: e.target.value })}
                placeholder="账号-01"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="label">权重</label>
                <input
                  type="number"
                  className="input"
                  value={form.weight}
                  onChange={(e) => setForm({ ...form, weight: Number(e.target.value) })}
                />
              </div>
              <div>
                <label className="label">最大并发</label>
                <input
                  type="number"
                  className="input"
                  value={form.max_concurrency}
                  onChange={(e) =>
                    setForm({ ...form, max_concurrency: Number(e.target.value) })
                  }
                />
              </div>
            </div>
          </div>
          <div>
            <label className="label">Auth Token(逆向抓包得到)</label>
            <textarea
              className="input min-h-[70px] resize-none font-mono text-xs"
              value={form.auth_token}
              onChange={(e) => setForm({ ...form, auth_token: e.target.value })}
              placeholder="eyJhbGciOi..."
            />
          </div>
          <div>
            <label className="label">Cookie(可选)</label>
            <textarea
              className="input min-h-[60px] resize-none font-mono text-xs"
              value={form.cookie}
              onChange={(e) => setForm({ ...form, cookie: e.target.value })}
            />
          </div>
          <div className="flex justify-end gap-3">
            <button onClick={() => setShowForm(false)} className="btn-ghost">
              取消
            </button>
            <button onClick={create} className="btn-primary">
              保存
            </button>
          </div>
        </div>
      )}

      <div className="card mt-6 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="border-b border-white/[0.06] text-left text-xs uppercase text-slate-500">
            <tr>
              <th className="px-5 py-3">名称</th>
              <th className="px-5 py-3">状态</th>
              <th className="px-5 py-3">权重/并发</th>
              <th className="px-5 py-3">成功/失败</th>
              <th className="px-5 py-3">最近错误</th>
              <th className="px-5 py-3 text-right">操作</th>
            </tr>
          </thead>
          <tbody>
            {accounts.map((a) => (
              <tr key={a.id} className="border-b border-white/[0.03] hover:bg-white/[0.02]">
                <td className="px-5 py-3 font-medium text-white">{a.label}</td>
                <td className="px-5 py-3">
                  <span className={cn("rounded-full px-2 py-0.5 text-xs", STATUS_STYLE[a.status])}>
                    {a.status}
                  </span>
                </td>
                <td className="px-5 py-3 text-slate-300">
                  {a.weight} / {a.max_concurrency}
                </td>
                <td className="px-5 py-3 text-slate-300">
                  <span className="text-emerald-300">{a.success_count}</span> /{" "}
                  <span className="text-red-300">{a.fail_count}</span>
                </td>
                <td className="max-w-[200px] truncate px-5 py-3 text-xs text-slate-500">
                  {a.last_error || "—"}
                </td>
                <td className="px-5 py-3">
                  <div className="flex justify-end gap-2">
                    <button
                      onClick={() => toggle(a)}
                      className="grid h-8 w-8 place-items-center rounded-lg glass text-slate-300 hover:text-white"
                      title="启用/禁用"
                    >
                      <Power className="h-4 w-4" />
                    </button>
                    <button
                      onClick={() => remove(a.id)}
                      className="grid h-8 w-8 place-items-center rounded-lg glass text-red-300 hover:bg-red-500/10"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {accounts.length === 0 && (
              <tr>
                <td colSpan={6} className="px-5 py-10 text-center text-slate-500">
                  暂无账号,点击右上角新增
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
