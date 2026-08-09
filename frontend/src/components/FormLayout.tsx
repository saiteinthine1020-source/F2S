import type { FormEventHandler, ReactNode } from "react";

interface FormLayoutProps {
  readonly title: string;
  readonly description: string;
  readonly children: ReactNode;
  readonly submitLabel: string;
  readonly busyLabel: string;
  readonly busy: boolean;
  readonly error?: string | null;
  readonly success?: string | null;
  readonly onSubmit: FormEventHandler<HTMLFormElement>;
  readonly footer?: ReactNode;
}

export function FormLayout({
  busy,
  busyLabel,
  children,
  description,
  error,
  footer,
  onSubmit,
  submitLabel,
  success,
  title,
}: FormLayoutProps) {
  return (
    <section className="form-card">
      <div className="form-card__heading">
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {error ? (
        <p className="notice notice--danger" role="alert">
          {error}
        </p>
      ) : null}
      {success ? (
        <p className="notice notice--success" role="status">
          {success}
        </p>
      ) : null}
      <form className="form-stack" onSubmit={onSubmit}>
        <fieldset disabled={busy}>{children}</fieldset>
        <button className="button" type="submit" disabled={busy}>
          {busy ? busyLabel : submitLabel}
        </button>
      </form>
      {footer ? <div className="form-card__footer">{footer}</div> : null}
    </section>
  );
}

interface FieldProps {
  readonly label: string;
  readonly name: string;
  readonly type?: "text" | "email" | "password";
  readonly autoComplete?: string;
  readonly required?: boolean;
  readonly minLength?: number;
  readonly maxLength?: number;
  readonly hint?: string;
  readonly defaultValue?: string;
}

export function Field({ hint, label, name, ...input }: FieldProps) {
  const hintId = hint ? `${name}-hint` : undefined;
  return (
    <div className="field">
      <label htmlFor={name}>{label}</label>
      {hint ? <p id={hintId}>{hint}</p> : null}
      <input id={name} name={name} aria-describedby={hintId} {...input} />
    </div>
  );
}

interface SelectFieldProps {
  readonly label: string;
  readonly name: string;
  readonly children: ReactNode;
  readonly defaultValue?: string;
}

export function SelectField({ children, defaultValue, label, name }: SelectFieldProps) {
  return (
    <div className="field">
      <label htmlFor={name}>{label}</label>
      <select id={name} name={name} defaultValue={defaultValue}>
        {children}
      </select>
    </div>
  );
}
