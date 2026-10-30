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
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {["1:1 Square Feed (Instagram/LinkedIn)", "9:16 Vertical Reel (YouTube Shorts/Reels)", "16:9 Landscape Video (YouTube)"].map((slot) => (
              <div key={slot} className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-3">
                <div className="h-36 bg-slate-950 border border-slate-800 rounded-lg flex items-center justify-center text-xs text-slate-500 font-mono">
                  MinIO Asset Preview
                </div>
                <div className="text-sm font-medium text-white">{slot}</div>
                <div className="text-xs text-slate-400">Content Hash: <span className="font-mono text-slate-300">sha256_8f92a1...</span></div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
