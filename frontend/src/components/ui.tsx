/**
 * ProDesk Design System Primitives
 * Professional, calm, high-density workspace UI components.
 */
import {
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Info,
  Loader2,
  X,
} from "lucide-react";
import {
  forwardRef,
  isValidElement,
  useEffect,
  useId,
  type ButtonHTMLAttributes,
  type ComponentType,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from "react";
import { cn, humanize } from "../utils/format";

/* -------------------------------------------------------------------------- */
/*                                   BUTTONS                                  */
/* -------------------------------------------------------------------------- */

export type ButtonVariant = "primary" | "secondary" | "outline" | "ghost" | "danger" | "subtle";
export type ButtonSize = "xs" | "sm" | "md" | "lg";

const buttonVariants: Record<ButtonVariant, string> = {
  primary:
    "bg-brand-700 text-white hover:bg-brand-800 shadow-sm border border-brand-800/20 focus-visible:ring-brand-500 disabled:bg-brand-700/60",
  secondary:
    "border border-ink-200 bg-white text-ink-800 hover:bg-ink-50 hover:text-ink-950 shadow-sm focus-visible:ring-ink-400 disabled:bg-ink-50",
  outline:
    "border border-ink-300 text-ink-700 hover:bg-ink-50 hover:border-ink-400 focus-visible:ring-ink-400",
  ghost:
    "text-ink-600 hover:bg-ink-100/70 hover:text-ink-900 focus-visible:ring-ink-300",
  danger:
    "bg-rose-600 text-white hover:bg-rose-700 shadow-sm focus-visible:ring-rose-500 disabled:bg-rose-600/60",
  subtle:
    "bg-brand-50 text-brand-800 hover:bg-brand-100 border border-brand-200/60 focus-visible:ring-brand-500",
};

const buttonSizes: Record<ButtonSize, string> = {
  xs: "h-7 px-2 text-[11px] font-medium gap-1 rounded-md",
  sm: "h-8 px-2.5 text-xs font-medium gap-1.5 rounded-lg",
  md: "h-9 px-3.5 text-sm font-medium gap-2 rounded-lg",
  lg: "h-10 px-4 text-sm font-medium gap-2 rounded-lg",
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "primary", size = "md", loading, className, children, disabled, ...props },
  ref
) {
  return (
    <button
      ref={ref}
      {...props}
      disabled={disabled || loading}
      className={cn(
        "inline-flex items-center justify-center whitespace-nowrap font-medium transition-all duration-150 select-none",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-1",
        "active:scale-[0.985] disabled:cursor-not-allowed disabled:opacity-60 disabled:active:scale-100",
        buttonSizes[size],
        buttonVariants[variant],
        className
      )}
    >
      {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
      {children}
    </button>
  );
});

export function IconButton({
  icon: Icon,
  label,
  variant = "ghost",
  size = "md",
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  variant?: ButtonVariant;
  size?: ButtonSize;
}) {
  const iconSizes = {
    xs: "h-3.5 w-3.5",
    sm: "h-4 w-4",
    md: "h-4 w-4",
    lg: "h-5 w-5",
  };
  const boxSizes = {
    xs: "h-7 w-7 rounded-md",
    sm: "h-8 w-8 rounded-lg",
    md: "h-9 w-9 rounded-lg",
    lg: "h-10 w-10 rounded-lg",
  };
  return (
    <button
      {...props}
      aria-label={label}
      title={label}
      className={cn(
        "inline-flex items-center justify-center text-ink-600 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-1 disabled:opacity-50",
        boxSizes[size],
        buttonVariants[variant],
        className
      )}
    >
      <Icon className={iconSizes[size]} />
    </button>
  );
}

/* -------------------------------------------------------------------------- */
/*                                FORM FIELDS                                 */
/* -------------------------------------------------------------------------- */

const fieldBase =
  "block w-full rounded-lg border border-ink-200 bg-white px-3 py-2 text-sm text-ink-900 shadow-xs " +
  "placeholder:text-ink-400 hover:border-ink-300 focus:border-brand-600 focus:outline-none focus:ring-2 " +
  "focus:ring-brand-500/20 disabled:bg-ink-50/70 disabled:text-ink-400 disabled:cursor-not-allowed transition-all duration-150";

