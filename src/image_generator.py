"""Generate spotlight images for LinkedIn posts via Nano Banana Pro (Gemini 3 Pro Image)."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.models import JobListing

STYLE_REFERENCE_PATH = Path(__file__).parent.parent / "job spotlight template.png"
IMAGES_DIR = Path(__file__).parent.parent / "data" / "images"

# Nano Banana Pro = Gemini 3 Pro Image
# Confirmed model ID: https://ai.google.dev/gemini-api/docs/models
GEMINI_IMAGE_MODEL = "gemini-3-pro-image-preview"

_PROMPT_STATIC = """\
Create a professional, sophisticated job posting graphic in 1:1 square aspect ratio at 2K resolution.

Background: Solid warm brown (#6B4E3D) with subtle thin curved wireframe lines over the background, resembling delicate topographic contours.

Decorative elements: A single, cohesive, flowing organic ribbon stripe with layered, marbled fluid-art textures in burnt orange, deep teal, sky blue, and cream. Position this as a consolidated accent in the top right corner — it should NOT overlap with the text areas.

Text and Layout: All text is white, placed on the solid brown background for maximum legibility, and left-justified. Use a professional, clean serif font. Add a solid white vertical bar on the left side, aligned with and spanning only the height of the main title text.

Sub-bullet icons: Each sub-bullet is preceded by a small flat, minimal line icon. Icons must use only white and rust (#B85C38) — no standard emoji colors, no gradients, no outlines in any other color.

=== JOB DETAILS ===

{job_details}

=== END JOB DETAILS ===

Style: Warm, editorial, sophisticated. No clipart, no stock photos, no glossy effects, no drop shadows on text. Generous whitespace. No logo. The overall feel should be a high-end think tank or academic institution, not a tech startup.

Match the composition, proportions, and visual style of the reference image exactly.\
"""


def build_image_prompt(listing: JobListing) -> str:
    """Build the image generation prompt for a spotlight graphic.

    Static style instructions are combined with dynamic listing fields.
    Optional fields are omitted when None rather than shown as blank.

    Args:
        listing: The JobListing to generate a prompt for.

    Returns:
        Complete prompt string ready to pass to generate_spotlight_image().
    """
    lines = []
    lines.append(f'Title in large text: "{listing.title}"')
    lines.append("")
    lines.append("Sub-bullets placed below the title, each preceded by a small flat white/rust icon:")

    if listing.salary_range:
        lines.append(f"[coin stack icon] Stipend: {listing.salary_range}")

    location_str = listing.location or listing.work_mode
    if location_str:
        lines.append(f"[location pin icon] Location: {location_str}")

    if listing.date_closes:
        lines.append(f"[calendar icon] Deadline: {listing.date_closes.strftime('%B %-d, %Y')}")

    lines.append("")
    lines.append(f'Organization name placed independently in the bottom left corner: "{listing.organization}"')

    job_details = "\n".join(lines)
    return _PROMPT_STATIC.format(job_details=job_details)


def generate_spotlight_image(prompt: str) -> Optional[bytes]:
    """Call Nano Banana Pro to generate a spotlight image.

    Sends the style reference image alongside the text prompt as a
    multimodal request. Returns raw PNG bytes on success, None on any
    failure (missing API key, missing reference file, API error).

    Args:
        prompt: Complete text prompt, typically from build_image_prompt()
                and possibly edited by the user.

    Returns:
        Raw image bytes (PNG) on success, None on failure.
    """
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return None
    if not STYLE_REFERENCE_PATH.exists():
        return None

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        ref_bytes = STYLE_REFERENCE_PATH.read_bytes()
        ref_part = types.Part.from_bytes(data=ref_bytes, mime_type="image/png")

        response = client.models.generate_content(
            model=GEMINI_IMAGE_MODEL,
            contents=[ref_part, prompt],
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
            ),
        )

        for part in response.candidates[0].content.parts:
            if part.inline_data:
                return part.inline_data.data

        return None
    except Exception:
        return None


def save_image_to_disk(image_bytes: bytes) -> Path:
    """Save generated image bytes to data/images/ with a timestamped filename.

    Mirrors the draft save convention: YYYY-MM-DD_HHMM_spotlight.png.
    Creates data/images/ if it does not exist.

    Args:
        image_bytes: Raw PNG bytes from generate_spotlight_image().

    Returns:
        Path to the saved image file.
    """
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    path = IMAGES_DIR / f"{timestamp}_spotlight.png"
    path.write_bytes(image_bytes)
    return path
