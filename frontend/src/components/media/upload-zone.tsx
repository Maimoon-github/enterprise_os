export function UploadZone({ onUpload }: { onUpload: (file: File) => void }) {
  return (
    <div className="border-2 border-dashed border-slate-800 rounded-xl p-8 text-center text-xs text-slate-400 hover:border-slate-700 cursor-pointer">
      Drag & drop raw assets or click to upload to MinIO
    </div>
  );
}
