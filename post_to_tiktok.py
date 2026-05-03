#!/usr/bin/env python3
"""
GoTrendy.lb TikTok Automation
Posts videos and photos to TikTok using the Content Posting API.
- Photos → converted to 8-second video with brand overlay → posted as TikTok video
- Videos → brand overlay added → posted as TikTok video
- Full-cycle posting: posts every item once before repeating
- AI-generated English captions with niche hashtags
- Same Dropbox source as Instagram automation
"""

import os
import re
import json
import random
import requests
import tempfile
import logging
import time
import numpy as np
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
try:
    from moviepy.editor import VideoClip, VideoFileClip, ImageClip, CompositeVideoClip, ColorClip
except ImportError:
    from moviepy import VideoClip, VideoFileClip, ImageClip, CompositeVideoClip, ColorClip
import dropbox
from openai import OpenAI

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# ── Credentials from GitHub Secrets ──────────────────────────────────────────
TIKTOK_ACCESS_TOKEN    = os.environ['TIKTOK_ACCESS_TOKEN']
TIKTOK_OPEN_ID         = os.environ['TIKTOK_OPEN_ID']
TIKTOK_CLIENT_KEY      = os.environ['TIKTOK_CLIENT_KEY']
TIKTOK_CLIENT_SECRET   = os.environ['TIKTOK_CLIENT_SECRET']
TIKTOK_REFRESH_TOKEN   = os.environ['TIKTOK_REFRESH_TOKEN']
DROPBOX_APP_KEY        = os.environ['DROPBOX_APP_KEY']
DROPBOX_APP_SECRET     = os.environ['DROPBOX_APP_SECRET']
DROPBOX_REFRESH_TOKEN  = os.environ['DROPBOX_REFRESH_TOKEN']
OPENAI_API_KEY         = os.environ['OPENAI_API_KEY']
IMGUR_CLIENT_ID        = os.environ.get('IMGUR_CLIENT_ID', '546c25a59c58ad7')
WHATSAPP               = os.environ.get('WHATSAPP', '96181921452')

# ── Constants ─────────────────────────────────────────────────────────────────
DROPBOX_FOLDER   = '/Gotrendy.lb Stories'
STORY_W, STORY_H = 1080, 1920
REEL_DURATION    = 8
REEL_FPS         = 30
POSTED_FILE      = Path('tiktok_posted.json')

# ── Niche hashtag sets ────────────────────────────────────────────────────────
HASHTAGS_BASE = "#Lebanon #Beirut #gotrendylb #GoTrendy #ShopLebanon #LebanonShopping"

HASHTAGS_BY_CATEGORY = {
    'gadget':   ("#GadgetsLebanon #TechLebanon #SmartGadgets #TechLovers #GadgetOfTheDay "
                 "#MustHaveGadgets #TechLife #CoolGadgets #OnlineShopping #Trending"),
    'home':     ("#HomeLebanon #HomeDecorLebanon #HomeShopping #SmartHome #HomeGadgets "
                 "#InteriorLebanon #HouseGoals #HomeShopping #OnlineShopping #Trending"),
    'beauty':   ("#BeautyLebanon #SkinCareLebanon #BeautyTools #GlowUp #SkinCare "
                 "#BeautyTips #SkincareRoutine #BeautyLovers #OnlineShopping #Trending"),
    'outdoor':  ("#OutdoorLebanon #GardenLebanon #OutdoorLife #NatureLebanon #GardenDecor "
                 "#OutdoorGadgets #SummerLebanon #OnlineShopping #Trending #LifestyleLebanon"),
    'kids':     ("#KidsLebanon #ParentsLebanon #KidsToys #ChildrenLebanon #FamilyLebanon "
                 "#KidsGifts #MomLebanon #DadLebanon #OnlineShopping #Trending"),
    'health':   ("#HealthLebanon #WellnessLebanon #HealthyLifestyle #SleepBetter #Wellness "
                 "#HealthTips #WellnessTools #OnlineShopping #Trending #LifestyleLebanon"),
    'default':  ("#OnlineShopping #LifestyleLebanon #GadgetsLebanon #Trending #MustHave "
                 "#ShoppingLebanon #DailyDeals #NewArrival #BestDeals #ShopNow"),
}

