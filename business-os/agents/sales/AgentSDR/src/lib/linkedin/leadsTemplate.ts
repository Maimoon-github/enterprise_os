import * as XLSX from "xlsx";

const TEMPLATE_SAMPLE_ROW = {
  "LinkedIn URL": "https://www.linkedin.com/in/johndoe",
  "LinkedIn API": "",
  Email: "john@acme.com",
  Name: "John Doe",
  Headline: "Software Engineer at Acme Corp",
  "Company Name": "Acme Corp",
  "Company Domain": "acme.com",
  Location: "San Francisco, CA",
  "Profile Picture URL": "https://media.licdn.com/dms/image/example.jpg",
  "Invitation Message (max 300 chars)": "Hi John, I came across your profile and would love to connect!",
  "Acceptance Message": "Thanks for connecting John! I wanted to reach out because...",
  "Follow-up 1": "Hey John, just following up on my last message. Would love to chat!",
  "Follow-up 2": "Hi John, one last follow-up — happy to schedule a quick call if you're open.",
};

export const buildLeadsTemplateBuffer = (): Buffer => {
  const worksheet = XLSX.utils.json_to_sheet([TEMPLATE_SAMPLE_ROW]);
  worksheet["!cols"] = [
    { wch: 45 },
    { wch: 18 },
    { wch: 30 },
    { wch: 25 },
    { wch: 45 },
    { wch: 25 },
    { wch: 25 },
    { wch: 25 },
    { wch: 55 },
    { wch: 32 },
    { wch: 60 },
    { wch: 60 },
    { wch: 60 },
    { wch: 60 },
  ];
  const workbook = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(workbook, worksheet, "Leads");
  return XLSX.write(workbook, { type: "buffer", bookType: "xlsx" }) as Buffer;
};

/** e.g. "Q1 Outreach" → "q1_outreach_lead_template" */
export const campaignLeadTemplateFilename = (campaignName: string): string => {
  const slug =
    campaignName
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_+|_+$/g, "")
      .slice(0, 80) || "campaign";
  return `${slug}_lead_template.xlsx`;
};
