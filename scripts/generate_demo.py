#!/usr/bin/env python3
"""Generate demo video from screenshots.html using Playwright and FFmpeg."""

import asyncio
import os
import subprocess
import sys
from pathlib import Path

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("Error: playwright not installed. Run: pip install playwright")
    sys.exit(1)


# Configuration
OUTPUT_DIR = Path(__file__).parent.parent / "docs" / "screenshots"
HTML_FILE = OUTPUT_DIR / "demo.html"
FRAMES_DIR = OUTPUT_DIR / ".frames"
OUTPUT_VIDEO = OUTPUT_DIR / "demo.mp4"

# Video settings
WIDTH = 1280
HEIGHT = 720
FPS = 30
SCALE = "device-scale-factor=1"


def check_ffmpeg():
    """Check if ffmpeg is available."""
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            check=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


async def capture_frames():
    """Capture frames using Playwright."""
    print(f"Loading {HTML_FILE}...")

    async with async_playwright() as p:
        # Launch browser
        browser = await p.chromium.launch(
            headless=True,
            args=[
                f"--window-size={WIDTH},{HEIGHT}",
                "--disable-gpu",
                "--disable-dev-shm-usage",
            ],
        )

        context = await browser.new_context(
            viewport={"width": WIDTH, "height": HEIGHT},
            # Force consistent font rendering
            locale="en-US",
        )

        page = await context.new_page()

        # Setup frame directory
        FRAMES_DIR.mkdir(exist_ok=True)
        # Clear existing frames
        for frame_file in FRAMES_DIR.glob("frame_*.png"):
            frame_file.unlink()

        # Load the demo page with capture mode
        file_url = f"file://{HTML_FILE.absolute()}?capture=true"
        await page.goto(file_url, wait_until="networkidle")

        # Wait for page to signal ready
        print("Waiting for demo to start...")
        await page.wait_for_function("window.demoReady === true", timeout=10000)

        # Get total frame count from page
        total_frames = await page.evaluate("window.totalFrames")
        print(f"Capturing {total_frames} frames at {FPS}fps...")

        # Capture frames
        frame_count = 0
        while not await page.evaluate("window.demoComplete || false"):
            frame_path = FRAMES_DIR / f"frame_{frame_count:06d}.png"
            await page.screenshot(path=str(frame_path), full_page=False)

            frame_count += 1
            if frame_count % 30 == 0:
                print(f"  Captured {frame_count}/{total_frames} frames...")

            # Wait for next frame (1/fps seconds)
            await asyncio.sleep(1 / FPS)

            # Safety check
            if frame_count > total_frames + 10:
                print("Warning: Exceeded expected frame count, stopping capture.")
                break

        await browser.close()
        print(f"Captured {frame_count} frames total.")


def create_video():
    """Create MP4 video from frames using FFmpeg."""
    if not check_ffmpeg():
        print("Error: ffmpeg is required but not installed.")
        print("Install with: brew install ffmpeg (macOS)")
        return False

    print(f"\nCreating video: {OUTPUT_VIDEO}")

    cmd = [
        "ffmpeg",
        "-y",  # Overwrite output
        "-framerate", str(FPS),
        "-i", str(FRAMES_DIR / "frame_%06d.png"),
        "-c:v", "libx264",
        "-preset", "slow",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-s", f"{WIDTH}x{HEIGHT}",
        str(OUTPUT_VIDEO),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"FFmpeg error: {result.stderr}")
        return False

    # Get file size
    size_mb = OUTPUT_VIDEO.stat().st_size / (1024 * 1024)
    print(f"✓ Video created: {OUTPUT_VIDEO} ({size_mb:.1f} MB)")

    return True


def cleanup_frames():
    """Remove temporary frame files."""
    import shutil
    if FRAMES_DIR.exists():
        shutil.rmtree(FRAMES_DIR)
        print("✓ Cleaned up temporary frames")


async def main():
    """Main entry point."""
    print("=" * 50)
    print("IELTS Demo Video Generator")
    print("=" * 50)

    # Check input file exists
    if not HTML_FILE.exists():
        print(f"Error: {HTML_FILE} not found")
        sys.exit(1)

    # Capture frames
    await capture_frames()

    # Create video
    if create_video():
        cleanup_frames()
        print("\n✓ Demo video generated successfully!")
        print(f"  Output: {OUTPUT_VIDEO}")
    else:
        print("\n✗ Failed to create video")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
