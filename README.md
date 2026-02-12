# OTSU Toolkit 🛠️

All-in-one web toolkit combining:
- **🖼 Watermark Tool** — Add "OTSU LABS" watermark to images & videos
- **🤖 YouTube AI Summarizer** — Summarize YouTube videos with Gemini AI
- **🎬 Video Contact Sheet** — Create frame grid from videos

## Quick Start (Local)

```bash
# Create & activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the app
python app.py
```

Open http://localhost:5001

## Deploy to Render.com (Free)

1. Push code to GitHub
2. Go to [render.com](https://render.com) → New → Web Service
3. Connect your GitHub repo
4. Settings:
   - **Environment**: Docker
   - **Plan**: Free
5. Add environment variable:
   - `GEMINI_API_KEY` = `your-api-key`
6. Click **Deploy**

## Tech Stack

- Python 3.11 + Flask
- FFmpeg (video processing)
- Pillow (image processing)
- Gemini AI (YouTube summarization)
- yt-dlp (YouTube video/audio download)

## License

MIT © OTSU Labs
