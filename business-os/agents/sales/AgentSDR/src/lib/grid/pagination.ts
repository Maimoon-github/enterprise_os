export const GRID_PAGE_SIZE = 200;

export function gridPageCount(total: number, pageSize = GRID_PAGE_SIZE): number {
  return Math.max(1, Math.ceil(Math.max(0, total) / pageSize));
}

export function clampGridPage(page: number, total: number, pageSize = GRID_PAGE_SIZE): number {
  const requested = Number.isFinite(page) ? Math.floor(page) : 0;
  return Math.min(Math.max(0, requested), gridPageCount(total, pageSize) - 1);
}

export function gridPageRange(page: number, total: number, pageSize = GRID_PAGE_SIZE) {
  if (total <= 0) return { start: 0, end: 0 };
  const safePage = clampGridPage(page, total, pageSize);
  return {
    start: safePage * pageSize + 1,
    end: Math.min((safePage + 1) * pageSize, total),
  };
}
