import {
  createContext, forwardRef, useCallback, useContext, useEffect, useRef, useState,
  type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes,
} from "react";
import { createPortal } from "react-dom";
import { AlertCircle, CheckCircle2, Info, Loader2, X } from "lucide-react";
import { cn } from "../lib/utils";

/* ---------------- Button ---------------- */

type BtnVariant = "primary" | "secondary" | "ghost" | "danger" | "outline" | "soft";
type BtnSize = "xs" | "sm" | "md" | "lg" | "icon" | "icon-sm";

const btnBase =
  "inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-md font-medium transition-colors " +
  "disabled:pointer-events-none disabled:opacity-50 select-none";
const btnVariants: Record<BtnVariant, string> = {
  primary: "bg-primary text-primary-fg hover:bg-primary/90 shadow-sm",
  secondary: "bg-surface text-fg border border-border-strong hover:bg-subtle shadow-sm",
  outline: "border border-border text-fg hover:bg-subtle",
  ghost: "text-fg-muted hover:text-fg hover:bg-muted",
  soft: "bg-primary-soft text-primary hover:bg-primary-soft/70",
  danger: "bg-danger text-white hover:bg-danger/90 shadow-sm",
};
const btnSizes: Record<BtnSize, string> = {
  xs: "h-6 px-2 text-xs",
  sm: "h-8 px-2.5 text-[13px]",
  md: "h-9 px-3.5 text-sm",
  lg: "h-10 px-4 text-sm",
  icon: "h-9 w-9",
  "icon-sm": "h-7 w-7",
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: BtnVariant;
  size?: BtnSize;
  loading?: boolean;
  icon?: ReactNode;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "secondary", size = "md", loading, icon, className, children, disabled, ...rest }, ref,
) {
  return (
    <button ref={ref} className={cn(btnBase, btnVariants[variant], btnSizes[size], className)} disabled={disabled || loading} {...rest}>
      {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : icon}
      {children}
    </button>
  );
});

/* ---------------- Badge ---------------- */

export type Tone = "neutral" | "primary" | "success" | "warning" | "danger" | "info" | "outline";
const tones: Record<Tone, string> = {
  neutral: "bg-muted text-fg-muted",
  primary: "bg-primary-soft text-primary",
  success: "bg-success-soft text-success",
  warning: "bg-warning-soft text-warning",
  danger: "bg-danger-soft text-danger",
  info: "bg-info-soft text-info",
  outline: "border border-border text-fg-muted",
};

export function Badge({ tone = "neutral", className, children, dot }: { tone?: Tone; className?: string; children: ReactNode; dot?: boolean }) {
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-2xs font-medium whitespace-nowrap", tones[tone], className)}>
      {dot && <span className="h-1.5 w-1.5 rounded-full bg-current" />}
      {children}
    </span>
  );
}

/* ---------------- Card ---------------- */

export function Card({ className, children, ...rest }: { className?: string; children: ReactNode } & React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("rounded-lg border border-border bg-surface shadow-card", className)} {...rest}>{children}</div>;
}

export function CardHeader({ title, description, actions, className }: { title: ReactNode; description?: ReactNode; actions?: ReactNode; className?: string }) {
  return (
    <div className={cn("flex items-start justify-between gap-4 border-b border-border px-5 py-3.5", className)}>
      <div className="min-w-0">
        <h3 className="text-sm font-semibold text-fg">{title}</h3>
        {description && <p className="mt-0.5 text-xs text-fg-subtle">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  );
}

/* ---------------- Form controls ---------------- */

/** Fields fill their container unless the caller passes its own width class. */
const w = (className?: string) => (className && /(^|\s)w-/.test(className) ? "" : "w-full");
const fieldBase =
  "rounded-md border border-border-strong bg-surface px-3 text-sm text-fg placeholder:text-fg-subtle " +
  "transition-colors focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20 disabled:opacity-60";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement> & { icon?: ReactNode }>(function Input(
  { className, icon, ...rest }, ref,
) {
  if (icon) {
    return (
      <div className={cn("relative", className)}>
        <span className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-fg-subtle">{icon}</span>
        <input ref={ref} className={cn(fieldBase, "h-9 w-full pl-8")} {...rest} />
      </div>
    );
  }
  return <input ref={ref} className={cn(fieldBase, w(className), "h-9", className)} {...rest} />;
});

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(function Textarea(
  { className, ...rest }, ref,
) {
  return <textarea ref={ref} className={cn(fieldBase, w(className), "py-2 leading-relaxed", className)} {...rest} />;
});

export function Select({ className, children, ...rest }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      className={cn(
        fieldBase,
        w(className),
        "h-9 appearance-none bg-no-repeat pr-8",
        "bg-[url('data:image/svg+xml;utf8,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%2212%22 height=%2212%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22%23888%22 stroke-width=%222%22><path d=%22m6 9 6 6 6-6%22/></svg>')] bg-[right_0.6rem_center]",
        className,
      )}
      {...rest}
    >
      {children}
    </select>
  );
}

