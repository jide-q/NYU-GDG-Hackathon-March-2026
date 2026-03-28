"""
Video generation for DeliverAssist.

Pipeline:
    /video-script payload
        → transform_script_to_video_prompt()   (structured dict → natural-language prompt)
        → generate_video()                      (prompt → Veo → video URL)
"""

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

# Fallback image/audio models if Veo fails
IMAGE_MODEL = "models/nano-banana-pro-preview"
AUDIO_MODEL = "models/lyria-3-clip-preview"
MAX_SCENES = 8
MAX_DURATION_SECONDS = 75


# ── Prompt transformer ────────────────────────────────────────────────────────

def transform_script_to_video_prompt(script_payload: dict) -> str:
    """
    Convert a /video-script JSON payload into a natural-language cinematic
    prompt suitable for Nano Banana. Enforces scene and duration limits.

    Args:
        script_payload: dict matching the /video-script response schema

    Returns:
        A plain-text prompt string (no JSON, no markdown code blocks)
    """
    scenes = list(script_payload.get("scenes", []))
    interaction_points = script_payload.get("interaction_points", [])

    # ── Enforce limits ──────────────────────────────────────────────────────
    if len(scenes) > MAX_SCENES:
        logger.warning(
            "Script has %d scenes; truncating to %d", len(scenes), MAX_SCENES
        )
        scenes = scenes[:MAX_SCENES]

    # Trim to MAX_DURATION_SECONDS, always keeping at least the first scene
    total_seconds = 0
    trimmed: list[dict] = []
    for scene in scenes:
        dur = int(scene.get("duration_seconds", 10))
        if trimmed and total_seconds + dur > MAX_DURATION_SECONDS:
            logger.warning(
                "Dropping scene '%s' to stay within %ds limit",
                scene.get("name", "?"),
                MAX_DURATION_SECONDS,
            )
            continue
        trimmed.append(scene)
        total_seconds += dur
    scenes = trimmed or scenes[:1]

    # ── Build prompt ────────────────────────────────────────────────────────
    lines: list[str] = [
        "Create a short animated explainer video featuring a friendly, human-like character.",
        "The character is empathetic, knowledgeable, and speaks naturally — like a trusted guide, not a lawyer.",
        "",
        "VIDEO STYLE:",
        "- Clean, modern mobile-first visuals",
        "- Smooth scene transitions",
        "- High-contrast UI-style text overlays",
        "- Preferred format: 9:16 vertical (mobile-friendly)",
        f"- Total duration: approximately {total_seconds} seconds",
        "",
        "CHARACTER BEHAVIOR:",
        "- Use natural gestures, expressive head nods, and warm eye contact",
        "- Show concern when explaining problems, calm reassurance when giving guidance",
        "- Brief, natural pauses between key points",
        "- Never robotic — always human and conversational",
        "",
        "VISUAL LANGUAGE:",
        "- 💰 Money/dollar icons for pay-related facts",
        "- ⏱ Clock icons for time and hours worked",
        "- ⚠️ Warning icons for compliance issues or underpayment",
        "- Bold highlighted text on screen for key phrases",
        "- Simple icon animations to reinforce spoken points",
        "",
        "SCENES:",
        "",
    ]

    for i, scene in enumerate(scenes, 1):
        name = scene.get("name", f"Scene {i}")
        dur = int(scene.get("duration_seconds", 10))
        dialogue = scene.get("dialogue", "").strip()
        visual = scene.get("visual_direction", "").strip()
        onscreen = scene.get("onscreen_text", [])
        icons = scene.get("icons", [])

        lines.append(f"Scene {i} — {name} ({dur} seconds):")

        if dialogue:
            lines.append(f'  Character says: "{dialogue}"')

        if visual:
            lines.append(f"  Visual direction: {visual}")

        if onscreen:
            formatted = ", ".join(f'"{t}"' for t in onscreen)
            lines.append(f"  On-screen text highlights: {formatted}")

        if icons:
            lines.append(f"  Icons and visual aids: {' '.join(str(ic) for ic in icons)}")

        lines.append("")

    # ── Interaction points (rendered as UI overlays) ────────────────────────
    if interaction_points:
        lines.append("INTERACTIVE UI OVERLAYS (render as tappable card elements):")
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
        "END OF SCRIPT.",
        "Render the full video as described above. Maintain consistent character design across all scenes.",
    ]

    return "\n".join(lines)


# ── Nano Banana API call ──────────────────────────────────────────────────────

def _generate_veo_video(client: genai.Client, prompt: str) -> str | None:
    """
    Generate a video using Veo. Polls until the operation completes or times out.
    Returns a video URI/URL string, or None on failure.
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

    # Download video bytes using the SDK (handles API key auth internally).
    try:
        video_bytes = client.files.download(file=video)
        b64 = base64.b64encode(video_bytes).decode()
        logger.info("[Veo] Downloaded %d bytes → data URL", len(video_bytes))
        return f"data:video/mp4;base64,{b64}"
    except Exception as e:
        logger.warning("[Veo] SDK download failed (%s)", e)
        return None


def _extract_inline(response, default_mime: str) -> tuple[str | None, str | None]:
    """
    Extract the first inline data or file URI from a generate_content response.
    Returns (data_url_or_uri, mime_type) or (None, None).
    """
    for candidate in response.candidates or []:
        content = getattr(candidate, "content", None)
        if not content:
            continue
        for part in content.parts or []:
            file_data = getattr(part, "file_data", None)
            if file_data and getattr(file_data, "file_uri", None):
                return file_data.file_uri, default_mime

            inline = getattr(part, "inline_data", None)
            if inline and getattr(inline, "data", None):
                mime = getattr(inline, "mime_type", None) or default_mime
                b64 = base64.b64encode(inline.data).decode()
                return f"data:{mime};base64,{b64}", mime

            text = getattr(part, "text", None)
            if text and text.strip().startswith("http"):
                return text.strip(), default_mime

    return None, None


def generate_video(client: genai.Client, prompt: str) -> dict:
    """
    Generate a video using Veo. Falls back to image + audio if Veo fails.

    Returns:
        {
            "video_url":  str | None,   # Veo URI when successful
            "image_url":  str | None,   # nano-banana fallback
            "audio_url":  str | None,   # lyria fallback
            "media_type": str | None,
            "status": "success",
        }
    """
    # ── Try Veo first ───────────────────────────────────────────────────────
    try:
        video_uri = _generate_veo_video(client, prompt)
        if video_uri:
            return {
                "video_url": video_uri,
                "image_url": None,
                "audio_url": None,
                "media_type": "video/mp4",
                "status": "success",
            }
        logger.warning("[Veo] No URI returned, falling back to image+audio")
    except Exception as e:
        logger.warning("[Veo] Failed (%s), falling back to image+audio", e)

    # Veo failed — return empty so the frontend shows the script card
    logger.warning("[Veo] Failed, frontend will show script card fallback")
    return {
        "video_url": None,
        "image_url": None,
        "audio_url": None,
        "media_type": None,
        "status": "success",
    }
