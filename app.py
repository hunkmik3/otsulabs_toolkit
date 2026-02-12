import os
import uuid
import re
import json
import math
import subprocess
import sys
import threading
import time
from urllib.parse import quote

from dotenv import load_dotenv
load_dotenv()

from flask import Flask, render_template, request, send_file, jsonify
from PIL import Image, ImageDraw, ImageFont

DEFAULT_GEMINI_KEY = os.getenv('GEMINI_API_KEY', '')

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
OUTPUT_FOLDER = os.path.join(BASE_DIR, 'output')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# ═══════════════════════════════════════════════════════════════
#  WATERMARK SETTINGS
# ═══════════════════════════════════════════════════════════════
WATERMARK_TEXT = "OTSU LABS"
FONT_PATH = os.path.join(BASE_DIR, "geist-font", "geist-font", "Geist", "ttf", "Geist-SemiBold.ttf")
LETTER_SPACING = -0.04
OPACITY = 25
TARGET_WIDTH_RATIO = 0.65

# ═══════════════════════════════════════════════════════════════
#  TASK MANAGEMENT (shared across tools)
# ═══════════════════════════════════════════════════════════════
TASKS = {}
TASKS_LOCK = threading.Lock()


def update_task_status(task_id, status, result=None, error=None, progress=None):
    with TASKS_LOCK:
        TASKS[task_id] = {
            'status': status,
            'result': result,
            'error': error,
            'progress': progress,
            'timestamp': time.time()
        }


def cleanup_old_tasks():
    with TASKS_LOCK:
        current_time = time.time()
        to_remove = [tid for tid, info in TASKS.items()
                     if current_time - info.get('timestamp', 0) > 3600]
        for tid in to_remove:
            del TASKS[tid]


# ═══════════════════════════════════════════════════════════════
#  WATERMARK FUNCTIONS
# ═══════════════════════════════════════════════════════════════
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp'}
VIDEO_EXTS = {'.mp4', '.mov', '.avi', '.mkv', '.webm'}


def get_optimal_font_size(img_width):
    ref_size = 100
    try:
        font = ImageFont.truetype(FONT_PATH, ref_size)
    except OSError:
        font = ImageFont.load_default()
        return int(img_width * 0.1)

    dummy_img = Image.new('RGBA', (1, 1))
    draw = ImageDraw.Draw(dummy_img)

    total_width = 0
    spacing = ref_size * LETTER_SPACING
    for char in WATERMARK_TEXT:
        bbox = draw.textbbox((0, 0), char, font=font)
        char_w = bbox[2] - bbox[0]
        total_width += char_w + spacing
    total_width -= spacing

    if total_width <= 0:
        return ref_size

    target_width = img_width * TARGET_WIDTH_RATIO
    scale_factor = target_width / total_width
    return int(ref_size * scale_factor)


def add_watermark_to_image(input_path, output_path):
    with Image.open(input_path) as img:
        img = img.convert("RGBA")
        txt_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(txt_layer)

        font_size = get_optimal_font_size(img.width)
        font = ImageFont.truetype(FONT_PATH, font_size)

        total_width = 0
        spacing = font_size * LETTER_SPACING
        chars_info = []
        for char in WATERMARK_TEXT:
            bbox = draw.textbbox((0, 0), char, font=font)
            char_w = bbox[2] - bbox[0]
            chars_info.append((char, char_w))
            total_width += char_w + spacing
        total_width -= spacing

        start_x = (img.width - total_width) / 2
        center_y = img.height / 2

        current_x = start_x
        for char, char_w in chars_info:
            draw.text((current_x, center_y), char, font=font,
                      fill=(255, 255, 255, OPACITY), anchor="lm")
            current_x += char_w + spacing

        out = Image.alpha_composite(img, txt_layer)
        if output_path.lower().endswith(('.jpg', '.jpeg')):
            out = out.convert("RGB")
        out.save(output_path)


