import os
import sys
import mimetypes
import urllib.parse
import json
import bottle
from bottle import Bottle, request, response, static_file, abort
from ..core.ffmpeg_utils import get_audio_info
from ..core.logger import log_client_event, log_info, log_error

# Allow large file uploads (up to 1 GB) so audio files don't trigger HTTP 413
bottle.BaseRequest.MEMFILE_MAX = 1024 * 1024 * 1024

def create_app(web_dir: str):
    app = Bottle()

    @app.route('/client_log', method=['POST', 'OPTIONS'])
    def client_log():
        response.content_type = 'application/json'
        response.set_header("Access-Control-Allow-Origin", "*")
        if request.method == 'OPTIONS':
            return "{}"
        try:
            data = request.json or {}
            level = data.get('level', 'info')
            msg = data.get('message', '')
            log_client_event(level, msg)
            return json.dumps({"status": "ok"})
        except Exception as e:
            return json.dumps({"status": "error", "error": str(e)})

    # Directory for temporary drag-and-drop imported files
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    import_dir = os.path.join(base_dir, 'imported_audio')
    os.makedirs(import_dir, exist_ok=True)

    @app.route('/')
    def index():
        return static_file('index.html', root=web_dir)

    @app.route('/static/<filepath:path>')
    def serve_static(filepath):
        return static_file(filepath, root=web_dir)

    @app.route('/stream_audio')
    def stream_audio():
        file_path = request.query.get('path')
        if not file_path:
            abort(400, "Missing path parameter")
        
        file_path = urllib.parse.unquote(file_path)
        
        if not os.path.exists(file_path) or not os.path.isfile(file_path):
            abort(404, "Audio file not found")

        directory, filename = os.path.split(os.path.abspath(file_path))
        mime, _ = mimetypes.guess_type(filename)
        if not mime:
            mime = 'audio/mpeg'

        response.set_header("Access-Control-Allow-Origin", "*")
        response.set_header("Accept-Ranges", "bytes")
        return static_file(filename, root=directory, mimetype=mime)

    @app.route('/upload_audio', method=['POST', 'OPTIONS'])
    def upload_audio():
        """
        Receives audio files via FormData (from Drag & Drop or HTML File Input).
        Saves them to imported_audio/ and returns metadata.
        """
        response.content_type = 'application/json'
        response.set_header("Access-Control-Allow-Origin", "*")
        
        if request.method == 'OPTIONS':
            return "{}"

        try:
            uploaded_files = request.files.getall('audio_files')
            
            if not uploaded_files:
                return json.dumps({"success": False, "clips": [], "error": "No audio files received in request."})

            clips = []
            for f in uploaded_files:
                raw_filename = f.filename
                if not raw_filename:
                    continue

                save_path = os.path.join(import_dir, raw_filename)
                # Avoid overwriting by appending counter if name exists with different size
                base_name, ext = os.path.splitext(raw_filename)
                counter = 1
                while os.path.exists(save_path):
                    save_path = os.path.join(import_dir, f"{base_name}_{counter}{ext}")
                    counter += 1

                f.save(save_path, overwrite=True)

                try:
                    info = get_audio_info(save_path)
                    clips.append(info)
                except Exception as e:
                    clips.append({
                        'path': save_path,
                        'filename': os.path.basename(save_path),
                        'duration': 0,
                        'duration_formatted': '00:00',
                        'sample_rate': 44100,
                        'channels': 2,
                        'bitrate_kbps': 0,
                        'format_name': ext.replace('.', '').upper(),
                        'size_bytes': os.path.getsize(save_path),
                        'size_formatted': '0 KB',
                        'error': str(e)
                    })

            return json.dumps({"success": True, "clips": clips})

        except Exception as e:
            return json.dumps({"success": False, "clips": [], "error": str(e)})

    # Directory for imported images
    image_import_dir = os.path.join(base_dir, 'imported_images')
    os.makedirs(image_import_dir, exist_ok=True)

    @app.route('/stream_image')
    def stream_image():
        file_path = request.query.get('path')
        if not file_path:
            abort(400, "Missing path parameter")
        file_path = urllib.parse.unquote(file_path)
        if not os.path.exists(file_path) or not os.path.isfile(file_path):
            abort(404, "Image file not found")

        directory, filename = os.path.split(os.path.abspath(file_path))
        mime, _ = mimetypes.guess_type(filename)
        if not mime or not mime.startswith('image/'):
            mime = 'image/png'

        response.set_header("Access-Control-Allow-Origin", "*")
        response.set_header("Cache-Control", "public, max-age=3600")
        return static_file(filename, root=directory, mimetype=mime)

    @app.route('/stream_video')
    def stream_video():
        file_path = request.query.get('path')
        if not file_path:
            abort(400, "Missing path parameter")
        file_path = urllib.parse.unquote(file_path)
        if not os.path.exists(file_path) or not os.path.isfile(file_path):
            abort(404, "Video file not found")

        directory, filename = os.path.split(os.path.abspath(file_path))
        mime, _ = mimetypes.guess_type(filename)
        if not mime or not mime.startswith('video/'):
            mime = 'video/mp4'

        response.set_header("Access-Control-Allow-Origin", "*")
        response.set_header("Accept-Ranges", "bytes")
        return static_file(filename, root=directory, mimetype=mime)

    @app.route('/upload_images', method=['POST', 'OPTIONS'])
    def upload_images():
        """
        Receives still image files via FormData (from Drag & Drop or HTML File Input).
        Saves them to imported_images/ and returns file paths.
        """
        response.content_type = 'application/json'
        response.set_header("Access-Control-Allow-Origin", "*")
        if request.method == 'OPTIONS':
            return "{}"

        try:
            uploaded_files = request.files.getall('image_files')
            if not uploaded_files:
                return json.dumps({"success": False, "images": [], "error": "No image files received."})

            images = []
            for f in uploaded_files:
                raw_filename = f.filename
                if not raw_filename:
                    continue

                save_path = os.path.join(image_import_dir, raw_filename)
                base_name, ext = os.path.splitext(raw_filename)
                counter = 1
                while os.path.exists(save_path):
                    save_path = os.path.join(image_import_dir, f"{base_name}_{counter}{ext}")
                    counter += 1

                f.save(save_path, overwrite=True)
                file_size = os.path.getsize(save_path)
                size_str = f"{file_size / (1024 * 1024):.2f} MB" if file_size >= 1024 * 1024 else f"{file_size / 1024:.1f} KB"

                images.append({
                    'path': save_path,
                    'filename': os.path.basename(save_path),
                    'size_bytes': file_size,
                    'size_formatted': size_str
                })

            return json.dumps({"success": True, "images": images})
        except Exception as e:
            return json.dumps({"success": False, "images": [], "error": str(e)})

    return app

