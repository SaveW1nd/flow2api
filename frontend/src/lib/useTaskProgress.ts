"use client";

import { useEffect, useRef, useState } from "react";

import { getToken } from "./api";
import { WS_BASE } from "./config";
import type { Output, TaskStatus } from "./types";

export interface ProgressState {
  status: TaskStatus | "idle";
  progress: number;
  outputs: Output[];
  error: string | null;
}

const initial: ProgressState = {
  status: "idle",
  progress: 0,
  outputs: [],
  error: null,
};

export function useTaskProgress() {
  const [state, setState] = useState<ProgressState>(initial);
  const wsRef = useRef<WebSocket | null>(null);

  function reset() {
    wsRef.current?.close();
    setState(initial);
  }

  function track(publicId: string) {
    wsRef.current?.close();
    setState({ status: "queued", progress: 0, outputs: [], error: null });

    const token = getToken();
    const ws = new WebSocket(
      `${WS_BASE}/ws/tasks/${publicId}?token=${encodeURIComponent(token ?? "")}`
    );
    wsRef.current = ws;

    ws.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data);
        if (data.type === "ping") return;
        setState({
          status: data.status,
          progress: data.progress ?? 0,
          outputs: data.outputs ?? [],
          error: data.error ?? null,
        });
        if (["succeeded", "failed", "cancelled"].includes(data.status)) {
          ws.close();
        }
      } catch {
        /* ignore */
      }
    };

    ws.onerror = () => {
      setState((s) => ({ ...s, error: s.error ?? "连接中断" }));
    };
  }

  useEffect(() => () => wsRef.current?.close(), []);

  return { state, track, reset };
}
