export interface BrandModel {
  id: string;
  name: string;
  slug: string;
  voice_guidelines?: string;
  default_platforms: string[];
}

export interface MediaAssetModel {
  id: string;
  minio_bucket: string;
  minio_key: string;
  content_hash: string;
  aspect_ratio?: string;
}