def add_watermark_to_video(input_path, output_path):
    cmd_probe = [
        'ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height', '-of', 'csv=s=x:p=0', input_path
    ]
    try:
        dim = subprocess.check_output(cmd_probe).decode('utf-8').strip().split('x')
        width, height = int(dim[0]), int(dim[1])
    except Exception:
        width, height = 1920, 1080

    txt_img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(txt_img)

    font_size = get_optimal_font_size(width)
    font = ImageFont.truetype(FONT_PATH, font_size)

    total_width = 0
    spacing = font_size * LETTER_SPACING
    chars_info = []
    for char in WATERMARK_TEXT:
        char_bbox = draw.textbbox((0, 0), char, font=font)
        char_w = char_bbox[2] - char_bbox[0]
        chars_info.append((char, char_w))
        total_width += char_w + spacing
    total_width -= spacing

    start_x = (width - total_width) / 2
    center_y = height / 2

    for char, char_w in chars_info:
        draw.text((start_x, center_y), char, font=font,
                  fill=(255, 255, 255, OPACITY), anchor="lm")
        start_x += char_w + spacing

    temp_wm_path = os.path.join(OUTPUT_FOLDER, f"temp_wm_{uuid.uuid4().hex}.png")
    txt_img.save(temp_wm_path)

    try:
        cmd_ffmpeg = [
            'ffmpeg', '-y',
            '-i', input_path,
            '-i', temp_wm_path,
            '-filter_complex', 'overlay=0:0',
            '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '23',
            '-c:a', 'copy',
            '-movflags', '+faststart',
            output_path
        ]
        subprocess.run(cmd_ffmpeg, check=True, capture_output=True)
    except subprocess.CalledProcessError:
        cmd_ffmpeg = [
            'ffmpeg', '-y',
            '-i', input_path,
            '-i', temp_wm_path,
            '-filter_complex', 'overlay=0:0',
            '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '23',
            '-c:a', 'aac',
            '-movflags', '+faststart',
            output_path
        ]
        subprocess.run(cmd_ffmpeg, check=True, capture_output=True)
    finally:
        if os.path.exists(temp_wm_path):
            os.remove(temp_wm_path)


def process_watermark_task(task_id, input_path, output_path, ext, original_filename):
    try:
        update_task_status(task_id, 'processing', progress='Adding watermark...')

        if ext in IMAGE_EXTS:
            add_watermark_to_image(input_path, output_path)
            file_type = 'image'
        elif ext in VIDEO_EXTS:
            add_watermark_to_video(input_path, output_path)
            file_type = 'video'
        else:
            raise ValueError(f"Unsupported format: {ext}")

        if os.path.exists(input_path):
            os.remove(input_path)

        update_task_status(task_id, 'completed', result={
            'filename': os.path.basename(output_path),
            'original_name': original_filename,
            'type': file_type
        })
    except Exception as e:
        update_task_status(task_id, 'failed', error=str(e))
        if os.path.exists(input_path):
            os.remove(input_path)


# ═══════════════════════════════════════════════════════════════
#  YOUTUBE SUMMARIZER FUNCTIONS
# ═══════════════════════════════════════════════════════════════
def get_video_id(url):
    if "v=" in url:
        return url.split("v=")[1].split("&")[0]
    elif "youtu.be" in url:
        return url.split("/")[-1].split("?")[0]
    return url


def get_transcript(video_id):
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        from youtube_transcript_api.formatters import TextFormatter

        api = YouTubeTranscriptApi()
        transcript_list = api.list(video_id)

        transcript = None
        try:
            transcript = transcript_list.find_manually_created_transcript(['vi', 'en'])
        except Exception:
            try:
                transcript = transcript_list.find_generated_transcript(['vi', 'en'])
            except Exception:
                transcript = next(iter(transcript_list))
                if transcript.language_code not in ['vi', 'en']:
                    transcript = transcript.translate('vi')

        if transcript:
            formatter = TextFormatter()
            text_formatted = formatter.format_transcript(transcript.fetch())
            return text_formatted
    except Exception as e:
        print(f"Could not retrieve transcript: {e}")
        return None


def get_video_title_yt(url):
    try:
        import yt_dlp
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            return info.get('title', 'Unknown')
    except Exception:
        return 'Unknown'


def download_audio_and_transcribe(url, api_key):
    try:
        import yt_dlp
        import google.generativeai as genai

        output_filename = os.path.join(UPLOAD_FOLDER, f"temp_audio_{uuid.uuid4().hex}.mp3")

        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': output_filename.replace('.mp3', '.%(ext)s'),
            'quiet': True,
            'noprogress': True
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        genai.configure(api_key=api_key)
        audio_file = genai.upload_file(output_filename)

        while audio_file.state.name == "PROCESSING":
            time.sleep(2)
            audio_file = genai.get_file(audio_file.name)

        if audio_file.state.name == "FAILED":
            return None

        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(
            [audio_file, "Please transcribe this audio accurately. Output only the transcript."],
            request_options={"timeout": 600}
        )

        if os.path.exists(output_filename):
            os.remove(output_filename)

        return response.text
    except Exception as e:
        print(f"Error in download/transcribe: {e}")
        return None


