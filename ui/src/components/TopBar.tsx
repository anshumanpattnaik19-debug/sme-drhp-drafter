import { Link } from "react-router-dom";
import { Cpu, Moon, Settings2, Sun } from "lucide-react";
import { useApp } from "../lib/state";
import { Button, Tooltip } from "./ui";
import { cn } from "../lib/utils";

export function Logo() {
  return (
    <svg viewBox="0 0 32 32" className="h-7 w-7" aria-hidden>
      <rect width="32" height="32" rx="8" className="fill-primary" />
      <path d="M10 8h8l5 5v11a1 1 0 0 1-1 1H10a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1z" fill="#fff" />
      <path d="M18 8v5h5" fill="#C9D3FA" />
      <rect x="12" y="16" width="8" height="1.6" rx=".8" className="fill-primary" />
      <rect x="12" y="19.4" width="6" height="1.6" rx=".8" className="fill-primary" />
    </svg>
  );
}

export function ModelStatus() {
  const { health, openSettings } = useApp();
  let tone = "bg-fg-subtle", label = "Service offline", detail = "The drafting service is not reachable.";
  if (health) {
    if (!health.use_model) {
      tone = "bg-warning";
      label = "Offline mock writer";
      detail = "SLM sections are drafted by the offline mock. Connect the fine-tuned model in Settings.";
    } else if (health.model.reachable) {
      tone = "bg-success";
      label = health.model_name;
      detail = `Connected to ${health.model_url}${health.model.latency_ms != null ? ` · ${health.model.latency_ms} ms` : ""}`;
    } else {
      tone = "bg-danger";
      label = "Model unreachable";
      detail = `${health.model_url}: ${health.model.error ?? "no response"}`;
    }
  }
  return (
    <Tooltip content={detail} side="bottom">
      <button
        onClick={() => openSettings()}
        className="flex h-8 items-center gap-2 rounded-md border border-border bg-surface px-2.5 text-xs font-medium text-fg-muted transition-colors hover:bg-subtle hover:text-fg"
      >
        <Cpu className="h-3.5 w-3.5" />
        <span className="max-w-[180px] truncate">{label}</span>
        <span className={cn("h-2 w-2 rounded-full", tone)} />
      </button>
    </Tooltip>
  );
}

export function TopBar() {
  const { theme, toggleTheme, openSettings } = useApp();
  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-border bg-surface px-4">
      <Link to="/projects" className="flex items-center gap-2.5">
        <Logo />
        <div className="leading-tight">
          <div className="text-[14px] font-semibold tracking-tight text-fg">DRHP Studio</div>
          <div className="text-2xs text-fg-subtle">SME offer document drafter</div>
        </div>
      </Link>
      <div className="flex items-center gap-1.5">
        <ModelStatus />
        <Tooltip content={theme === "dark" ? "Light theme" : "Dark theme"} side="bottom">
          <Button variant="ghost" size="icon" onClick={toggleTheme} aria-label="Toggle theme">
            {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </Button>
        </Tooltip>
        <Tooltip content="Settings" side="bottom">
          <Button variant="ghost" size="icon" onClick={() => openSettings()} aria-label="Settings">
            <Settings2 className="h-4 w-4" />
          </Button>
        </Tooltip>
      </div>
    </header>
  );
}