CATEGORY_KEYWORDS = {
    'gadget':  ['speaker', 'earbuds', 'charging', 'power', 'magnetic', 'robot', 'electric', 'drawing', 'silicone'],
    'home':    ['solar', 'water bottle', 'water', 'bottle', 'table', 'runner'],
    'beauty':  ['electric brush', 'brush', 'cooling', 'nasal', 'massage', 'gel'],
    'outdoor': ['solar', 'mosquito', 'outdoor', 'garden'],
    'kids':    ['drawing', 'robot', 'kids'],
    'health':  ['nasal', 'cooling', 'massage', 'strips'],
}

PRODUCT_KEYWORDS = {
    'solar': 'Solar Swaying Garden Lights',
    'speaker': 'Powerful Mini Bluetooth Speaker',
    'nasal': 'Nasal Strips for Better Breathing',
    'power bank': 'Portable Power Bank',
    'power': 'Portable Power Bank',
    'mosquito repellent': 'Mosquito Repellent',
    'mosquito killer': 'Mosquito Killer Lamp',
    'mosquito': 'Mosquito Killer/Repellent',
    'cooling': 'Cooling Gel Patches',
    'massage': 'Mini Massage Gun',
    'magnetic': 'Magnetic Phone Holder',
    'charging': 'Multi-Charging Cable 4-in-1',
    'electric brush': 'Electric Face Cleansing Brush',
    'electric': 'Electric Face Cleansing Brush',
    'drawing': 'LCD Drawing Board for Kids',
    'silicone': 'Silicone Phone Holder',
    'earbuds': 'Wireless Earbuds',
    'robot': 'Robot Vacuum Cleaner',
    'water bottle': 'Smart Water Bottle',
    'water': 'Smart Water Bottle',
    'bottle': 'Smart Water Bottle',
}

# ── OpenAI client ─────────────────────────────────────────────────────────────
openai_client = OpenAI(api_key=OPENAI_API_KEY, base_url='https://api.openai.com/v1')


# ═══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def get_product_name(filename):
    name = Path(filename).stem.lower()
    for keyword, product in PRODUCT_KEYWORDS.items():
        if keyword in name:
            return product
    return Path(filename).stem.replace('_', ' ').replace('-', ' ').title()


def get_hashtags_for_product(product_name):
    name_lower = product_name.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in name_lower for kw in keywords):
            return f"{HASHTAGS_BASE} {HASHTAGS_BY_CATEGORY[category]}"
    return f"{HASHTAGS_BASE} {HASHTAGS_BY_CATEGORY['default']}"


def get_dropbox_client():
    return dropbox.Dropbox(
        app_key=DROPBOX_APP_KEY,
        app_secret=DROPBOX_APP_SECRET,
        oauth2_refresh_token=DROPBOX_REFRESH_TOKEN
    )


def get_dropbox_files():
    dbx = get_dropbox_client()
    result = dbx.files_list_folder(DROPBOX_FOLDER)
    files = [e for e in result.entries
             if hasattr(e, 'name') and e.name.lower().endswith(
                 ('.jpg', '.jpeg', '.png', '.webp', '.mp4', '.mov'))]
    logger.info(f"Found {len(files)} files in Dropbox")
    return files


def download_dropbox_file(entry):
    dbx = get_dropbox_client()
    _, response = dbx.files_download(entry.path_lower)
    suffix = Path(entry.name).suffix
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(response.content)
    tmp.close()
    logger.info(f"Downloaded: {entry.name} ({len(response.content)} bytes)")
    return tmp.name


def is_video_file(path):
    return Path(path).suffix.lower() in ('.mp4', '.mov')


def get_fonts():
    try:
        return (
            ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48),
            ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 38),
            ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 32),
        )
    except Exception:
        d = ImageFont.load_default()
        return d, d, d


