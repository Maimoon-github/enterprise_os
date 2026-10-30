"use client";

import { useCallback, useState } from "react";
import { approvalsApi } from "@/lib/api/endpoints/approvals";
import { ApprovalResponse } from "@marketing-os/contracts";

export function useApprovals() {
  const [loading, setLoading] = useState(false);
  const [approvals, setApprovals] = useState<ApprovalResponse[]>([]);

  const fetchApprovals = useCallback(async () => {
    setLoading(true);
    try {
      const data = await approvalsApi.list();
      setApprovals(data);
      return data;
    } finally {
      setLoading(false);
    }
  }, []);

  const resume = async (
    id: string,
    approved: boolean,
    notes?: string,
    modifications?: Record<string, unknown>
  ) => {
    setLoading(true);
    try {
      const res = await approvalsApi.resume(id, {
        approved,
        notes: notes || null,
        modifications: modifications || null,
      });
      setApprovals((prev) => prev.filter((a) => a.id !== id));
      return res;
    } finally {
      setLoading(false);
    }
  };

  return { approvals, fetchApprovals, resume, loading };
}