export function Field({ label, hint, children, className, required, aside }: { label: ReactNode; hint?: ReactNode; children: ReactNode; className?: string; required?: boolean; aside?: ReactNode }) {
  return (
    <label className={cn("block", className)}>
      <span className="mb-1.5 flex items-center justify-between gap-2">
        <span className="text-[13px] font-medium text-fg">
          {label}
          {required && <span className="ml-0.5 text-danger">*</span>}
        </span>
        {aside}
      </span>
      {children}
      {hint && <span className="mt-1 block text-xs text-fg-subtle">{hint}</span>}
    </label>
  );
}

export function Switch({ checked, onChange, disabled, label }: { checked: boolean; onChange: (v: boolean) => void; disabled?: boolean; label?: string }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cn(
        "relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors disabled:opacity-50",
        checked ? "bg-primary" : "bg-border-strong",
      )}
    >
      <span className={cn("inline-block h-4 w-4 rounded-full bg-white shadow transition-transform", checked ? "translate-x-[18px]" : "translate-x-0.5")} />
    </button>
  );
}

export function Segmented<T extends string>({ value, onChange, options, size = "md" }: { value: T; onChange: (v: T) => void; options: { value: T; label: ReactNode }[]; size?: "sm" | "md" }) {
  return (
    <div className="inline-flex rounded-md border border-border bg-subtle p-0.5">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          onClick={() => onChange(o.value)}
          className={cn(
            "rounded-[5px] font-medium transition-colors",
            size === "sm" ? "px-2.5 py-1 text-xs" : "px-3 py-1.5 text-[13px]",
            value === o.value ? "bg-surface text-fg shadow-sm" : "text-fg-muted hover:text-fg",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

/* ---------------- Progress / spinner / skeleton ---------------- */

export function Progress({ value, className, tone = "primary" }: { value: number; className?: string; tone?: "primary" | "success" | "warning" }) {
  const bar = { primary: "bg-primary", success: "bg-success", warning: "bg-warning" }[tone];
  return (
    <div className={cn("h-1.5 w-full overflow-hidden rounded-full bg-muted", className)}>
      <div className={cn("h-full rounded-full transition-[width] duration-500", bar)} style={{ width: `${Math.max(0, Math.min(100, value * 100))}%` }} />
    </div>
  );
}

export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={cn("h-4 w-4 animate-spin text-fg-subtle", className)} />;
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("skeleton", className)} />;
}

/* ---------------- Empty state ---------------- */

export function EmptyState({ icon, title, description, action, className }: { icon?: ReactNode; title: ReactNode; description?: ReactNode; action?: ReactNode; className?: string }) {
  return (
    <div className={cn("flex flex-col items-center justify-center px-6 py-14 text-center", className)}>
      {icon && <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl border border-border bg-subtle text-fg-subtle">{icon}</div>}
      <h3 className="text-sm font-semibold text-fg">{title}</h3>
      {description && <p className="mt-1 max-w-sm text-[13px] text-fg-muted">{description}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

/* ---------------- Tooltip ---------------- */

export function Tooltip({ content, children, side = "top", className }: { content: ReactNode; children: ReactNode; side?: "top" | "bottom" | "right" | "left"; className?: string }) {
  const pos = {
    top: "bottom-full left-1/2 -translate-x-1/2 mb-1.5",
    bottom: "top-full left-1/2 -translate-x-1/2 mt-1.5",
    right: "left-full top-1/2 -translate-y-1/2 ml-1.5",
    left: "right-full top-1/2 -translate-y-1/2 mr-1.5",
  }[side];
  return (
    <span className={cn("group/tt relative inline-flex", className)}>
      {children}
      <span
        role="tooltip"
        className={cn(
          "pointer-events-none absolute z-50 w-max max-w-xs rounded-md bg-fg px-2 py-1 text-2xs font-medium text-bg opacity-0 shadow-pop transition-opacity delay-150 group-hover/tt:opacity-100",
          pos,
        )}
      >
        {content}
      </span>
    </span>
  );
}

/* ---------------- Dialog & Drawer ---------------- */

function useEscape(open: boolean, onClose: () => void) {
  useEffect(() => {
    if (!open) return;
    const h = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [open, onClose]);
}

export function Dialog({ open, onClose, title, description, children, footer, width = "max-w-lg" }: { open: boolean; onClose: () => void; title: ReactNode; description?: ReactNode; children: ReactNode; footer?: ReactNode; width?: string }) {
  useEscape(open, onClose);
  if (!open) return null;
  return createPortal(
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/40 p-4 pt-[8vh] backdrop-blur-[2px] animate-fade-in" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div role="dialog" aria-modal="true" className={cn("flex max-h-[86vh] w-full flex-col rounded-xl border border-border bg-surface shadow-pop animate-slide-up", width)}>
        <div className="flex shrink-0 items-start justify-between gap-4 px-6 pb-2 pt-5">
          <div>
            <h2 className="text-base font-semibold text-fg">{title}</h2>
            {description && <p className="mt-1 text-[13px] text-fg-muted">{description}</p>}
          </div>
          <Button variant="ghost" size="icon-sm" onClick={onClose} aria-label="Close"><X className="h-4 w-4" /></Button>
        </div>
        <div className="min-h-0 overflow-y-auto px-6 py-4 scroll-thin">{children}</div>
        {footer && <div className="flex shrink-0 items-center justify-end gap-2 rounded-b-xl border-t border-border bg-subtle/60 px-6 py-3">{footer}</div>}
      </div>
    </div>,
    document.body,
  );
}

export function Drawer({ open, onClose, children, width = "w-[min(860px,92vw)]" }: { open: boolean; onClose: () => void; children: ReactNode; width?: string }) {
  useEscape(open, onClose);
  if (!open) return null;
  return createPortal(
    <div className="fixed inset-0 z-40 flex justify-end bg-black/25 animate-fade-in" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className={cn("flex h-full flex-col border-l border-border bg-surface shadow-pop animate-slide-in-right", width)}>{children}</div>
    </div>,
    document.body,
  );
}

/* ---------------- Tabs ---------------- */

export function Tabs<T extends string>({ value, onChange, tabs, className }: { value: T; onChange: (v: T) => void; tabs: { value: T; label: ReactNode; count?: number }[]; className?: string }) {
  return (
    <div className={cn("scroll-thin flex items-center gap-1 overflow-x-auto border-b border-border", className)} role="tablist">
      {tabs.map((t) => (
        <button
          key={t.value}
          role="tab"
          aria-selected={value === t.value}
          onClick={() => onChange(t.value)}
          className={cn(
            "relative -mb-px flex items-center gap-1.5 whitespace-nowrap border-b-2 px-3 py-2 text-[13px] font-medium transition-colors",
            value === t.value ? "border-primary text-fg" : "border-transparent text-fg-muted hover:text-fg",
          )}
        >
          {t.label}
          {t.count !== undefined && <span className="rounded-full bg-muted px-1.5 text-2xs tabular text-fg-muted">{t.count}</span>}
        </button>
      ))}
    </div>
  );
}

/* ---------------- Menu ---------------- */

export function Menu({ trigger, items, align = "right" }: { trigger: ReactNode; items: ({ label: ReactNode; icon?: ReactNode; onClick: () => void; danger?: boolean; disabled?: boolean } | "sep")[]; align?: "left" | "right" }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const h = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && setOpen(false);
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, [open]);
  return (
    <div ref={ref} className="relative inline-flex">
      <span onClick={(e) => { e.stopPropagation(); setOpen((o) => !o); }}>{trigger}</span>
      {open && (
        <div className={cn("absolute top-full z-30 mt-1 min-w-[180px] rounded-lg border border-border bg-surface p-1 shadow-pop animate-fade-in", align === "right" ? "right-0" : "left-0")}>
          {items.map((it, i) =>
            it === "sep" ? (
              <div key={i} className="my-1 h-px bg-border" />
            ) : (
              <button
                key={i}
                disabled={it.disabled}
                onClick={(e) => { e.stopPropagation(); setOpen(false); it.onClick(); }}
                className={cn(
                  "flex w-full items-center gap-2 rounded-md px-2.5 py-1.5 text-left text-[13px] transition-colors disabled:opacity-40",
                  it.danger ? "text-danger hover:bg-danger-soft" : "text-fg hover:bg-muted",
                )}
              >
                {it.icon && <span className="text-fg-subtle [&>svg]:h-4 [&>svg]:w-4">{it.icon}</span>}
                {it.label}
              </button>
            ),
          )}
        </div>
      )}
    </div>
  );
}

/* ---------------- Toasts ---------------- */

type ToastKind = "success" | "error" | "info";
interface ToastItem { id: number; kind: ToastKind; title: string; detail?: string }
const ToastCtx = createContext<(kind: ToastKind, title: string, detail?: string) => void>(() => {});

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const push = useCallback((kind: ToastKind, title: string, detail?: string) => {
    const id = Date.now() + Math.random();
    setItems((xs) => [...xs.slice(-3), { id, kind, title, detail }]);
    setTimeout(() => setItems((xs) => xs.filter((x) => x.id !== id)), kind === "error" ? 7000 : 4000);
  }, []);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      {createPortal(
        <div className="pointer-events-none fixed bottom-4 right-4 z-[60] flex w-[360px] flex-col gap-2">
          {items.map((t) => (
            <div key={t.id} className="pointer-events-auto flex items-start gap-3 rounded-lg border border-border bg-surface p-3 shadow-pop animate-slide-up">
              {t.kind === "success" && <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success" />}
              {t.kind === "error" && <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-danger" />}
              {t.kind === "info" && <Info className="mt-0.5 h-4 w-4 shrink-0 text-info" />}
              <div className="min-w-0 flex-1">
                <p className="text-[13px] font-medium text-fg">{t.title}</p>
                {t.detail && <p className="mt-0.5 break-words text-xs text-fg-muted">{t.detail}</p>}
              </div>
              <button className="text-fg-subtle hover:text-fg" onClick={() => setItems((xs) => xs.filter((x) => x.id !== t.id))} aria-label="Dismiss">
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}
        </div>,
        document.body,
      )}
    </ToastCtx.Provider>
  );
}

export const useToast = () => useContext(ToastCtx);

/* ---------------- Misc ---------------- */

export function Kbd({ children }: { children: ReactNode }) {
  return <kbd className="rounded border border-border bg-subtle px-1.5 py-0.5 font-mono text-2xs text-fg-muted">{children}</kbd>;
}

export function Stat({ label, value, sub, icon, tone }: { label: string; value: ReactNode; sub?: ReactNode; icon?: ReactNode; tone?: "danger" | "success" | "warning" }) {
  return (
    <Card className="p-4">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-fg-muted">{label}</span>
        {icon && <span className="text-fg-subtle [&>svg]:h-4 [&>svg]:w-4">{icon}</span>}
      </div>
      <div className={cn("mt-2 text-2xl font-semibold tracking-tight tabular", tone === "danger" && "text-danger", tone === "success" && "text-success", tone === "warning" && "text-warning")}>{value}</div>
      {sub && <div className="mt-1 text-xs text-fg-subtle">{sub}</div>}
    </Card>
  );
}

export function PageHeader({ title, description, actions, eyebrow }: { title: ReactNode; description?: ReactNode; actions?: ReactNode; eyebrow?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        {eyebrow && <div className="mb-1 text-xs font-medium uppercase tracking-wider text-fg-subtle">{eyebrow}</div>}
        <h1 className="text-xl font-semibold tracking-tight text-fg">{title}</h1>
        {description && <p className="mt-1 max-w-2xl text-[13px] text-fg-muted">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}
