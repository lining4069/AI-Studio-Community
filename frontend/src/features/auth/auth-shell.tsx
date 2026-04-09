type AuthShellProps = {
  eyebrow: string;
  title: string;
  description: string;
  children: React.ReactNode;
  footer: React.ReactNode;
  gradient: string;
};

export function AuthShell({
  eyebrow,
  title,
  description,
  children,
  footer,
  gradient,
}: AuthShellProps) {
  return (
    <div className={`flex min-h-screen items-center justify-center px-6 ${gradient}`}>
      <div className="w-full max-w-md rounded-[2rem] border border-white/70 bg-white/85 p-10 shadow-2xl shadow-slate-200 backdrop-blur-xl">
        <p className="text-xs font-semibold uppercase tracking-[0.28em] text-sky-600">
          {eyebrow}
        </p>
        <h1 className="mt-4 text-3xl font-semibold text-slate-950">{title}</h1>
        <p className="mt-3 text-sm leading-6 text-slate-500">{description}</p>
        <div className="mt-8">{children}</div>
        <div className="mt-6 text-sm text-slate-500">{footer}</div>
      </div>
    </div>
  );
}
