"use client";

import { useState } from "react";
import { approvalsApi } from "@/lib/api/endpoints/approvals";

export function useApprovals() {
  const [loading, setLoading] = useState(false);

  const resume = async (id: string, approved: boolean, notes?: string) => {
    setLoading(true);
    try {
      return await approvalsApi.resume(id, { approved, notes });
    } finally {
      setLoading(false);
    }
  };

  return { resume, loading };
}
