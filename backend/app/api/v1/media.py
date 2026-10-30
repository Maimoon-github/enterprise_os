from fastapi import APIRouter

router = APIRouter()

@router.get("")
async def list_media_assets():
    return []

@router.post("/upload")
async def upload_media():
    return {"status": "uploaded", "minio_bucket": "marketing-raw-assets"}