def draw_brand_overlay(canvas_rgba):
    """Draw @gotrendy.lb top bar and WhatsApp CTA bottom bar on an RGBA image."""
    draw = ImageDraw.Draw(canvas_rgba)
    w, h = canvas_rgba.size
    font_large, font_medium, font_small = get_fonts()

    # Top bar
    draw.rectangle([(0, 0), (w, 100)], fill=(0, 0, 0, 190))
    brand = "@gotrendy.lb"
    bb = draw.textbbox((0, 0), brand, font=font_large)
    draw.text(((w - (bb[2]-bb[0])) // 2, 22), brand, fill=(255, 215, 0, 255), font=font_large)

    # Bottom bar
    draw.rectangle([(0, h - 130), (w, h)], fill=(0, 0, 0, 200))
    cta1 = "📲 Order via WhatsApp"
    cta2 = f"wa.me/{WHATSAPP}"
    bb1 = draw.textbbox((0, 0), cta1, font=font_medium)
    bb2 = draw.textbbox((0, 0), cta2, font=font_small)
    draw.text(((w - (bb1[2]-bb1[0])) // 2, h - 125), cta1, fill=(255, 255, 255, 255), font=font_medium)
    draw.text(((w - (bb2[2]-bb2[0])) // 2, h - 72),  cta2, fill=(255, 255, 255, 255), font=font_small)
    return canvas_rgba


# ═══════════════════════════════════════════════════════════════════════════════
#  VIDEO CREATION
# ═══════════════════════════════════════════════════════════════════════════════

def make_tiktok_video_from_photo(image_path):
    """Generate a static 8-second TikTok video from a photo (no zoom/pan)."""
    img = Image.open(image_path).convert('RGB')
    usable_h = STORY_H - 100 - 130
    scale = min(STORY_W / img.width, usable_h / img.height)
    new_w, new_h = int(img.width * scale), int(img.height * scale)
    img = img.resize((new_w, new_h), Image.LANCZOS)

    base_canvas = Image.new('RGBA', (STORY_W, STORY_H), (255, 255, 255, 255))
    base_canvas.paste(img.convert('RGBA'), ((STORY_W - new_w) // 2, 100 + (usable_h - new_h) // 2))
    base_canvas = draw_brand_overlay(base_canvas)
    frame_array = np.array(base_canvas.convert('RGB'))

    def make_frame(t):
        return frame_array

    clip = VideoClip(make_frame, duration=REEL_DURATION)
    clip = clip.set_fps(REEL_FPS)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
    tmp.close()
    clip.write_videofile(tmp.name, codec='libx264', audio=False,
                         preset='ultrafast', logger=None)
    logger.info(f"TikTok video from photo created: {tmp.name}")
    return tmp.name


def make_tiktok_video_from_video(video_path):
    """Add brand overlay to an existing video for TikTok."""
    clip = VideoFileClip(video_path)
    # Resize to 1080x1920 if needed
    target_w, target_h = STORY_W, STORY_H
    clip_w, clip_h = clip.size

    scale = min(target_w / clip_w, target_h / clip_h)
    new_w = int(clip_w * scale)
    new_h = int(clip_h * scale)
    clip = clip.resize((new_w, new_h))

    # Create a black background
    bg = ColorClip(size=(target_w, target_h), color=[0, 0, 0], duration=clip.duration)
    x_offset = (target_w - new_w) // 2
    y_offset = (target_h - new_h) // 2
    clip = clip.set_position((x_offset, y_offset))
    composite = CompositeVideoClip([bg, clip])

    # Create overlay image
    overlay_img = Image.new('RGBA', (target_w, target_h), (0, 0, 0, 0))
    overlay_img = draw_brand_overlay(overlay_img)
    overlay_array = np.array(overlay_img)

    def add_overlay(frame):
        overlay_rgb = overlay_array[:, :, :3]
        alpha = overlay_array[:, :, 3:4] / 255.0
        return (frame * (1 - alpha) + overlay_rgb * alpha).astype(np.uint8)

    final = composite.fl_image(add_overlay)

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
    tmp.close()
    final.write_videofile(tmp.name, codec='libx264', audio=clip.audio is not None,
                          preset='ultrafast', logger=None)
    logger.info(f"TikTok video from video created: {tmp.name}")
    return tmp.name


# ═══════════════════════════════════════════════════════════════════════════════
#  AI CAPTION GENERATION
# ═══════════════════════════════════════════════════════════════════════════════

def generate_caption(product_name):
    """Generate an English TikTok caption with CTA and WhatsApp link."""
    try:
        prompt = (
            f"Write a short, engaging TikTok caption in English only (no Arabic) for a product called '{product_name}'. "
            f"The caption should be 2-3 sentences max, exciting and trendy. "
            f"End with: 'Tag a friend who needs this! 👇 Order now: wa.me/{WHATSAPP}' "
            f"Do NOT include hashtags (they will be added separately)."
        )
        resp = openai_client.chat.completions.create(
            model='gpt-4.1-mini',
            messages=[{'role': 'user', 'content': prompt}],
            max_tokens=120,
            temperature=0.8
        )
        caption = resp.choices[0].message.content.strip()
        logger.info(f"Generated caption: {caption[:80]}...")
        return caption
    except Exception as e:
        logger.warning(f"Caption generation failed: {e}")
        return (f"Check out this amazing {product_name}! 🔥 Perfect for everyday use. "
                f"Tag a friend who needs this! 👇 Order now: wa.me/{WHATSAPP}")


# ═══════════════════════════════════════════════════════════════════════════════
#  CDN UPLOAD (Imgur)
# ═══════════════════════════════════════════════════════════════════════════════

def upload_video_to_cdn(video_path):
    """Upload video to Imgur and return the URL."""
    try:
        with open(video_path, 'rb') as f:
            resp = requests.post(
                'https://api.imgur.com/3/upload',
                headers={'Authorization': f'Client-ID {IMGUR_CLIENT_ID}'},
                files={'video': f},
                timeout=120
            )
        if resp.status_code == 200:
            url = resp.json()['data']['link']
            logger.info(f"Video uploaded to CDN: {url}")
            return url
        logger.error(f"CDN upload failed: {resp.text}")
        return None
    except Exception as e:
        logger.error(f"CDN upload error: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════════════
#  TIKTOK TOKEN MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

def refresh_tiktok_token():
    """Refresh the TikTok access token using the refresh token."""
    try:
        resp = requests.post(
            'https://open.tiktokapis.com/v2/oauth/token/',
            headers={
                'Content-Type': 'application/x-www-form-urlencoded',
                'Cache-Control': 'no-cache'
            },
            data={
                'client_key': TIKTOK_CLIENT_KEY,
                'client_secret': TIKTOK_CLIENT_SECRET,
                'grant_type': 'refresh_token',
                'refresh_token': TIKTOK_REFRESH_TOKEN
            }
        )
        if resp.status_code == 200 and 'access_token' in resp.json():
            new_token = resp.json()['access_token']
            logger.info("TikTok access token refreshed successfully")
            return new_token
        logger.warning(f"Token refresh failed: {resp.text}")
        return TIKTOK_ACCESS_TOKEN
    except Exception as e:
        logger.warning(f"Token refresh error: {e}")
        return TIKTOK_ACCESS_TOKEN


# ═══════════════════════════════════════════════════════════════════════════════
#  TIKTOK POSTING
# ═══════════════════════════════════════════════════════════════════════════════

def post_video_to_tiktok(video_path, caption, product_name=''):
    """Upload a video file directly to TikTok using FILE_UPLOAD method."""
    hashtags = get_hashtags_for_product(product_name)
    # TikTok title has 150 char limit
    full_title = f"{caption}\n\n{hashtags}"
    if len(full_title) > 2200:
        full_title = full_title[:2197] + "..."

    access_token = TIKTOK_ACCESS_TOKEN
    video_size = os.path.getsize(video_path)

    # Step 1: Initialize the upload
    init_resp = requests.post(
        'https://open.tiktokapis.com/v2/post/publish/video/init/',
        headers={
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json; charset=UTF-8'
        },
        json={
            'post_info': {
                'title': full_title[:2200],
                'privacy_level': 'PUBLIC_TO_EVERYONE',
                'disable_duet': False,
                'disable_comment': False,
                'disable_stitch': False,
                'video_cover_timestamp_ms': 1000
            },
            'source_info': {
                'source': 'FILE_UPLOAD',
                'video_size': video_size,
                'chunk_size': video_size,
                'total_chunk_count': 1
            }
        }
    )

    if init_resp.status_code != 200:
        logger.error(f"TikTok init failed: {init_resp.text}")
        return False

    init_data = init_resp.json().get('data', {})
    publish_id = init_data.get('publish_id')
    upload_url = init_data.get('upload_url')

    if not publish_id or not upload_url:
        logger.error(f"No publish_id or upload_url: {init_resp.text}")
        return False

    logger.info(f"TikTok publish_id: {publish_id}")

    # Step 2: Upload the video file
    with open(video_path, 'rb') as f:
        video_data = f.read()

    upload_resp = requests.put(
        upload_url,
        headers={
            'Content-Range': f'bytes 0-{video_size-1}/{video_size}',
            'Content-Type': 'video/mp4'
        },
        data=video_data,
        timeout=120
    )

    if upload_resp.status_code not in (200, 201, 206):
        logger.error(f"TikTok upload failed: {upload_resp.status_code} {upload_resp.text}")
        return False

    logger.info(f"Video uploaded to TikTok, checking status...")

    # Step 3: Poll for publish status
    for attempt in range(20):
        time.sleep(5)
        status_resp = requests.post(
            'https://open.tiktokapis.com/v2/post/publish/status/fetch/',
            headers={
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json; charset=UTF-8'
            },
            json={'publish_id': publish_id}
        )
        if status_resp.status_code == 200:
            status_data = status_resp.json().get('data', {})
            status = status_data.get('status', '')
            logger.info(f"Publish status (attempt {attempt+1}): {status}")
            if status == 'PUBLISH_COMPLETE':
                logger.info(f"✅ TikTok video published! publish_id: {publish_id}")
                return True
            elif status in ('FAILED', 'ERROR'):
                logger.error(f"TikTok publish failed with status: {status}")
                logger.error(f"Status details: {status_resp.text}")
                return False
        else:
            logger.warning(f"Status check failed: {status_resp.text}")

    logger.error("TikTok publish timed out")
    return False


# ═══════════════════════════════════════════════════════════════════════════════
#  CYCLE TRACKING (same full-cycle logic as Instagram)
# ═══════════════════════════════════════════════════════════════════════════════

def load_cycle_data():
    if POSTED_FILE.exists():
        with open(POSTED_FILE) as f:
            data = json.load(f)
            if isinstance(data, list):
                return {'round': 1, 'posted_this_round': data}
            return data
    return {'round': 1, 'posted_this_round': []}


def save_cycle_data(data):
    with open(POSTED_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def get_available_items(all_files):
    cycle = load_cycle_data()
    posted_this_round = set(cycle.get('posted_this_round', []))
    available = [f for f in all_files if f.name not in posted_this_round]
    if not available:
        current_round = cycle.get('round', 1)
        logger.info(f"🔄 Round {current_round} complete! Starting Round {current_round + 1}")
        cycle = {'round': current_round + 1, 'posted_this_round': []}
        save_cycle_data(cycle)
        available = list(all_files)
    round_num = cycle.get('round', 1)
    logger.info(f"Round {round_num}: {len(available)} items remaining out of {len(all_files)} total.")
    return available, cycle


def mark_as_posted(name, cycle):
    cycle['posted_this_round'].append(name)
    save_cycle_data(cycle)


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def process_one_product(entry):
    """Download, process, and post one product to TikTok."""
    product_name = get_product_name(entry.name)
    logger.info(f"Processing: {product_name} ({entry.name})")

    original_path = download_dropbox_file(entry)
    video_path = None

    try:
        caption = generate_caption(product_name)
        is_video = is_video_file(original_path)

        if is_video:
            logger.info("Video file — adding brand overlay for TikTok.")
            video_path = make_tiktok_video_from_video(original_path)
        else:
            logger.info("Photo file — converting to 8-second TikTok video.")
            video_path = make_tiktok_video_from_photo(original_path)

        success = post_video_to_tiktok(video_path, caption, product_name)
        logger.info(f"Product done — TikTok: {'✅' if success else '❌'}")
        return success

    finally:
        for p in [original_path, video_path]:
            if p:
                try:
                    os.unlink(p)
                except Exception:
                    pass


def run_automation():
    logger.info("=" * 60)
    logger.info(f"GoTrendy.lb TikTok Automation started at {datetime.now()}")
    logger.info("=" * 60)

    all_files = get_dropbox_files()
    if not all_files:
        logger.error("No files found in Dropbox!")
        return False

    available, cycle = get_available_items(all_files)
    selected = random.choice(available)
    logger.info(f"Selected: {selected.name}")

    success = process_one_product(selected)
    if success:
        mark_as_posted(selected.name, cycle)

    logger.info(f"Done! {'✅ Success' if success else '❌ Failed'}.")
    logger.info("=" * 60)
    return success


if __name__ == '__main__':
    run_automation()

