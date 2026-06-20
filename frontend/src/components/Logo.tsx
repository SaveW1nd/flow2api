import { cn } from "@/lib/utils";

export function Logo({ className }: { className?: string }) {
  return (
    <div className={cn("flex items-center gap-2.5", className)}>
      <div className="relative grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-brand-500 to-cyanx-500 shadow-glow">
        <svg viewBox="0 0 24 24" className="h-5 w-5 text-white" fill="none">
          <path
            d="M4 12c4-6 12-6 16 0-4 6-12 6-16 0Z"
            stroke="currentColor"
            strokeWidth="1.8"
          />
          <circle cx="12" cy="12" r="2.4" fill="currentColor" />
        </svg>
      </div>
      <span className="text-lg font-semibold tracking-tight text-white">
        Flow<span className="text-brand-400">2</span>API
      </span>
    </div>
  );
}
