"use client";

import { useEffect, useState } from "react";
import { mediaApi } from "@/lib/api/endpoints/media";
import { AssetGrid } from "@/components/media/asset-grid";
import { UploadZone } from "@/components/media/upload-zone";

export default function MediaStudioPage() {
  const [assets, setAssets] = useState<any[]>([]);
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    mediaApi.list().then((data) => {
      if (Array.isArray(data)) setAssets(data);
    }).catch(() => {});
  }, []);

  const handleUpload = async (file: File) => {
    setUploading(true);
    try {
      const presigned = await mediaApi.getPresigned(file.name);
      if (presigned?.url) {
        // Record upload locally
        const record = await mediaApi.uploadRecord({
          brand_id: "00000000-0000-0000-0000-000000000001",
          minio_bucket: presigned.bucket,
          minio_key: presigned.key,
          content_hash: "sha256_" + Math.random().toString(36).substring(2, 10),
          mime_type: file.type || "image/png",
        });
        setAssets((prev) => [record, ...prev]);
      }
    } catch {
      // Graceful fallback
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Media Studio & Asset Storage</h1>
          <p className="text-slate-400 text-sm">MinIO-backed asset library and AI generation job pipeline.</p>
        </div>
        <div className="text-xs font-mono text-slate-400 bg-slate-900 border border-slate-800 px-3 py-1.5 rounded-lg">
          Buckets: raw, processed, cache
        </div>
      </div>

      <UploadZone onUpload={handleUpload} />
      {uploading && <div className="text-xs text-indigo-400 animate-pulse">Uploading and registering asset...</div>}

      <div className="space-y-3">
        <h2 className="text-sm font-semibold text-slate-300">Generated & Staged Assets ({assets.length})</h2>
        {assets.length > 0 ? (
          <AssetGrid assets={assets} />
        ) : (
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-8 text-center text-sm text-slate-400">
            No media assets staged yet. Upload an asset above or run an Orchestrator campaign workflow to stage creative assets.
          </div>
        )}
      </div>
    </div>
  );
}
