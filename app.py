from flask import Flask, request, send_file, render_template_string, jsonify
from moviepy.editor import ImageSequenceClip, AudioFileClip, TextClip, CompositeVideoClip
from moviepy.video.fx.all import colorx, gamma_corr
import os
import shutil
import uuid
import threading
from werkzeug.utils import secure_filename

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'outputs'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

jobs = {}  # simpan status job: {id: 'processing'/'done'/'error'}

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
        button:disabled { background: #ccc; cursor: not-allowed; }
        .progress { display: none; margin-top: 20px; }
        .progress-bar { width: 100%; height: 20px; background: #eee; border-radius: 10px; overflow: hidden; }
        .progress-fill { height: 100%; width: 0%; background: #ff0050; transition: width 0.3s; }
        .status { margin-top: 10px; font-weight: bold; }
        .download-btn { display: none; margin-top: 15px; background: #00c853; }
    </style>
</head>
<body>
    <div class="container">
        <h2>🎬 Image to TikTok Video</h2>
        <form id="uploadForm">
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
            
            <button type="submit" id="submitBtn">Buat Video 9:16</button>
        </form>
        
        <div class="progress" id="progressDiv">
            <div class="progress-bar"><div class="progress-fill" id="progressFill"></div></div>
            <div class="status" id="statusText">Memproses video...</div>
            <button class="download-btn" id="downloadBtn">Download Video</button>
        </div>
    </div>

<script>
const form = document.getElementById('uploadForm');
const submitBtn = document.getElementById('submitBtn');
const progressDiv = document.getElementById('progressDiv');
const progressFill = document.getElementById('progressFill');
const statusText = document.getElementById('statusText');
const downloadBtn = document.getElementById('downloadBtn');

form.addEventListener('submit', async (e) => {
    e.preventDefault();
    submitBtn.disabled = true;
    progressDiv.style.display = 'block';
    progressFill.style.width = '30%';
    statusText.textContent = 'Uploading files...';
    
    const formData = new FormData(form);
    
    const res = await fetch('/upload', { method: 'POST', body: formData });
    const data = await res.json();
    
    if (data.job_id) {
        pollStatus(data.job_id);
    } else {
        alert('Error: ' + data.error);
        submitBtn.disabled = false;
        progressDiv.style.display = 'none';
    }
});

async function pollStatus(jobId) {
    progressFill.style.width = '70%';
    statusText.textContent = 'Rendering video, sabar ya...';
    
    const interval = setInterval(async () => {
        const res = await fetch('/status/' + jobId);
        const data = await res.json();
        
        if (data.status === 'done') {
            clearInterval(interval);
            progressFill.style.width = '100%';
            statusText.textContent = 'Selesai!';
            downloadBtn.style.display = 'inline-block';
            downloadBtn.onclick = () => window.location.href = '/download/' + jobId;
            submitBtn.disabled = false;
        } else if (data.status === 'error') {
            clearInterval(interval);
            statusText.textContent = 'Error: ' + data.error;
            submitBtn.disabled = false;
        }
    }, 2000);
}
</script>
</body>
</html>
'''

def process_video(job_id, files, audio_file, fps, filter_name, text_overlay):
    try:
        job_folder = os.path.join(UPLOAD_FOLDER, job_id)
        os.makedirs(job_folder, exist_ok=True)
        
        # Simpan gambar
        image_paths = []
        for f in files:
            if f.filename:
                path = os.path.join(job_folder, secure_filename(f.filename))
                f.save(path)
                image_paths.append(path)
        image_paths.sort()
        
        clip = ImageSequenceClip(image_paths, fps=fps)
        clip = clip.resize(height=1920).crop(width=1080, x_center=clip.w/2, y_center=clip.h/2)
        clip = FILTERS.get(filter_name, FILTERS['none'])(clip)
        
        if text_overlay:
            txt_clip = TextClip(text_overlay, fontsize=80, color='white', stroke_color='black', stroke_width=2)
            txt_clip = txt_clip.set_position(('center', 'bottom')).set_duration(clip.duration).margin(bottom=100)
            clip = CompositeVideoClip([clip, txt_clip])
        
        if audio_file and audio_file.filename:
            audio_path = os.path.join(job_folder, secure_filename(audio_file.filename))
            audio_file.save(audio_path)
            audio = AudioFileClip(audio_path)
            clip = clip.set_audio(audio).subclip(0, min(clip.duration, audio.duration))
        
        clip = clip.fadein(0.5).fadeout(0.5)
        
        output_path = os.path.join(OUTPUT_FOLDER, f'{job_id}.mp4')
        clip.write_videofile(output_path, codec='libx264', audio_codec='aac', verbose=False, logger=None)
        
        jobs[job_id] = {'status': 'done', 'path': output_path}
    except Exception as e:
        jobs[job_id] = {'status': 'error', 'error': str(e)}

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/upload', methods=['POST'])
def upload():
    job_id = str(uuid.uuid4())
    jobs[job_id] = {'status': 'processing'}
    
    files = request.files.getlist('images')
    audio_file = request.files.get('audio')
    fps = int(request.form.get('fps', 24))
    filter_name = request.form.get('filter', 'none')
    text_overlay = request.form.get('text', '')
    
    thread = threading.Thread(target=process_video, args=(job_id, files, audio_file, fps, filter_name, text_overlay))
    thread.start()
    
    return jsonify({'job_id': job_id})

@app.route('/status/<job_id>')
def status(job_id):
    return jsonify(jobs.get(job_id, {'status': 'not_found'}))

@app.route('/download/<job_id>')
def download(job_id):
    job = jobs.get(job_id)
    if job and job['status'] == 'done':
        return send_file(job['path'], as_attachment=True, download_name='hasil_tiktok.mp4')
    return 'File not found', 404

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
