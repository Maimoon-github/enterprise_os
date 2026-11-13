export const PAGE_SIZE = 10;

export const parsePageParam = (raw: string | undefined): number => {
  const n = Number(raw);
  if (!Number.isFinite(n) || n < 1) return 1;
  return Math.floor(n);
};

export const totalPages = (totalCount: number): number =>
  Math.max(1, Math.ceil(totalCount / PAGE_SIZE));

export const clampPage = (page: number, totalCount: number): number => {
  const max = totalPages(totalCount);
  return Math.min(Math.max(1, page), max);
};

export const pageSlice = (page: number) => ({
  skip: (page - 1) * PAGE_SIZE,
  take: PAGE_SIZE,
});

export const pageRangeLabel = (page: number, totalCount: number): string => {
  if (totalCount === 0) return "0 results";
  const from = (page - 1) * PAGE_SIZE + 1;
  const to = Math.min(page * PAGE_SIZE, totalCount);
  return `${from}–${to} of ${totalCount}`;
};
