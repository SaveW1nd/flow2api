"use client";

import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle, CheckCircle2, Info, X, XCircle } from "lucide-react";
import { useEffect, useState } from "react";

type ToastKind = "success" | "error" | "info" | "warn";

type ToastItem = {
  id: number;
  kind: ToastKind;
  message: string;
};

type Listener = (items: ToastItem[]) => void;

let items: ToastItem[] = [];
let seq = 0;
const listeners = new Set<Listener>();

function emit() {
  for (const l of listeners) l([...items]);
}

function push(kind: ToastKind, message: string) {
  const id = ++seq;
  items = [...items, { id, kind, message }];
  emit();
  setTimeout(() => {
    items = items.filter((t) => t.id !== id);
    emit();
  }, 3600);
}

export const toast = {
  success: (m: string) => push("success", m),
  error: (m: string) => push("error", m),
  info: (m: string) => push("info", m),
  warn: (m: string) => push("warn", m),
};

const STYLE: Record<ToastKind, { cls: string; icon: React.ElementType }> = {
  success: { cls: "border-emerald-500/25 bg-emerald-500/10 text-emerald-200", icon: CheckCircle2 },
  error: { cls: "border-red-500/25 bg-red-500/10 text-red-200", icon: XCircle },
  info: { cls: "border-brand-500/25 bg-brand-500/10 text-brand-200", icon: Info },
  warn: { cls: "border-amber-500/25 bg-amber-500/10 text-amber-200", icon: AlertTriangle },
};

export function Toaster() {
  const [list, setList] = useState<ToastItem[]>([]);

  useEffect(() => {
    listeners.add(setList);
    return () => {
      listeners.delete(setList);
    };
  }, []);

  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-[100] flex w-[min(92vw,320px)] flex-col gap-2">
      <AnimatePresence initial={false}>
        {list.map((t) => {
          const s = STYLE[t.kind];
          const Icon = s.icon;
          return (
            <motion.div
              key={t.id}
              initial={{ opacity: 0, x: 24 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 24 }}
              className={`pointer-events-auto flex items-start gap-2 rounded-md border px-3 py-2 text-xs backdrop-blur-xl ${s.cls}`}
            >
              <Icon className="mt-0.5 h-4 w-4 shrink-0" />
              <span className="flex-1 leading-relaxed">{t.message}</span>
              <button
                onClick={() => {
                  items = items.filter((x) => x.id !== t.id);
                  emit();
                }}
                className="shrink-0 opacity-60 transition hover:opacity-100"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}
