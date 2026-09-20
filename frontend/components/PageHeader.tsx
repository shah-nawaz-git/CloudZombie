type PageHeaderProps = { title: string; children?: React.ReactNode };
export function PageHeader({ title, children }: PageHeaderProps) {
  return (
    <div className="page-header">
      <h1>{title}</h1>
      {children}
    </div>
  );
}
