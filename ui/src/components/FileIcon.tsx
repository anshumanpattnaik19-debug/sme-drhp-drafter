import { FileImage, FileSpreadsheet, FileText, FileType2, ScanLine } from "lucide-react";
import { cn } from "../lib/utils";

const STYLE: Record<string, { cls: string; icon: JSX.Element; label: string }> = {
  pdf: { cls: "bg-danger-soft text-danger", icon: <FileText />, label: "PDF" },
  pdf_scanned: { cls: "bg-warning-soft text-warning", icon: <ScanLine />, label: "SCAN" },
  pdf_mixed: { cls: "bg-warning-soft text-warning", icon: <ScanLine />, label: "PDF" },
  docx: { cls: "bg-info-soft text-info", icon: <FileType2 />, label: "DOC" },
  xlsx: { cls: "bg-success-soft text-success", icon: <FileSpreadsheet />, label: "XLS" },
  image: { cls: "bg-primary-soft text-primary", icon: <FileImage />, label: "IMG" },
  text: { cls: "bg-muted text-fg-muted", icon: <FileText />, label: "TXT" },
};

export function FileIcon({ format, size = "md" }: { format: string; size?: "sm" | "md" | "lg" }) {
  const s = STYLE[format] ?? STYLE.text;
  return (
    <span
      className={cn(
        "flex shrink-0 items-center justify-center rounded-md",
        s.cls,
        size === "sm" && "h-6 w-6 [&>svg]:h-3.5 [&>svg]:w-3.5",
        size === "md" && "h-8 w-8 [&>svg]:h-4 [&>svg]:w-4",
        size === "lg" && "h-10 w-10 [&>svg]:h-5 [&>svg]:w-5",
      )}
      title={s.label}
    >
      {s.icon}
    </span>
  );
}
