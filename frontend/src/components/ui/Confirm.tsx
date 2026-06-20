"use client";

import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useState } from "react";

type ConfirmOptions = {
  title?: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  danger?: boolean;
};

type Pending = ConfirmOptions & { resolve: (ok: boolean) => void };

let setter: ((p: Pending | null) => void) | null = null;

export function confirmDialog(options: ConfirmOptions): Promise<boolean> {
  return new Promise((resolve) => {
    if (!setter) {
      resolve(false);
      return;
    }
    setter({ ...options, resolve });
  });
}

export function ConfirmHost() {
  const [pending, setPending] = useState<Pending | null>(null);

  useEffect(() => {
    setter = setPending;
    return () => {
      setter = null;
    };
  }, []);

  function close(ok: boolean) {
    pending?.resolve(ok);
    setPending(null);
  }

  return (
    <AnimatePresence>
      {pending && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-[110] grid place-items-center bg-black/50 p-4 backdrop-blur-sm"
          onClick={() => close(false)}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.96, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 8 }}
            onClick={(e) => e.stopPropagation()}
            className="glass-strong w-full max-w-sm rounded-md p-5 shadow-card"
          >
            {pending.title && (
              <div className="mb-1 text-sm text-white">{pending.title}</div>
            )}
            <p className="text-xs leading-relaxed text-slate-300">{pending.message}</p>
            <div className="mt-5 flex justify-end gap-2">
              <button onClick={() => close(false)} className="btn-ghost btn-sm">
                {pending.cancelText ?? "取消"}
              </button>
              <button
                onClick={() => close(true)}
                className={pending.danger ? "btn-danger btn-sm" : "btn-primary btn-sm"}
              >
                {pending.confirmText ?? "确认"}
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
