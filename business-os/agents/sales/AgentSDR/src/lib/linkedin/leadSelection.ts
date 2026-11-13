export const toggleLeadSelection = (
  selected: Set<string>,
  id: string,
  checked: boolean
): Set<string> => {
  const next = new Set(selected);
  if (checked) next.add(id);
  else next.delete(id);
  return next;
};

export const toggleAllOnPage = (
  selected: Set<string>,
  pageIds: string[],
  selectAll: boolean
): Set<string> => {
  const next = new Set(selected);
  for (const id of pageIds) {
    if (selectAll) next.add(id);
    else next.delete(id);
  }
  return next;
};

export const isAllPageSelected = (selected: Set<string>, pageIds: string[]): boolean =>
  pageIds.length > 0 && pageIds.every((id) => selected.has(id));

export const isSomePageSelected = (selected: Set<string>, pageIds: string[]): boolean =>
  pageIds.some((id) => selected.has(id));