export function Field({
  label,
  hint,
  error,
  children,
  htmlFor,
  className,
}: {
  label: string;
  hint?: string;
  error?: string;
  required?: boolean;
  children: ReactNode;
  htmlFor?: string;
  className?: string;
}) {
  return (
    <div className={cn("space-y-1.5", className)}>
      <label htmlFor={htmlFor} className="block text-xs font-semibold text-ink-700 tracking-tight">
        {label}
      </label>
      {children}
      {error ? (
        <p className="flex items-center gap-1 text-xs font-medium text-rose-600 animate-fade-in">
          <AlertCircle className="h-3 w-3 shrink-0" />
          {error}
        </p>
      ) : hint ? (
        <p className="text-xs text-ink-500">{hint}</p>
      ) : null}
    </div>
  );
}

export function Input({
  label,
  hint,
  error,
  required,
  className,
  icon: Icon,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & {
  label?: string;
  hint?: string;
  error?: string;
  icon?: React.ComponentType<{ className?: string }>;
}) {
  const id = useId();
  const inputId = props.id ?? id;
  const inputEl = (
    <div className="relative flex items-center">
      {Icon && (
        <div className="pointer-events-none absolute left-3 flex items-center text-ink-400">
          <Icon className="h-4 w-4" />
        </div>
      )}
      <input
        id={inputId}
        {...props}
        className={cn(fieldBase, Icon && "pl-9", error && "border-rose-300 focus:border-rose-500 focus:ring-rose-500/20", className)}
      />
    </div>
  );

  return label ? (
    <Field label={label} hint={hint} error={error} required={required} htmlFor={inputId}>
      {inputEl}
    </Field>
  ) : (
    inputEl
  );
}

export function Textarea({
  label,
  hint,
  error,
  required,
  className,
  rows = 3,
  ...props
}: TextareaHTMLAttributes<HTMLTextAreaElement> & {
  label?: string;
  hint?: string;
  error?: string;
}) {
  const id = useId();
  const inputId = props.id ?? id;
  const el = (
    <textarea
      id={inputId}
      rows={rows}
      {...props}
      className={cn(fieldBase, error && "border-rose-300 focus:border-rose-500 focus:ring-rose-500/20", className)}
    />
  );
  return label ? (
    <Field label={label} hint={hint} error={error} required={required} htmlFor={inputId}>
      {el}
    </Field>
  ) : (
    el
  );
}

export function Select({
  label,
  options,
  placeholder,
  hint,
  error,
  required,
  className,
  ...props
}: SelectHTMLAttributes<HTMLSelectElement> & {
  label?: string;
  options: readonly (string | { value: string; label: string })[];
  placeholder?: string;
  hint?: string;
  error?: string;
}) {
  const id = useId();
  const selectId = props.id ?? id;
  const el = (
    <div className="relative">
      <select
        id={selectId}
        {...props}
        className={cn(
          fieldBase,
          "appearance-none pr-8 bg-no-repeat cursor-pointer",
          error && "border-rose-300 focus:border-rose-500 focus:ring-rose-500/20",
          className
        )}
      >
        {placeholder !== undefined && <option value="">{placeholder}</option>}
        {options.map((o) =>
          typeof o === "string" ? (
            <option key={o} value={o}>
              {humanize(o)}
            </option>
          ) : (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          )
        )}
      </select>
      <div className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-ink-400">
        <ChevronRight className="h-4 w-4 rotate-90" />
      </div>
    </div>
  );
  return label ? (
    <Field label={label} hint={hint} error={error} required={required} htmlFor={selectId}>
      {el}
    </Field>
  ) : (
    el
  );
}

/* -------------------------------------------------------------------------- */
/*                                   BADGES                                   */
/* -------------------------------------------------------------------------- */

const toneClasses: Record<string, { bg: string; text: string; border: string; dot: string }> = {
  green: {
    bg: "bg-emerald-50/80",
    text: "text-emerald-800",
    border: "border-emerald-200/80",
    dot: "bg-emerald-500",
  },
  blue: {
    bg: "bg-sky-50/80",
    text: "text-sky-800",
    border: "border-sky-200/80",
    dot: "bg-sky-500",
  },
  amber: {
    bg: "bg-amber-50/80",
    text: "text-amber-800",
    border: "border-amber-200/80",
    dot: "bg-amber-500",
  },
  red: {
    bg: "bg-rose-50/80",
    text: "text-rose-800",
    border: "border-rose-200/80",
    dot: "bg-rose-500",
  },
  gray: {
    bg: "bg-slate-100/70",
    text: "text-slate-700",
    border: "border-slate-200",
    dot: "bg-slate-400",
  },
  violet: {
    bg: "bg-violet-50/80",
    text: "text-violet-800",
    border: "border-violet-200/80",
    dot: "bg-violet-500",
  },
};

const STATUS_TONE: Record<string, keyof typeof toneClasses> = {
  APPROVED: "green",
  DELIVERED: "green",
  COMPLETED: "green",
  COMPLETE: "green",
  PAID: "green",
  SENT: "blue",
  READ: "green",
  RECEIVED: "green",
  ACTIVE: "green",
  FILED: "green",
  DOWNLOADED: "green",
  OPTED_IN: "green",
  RESOLVED: "green",
  CAPTURED: "green",
  UPLOADED: "gray",
  NEW_REQUEST: "gray",
  DRAFT: "gray",
  PENDING: "amber",
  QUEUED: "gray",
  NOT_SUBMITTED: "gray",
  BOT: "gray",
  UNDER_REVIEW: "violet",
  WORK_IN_PROGRESS: "blue",
  DOCUMENTS_PENDING: "amber",
  DOCUMENTS_RECEIVED: "blue",
  PARTIAL: "blue",
  PARTIALLY_PAID: "blue",
  IN_PROGRESS: "blue",
  OPEN: "blue",
  AGENT_ASSIGNED: "violet",
  HUMAN_ACTIVE: "violet",
  BOT_RESUMED: "gray",
  REJECTED: "red",
  FAILED: "red",
  OVERDUE: "red",
  CANCELLED: "gray",
  ARCHIVED: "gray",
  HUMAN_REQUESTED: "amber",
  ERROR: "red",
  INACTIVE: "gray",
  OPTED_OUT: "red",
  NOT_OPTED_IN: "amber",
  URGENT: "red",
  HIGH: "amber",
  MEDIUM: "gray",
  LOW: "gray",
  PAUSED: "amber",
  DISABLED: "gray",
};

export function Badge({
  value,
  label,
  color,
  showDot = true,
  className,
}: {
  value: string;
  label?: string;
  color?: keyof typeof toneClasses;
  showDot?: boolean;
  className?: string;
}) {
  const chosenTone = color ?? STATUS_TONE[value] ?? "gray";
  const t = toneClasses[chosenTone] ?? toneClasses.gray;

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 whitespace-nowrap rounded-md px-2 py-0.5 text-[11px] font-medium border shadow-2xs select-none",
        t.bg,
        t.text,
        t.border,
        className
      )}
    >
      {showDot && <span className={cn("h-1.5 w-1.5 rounded-full shrink-0", t.dot)} />}
      <span>{label ?? humanize(value)}</span>
    </span>
  );
}

