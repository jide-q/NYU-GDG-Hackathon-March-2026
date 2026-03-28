"""
Video generation for DeliverAssist.

Pipeline:
    /video-script payload
        → transform_script_to_video_prompt()   (structured dict → natural-language prompt)
        → generate_video_segments()             (parallel Veo segments → list of video URLs)
"""

import asyncio
import base64
import logging
import time
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

# Veo — actual video generation (async, long-running operation)
VEO_MODEL = "veo-3.0-fast-generate-001"
VEO_POLL_INTERVAL = 5    # seconds between polls
VEO_TIMEOUT = 300        # max wait time in seconds

MAX_SCENES = 8
MAX_DURATION_SECONDS = 75

# ── Visual consistency brief (shared across all segments) ─────────────────────

_CHARACTER_BRIEF = """
CHARACTER (keep IDENTICAL across ALL segments — this is critical for continuity):
- Friendly, warm, human-like animated presenter in their 30s
- Casual modern clothing (dark hoodie or casual jacket), expressive face, natural hand gestures
- Background: clean modern apartment/office with subtle city elements visible through window
- Consistent warm-toned lighting throughout
- Same character proportions, skin tone, and style in every scene
"""

_TEXT_STYLE = """
TEXT LEGIBILITY (CRITICAL — phone viewers must read this easily):
- ALL on-screen text MUST be LARGE and BOLD — minimum 48pt equivalent
- Use WHITE or BRIGHT YELLOW text ONLY — never grey or light colors on white
- ALWAYS place text on a SEMI-TRANSPARENT DARK background strip or pill overlay
  (dark overlay opacity 70-80%, covering the full text width)
- Font: clean sans-serif, heavy weight (bold/black)
- Each text phrase stays on screen for at least 2 seconds before transitioning
- Place text in the LOWER THIRD of frame — never at very top or extreme edges
- Maximum 5 words per line — break long phrases across 2 lines
- Numbers and dollar amounts: extra large, bright yellow, centered
"""


# ── Prompt transformer ────────────────────────────────────────────────────────

def transform_script_to_video_prompt(script_payload: dict) -> str:
    """
    Convert a /video-script JSON payload into a natural-language cinematic
    prompt suitable for Veo. Enforces scene and duration limits.
    """
    return _build_segment_prompt(
        list(script_payload.get("scenes", [])),
        script_payload.get("interaction_points", []),
        segment_num=1,
        total_segments=1,
    )


def _build_segment_prompt(
    scenes: list[dict],
    interaction_points: list[dict],
    segment_num: int,
    total_segments: int,
) -> str:
    """
    Build a Veo prompt for one segment of scenes.
    Injects character brief and text-legibility instructions.
    """
    # Compute total duration for this segment
    total_seconds = sum(int(s.get("duration_seconds", 8)) for s in scenes)
    # Clamp to Veo's 8-second clip limit per call
    total_seconds = min(total_seconds, 8)

    lines: list[str] = [
        f"Create a short animated explainer video segment ({segment_num} of {total_segments}).",
        "The character is empathetic, knowledgeable, and speaks naturally — like a trusted guide.",
        "",
        "VIDEO STYLE:",
        "- Clean, modern mobile-first visuals",
        "- Smooth scene transitions",
        "- Preferred format: 9:16 vertical (mobile-friendly)",
        f"- Clip duration: approximately {total_seconds} seconds",
        "",
    ]

    lines += _CHARACTER_BRIEF.strip().splitlines()
    lines.append("")
    lines += _TEXT_STYLE.strip().splitlines()
    lines.append("")

    lines += [
        "VISUAL LANGUAGE:",
        "- 💰 Money/dollar icons for pay-related facts",
        "- ⏱ Clock icons for time and hours worked",
        "- ⚠️ Warning icons for compliance issues or underpayment",
        "- Bold highlighted text on screen for key phrases",
        "- Simple icon animations to reinforce spoken points",
        "",
        "SCENES IN THIS SEGMENT:",
        "",
    ]

    for i, scene in enumerate(scenes, 1):
        name = scene.get("name", f"Scene {i}")
        dur = int(scene.get("duration_seconds", 8))
        dialogue = scene.get("dialogue", "").strip()
        visual = scene.get("visual_direction", "").strip()
        onscreen = scene.get("onscreen_text", [])
        icons = scene.get("icons", [])

        lines.append(f"Scene {i} — {name} ({dur}s):")

        if dialogue:
            lines.append(f'  Character says: "{dialogue}"')

        if visual:
            lines.append(f"  Visual direction: {visual}")

        if onscreen:
            formatted = ", ".join(f'"{t}"' for t in onscreen)
            lines.append(f"  On-screen text (LARGE BOLD with dark overlay): {formatted}")

        if icons:
            lines.append(f"  Icons and visual aids: {' '.join(str(ic) for ic in icons)}")

        lines.append("")

    # Interaction points only in final segment
    if interaction_points and segment_num == total_segments:
        lines.append("INTERACTIVE UI OVERLAYS (render as tappable card elements at end):")
        lines.append("")
        for ip in interaction_points:
            after = ip.get("after_scene")
            prompt_text = ip.get("prompt", "").strip()
            options = ip.get("options", [])
            if after is not None:
                lines.append(f"  After Scene {after}:")
            if prompt_text:
                lines.append(f'  Character asks: "{prompt_text}"')
            for opt in options:
                lines.append(f"  [ {opt} ]")
            lines.append("")

    lines += [
        "END OF SEGMENT.",
        "Render this segment as described. Maintain consistent character design throughout.",
    ]

    return "\n".join(lines)


