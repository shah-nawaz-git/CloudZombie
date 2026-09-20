type DataTableProps = { children: React.ReactNode; label: string; caption?: string };
export function DataTable({ children, label, caption }: DataTableProps) {
  return (
    <div className="table-wrap">
      <table aria-label={label}>
        {caption && <caption>{caption}</caption>}
        {children}
      </table>
    </div>
  );
}