def summarize_text(text, api_key, custom_prompt=None):
    if not text:
        return "No text to summarize."

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)

        model = genai.GenerativeModel("gemini-2.0-flash")

        if custom_prompt:
            base_prompt = custom_prompt
        else:
            base_prompt = "Hãy tóm tắt chi tiết, đầy đủ các ý chính của video sau bằng tiếng Việt. Trình bày rõ ràng, dễ hiểu."

        prompt = f"{base_prompt}\n\nNội dung Transcript:\n{text[:30000]}"
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error summarizing: {e}"


def process_youtube_task(task_id, video_url, api_key, custom_prompt=None):
    try:
        update_task_status(task_id, 'processing', progress='Getting video title...')
        title = get_video_title_yt(video_url)

        update_task_status(task_id, 'processing', progress='Extracting transcript...')
        video_id = get_video_id(video_url)
        full_text = get_transcript(video_id)

        if not full_text:
            update_task_status(task_id, 'processing',
                               progress='No transcript found. Downloading audio for AI transcription...')
            full_text = download_audio_and_transcribe(video_url, api_key)

        if not full_text:
            update_task_status(task_id, 'failed',
                               error='Could not extract any text from the video.')
            return

        update_task_status(task_id, 'processing', progress='Summarizing with Gemini AI...')
        summary = summarize_text(full_text, api_key, custom_prompt)

        update_task_status(task_id, 'completed', result={
            'title': title,
            'transcript_preview': full_text[:1000],
            'summary': summary,
            'video_url': video_url
        })

    except Exception as e:
        update_task_status(task_id, 'failed', error=str(e))


# ═══════════════════════════════════════════════════════════════
#  CONTACT SHEET FUNCTIONS
# ═══════════════════════════════════════════════════════════════
def get_video_duration(video_path):
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        video_path
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)

        if 'format' in data and 'duration' in data['format']:
            return float(data['format']['duration'])

        for stream in data.get('streams', []):
            if stream.get('codec_type') == 'video' and 'duration' in stream:
                return float(stream['duration'])

        raise ValueError("Could not determine video duration")
    except Exception as e:
        raise Exception(f"Error getting video duration: {e}")


def create_contact_sheet(video_path, interval=3, width=320, cols=5, output_path=None):
    if output_path is None:
        base, _ = os.path.splitext(video_path)
        output_path = f"{base}_contact_sheet.jpg"

    duration = get_video_duration(video_path)
    num_frames = int(duration / interval) + 1
    rows = math.ceil(num_frames / cols)

    vf_filter = f"fps=1/{interval},scale={width}:-1,tile={cols}x{rows}"

    cmd = [
        "ffmpeg",
        "-i", video_path,
        "-vf", vf_filter,
        "-frames:v", "1",
        "-y",
        output_path
    ]

    subprocess.run(cmd, check=True, capture_output=True)
    return output_path


def process_contact_sheet_task(task_id, input_path, interval, width, cols, original_filename):
    try:
        update_task_status(task_id, 'processing', progress='Generating contact sheet...')

        output_filename = f"contact_sheet_{task_id}.jpg"
        output_path = os.path.join(OUTPUT_FOLDER, output_filename)

        duration = get_video_duration(input_path)
        num_frames = int(duration / interval) + 1
        rows = math.ceil(num_frames / cols)

        create_contact_sheet(input_path, interval, width, cols, output_path)

        if os.path.exists(input_path):
            os.remove(input_path)

        update_task_status(task_id, 'completed', result={
            'filename': output_filename,
            'original_name': original_filename,
            'duration': round(duration, 2),
            'frames': num_frames,
            'grid': f'{cols}x{rows}',
            'type': 'contact_sheet'
        })

    except Exception as e:
        update_task_status(task_id, 'failed', error=str(e))
        if os.path.exists(input_path):
            os.remove(input_path)


# ═══════════════════════════════════════════════════════════════
#  ROUTES
# ═══════════════════════════════════════════════════════════════
@app.route('/')
def index():
    return render_template('index.html')


