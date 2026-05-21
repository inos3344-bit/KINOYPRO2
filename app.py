from flask import Flask, request, send_file, render_template_string
from moviepy.editor import ImageSequenceClip, AudioFileClip, TextClip, CompositeVideoClip
from moviepy.video.fx.all import colorx, gamma_corr
import os
import shutil
from werkzeug.utils import secure_filename

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'outputs'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

FILTERS = {
    'none': lambda clip: clip,
    'bright': lambda clip: colorx(clip, 1.2),
    'dark': lambda clip: colorx(clip, 0.8),
    'warm': lambda clip: gamma_corr(clip, 0.9),
    'cool': lambda clip: gamma_corr(clip, 1.1)
}

HTML = '''
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Image to Video Generator</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 600px; margin: 30px auto; padding: 15px; background: #f5f5f5; }
        .container { border: 2px dashed #ccc; padding: 25px; text-align: center; border-radius: 12px; background: white; }
        input, select { margin: 10px 0; padding: 10px; width: 90%; border: 1px solid #ddd; border-radius: 6px; }
        button { padding: 14px 30px; background: #ff0050; color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: bold; font-size: 16px; }
        button:hover { background: #e60045; }
        .feature { font-size: 14px; color: #555; margin-top: 20px; text-align: left; }
        h2 { color: #ff0050; }
    </style>
</head>
<body>
    <div class="container">
        <h2>🎬 Image to TikTok Video</h2>
        <form method="POST" enctype="multipart/form-data">
            <label><b>1. Upload Gambar</b></label><br>
            <input type="file" name="images" multiple accept="image/*" required><br>
            
            <label><b>2. Upload Audio</b> - opsional</label><br>
            <input type="file" name="audio" accept="audio/*"><br>
            
            <label><b>3. Text Overlay</b> - opsional</label><br>
            <input type="text" name="text" placeholder="Tulis caption di video"><br>
            
            <label><b>4. Filter</b></label><br>
            <select name="filter">
                <option value="none">None</option>
                <option value="bright">Bright</option>
                <option value="dark">Dark</option>
                <option value="warm">Warm</option>
                <option value="cool">Cool</option>
            </select><br>
            
            <label><b>5. FPS:</b></label>
            <input type="number" name="fps" value="24" min="1" max="60"><br><br>
            
            <button type="submit">Buat Video 9:16</button>
        </form>
        <div class="feature">
            ✅ Auto resize ke 1080x1920 untuk TikTok/Reels<br>
            ✅ Support tambah musik<br>
            ✅ Text overlay dengan outline<br>
            ✅ 5 filter warna<br>
            ✅ Fade in/out otomatis
        </div>
    </div>
</body>
</html>
'''

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # Bersihkan folder upload
        if os.path.exists(UPLOAD_FOLDER):
            shutil.rmtree(UPLOAD_FOLDER)
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        
        files = request.files.getlist('images')
        audio_file = request.files.get('audio')
        fps = int(request.form.get('fps', 24))
        filter_name = request.form.get('filter', 'none')
        text_overlay = request.form.get('text', '')
        
        if not files:
            return "Upload gambar dulu!"
        
        # Simpan gambar
        image_paths = []
        for f in files:
            if f.filename:
                path = os.path.join(UPLOAD_FOLDER, secure_filename(f.filename))
                f.save(path)
                image_paths.append(path)
        image_paths.sort()
        
        # Buat video
        clip = ImageSequenceClip(image_paths, fps=fps)
        clip = clip.resize(height=1920).crop(width=1080, x_center=clip.w/2, y_center=clip.h/2)
        clip = FILTERS.get(filter_name, FILTERS['none'])(clip)
        
        # Text overlay
        if text_overlay:
            txt_clip = TextClip(text_overlay, fontsize=80, color='white', stroke_color='black', stroke_width=2, font='Arial-Bold')
            txt_clip = txt_clip.set_position(('center', 'bottom')).set_duration(clip.duration).margin(bottom=100)
            clip = CompositeVideoClip([clip, txt_clip])
        
        # Audio
        if audio_file and audio_file.filename:
            audio_path = os.path.join(UPLOAD_FOLDER, secure_filename(audio_file.filename))
            audio_file.save(audio_path)
            audio = AudioFileClip(audio_path)
            clip = clip.set_audio(audio).subclip(0, min(clip.duration, audio.duration))
        
        clip = clip.fadein(0.5).fadeout(0.5)
        
        output_path = os.path.join(OUTPUT_FOLDER, 'hasil.mp4')
        clip.write_videofile(output_path, codec='libx264', audio_codec='aac', verbose=False, logger=None)
        
        return send_file(output_path, as_attachment=True, download_name='hasil_tiktok.mp4')
    
    return render_template_string(HTML)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