/* -------------------------------------------------------------------------- */
/*                               CARDS & PANELS                               */
/* -------------------------------------------------------------------------- */

export function Card({
  title,
  subtitle,
  description,
  actions,
  children,
  className,
  padded = true,
  footer,
}: {
  title?: ReactNode;
  subtitle?: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  padded?: boolean;
  footer?: ReactNode;
}) {
  const sub = subtitle ?? description;
  return (
    <section
      className={cn(
        "rounded-xl border border-ink-200/80 bg-white shadow-card transition-all duration-150 overflow-hidden",
        className
      )}
    >
      {(title || actions || sub) && (
        <header className="flex flex-wrap items-center justify-between gap-3 border-b border-ink-100/80 px-5 py-3.5 bg-white">
          <div className="min-w-0">
            {title && <h2 className="text-sm font-semibold text-ink-950 tracking-tight">{title}</h2>}
            {sub && <p className="text-xs text-ink-500 mt-0.5">{sub}</p>}
          </div>
          {actions && <div className="flex items-center gap-2 shrink-0">{actions}</div>}
        </header>
      )}
      <div className={padded ? "p-5" : ""}>{children}</div>
      {footer && (
        <footer className="border-t border-ink-100/80 bg-ink-50/50 px-5 py-3 text-xs text-ink-500">
          {footer}
        </footer>
      )}
    </section>
  );
}

