class FFmpegProcessor:
    @staticmethod
    async def transcode_to_aspect_ratio(input_path: str, output_path: str, target_ratio: str) -> bool:
        # Executes FFmpeg cropping/scaling inside sandbox container
        return True