# --- WATERMARK ROUTES ---
@app.route('/api/watermark/upload', methods=['POST'])
def watermark_upload():
    cleanup_old_tasks()

    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in IMAGE_EXTS and ext not in VIDEO_EXTS:
        return jsonify({'error': f'Unsupported file format: {ext}'}), 400

    task_id = uuid.uuid4().hex
    input_filename = f"{task_id}{ext}"
    input_path = os.path.join(UPLOAD_FOLDER, input_filename)
    file.save(input_path)

    output_filename = f"watermarked_{task_id}{ext}"
    output_path = os.path.join(OUTPUT_FOLDER, output_filename)

    update_task_status(task_id, 'queued')

    thread = threading.Thread(
        target=process_watermark_task,
        args=(task_id, input_path, output_path, ext, file.filename)
    )
    thread.start()

    return jsonify({'success': True, 'task_id': task_id})


# --- YOUTUBE SUMMARIZER ROUTES ---
@app.route('/api/youtube/summarize', methods=['POST'])
def youtube_summarize():
    cleanup_old_tasks()

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    video_url = data.get('url', '').strip()
    api_key = data.get('api_key', '').strip() or DEFAULT_GEMINI_KEY
    custom_prompt = data.get('custom_prompt', '').strip() or None

    if not video_url:
        return jsonify({'error': 'YouTube URL is required'}), 400
    if not api_key:
        return jsonify({'error': 'Gemini API Key is required'}), 400

    task_id = uuid.uuid4().hex
    update_task_status(task_id, 'queued')

    thread = threading.Thread(
        target=process_youtube_task,
        args=(task_id, video_url, api_key, custom_prompt)
    )
    thread.start()

    return jsonify({'success': True, 'task_id': task_id})


# --- CONTACT SHEET ROUTES ---
@app.route('/api/contactsheet/upload', methods=['POST'])
def contactsheet_upload():
    cleanup_old_tasks()

    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in VIDEO_EXTS:
        return jsonify({'error': f'Only video files are supported. Got: {ext}'}), 400

    interval = float(request.form.get('interval', 3))
    width = int(request.form.get('width', 320))
    cols = int(request.form.get('cols', 5))

    task_id = uuid.uuid4().hex
    input_filename = f"{task_id}{ext}"
    input_path = os.path.join(UPLOAD_FOLDER, input_filename)
    file.save(input_path)

    update_task_status(task_id, 'queued')

    thread = threading.Thread(
        target=process_contact_sheet_task,
        args=(task_id, input_path, interval, width, cols, file.filename)
    )
    thread.start()

    return jsonify({'success': True, 'task_id': task_id})


# --- SHARED ROUTES ---
@app.route('/api/status/<task_id>')
def task_status(task_id):
    with TASKS_LOCK:
        task_info = TASKS.get(task_id)

    if not task_info:
        return jsonify({'error': 'Task not found'}), 404

    return jsonify(task_info)


@app.route('/preview/<filename>')
def preview(filename):
    file_path = os.path.join(OUTPUT_FOLDER, filename)
    if not os.path.exists(file_path):
        return jsonify({'error': 'File not found'}), 404
    return send_file(file_path)


@app.route('/download/<filename>')
def download(filename):
    file_path = os.path.join(OUTPUT_FOLDER, filename)
    if not os.path.exists(file_path):
        return jsonify({'error': 'File not found'}), 404

    # Get original name from query param, fallback to server filename
    original_name = request.args.get('original_name', filename)

    # Ensure the download name has proper extension from the actual file
    server_ext = os.path.splitext(filename)[1]  # e.g. .jpg, .mp4
    orig_base, orig_ext = os.path.splitext(original_name)

    # If original_name has no extension, add the server file's extension
    if not orig_ext:
        original_name = orig_base + server_ext

    # Create ASCII-safe version for Content-Disposition fallback
    ascii_safe = re.sub(r'[^\w\-.]', '_', original_name)

    # URL-encode for UTF-8 filename* parameter
    encoded_name = quote(original_name)

    # Detect proper MIME type
    import mimetypes
    mimetype = mimetypes.guess_type(file_path)[0] or 'application/octet-stream'

    response = send_file(
        file_path,
        mimetype=mimetype,
        as_attachment=True,
        download_name=original_name
    )
    response.headers['Content-Disposition'] = (
        f"attachment; filename=\"{ascii_safe}\"; filename*=UTF-8''{encoded_name}"
    )
    return response


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    debug = os.environ.get('FLASK_ENV', 'development') == 'development'
    app.run(debug=debug, host='0.0.0.0', port=port)