export function StatCard({
  label,
  value,
  hint,
  tone = "default",
  icon: Icon,
  badge,
  onClick,
  className,
}: {
  label: string;
  value: ReactNode;
  hint?: string;
  tone?: "default" | "warn" | "danger" | "good";
  icon?: React.ComponentType<{ className?: string }>;
  badge?: ReactNode;
  onClick?: () => void;
  className?: string;
}) {
  const accent = {
    default: "text-ink-950",
    warn: "text-amber-700",
    danger: "text-rose-700",
    good: "text-brand-700",
  }[tone];

  const toneBg = {
    default: "hover:border-ink-300",
    warn: "hover:border-amber-300",
    danger: "hover:border-rose-300",
    good: "hover:border-brand-300",
  }[tone];

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={!onClick}
      className={cn(
        "group relative flex w-full flex-col items-start rounded-xl border border-ink-200/80 bg-white p-4 text-left shadow-card transition-all duration-150",
        onClick ? "cursor-pointer hover:shadow-card-hover" : "cursor-default",
        toneBg,
        className
      )}
    >
      <div className="flex w-full items-center justify-between gap-2">
        <span className="text-xs font-semibold uppercase tracking-wider text-ink-500">{label}</span>
        <div className="flex items-center gap-1.5">
          {badge}
          {Icon && (
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-ink-100/70 text-ink-600 transition-colors group-hover:bg-brand-50 group-hover:text-brand-700">
              <Icon className="h-4 w-4" />
            </div>
          )}
        </div>
      </div>
      <span className={cn("mt-2 text-2xl font-bold tracking-tight tabular-nums", accent)}>
        {value}
      </span>
      {hint && <span className="mt-1 text-xs text-ink-500 font-normal">{hint}</span>}
    </button>
  );
}

