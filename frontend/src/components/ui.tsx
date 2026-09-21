// Small UI primitives shared across pages.
import { type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes, forwardRef } from "react";

type ClassNames = string | false | null | undefined;
export function cn(...xs: ClassNames[]): string {
  return xs.filter(Boolean).join(" ");
}

const baseField =
  "block w-full rounded border border-slate-300 px-2 py-1 text-sm focus:border-blue-600 focus:outline-none";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(function Input(
  { className, ...rest },
  ref,
) {
  return <input ref={ref} className={cn(baseField, className)} {...rest} />;
});

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(
  function Textarea({ className, ...rest }, ref) {
    return <textarea ref={ref} className={cn(baseField, "min-h-[80px]", className)} {...rest} />;
  },
);

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(function Select(
  { className, ...rest },
  ref,
) {
  return <select ref={ref} className={cn(baseField, "bg-white", className)} {...rest} />;
});

export function Button({
  variant = "primary",
  className,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "danger" }) {
  const styles =
    variant === "primary"
      ? "bg-blue-700 text-white hover:bg-blue-800"
      : variant === "danger"
        ? "bg-red-600 text-white hover:bg-red-700"
        : "bg-white border border-slate-300 text-ink hover:bg-slate-50";
  return (
    <button
      type="button"
      className={cn("rounded px-3 py-1.5 text-sm font-medium disabled:opacity-50", styles, className)}
      {...rest}
    />
  );
}

export function Card({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn("rounded border border-slate-200 bg-white p-4 shadow-sm", className)}>
      {children}
    </div>
  );
}

export function Label({ children, htmlFor }: { children: ReactNode; htmlFor?: string }) {
  return (
    <label htmlFor={htmlFor} className="block text-sm font-medium text-slate-700 mb-1">
      {children}
    </label>
  );
}

export function ErrorBox({ message }: { message?: string }) {
  if (!message) return null;
  return (
    <div className="rounded bg-red-50 border border-red-200 text-red-700 text-sm p-2">{message}</div>
  );
}
