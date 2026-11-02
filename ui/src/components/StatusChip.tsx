import { AlertTriangle, CheckCircle2, Clock, Loader2, XCircle } from "lucide-react";
import type { IssuerFile } from "../lib/types";
import { Badge, Tooltip } from "./ui";

export function FileStatusChip({ f }: { f: IssuerFile }) {
  if (f.status === "processing") return <Badge tone="primary"><Loader2 className="h-3 w-3 animate-spin" /> Reading</Badge>;
  if (f.status === "queued") return <Badge tone="neutral"><Clock className="h-3 w-3" /> Queued</Badge>;
  if (f.status === "failed")
    return (
      <Tooltip content={f.error || "Failed"}>
        <Badge tone="danger"><XCircle className="h-3 w-3" /> Failed</Badge>
      </Tooltip>
    );
  if (f.needs_ocr_pages)
    return (
      <Tooltip content={`${f.needs_ocr_pages} scanned page(s) not read. ${f.warnings?.[0] ?? ""}`}>
        <Badge tone="warning"><AlertTriangle className="h-3 w-3" /> {f.needs_ocr_pages} p. unread</Badge>
      </Tooltip>
    );
  return (
    <Badge tone="success">
      <CheckCircle2 className="h-3 w-3" /> {f.ocr_pages ? `Read · OCR ${f.ocr_pages}p` : "Read"}
    </Badge>
  );
}
