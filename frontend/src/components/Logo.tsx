import { cn } from "@/lib/utils";

export function Logo({ className }: { className?: string }) {
  return (
    <div className={cn("flex items-center gap-2", className)}>
      <div className="relative grid h-8 w-8 place-items-center rounded-md bg-gradient-to-br from-brand-500 to-cyanx-500 shadow-glow">
        <svg viewBox="0 0 24 24" className="h-4 w-4 text-white" fill="none">
          <path
            d="M4 12c4-6 12-6 16 0-4 6-12 6-16 0Z"
            stroke="currentColor"
            strokeWidth="1.8"
          />
          <circle cx="12" cy="12" r="2.4" fill="currentColor" />
        </svg>
      </div>
      <span className="text-sm tracking-tight text-white">
        Flow<span className="text-brand-400">2</span>API
      </span>
    </div>
  );
}
