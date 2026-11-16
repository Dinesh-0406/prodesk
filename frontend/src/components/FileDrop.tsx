import { FileText, UploadCloud } from "lucide-react";
import { useRef, useState } from "react";
import { cn, fileSize } from "../utils/format";

export const ACCEPT = ".pdf,.jpg,.jpeg,.png,.doc,.docx,.xls,.xlsx";

export function FileDrop({
  file,
  onFile,
  label = "Drop a file here or click to browse",
}: {
  file: File | null;
  onFile: (f: File | null) => void;
  label?: string;
}) {
  const ref = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setOver(false);
        onFile(e.dataTransfer.files[0] ?? null);
      }}
      onClick={() => ref.current?.click()}
      className={cn(
        "group flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed p-6 text-center transition-all duration-150 select-none",
        over
          ? "border-brand-600 bg-brand-50/70"
          : "border-ink-200/90 bg-ink-50/30 hover:border-brand-400 hover:bg-brand-50/20"
      )}
    >
      <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-white border border-ink-200/80 shadow-2xs group-hover:scale-105 transition-transform">
        {file ? (
          <FileText className="h-5 w-5 text-brand-700" />
        ) : (
          <UploadCloud className="h-5 w-5 text-ink-500 group-hover:text-brand-600" />
        )}
      </div>

      {file ? (
        <div className="space-y-0.5">
          <p className="text-xs font-semibold text-ink-950 truncate max-w-sm">{file.name}</p>
          <p className="text-[11px] text-ink-500 tabular-nums">{fileSize(file.size)}</p>
        </div>
      ) : (
        <div className="space-y-0.5">
          <p className="text-xs font-semibold text-ink-800">{label}</p>
          <p className="text-[11px] text-ink-400">PDF, JPG, PNG, Word, Excel · up to 25 MB</p>
        </div>
      )}

      <input
        ref={ref}
        type="file"
        accept={ACCEPT}
        className="hidden"
        data-testid="file-input"
        onChange={(e) => onFile(e.target.files?.[0] ?? null)}
      />
    </div>
  );
}
