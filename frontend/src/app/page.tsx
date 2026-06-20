"use client";

import { motion } from "framer-motion";
import { ArrowRight, Film, ImageIcon, ShieldCheck, Zap } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Logo } from "@/components/Logo";
import { getToken, login, register } from "@/lib/api";

export default function LandingPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (getToken()) router.replace("/workbench");
  }, [router]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      if (mode === "register") {
        await register(email, password, name);
      }
      await login(email, password);
      router.replace("/workbench");
    } catch (err) {
      setError(err instanceof Error ? err.message : "操作失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen">
      <nav className="mx-auto flex max-w-6xl items-center justify-between px-6 py-5">
        <Logo />
        <span className="text-xs text-slate-400">企业级 AIGC 生成平台</span>
      </nav>

      <main className="mx-auto grid max-w-6xl items-center gap-10 px-6 pb-16 pt-8 lg:grid-cols-2 lg:pt-16">
        {/* Hero */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
        >
          <div className="mb-4 inline-flex items-center gap-2 rounded-full glass px-3 py-1 text-xs text-brand-300">
            <span className="h-1.5 w-1.5 rounded-full bg-cyanx-400 animate-pulse" />
            基于 FLOW 的高并发出图 / 出视频引擎
          </div>
          <h1 className="text-2xl leading-tight tracking-tight text-white sm:text-3xl">
            让创意
            <span className="bg-gradient-to-r from-brand-400 to-cyanx-400 bg-clip-text text-transparent">
              一键成像
            </span>
            <br />
            出图与出视频，一站完成
          </h1>
          <p className="mt-4 max-w-lg text-sm leading-relaxed text-slate-400">
            面向团队与企业的多用户 AIGC 平台。强大的账号池调度与任务队列，支撑高并发稳定生成，管理员可精细配置额度与资源。
          </p>

          <div className="mt-8 grid grid-cols-2 gap-3 sm:max-w-md">
            <Feature icon={<ImageIcon className="h-5 w-5" />} title="高清出图" desc="多比例 / 批量生成" />
            <Feature icon={<Film className="h-5 w-5" />} title="智能出视频" desc="文生视频 / 图生视频" />
            <Feature icon={<Zap className="h-5 w-5" />} title="高并发" desc="队列 + 账号池调度" />
            <Feature icon={<ShieldCheck className="h-5 w-5" />} title="企业管控" desc="额度 / 权限 / 监控" />
          </div>
        </motion.div>

        {/* Auth card */}
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.15 }}
          className="flex items-center"
        >
          <div className="card w-full max-w-md p-6">
            <div className="mb-5 flex rounded-md bg-ink-900/60 p-1">
              {(["login", "register"] as const).map((m) => (
                <button
                  key={m}
                  onClick={() => setMode(m)}
                  className={`flex-1 rounded py-1.5 text-[13px] transition ${
                    mode === m
                      ? "bg-gradient-to-r from-brand-500 to-cyanx-500 text-white shadow-glow"
                      : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  {m === "login" ? "登录" : "注册"}
                </button>
              ))}
            </div>

            <form onSubmit={submit} className="space-y-3.5">
              {mode === "register" && (
                <div>
                  <label className="label">昵称</label>
                  <input
                    className="input"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="你的名字"
                  />
                </div>
              )}
              <div>
                <label className="label">邮箱</label>
                <input
                  type="email"
                  required
                  className="input"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@company.com"
                />
              </div>
              <div>
                <label className="label">密码</label>
                <input
                  type="password"
                  required
                  minLength={8}
                  className="input"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="至少 8 位"
                />
              </div>

              {error && <div className="alert-error">{error}</div>}

              <button type="submit" disabled={loading} className="btn-primary w-full">
                {loading ? "处理中…" : mode === "login" ? "进入工作台" : "注册并登录"}
                <ArrowRight className="h-4 w-4" />
              </button>
            </form>

            <p className="mt-5 text-center text-xs text-slate-500">
              登录即代表同意平台服务条款与生成内容合规要求
            </p>
          </div>
        </motion.div>
      </main>
    </div>
  );
}

function Feature({
  icon,
  title,
  desc,
}: {
  icon: React.ReactNode;
  title: string;
  desc: string;
}) {
  return (
    <div className="glass rounded-md p-3.5">
      <div className="mb-2 grid h-8 w-8 place-items-center rounded-md bg-brand-500/15 text-brand-300">
        {icon}
      </div>
      <div className="text-[13px] text-white">{title}</div>
      <div className="text-xs text-slate-400">{desc}</div>
    </div>
  );
}
