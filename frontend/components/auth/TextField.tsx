import type { InputHTMLAttributes, Ref } from "react";

interface Props extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  error?: string;
  hint?: string;
  ref?: Ref<HTMLInputElement>;
}

export function TextField({ label, error, hint, id, ref, ...rest }: Props) {
  const fieldId = id ?? rest.name ?? label;
  const describedBy = [error ? `${fieldId}-error` : null, hint ? `${fieldId}-hint` : null].filter(Boolean).join(" ") || undefined;
  return (
    <div>
      <label htmlFor={fieldId} className="mb-1.5 block text-sm font-semibold">
        {label}
      </label>
      <input
        id={fieldId}
        ref={ref}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        className={`w-full rounded-lg border bg-panel px-4 py-3 text-text placeholder:text-muted ${error ? "border-red" : "border-line"}`}
        {...rest}
      />
      {hint && !error && (
        <p id={`${fieldId}-hint`} className="mt-1.5 text-sm text-muted">
          {hint}
        </p>
      )}
      {error && (
        <p id={`${fieldId}-error`} role="alert" className="mt-1.5 text-sm text-red">
          {error}
        </p>
      )}
    </div>
  );
}