export function PageHeader({
  title,
  subtitle,
  actions,
  breadcrumbs,
}: {
  title: string;
  subtitle?: ReactNode;
  actions?: ReactNode;
  breadcrumbs?: { label: string; href?: string }[];
}) {
  return (
    <div className="mb-6 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0">
        {breadcrumbs && (
          <nav aria-label="Breadcrumb" className="mb-1 flex items-center gap-1.5 text-xs text-ink-500">
            {breadcrumbs.map((b, i) => (
              <span key={i} className="flex items-center gap-1.5">
                {b.href ? (
                  <a href={b.href} className="hover:text-ink-800 transition-colors">
                    {b.label}
                  </a>
                ) : (
                  <span>{b.label}</span>
                )}
                {i < breadcrumbs.length - 1 && <span className="text-ink-300">/</span>}
              </span>
            ))}
          </nav>
        )}
        <h1 className="text-2xl font-bold tracking-tight text-ink-950">{title}</h1>
        {subtitle && <div className="mt-1 text-sm text-ink-500">{subtitle}</div>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2.5 shrink-0 pt-1">{actions}</div>}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/*                                    TABS                                    */
/* -------------------------------------------------------------------------- */

export function Tabs({
  tabs,
  value,
  onChange,
  variant = "line",
  className,
}: {
  tabs: { value: string; label: string; count?: number; icon?: React.ComponentType<{ className?: string }> }[];
  value: string;
  onChange: (v: string) => void;
  variant?: "line" | "pill";
  className?: string;
}) {
  if (variant === "pill") {
    return (
      <div
        role="tablist"
        className={cn(
          "inline-flex items-center gap-1 rounded-xl bg-ink-100/80 p-1 border border-ink-200/50",
          className
        )}
      >
        {tabs.map((t) => {
          const active = value === t.value;
          const Icon = t.icon;
          return (
            <button
              key={t.value}
              role="tab"
              aria-selected={active}
              onClick={() => onChange(t.value)}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition-all duration-150 select-none",
                active
                  ? "bg-white text-ink-950 shadow-xs"
                  : "text-ink-600 hover:text-ink-950 hover:bg-white/40"
              )}
            >
              {Icon && <Icon className="h-3.5 w-3.5" />}
              <span>{t.label}</span>
              {t.count !== undefined && (
                <span
                  className={cn(
                    "rounded-full px-1.5 py-0.2 text-[10px] tabular-nums font-bold",
                    active ? "bg-brand-50 text-brand-700" : "bg-ink-200/70 text-ink-600"
                  )}
                >
                  {t.count}
                </span>
              )}
            </button>
          );
        })}
      </div>
    );
  }

  return (
    <div role="tablist" className={cn("flex gap-4 overflow-x-auto border-b border-ink-200/80", className)}>
      {tabs.map((t) => {
        const active = value === t.value;
        const Icon = t.icon;
        return (
          <button
            key={t.value}
            role="tab"
            aria-selected={active}
            onClick={() => onChange(t.value)}
            className={cn(
              "-mb-px inline-flex items-center gap-2 whitespace-nowrap border-b-2 py-3 px-1 text-sm font-medium transition-all duration-150",
              active
                ? "border-brand-600 text-brand-900 font-semibold"
                : "border-transparent text-ink-500 hover:border-ink-300 hover:text-ink-800"
            )}
          >
            {Icon && <Icon className="h-4 w-4" />}
            <span>{t.label}</span>
            {t.count !== undefined && (
              <span
                className={cn(
                  "rounded-full px-2 py-0.5 text-[11px] font-semibold tabular-nums transition-colors",
                  active ? "bg-brand-100 text-brand-800" : "bg-ink-100 text-ink-600"
                )}
              >
                {t.count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/*                                    TABLE                                   */
/* -------------------------------------------------------------------------- */

export interface Column<T> {
  key: string;
  header: ReactNode;
  render: (row: T) => ReactNode;
  className?: string;
  headerClassName?: string;
}

export function Table<T extends { id: string }>({
  rows,
  columns,
  onRowClick,
  empty,
  className,
}: {
  rows: T[];
  columns: Column<T>[];
  onRowClick?: (r: T) => void;
  empty?: ReactNode;
  className?: string;
}) {
  if (!rows.length) {
    return <>{empty ?? <EmptyState title="Nothing here yet" />}</>;
  }

  return (
    <div className={cn("overflow-x-auto", className)}>
      <table className="min-w-full text-sm">
        <thead>
          <tr className="border-b border-ink-100/90 bg-ink-50/50 text-left text-[11px] font-semibold uppercase tracking-wider text-ink-500">
            {columns.map((c) => (
              <th key={c.key} className={cn("px-4 py-3 first:pl-5 last:pr-5", c.headerClassName ?? c.className)}>
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-ink-100/80 bg-white">
          {rows.map((r) => (
            <tr
              key={r.id}
              onClick={onRowClick ? () => onRowClick(r) : undefined}
              className={cn(
                "group transition-colors duration-100 text-ink-800",
                onRowClick && "cursor-pointer hover:bg-ink-50/70"
              )}
            >
              {columns.map((c) => (
                <td key={c.key} className={cn("px-4 py-3 align-middle first:pl-5 last:pr-5", c.className)}>
                  {c.render(r)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Pagination({
  page,
  pageSize,
  total,
  onPage,
}: {
  page: number;
  pageSize: number;
  total: number;
  onPage: (p: number) => void;
}) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  if (total <= pageSize) return null;
  const start = (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, total);

  return (
    <div className="flex items-center justify-between border-t border-ink-100/80 bg-white px-5 py-3 text-xs text-ink-500">
      <span>
        Showing <span className="font-semibold text-ink-900 tabular-nums">{start}</span>–
        <span className="font-semibold text-ink-900 tabular-nums">{end}</span> of{" "}
        <span className="font-semibold text-ink-900 tabular-nums">{total}</span> items
      </span>
      <div className="flex items-center gap-1.5">
        <Button
          size="sm"
          variant="outline"
          aria-label="Previous page"
          disabled={page <= 1}
          onClick={() => onPage(page - 1)}
        >
          <ChevronLeft className="h-3.5 w-3.5" />
          <span>Prev</span>
        </Button>
        <span className="px-2 font-medium text-ink-700">
          Page {page} of {pages}
        </span>
        <Button
          size="sm"
          variant="outline"
          aria-label="Next page"
          disabled={page >= pages}
          onClick={() => onPage(page + 1)}
        >
          <span>Next</span>
          <ChevronRight className="h-3.5 w-3.5" />
        </Button>
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/*                                 EMPTY STATE                                */
/* -------------------------------------------------------------------------- */

export function EmptyState({
  title,
  hint,
  description,
  icon: IconOrNode = Info,
  action,
  className,
}: {
  title: string;
  hint?: string;
  description?: string;
  icon?: ComponentType<{ className?: string }> | ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  const renderedHint = hint ?? description;
  const isElement = isValidElement(IconOrNode);
  const IconComponent = !isElement ? (IconOrNode as ComponentType<{ className?: string }>) : null;

  return (
    <div className={cn("flex flex-col items-center justify-center gap-2 px-6 py-14 text-center", className)}>
      <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-ink-100/80 border border-ink-200/50 text-ink-500 mb-2">
        {isElement ? IconOrNode : IconComponent ? <IconComponent className="h-6 w-6" /> : null}
      </div>
      <h3 className="text-sm font-semibold text-ink-900">{title}</h3>
      {renderedHint && <p className="max-w-sm text-xs text-ink-500 leading-relaxed">{renderedHint}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/*                                   SPINNER                                  */
/* -------------------------------------------------------------------------- */

export function Spinner({ label = "Loading ProDesk…" }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2.5 py-16 text-xs text-ink-500">
      <Loader2 className="h-5 w-5 animate-spin text-brand-600" />
      <span>{label}</span>
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-md bg-ink-200/60", className)} />;
}

/* -------------------------------------------------------------------------- */
/*                                   ALERTS                                   */
/* -------------------------------------------------------------------------- */

export function ErrorBox({ error }: { error: unknown }) {
  if (!error) return null;
  const msg = error instanceof Error ? error.message : String(error);
  return (
    <div
      role="alert"
      className="flex items-start gap-2.5 rounded-lg border border-rose-200 bg-rose-50/90 px-3.5 py-2.5 text-xs text-rose-800 shadow-2xs"
    >
      <AlertTriangle className="h-4 w-4 shrink-0 text-rose-600 mt-0.5" />
      <div className="flex-1 font-medium leading-relaxed">{msg}</div>
    </div>
  );
}

export function Alert({
  variant = "info",
  title,
  children,
  className,
}: {
  variant?: "info" | "warning" | "success" | "error";
  title?: string;
  children: ReactNode;
  className?: string;
}) {
  const configs = {
    info: { bg: "bg-sky-50", border: "border-sky-200", text: "text-sky-800", icon: Info },
    warning: { bg: "bg-amber-50", border: "border-amber-200", text: "text-amber-800", icon: AlertTriangle },
    success: { bg: "bg-emerald-50", border: "border-emerald-200", text: "text-emerald-800", icon: CheckCircle2 },
    error: { bg: "bg-rose-50", border: "border-rose-200", text: "text-rose-800", icon: AlertCircle },
  }[variant];
  const Icon = configs.icon;

  return (
    <div className={cn("flex items-start gap-3 rounded-lg border p-3.5 text-xs", configs.bg, configs.border, configs.text, className)}>
      <Icon className="h-4 w-4 shrink-0 mt-0.5" />
      <div className="space-y-0.5">
        {title && <p className="font-semibold">{title}</p>}
        <div className="leading-relaxed font-normal">{children}</div>
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/*                                    MODAL                                   */
/* -------------------------------------------------------------------------- */

export function Modal({
  open,
  onClose,
  title,
  subtitle,
  description,
  children,
  footer,
  wide,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  subtitle?: string;
  description?: string;
  children: ReactNode;
  footer?: ReactNode;
  wide?: boolean;
}) {
  const sub = subtitle ?? description;
  useEffect(() => {
    if (!open) return;
    const h = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-ink-950/40 p-4 pt-[6vh] backdrop-blur-xs animate-fade-in"
      onMouseDown={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onMouseDown={(e) => e.stopPropagation()}
        className={cn(
          "w-full rounded-2xl border border-ink-200 bg-white shadow-modal overflow-hidden animate-slide-down",
          wide ? "max-w-3xl" : "max-w-lg"
        )}
      >
        <div className="flex items-center justify-between border-b border-ink-100 px-6 py-4">
          <div>
            <h3 className="text-base font-semibold text-ink-950 tracking-tight">{title}</h3>
            {sub && <p className="text-xs text-ink-500 mt-0.5">{sub}</p>}
          </div>
          <button
            aria-label="Close"
            onClick={onClose}
            className="rounded-lg p-1.5 text-ink-400 hover:bg-ink-100 hover:text-ink-700 transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="max-h-[72vh] overflow-y-auto px-6 py-5">{children}</div>
        {footer && (
          <div className="flex items-center justify-end gap-2.5 border-t border-ink-100/90 bg-ink-50/50 px-6 py-3.5">
            {footer}
          </div>
        )}
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/*                                   DRAWER                                   */
/* -------------------------------------------------------------------------- */

export function Drawer({
  open,
  onClose,
  title,
  subtitle,
  children,
  footer,
  width = "max-w-md",
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  subtitle?: string;
  children: ReactNode;
  footer?: ReactNode;
  width?: string;
}) {
  useEffect(() => {
    if (!open) return;
    const h = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-hidden bg-ink-950/30 backdrop-blur-xs animate-fade-in" onMouseDown={onClose}>
      <div className="absolute inset-y-0 right-0 flex max-w-full pl-10">
        <div
          role="dialog"
          aria-modal="true"
          aria-label={title}
          onMouseDown={(e) => e.stopPropagation()}
          className={cn(
            "w-screen bg-white shadow-modal flex flex-col border-l border-ink-200 animate-slide-left",
            width
          )}
        >
          <div className="flex items-center justify-between border-b border-ink-100 px-6 py-4">
            <div>
              <h3 className="text-base font-semibold text-ink-950 tracking-tight">{title}</h3>
              {subtitle && <p className="text-xs text-ink-500 mt-0.5">{subtitle}</p>}
            </div>
            <button
              aria-label="Close"
              onClick={onClose}
              className="rounded-lg p-1.5 text-ink-400 hover:bg-ink-100 hover:text-ink-700 transition-colors"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
          <div className="flex-1 overflow-y-auto px-6 py-5">{children}</div>
          {footer && (
            <div className="border-t border-ink-100/90 bg-ink-50/50 px-6 py-3.5 flex items-center justify-end gap-2.5">
              {footer}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/*                                   AVATAR                                   */
/* -------------------------------------------------------------------------- */

const AVATAR_PALETTE = [
  "bg-teal-600 text-white",
  "bg-emerald-600 text-white",
  "bg-sky-600 text-white",
  "bg-indigo-600 text-white",
  "bg-violet-600 text-white",
  "bg-amber-600 text-white",
  "bg-rose-600 text-white",
  "bg-slate-700 text-white",
];

function stringToColor(str: string): string {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = str.charCodeAt(i) + ((hash << 5) - hash);
  }
  return AVATAR_PALETTE[Math.abs(hash) % AVATAR_PALETTE.length];
}

export function Avatar({
  name,
  src,
  size = "md",
  className,
}: {
  name: string;
  src?: string | null;
  size?: "xs" | "sm" | "md" | "lg" | "xl";
  className?: string;
}) {
  const initials = name
    .split(" ")
    .filter(Boolean)
    .map((p) => p[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();

  const sizeClasses = {
    xs: "h-6 w-6 text-[10px]",
    sm: "h-7 w-7 text-xs",
    md: "h-8 w-8 text-xs font-semibold",
    lg: "h-10 w-10 text-sm font-semibold",
    xl: "h-12 w-12 text-base font-semibold",
  }[size];

  if (src) {
    return (
      <img
        src={src}
        alt={name}
        className={cn("rounded-full object-cover shrink-0 ring-1 ring-ink-200", sizeClasses, className)}
      />
    );
  }

  return (
    <div
      title={name}
      className={cn(
        "rounded-full flex items-center justify-center shrink-0 tracking-tight font-medium ring-1 ring-white/20 select-none shadow-2xs",
        stringToColor(name),
        sizeClasses,
        className
      )}
    >
      {initials || "?"}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/*                                KEY VALUE LIST                              */
/* -------------------------------------------------------------------------- */

export function KeyValue({ items }: { items: [string, ReactNode][] }) {
  return (
    <dl className="grid grid-cols-1 gap-x-6 gap-y-3.5 sm:grid-cols-2">
      {items.map(([k, v]) => (
        <div key={k} className="space-y-0.5">
          <dt className="text-xs font-medium text-ink-500 uppercase tracking-wider">{k}</dt>
          <dd className="text-sm font-medium text-ink-900 break-words">{v ?? "—"}</dd>
        </div>
      ))}
    </dl>
  );
}

/* -------------------------------------------------------------------------- */
/*                                PROGRESS BAR                                */
/* -------------------------------------------------------------------------- */

export function ProgressBar({
  value,
  max = 100,
  className,
  color = "brand",
}: {
  value: number;
  max?: number;
  className?: string;
  color?: "brand" | "amber" | "rose" | "blue";
}) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100));
  const bg = {
    brand: "bg-brand-600",
    amber: "bg-amber-500",
    rose: "bg-rose-500",
    blue: "bg-sky-500",
  }[color];

  return (
    <div className={cn("h-1.5 w-full overflow-hidden rounded-full bg-ink-100", className)}>
      <div className={cn("h-full transition-all duration-300 rounded-full", bg)} style={{ width: `${pct}%` }} />
    </div>
  );
}
