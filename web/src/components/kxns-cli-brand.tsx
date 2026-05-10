import { kxnsCliVersion } from "@/lib/version";
import { cn } from "@/lib/utils";

type KxnsCliBrandProps = {
  className?: string;
  size?: "sm" | "md";
  showVersion?: boolean;
};

export function KxnsCliBrand({
  className,
  size = "md",
  showVersion = true,
}: KxnsCliBrandProps) {
  const textSizeClass = size === "sm" ? "text-base" : "text-lg";
  const versionPadding = size === "sm" ? "text-xs" : "text-sm";

  return (
    <div className={cn("flex items-center gap-2", className)}>
      <span className={cn(textSizeClass, "font-semibold text-foreground")}>
        Kxns Hunter CLI
      </span>
      {showVersion && (
        <span
          className={cn("text-muted-foreground font-medium", versionPadding)}
        >
          v{kxnsCliVersion}
        </span>
      )}
    </div>
  );
}
