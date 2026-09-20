type PaginationProps = {
  page: number;
  pageSize: number;
  total: number;
  go: (page: number) => void;
};
export function Pagination({ page, pageSize, total, go }: PaginationProps) {
  return (
    <div className="pagination">
      <button disabled={page <= 1} onClick={() => go(page - 1)}>
        Previous
      </button>
      <span>
        Page {page} · {total} findings
      </span>
      <button disabled={page * pageSize >= total} onClick={() => go(page + 1)}>
        Next
      </button>
    </div>
  );
}