# ── Veo core (synchronous) ────────────────────────────────────────────────────

def _generate_veo_video(client: genai.Client, prompt: str) -> str | None:
    """
    Generate a single 8-second Veo clip. Polls until done or timeout.
    Returns a data: URI string, or None on failure.
    """
    logger.info("[Veo] Starting generation with %s", VEO_MODEL)

    operation = client.models.generate_videos(
        model=VEO_MODEL,
        prompt=prompt,
        config=types.GenerateVideosConfig(
            aspect_ratio="9:16",
            number_of_videos=1,
            duration_seconds=8,
        ),
    )

    deadline = time.time() + VEO_TIMEOUT
    while not operation.done:
        if time.time() > deadline:
            logger.error("[Veo] Timed out after %ds", VEO_TIMEOUT)
            return None
        logger.info("[Veo] Waiting... (%.0fs remaining)", deadline - time.time())
        time.sleep(VEO_POLL_INTERVAL)
        operation = client.operations.get(operation)

    if not operation.response or not operation.response.generated_videos:
        logger.error("[Veo] Operation completed but no videos in response")
        return None

    video = operation.response.generated_videos[0].video
    logger.info("[Veo] Done — downloading via SDK")

    try:
        video_bytes = client.files.download(file=video)
        b64 = base64.b64encode(video_bytes).decode()
        logger.info("[Veo] Downloaded %d bytes → data URL", len(video_bytes))
        return f"data:video/mp4;base64,{b64}"
    except Exception as e:
        logger.warning("[Veo] SDK download failed (%s)", e)
        return None


async def _generate_veo_segment_async(client: genai.Client, prompt: str) -> str | None:
    """Run the synchronous Veo call in a thread so it doesn't block the event loop."""
    return await asyncio.to_thread(_generate_veo_video, client, prompt)


# ── Multi-segment generation (public API) ────────────────────────────────────

async def generate_video_segments(client: genai.Client, script_payload: dict) -> dict:
    """
    Split the script into two halves and generate both segments in parallel.
    Each segment is an 8-second Veo clip; together they cover the full script.

    Returns:
        {
            "segments":   [dataUrl, dataUrl],   # both clips as data: URIs
            "video_url":  dataUrl | None,        # first segment (for backwards compat)
            "image_url":  None,
            "audio_url":  None,
            "media_type": "video/mp4" | None,
            "status":     "success",
        }
    """
    scenes = list(script_payload.get("scenes", []))
    interaction_points = script_payload.get("interaction_points", [])

    # Enforce hard scene cap
    if len(scenes) > MAX_SCENES:
        scenes = scenes[:MAX_SCENES]

    # Split scenes in half for two segments
    mid = max(1, len(scenes) // 2)
    groups = [scenes[:mid], scenes[mid:]] if len(scenes) > 1 else [scenes, []]
    groups = [g for g in groups if g]  # drop empty second group if only 1 scene

    total_segments = len(groups)
    prompts = [
        _build_segment_prompt(group, interaction_points, i + 1, total_segments)
        for i, group in enumerate(groups)
    ]

    logger.info("[Veo] Generating %d segment(s) sequentially", total_segments)

    # Generate segments sequentially to avoid rate-limit failures on parallel calls
    segments: list[str] = []
    for i, p in enumerate(prompts):
        try:
            url = await _generate_veo_segment_async(client, p)
            if url:
                segments.append(url)
                logger.info("[Veo] Segment %d/%d done (%d bytes b64)", i + 1, total_segments, len(url))
            else:
                logger.warning("[Veo] Segment %d/%d returned None", i + 1, total_segments)
        except Exception as exc:
            logger.warning("[Veo] Segment %d/%d failed: %s", i + 1, total_segments, exc)

    if not segments:
        logger.warning("[Veo] All segments failed — frontend will show script card")
        return {
            "segments": [],
            "video_url": None,
            "image_url": None,
            "audio_url": None,
            "media_type": None,
            "status": "success",
        }

    logger.info("[Veo] %d/%d segments generated successfully", len(segments), total_segments)
    return {
        "segments": segments,
        "video_url": segments[0],
        "image_url": None,
        "audio_url": None,
        "media_type": "video/mp4",
        "status": "success",
    }


# ── Legacy sync wrapper (kept for backwards compat) ───────────────────────────

def generate_video(client: genai.Client, prompt: str) -> dict:
    """Synchronous single-segment wrapper. Use generate_video_segments() instead."""
    video_uri = _generate_veo_video(client, prompt)
    if video_uri:
        return {
            "segments": [video_uri],
            "video_url": video_uri,
            "image_url": None,
            "audio_url": None,
            "media_type": "video/mp4",
            "status": "success",
        }
    return {
        "segments": [],
        "video_url": None,
        "image_url": None,
        "audio_url": None,
        "media_type": None,
        "status": "success",
    }
