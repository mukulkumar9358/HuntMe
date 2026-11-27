export function AuthShell({ title, subtitle, children, footer }: { title: string; subtitle: string; children: React.ReactNode; footer: React.ReactNode }) {
  return (
    <div className="mx-auto w-full max-w-md px-5 pb-20 pt-10 sm:pt-16">
      <h1 className="font-display text-4xl font-bold tracking-tight">{title}</h1>
      <p className="mt-2 text-muted">{subtitle}</p>
      <div className="mt-8">{children}</div>
      <p className="mt-6 text-sm text-muted">{footer}</p>
    </div>
  );
}
