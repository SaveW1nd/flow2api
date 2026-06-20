"use client";

import { CheckCircle2, Plus, Power, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { confirmDialog } from "@/components/ui/Confirm";
import { toast } from "@/components/ui/Toast";
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
    email: "",
    project_id: "",
    session_token: "",
    google_cookies: "",
    proxy: "",
    weight: 1,
    max_concurrency: 2,
  });

  const load = () => api<FlowAccount[]>("/admin/accounts").then(setAccounts).catch(() => {});

  useEffect(() => {
    load();
  }, []);

  async function create() {
    if (!form.label || !form.session_token || !form.project_id) {
      toast.warn("请填写名称、Session Token(ST)与 Project ID");
      return;
    }
    try {
      await api("/admin/accounts", { method: "POST", body: JSON.stringify(form) });
      setForm({ label: "", email: "", project_id: "", session_token: "", google_cookies: "", proxy: "", weight: 1, max_concurrency: 2 });
      setShowForm(false);
      load();
      toast.success("账号已新增");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "新增失败");
    }
  }

  async function test(a: FlowAccount) {
    try {
      const r = await api<{ email: string | null; expires_at: string }>(
        `/admin/accounts/${a.id}/test`,
        { method: "POST" }
      );
      toast.success(`凭证有效:${r.email ?? "?"}(令牌至 ${new Date(r.expires_at).toLocaleString()})`);
      load();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "校验失败");
    }
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
    const ok = await confirmDialog({
      title: "删除账号",
      message: "删除后该账号将从账号池移除,确认继续?",
      confirmText: "删除",
      danger: true,
    });
    if (!ok) return;
    await api(`/admin/accounts/${id}`, { method: "DELETE" });
    load();
    toast.success("账号已删除");
  }

  return (
    <div>
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="page-title">FLOW 账号池</h1>
          <p className="page-sub">
            每个账号 = Session Token(ST)+ Project ID + Google Cookies,系统纯 HTTP 刷新 access token 并获取 reCAPTCHA
          </p>
        </div>
        <button onClick={() => setShowForm((s) => !s)} className="btn-primary shrink-0">
          <Plus className="h-4 w-4" />
          新增账号
        </button>
      </div>

      {showForm && (
        <div className="card mt-4 space-y-3.5 p-4">
          <div className="grid gap-3.5 sm:grid-cols-2">
            <div>
              <label className="label">名称</label>
              <input
                className="input"
                value={form.label}
                onChange={(e) => setForm({ ...form, label: e.target.value })}
                placeholder="账号-01"
              />
            </div>
            <div>
              <label className="label">Google 邮箱(可选)</label>
              <input
                className="input"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                placeholder="user@gmail.com"
              />
            </div>
          </div>
          <div>
            <label className="label">Project ID</label>
            <input
              className="input font-mono"
              value={form.project_id}
              onChange={(e) => setForm({ ...form, project_id: e.target.value })}
              placeholder="0131165a-627e-... (labs.google flow 项目 URL 里的 project id)"
            />
          </div>
          <div>
            <label className="label">专用代理(可选,留空用全局)</label>
            <input
              className="input font-mono text-xs"
              value={form.proxy}
              onChange={(e) => setForm({ ...form, proxy: e.target.value })}
              placeholder="http://user:pass@host:port 或 socks5://user:pass@host:port"
            />
          </div>
          <div className="grid grid-cols-2 gap-3.5 sm:max-w-xs">
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
                onChange={(e) => setForm({ ...form, max_concurrency: Number(e.target.value) })}
              />
            </div>
          </div>
          <div>
            <label className="label">Session Token(ST · __Secure-next-auth.session-token)</label>
            <textarea
              className="input min-h-[72px] resize-none font-mono text-xs"
              value={form.session_token}
              onChange={(e) => setForm({ ...form, session_token: e.target.value })}
              placeholder="eyJhbGciOiJkaXIiLCJlbmMi...(浏览器 labs.google Cookie 里复制)"
            />
          </div>
          <div>
            <label className="label">Google Cookies(推荐,用于纯协议 reCAPTCHA)</label>
            <textarea
              className="input min-h-[88px] resize-none font-mono text-xs"
              value={form.google_cookies}
              onChange={(e) => setForm({ ...form, google_cookies: e.target.value })}
              placeholder='从 Cookie Editor 导出 .google.com + accounts.google.com cookies JSON,需包含 SID/HSID/SSID/APISID/SAPISID 等'
            />
          </div>
          <div className="alert-warn">
            纯协议模式需要 Google 登录 cookies 提高 reCAPTCHA 评分。仅有 ST 可以刷新 access token,但 reCAPTCHA 可能被 Google 判低分。
          </div>
          <div className="flex justify-end gap-2">
            <button onClick={() => setShowForm(false)} className="btn-ghost">
              取消
            </button>
            <button onClick={create} className="btn-primary">
              保存
            </button>
          </div>
        </div>
      )}

      <div className="card mt-4 overflow-x-auto">
        <table className="w-full min-w-[820px] text-[13px]">
          <thead className="border-b border-white/[0.06] text-left text-xs uppercase text-slate-500">
            <tr>
              <th className="px-4 py-2.5">名称 / 邮箱</th>
              <th className="px-4 py-2.5">状态</th>
              <th className="px-4 py-2.5">凭证</th>
              <th className="px-4 py-2.5">额度</th>
              <th className="px-4 py-2.5">权重/并发</th>
              <th className="px-4 py-2.5">成功/失败</th>
              <th className="px-4 py-2.5 text-right">操作</th>
            </tr>
          </thead>
          <tbody>
            {accounts.map((a) => (
              <tr key={a.id} className="border-b border-white/[0.03] hover:bg-white/[0.02]">
                <td className="px-4 py-2.5">
                  <div className="text-white">{a.label}</div>
                  <div className="text-xs text-slate-500">{a.email || a.chrome_profile}</div>
                </td>
                <td className="px-4 py-2.5">
                  <span className={cn("badge", STATUS_STYLE[a.status])}>
                    {a.status}
                  </span>
                </td>
                <td className="px-4 py-2.5">
                  <span
                    className={cn(
                      "badge",
                      a.has_session_token ? "bg-emerald-500/15 text-emerald-300" : "bg-red-500/15 text-red-300"
                    )}
                  >
                    {a.has_session_token ? "ST" : "缺 ST"}
                  </span>
                  <span
                    className={cn(
                      "badge ml-1",
                      a.has_google_cookies ? "bg-emerald-500/15 text-emerald-300" : "bg-amber-500/15 text-amber-300"
                    )}
                  >
                    {a.has_google_cookies ? "G-Cookies" : "缺 Cookies"}
                  </span>
                </td>
                <td className="px-4 py-2.5 text-slate-300">{a.remaining_credits ?? "—"}</td>
                <td className="px-4 py-2.5 text-slate-300">
                  {a.weight} / {a.max_concurrency}
                </td>
                <td className="px-4 py-2.5 text-slate-300">
                  <span className="text-emerald-300">{a.success_count}</span> /{" "}
                  <span className="text-red-300">{a.fail_count}</span>
                </td>
                <td className="px-4 py-2.5">
                  <div className="flex justify-end gap-2">
                    <button
                      onClick={() => test(a)}
                      className="grid h-7 w-7 place-items-center rounded-md glass text-sky-300 hover:text-white"
                      title="校验 ST 凭证"
                    >
                      <CheckCircle2 className="h-3.5 w-3.5" />
                    </button>
                    <button
                      onClick={() => toggle(a)}
                      className="grid h-7 w-7 place-items-center rounded-md glass text-slate-300 hover:text-white"
                      title="启用/禁用"
                    >
                      <Power className="h-3.5 w-3.5" />
                    </button>
                    <button
                      onClick={() => remove(a.id)}
                      className="grid h-7 w-7 place-items-center rounded-md glass text-red-300 hover:bg-red-500/10"
                      title="删除"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {accounts.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-10 text-center text-slate-500">
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
