import * as XLSX from "xlsx";

const TEMPLATE_SAMPLE_ROW = {
  "Company Name": "Acme Corp",
  "Search URL": "https://www.linkedin.com/search/results/people/?keywords=acme+corp",
};

export const buildSearchQueueTemplateBuffer = (): Buffer => {
  const worksheet = XLSX.utils.json_to_sheet([TEMPLATE_SAMPLE_ROW]);
  worksheet["!cols"] = [{ wch: 30 }, { wch: 70 }];
  const workbook = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(workbook, worksheet, "Search Queue");
  return XLSX.write(workbook, { type: "buffer", bookType: "xlsx" }) as Buffer;
};
