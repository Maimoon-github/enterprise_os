---
name: media-compliance
description: Validates media dimensions, aspect ratios, file sizes, and color palettes against platform rules. Activate during asset staging or media verification before publishing.
compatibility: Universal JSON schema and media validation runtime.
allowed-tools: none
---

# Media Compliance Skill

## Objective
Enforce strict multi-platform compliance on synthetic and uploaded media assets, validating aspect ratios, resolutions, and MIME encodings before platform distribution.

## Activation Criteria
Activate this skill whenever:
1. `PublishingFanoutSubgraph` prepares outbound social media assets.
2. `MediaStudioServer` registers generated or uploaded imagery / video files.
3. Checking staged `PlatformAssetSpec` objects for `compliance_passed = True`.

## Verification Protocol
1. **Load Rules:** Reference `assets/aspect_ratio_rules.json` for target platform requirements.
2. **Dimension Verification:**
   - **LinkedIn:** Square feed (`1:1`), Landscape (`16:9`), or Vertical (`4:5`).
   - **YouTube:** Standard (`16:9`) or Vertical Shorts (`9:16`).
   - **Instagram:** Feed (`1:1`, `4:5`) or Reels/Stories (`9:16`).
   - **Threads:** Square (`1:1`) or Vertical (`9:16`).
   - **Facebook:** Feed (`1:1`, `16:9`) or Reels (`9:16`).
   - **X (Twitter):** Landscape (`16:9`) or Square (`1:1`).
   - **Pinterest:** Standard vertical pin (`2:3`) or Square (`1:1`).
   - **Google Business Profile:** Square (`1:1`), Landscape (`16:9`), or Vertical (`4:5`).
3. **Format & Integrity Check:**
   - Verify image MIME is `image/png` or `image/jpeg`.
   - Verify video MIME is `video/mp4` with H.264 video codec and AAC audio.
   - Verify file sizes remain strictly within platform maximum limits.
4. **Resolution:** If non-compliant, route asset to `MediaStudioServer` for automatic aspect ratio transcoding or FFmpeg cropping.
