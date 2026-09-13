"""Local, selection-only Google Cloud audiobook builder."""
import hashlib
import json
import math
import os
import re
from pathlib import Path
import secrets
import shutil
import subprocess
import threading
import wave
import webbrowser
import zipfile
from urllib.parse import urlencode
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template, request, send_file

ROOT = Path(__file__).resolve().parent
BOOKS = ROOT / 'books'
STATE = ROOT / '.state'
CACHE = ROOT / '.audio-cache'
PACKAGES = ROOT / 'packages'
MAX_BYTES = 4999
BITRATES = (32000, 48000, 64000)
MONTH_LIMITS = {'Wavenet': 4_000_000, 'Neural2': 1_000_000}
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16_384
TOKEN = secrets.token_urlsafe(32)
lock = threading.RLock()
job = {'running': False, 'message': 'Bir kitap seçin.', 'done': 0, 'total': 0, 'error': '', 'package_url': ''}
stop = threading.Event()
voices_cache = {}
DEFAULT_SETTINGS = {'speaking_rate': 1.0, 'pitch': 0.0, 'volume_gain_db': 0.0}


def audio_settings(values=None):
    values = values or {}
    if not isinstance(values, dict):
        raise ValueError('Ses ayarları geçersiz.')
    limits = {'speaking_rate': (0.25, 2), 'pitch': (-20, 20), 'volume_gain_db': (-96, 16)}
    result = {}
    for name, default in DEFAULT_SETTINGS.items():
        try:
            number = float(values.get(name, default))
        except (TypeError, ValueError):
            raise ValueError(f'Geçersiz ses ayarı: {name}') from None
        low, high = limits[name]
        if not math.isfinite(number) or not low <= number <= high:
            raise ValueError(f'{name}: {low} ile {high} arasında olmalı.')
        result[name] = number
    return result


def atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_bytes(data)
    tmp.replace(path)


def json_read(path, default):
    return json.loads(path.read_text('utf-8')) if path.exists() else default


def month():
    return datetime.now(timezone.utc).strftime('%Y-%m')


def ledger_read():
    ledger = json_read(STATE / 'usage.json', {})
    if any(not isinstance(values, dict) for values in ledger.values()):
        raise ValueError('Eski sayaç kaydı model bilgisi içermiyor. Kayıt korunmuştur; model bazında aktarılması gerekiyor.')
    return ledger


def usage():
    with lock:
        ledger = ledger_read()
        return {family: {
            'monthly': ledger.get(month(), {}).get(family, 0),
            'gross': sum(values.get(family, 0) for values in ledger.values()),
            'limit': limit,
        } for family, limit in MONTH_LIMITS.items()}


def check_budget(family, count, external, used):
    if family not in MONTH_LIMITS:
        raise ValueError('Desteklenmeyen ses modeli.')
    if count < 0 or external < 0:
        raise ValueError('Karakter sayısı negatif olamaz.')
    if used + count + external > MONTH_LIMITS[family]:
        raise ValueError(f'{family}: aylık {MONTH_LIMITS[family]:,} karakter sınırı aşılıyor.')


def reserve(family, count, external):
    with lock:
        ledger = ledger_read()
        current_month = month()
        used = ledger.get(current_month, {}).get(family, 0)
        check_budget(family, count, external, used)
        ledger.setdefault(current_month, {})[family] = used + count
        atomic(STATE / 'usage.json', json.dumps(ledger).encode())


def book_paths():
    BOOKS.mkdir(exist_ok=True)
    return sorted([p for p in BOOKS.iterdir() if not p.is_symlink() and
                   ((p.is_dir() and p.name != 'audiobook' and not p.name.startswith('.'))
                    or (p.is_file() and p.suffix.lower() == '.txt'))], key=lambda p: p.name)


def resolve_book(name):
    for path in book_paths():
        if path.name == name:
            return path
    raise ValueError('Kitap bulunamadı.')


def source_files(book):
    files = [book] if book.is_file() else sorted(book.rglob('*.txt'))
    return [p for p in files if not p.is_symlink() and
            p.resolve().is_relative_to(BOOKS.resolve()) and
            'audiobook' not in p.relative_to(BOOKS).parts]


def split_text(text):
    if not text.strip():
        raise ValueError('Boş metin dosyası.')
    if len(text.encode('utf-8')) > MAX_BYTES:
        raise ValueError(f'Dosya {len(text.encode("utf-8"))} bayt; en fazla 4.999 bayt olabilir. Kitap hiç gönderilmedi; metni düzeltin.')
    return [text]


def configured_api_key():
    key = os.environ.get('GOOGLE_CLOUD_TTS_API_KEY', '').strip()
    path = STATE / 'google-api-key.txt'
    return key or (path.read_text('utf-8').strip() if path.exists() else '')


def client():
    from google.cloud import texttospeech
    key = configured_api_key()
    if key:
        return texttospeech.TextToSpeechClient(client_options={'api_key': key})
    return texttospeech.TextToSpeechClient()


def available_voices(language, family):
    if family not in MONTH_LIMITS:
        raise ValueError('Desteklenmeyen ses modeli.')
    key = (language, family)
    if key not in voices_cache:
        response = client().list_voices(request={'language_code': language}, timeout=30)
        voices_cache[key] = sorted(v.name for v in response.voices
                                   if f'-{family}-' in v.name and language in v.language_codes)
    return voices_cache[key]


def inspect_book(book):
    files = []
    for p in source_files(book):
        raw = p.read_bytes()
        entry = {'name': str(p.relative_to(book)) if book.is_dir() else p.name,
                 'bytes': len(raw), 'characters': 0, 'error': ''}
        try:
            text = raw.decode('utf-8')
            entry['characters'] = len(text)
            if not text.strip():
                entry['error'] = 'Boş metin'
        except UnicodeDecodeError:
            entry['error'] = 'UTF-8 değil'
        files.append(entry)
    return {'name': book.name, 'files': files, 'characters': sum(f['characters'] for f in files),
            'oversize': sum(f['bytes'] > MAX_BYTES for f in files)}


def plan(book, voice, settings=None, language=None):
    settings = audio_settings(settings)
    items = []
    for p in source_files(book):
        relative = p.relative_to(book) if book.is_dir() else Path(p.name)
        text = p.read_bytes().decode('utf-8')
        try:
            chunks = split_text(text)
        except ValueError as exc:
            raise ValueError(f'{relative}: {exc}') from exc
        identity = voice + '\0' + text
        # Keep existing default-speed cache usable without another billable request.
        if settings != DEFAULT_SETTINGS or (language and not voice.startswith(language + '-')):
            # paragraph_pause is retired, but it stays in the key so audio produced while
            # the control existed is still reused instead of re-synthesised.
            keyed = {**settings, 'paragraph_pause': 0.0}
            identity += '\0' + json.dumps({'settings': keyed, 'language': language or '-'.join(voice.split('-')[:2])}, sort_keys=True)
        digest = hashlib.sha256(identity.encode()).hexdigest()
        parts = []
        for index, chunk in enumerate(chunks):
            part_hash = hashlib.sha256(chunk.encode()).hexdigest()[:16]
            parts.append((chunk, CACHE / digest / f'{index}-{part_hash}.wav'))
        items.append((relative.with_suffix('.wav'), parts))
    if not items:
        raise ValueError('Bu kitapta .txt dosyası yok.')
    return items


def valid_wav(path):
    if not path.exists():
        return False
    try:
        with wave.open(str(path), 'rb') as audio:
            return audio.getnframes() > 0 and len(audio.readframes(audio.getnframes())) == (
                audio.getnframes() * audio.getnchannels() * audio.getsampwidth())
    except (wave.Error, EOFError):
        return False


def combine(parts, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp = destination.with_suffix('.tmp')
    with wave.open(str(tmp), 'wb') as output:
        expected = None
        for _, path in parts:
            with wave.open(str(path), 'rb') as source:
                params = (source.getnchannels(), source.getsampwidth(), source.getframerate())
                if expected is None:
                    expected = params
                    output.setnchannels(params[0])
                    output.setsampwidth(params[1])
                    output.setframerate(params[2])
                if params != expected:
                    raise ValueError('Ses parçalarının biçimleri uyuşmuyor.')
                output.writeframes(source.readframes(source.getnframes()))
    tmp.replace(destination)


def update(**values):
    with lock:
        job.update(values)


def preview_history():
    return json_read(STATE / 'previews.json', [])


def save_preview(source, book, filename, voice, settings):
    with lock:
        records = preview_history()
        identifier = secrets.token_hex(16)
        destination = CACHE / 'previews' / f'{identifier}.wav'
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        record = {'id': identifier, 'book': book, 'file': str(filename), 'voice': voice,
                  'settings': settings, 'created': datetime.now(timezone.utc).isoformat(),
                  'url': '/api/preview?' + urlencode({'id': identifier})}
        records.insert(0, record)
        atomic(STATE / 'previews.json', json.dumps(records, ensure_ascii=False).encode())
        return record


def convert(book, voice, language, items, external, family, preview=False, settings=None):
    current = ''
    try:
        settings = audio_settings(settings)
        from google.cloud import texttospeech as tts
        service = client()
        stage = CACHE / 'assembled' / book.name
        if preview:
            previous = BOOKS / 'audiobook' / book.name / items[0][0]
            with lock:
                known = any(r['book'] == book.name and r['file'] == str(items[0][0]) for r in preview_history())
                if not known and valid_wav(previous):
                    save_preview(previous, book.name, items[0][0], 'Önceki kayıt (ayarları bilinmiyor)', None)
        for index, (relative, parts) in enumerate(items):
            current = str(relative)
            for text, path in parts:
                if stop.is_set():
                    update(message='Durduruldu. Tamamlanan parçalar tekrar gönderilmez.')
                    return
                if valid_wav(path):
                    continue
                if len(text.encode('utf-8')) > MAX_BYTES:
                    raise ValueError('Gönderim öncesi bayt kontrolü başarısız.')
                update(message=f'Seslendiriliyor: {relative}')
                reserve(family, len(text), external)
                response = service.synthesize_speech(
                    request={'input': tts.SynthesisInput(text=text),
                             'voice': tts.VoiceSelectionParams(language_code=language, name=voice),
                             'audio_config': tts.AudioConfig(audio_encoding=tts.AudioEncoding.LINEAR16,
                                                             sample_rate_hertz=24000,
                                                             speaking_rate=settings['speaking_rate'],
                                                             pitch=settings['pitch'],
                                                             volume_gain_db=settings['volume_gain_db'])},
                    retry=None, timeout=120)
                atomic(path, response.audio_content)
                if not valid_wav(path):
                    raise ValueError('Google geçerli bir WAV dosyası döndürmedi.')
            combine(parts, stage / relative)
            update(done=index + 1)
        current = ''
        target = BOOKS / 'audiobook' / book.name
        for relative, _ in items:
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            tmp = destination.with_suffix('.tmp')
            shutil.copyfile(stage / relative, tmp)
            tmp.replace(destination)
        if not preview:
            atomic(target / 'playlist.m3u', ('#EXTM3U\n' + '\n'.join(p.as_posix() for p, _ in items) + '\n').encode())
        record = save_preview(target / items[0][0], book.name, items[0][0], voice, settings) if preview else None
        preview_url = record['url'] if record else ''
        update(message=f'Tamamlandı: books/audiobook/{book.name}', output=str(target), preview_url=preview_url,
               preview_settings=settings, preview_voice=voice)
    except Exception as exc:
        reason = friendly_error(exc)
        if current:
            reason = f'{current} dosyasında durdu.\n{reason}'
        update(message=f'İşlem durdu: {reason}', error=reason)
    finally:
        update(running=False)


def flat_name(relative):
    """One folder holds every chapter, so subdirectories fold into the file name."""
    return relative.with_suffix('').as_posix().replace('/', '_')


def package_items(book):
    items = []
    for text_path in source_files(book):
        relative = text_path.relative_to(book) if book.is_dir() else Path(text_path.name)
        wav = BOOKS / 'audiobook' / book.name / relative.with_suffix('.wav')
        if not valid_wav(wav):
            raise ValueError(f'{relative.with_suffix(".wav")} eksik veya bozuk. Önce kitabın tamamını seslendirin.')
        items.append((relative, text_path, wav))
    if not items:
        raise ValueError('Bu kitapta .txt dosyası yok.')
    return items


def encode_audio(source, destination, bitrate):
    commands = [['afconvert', '-f', 'm4af', '-d', 'aac', '-b', str(bitrate), str(source), str(destination)],
                ['ffmpeg', '-y', '-loglevel', 'error', '-i', str(source),
                 '-c:a', 'aac', '-b:a', f'{bitrate // 1000}k', str(destination)]]
    for command in commands:
        if not shutil.which(command[0]):
            continue
        result = subprocess.run(command, capture_output=True, timeout=600)
        if result.returncode and not (destination.exists() and destination.stat().st_size):
            detail = result.stderr.decode('utf-8', 'replace').strip()[:300]
            raise ValueError(f'{command[0]} sesi dönüştüremedi: {detail}')
        return command[0]
    raise ValueError('Ses dönüştürücü bulunamadı. macOS afconvert veya ffmpeg gerekir.')


def package(book, bitrate):
    current = ''
    try:
        items = package_items(book)
        PACKAGES.mkdir(parents=True, exist_ok=True)
        staging = CACHE / 'package'
        staging.mkdir(parents=True, exist_ok=True)
        target = PACKAGES / f'{book.name}.zip'
        tmp = target.with_name(target.name + '.tmp')
        chapters = []
        with zipfile.ZipFile(tmp, 'w') as bundle:
            for index, (relative, text_path, wav) in enumerate(items):
                if stop.is_set():
                    update(message='Paketleme durduruldu.')
                    return
                current = str(relative.with_suffix('.wav'))
                name = flat_name(relative)
                update(message=f'Sıkıştırılıyor: {relative}')
                encoded = staging / f'{name}.m4a'
                try:
                    encode_audio(wav, encoded, bitrate)
                    # Already-compressed audio is stored; only text and metadata deflate.
                    bundle.write(encoded, f'{book.name}/{name}.m4a', compress_type=zipfile.ZIP_STORED)
                    size = encoded.stat().st_size
                finally:
                    encoded.unlink(missing_ok=True)
                bundle.write(text_path, f'{book.name}/{name}.txt', compress_type=zipfile.ZIP_DEFLATED)
                with wave.open(str(wav), 'rb') as audio:
                    seconds = audio.getnframes() / audio.getframerate()
                chapters.append({'index': index + 1, 'title': name, 'audio': f'{name}.m4a',
                                 'text': f'{name}.txt', 'seconds': round(seconds, 3), 'bytes': size})
                update(done=index + 1)
            current = ''
            manifest = {'book': book.name, 'created': datetime.now(timezone.utc).isoformat(),
                        'audio': {'container': 'm4a', 'codec': 'aac', 'bitrate': bitrate,
                                  'sample_rate': 24000, 'channels': 1},
                        'seconds': round(sum(c['seconds'] for c in chapters), 3),
                        'chapters': chapters}
            bundle.writestr(f'{book.name}/manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2))
            playlist = ['#EXTM3U']
            for chapter in chapters:
                playlist += [f'#EXTINF:{round(chapter["seconds"])},{chapter["title"]}', chapter['audio']]
            bundle.writestr(f'{book.name}/playlist.m3u', '\n'.join(playlist) + '\n')
        tmp.replace(target)
        update(message=f'Paket hazır: packages/{book.name}.zip ({target.stat().st_size // 1048576} MB)',
               output=str(target), package_url='/api/package/download?' + urlencode({'book': book.name}))
    except Exception as exc:
        reason = friendly_error(exc)
        if current:
            reason = f'{current} dosyasında durdu.\n{reason}'
        update(message=f'Paketleme durdu: {reason}', error=reason)
    finally:
        tmp_path = PACKAGES / f'{book.name}.zip.tmp'
        tmp_path.unlink(missing_ok=True)
        update(running=False)


def google_hint(exc):
    try:
        from google.api_core import exceptions as api
        from google.auth import exceptions as auth
    except ImportError:
        return ''
    causes = [
        (auth.DefaultCredentialsError, 'Google kimlik doğrulaması eksik. API-KEY-KURULUMU.md dosyasındaki adımları tamamlayın.'),
        (auth.RefreshError, 'Google oturumu yenilenemedi. gcloud auth application-default login komutunu tekrar çalıştırın.'),
        (api.Unauthenticated, 'Google kimlik bilgisini kabul etmedi. API anahtarını veya hesap girişini yenileyin.'),
        (api.PermissionDenied, 'Google bu projede izin vermedi. Cloud Text-to-Speech API etkin mi ve anahtarın kısıtlamaları doğru mu kontrol edin.'),
        (api.InvalidArgument, 'Google isteği geçersiz buldu. Seçili dil kodunu, ses adını ve metni kontrol edin.'),
        (api.NotFound, 'Google seçili sesi bulamadı. Sesleri yeniden getirip listeden seçin.'),
        (api.ResourceExhausted, 'Google kotası doldu veya istek hızı sınırı aşıldı. Google Cloud kotalarınızı kontrol edin.'),
        (api.DeadlineExceeded, 'Google zamanında yanıt vermedi. Bağlantınızı kontrol edip tekrar deneyin.'),
        (api.ServiceUnavailable, 'Google servisi şu an yanıt vermiyor. Bir süre sonra tekrar deneyin.'),
        (OSError, 'Dosya veya ağ işlemi başarısız oldu. Disk alanını ve bağlantınızı kontrol edin.'),
    ]
    return next((hint for kind, hint in causes if isinstance(exc, kind)), '')


def friendly_error(exc):
    detail = str(exc).strip() or exc.__class__.__name__
    key = configured_api_key()
    if key:
        detail = detail.replace(key, '[gizli anahtar]')
    if len(detail) > 1200:
        detail = detail[:1200] + '…'
    hint = google_hint(exc)
    return f'{hint}\n\nAyrıntı: {detail}' if hint else detail


@app.before_request
def protect_local():
    if request.host.split(':')[0] not in ('127.0.0.1', 'localhost'):
        return jsonify(error='Yalnızca yerel erişim.'), 403
    if request.method == 'POST' and request.headers.get('X-Local-Token') != TOKEN:
        return jsonify(error='Sunucu bağlantısı yenilendi. Seçimleriniz korunuyor; tekrar oluştur düğmesine basın.', code='session_changed'), 403


@app.after_request
def prevent_stale_responses(response):
    response.headers['Cache-Control'] = 'no-store'
    return response


@app.get('/api/session')
def session():
    return jsonify(token=TOKEN)


@app.get('/')
def home():
    return render_template('index.html', token=TOKEN)


@app.get('/api/books')
def books():
    return jsonify(books=[inspect_book(p) for p in book_paths()], usage=usage())


@app.get('/api/voices')
def voices():
    try:
        return jsonify(voices=available_voices(request.args.get('language', 'tr-TR'),
                                               request.args.get('family', 'Wavenet')))
    except Exception as exc:
        return jsonify(error=friendly_error(exc)), 400


@app.get('/api/status')
def status():
    with lock:
        return jsonify(**job, usage=usage())


@app.get('/api/audio')
def audio():
    try:
        book = resolve_book(request.args.get('book'))
        root = (BOOKS / 'audiobook' / book.name).resolve()
        path = (root / request.args.get('file', '')).resolve()
        if not path.is_relative_to(root) or path.suffix != '.wav' or not path.is_file():
            raise ValueError('Ses bulunamadı.')
        return send_file(path, mimetype='audio/wav', conditional=True, max_age=0)
    except ValueError as exc:
        return jsonify(error=str(exc)), 404


@app.get('/api/preview')
def preview_audio():
    identifier = request.args.get('id', '')
    if not re.fullmatch(r'[0-9a-f]{32}', identifier):
        return jsonify(error='Ses bulunamadı.'), 404
    path = (CACHE / 'previews' / f'{identifier}.wav').resolve()
    if not path.is_relative_to(CACHE.resolve()) or not path.is_file():
        return jsonify(error='Ses bulunamadı.'), 404
    response = send_file(path, mimetype='audio/wav', conditional=True)
    response.headers['Cache-Control'] = 'no-store'
    return response


@app.get('/api/previews')
def list_previews():
    with lock:
        return jsonify(previews=preview_history())


@app.post('/api/previews/delete')
def delete_preview():
    identifier = (request.get_json(silent=True) or {}).get('id', '')
    with lock:
        records = preview_history()
        if not any(r['id'] == identifier for r in records):
            return jsonify(error='Ön dinleme bulunamadı.'), 404
        atomic(STATE / 'previews.json', json.dumps([r for r in records if r['id'] != identifier], ensure_ascii=False).encode())
        (CACHE / 'previews' / f'{identifier}.wav').unlink(missing_ok=True)
        if job.get('preview_url') == '/api/preview?' + urlencode({'id': identifier}):
            job['preview_url'] = ''
        return jsonify(ok=True)


@app.post('/api/start')
def start():
    with lock:
        if job['running']:
            return jsonify(error='Bir kitap zaten işleniyor.'), 409
        try:
            data = request.get_json()
            book = resolve_book(data['book'])
            language, family, voice = data['language'], data['family'], data['voice']
            external = int(data.get('external', 0))
            if external < 0:
                raise ValueError('Diğer kullanım negatif olamaz.')
            settings = audio_settings(data.get('settings'))
            items = plan(book, voice, settings, language)
            # Always validate the entire book, including for a single-file preview.
            preview_file = data.get('file')
            preview = preview_file is not None
            if preview:
                names = {str(p.relative_to(book)) if book.is_dir() else p.name for p in source_files(book)}
                if preview_file not in names:
                    raise ValueError('Seçili kitapta bu metin dosyası yok.')
                items = [item for item in items if item[0] == Path(preview_file).with_suffix('.wav')]
            remaining = sum(len(text) for _, parts in items for text, path in parts if not valid_wav(path))
            if family not in MONTH_LIMITS:
                raise ValueError('Desteklenmeyen ses modeli.')
            check_budget(family, remaining, external, usage()[family]['monthly'])
            if voice not in available_voices(language, family):
                raise ValueError('Bu dil/model için geçerli bir ses seçin.')
            stop.clear()
            job_id = secrets.token_hex(16)
            update(running=True, done=0, total=len(items), message='Başlatılıyor…', output='', preview_url='', package_url='', error='', job_id=job_id)
            threading.Thread(target=convert, args=(book, voice, language, items, external, family, preview, settings), daemon=True).start()
            return jsonify(ok=True, job_id=job_id)
        except Exception as exc:
            return jsonify(error=friendly_error(exc)), 400


@app.post('/api/package')
def start_package():
    with lock:
        if job['running']:
            return jsonify(error='Bir işlem zaten sürüyor.'), 409
        try:
            data = request.get_json()
            book = resolve_book(data['book'])
            bitrate = int(data.get('bitrate', 48000))
            if bitrate not in BITRATES:
                raise ValueError('Desteklenmeyen ses kalitesi.')
            items = package_items(book)
            stop.clear()
            job_id = secrets.token_hex(16)
            update(running=True, done=0, total=len(items), message='Paketleniyor…', output='',
                   preview_url='', package_url='', error='', job_id=job_id)
            threading.Thread(target=package, args=(book, bitrate), daemon=True).start()
            return jsonify(ok=True, job_id=job_id)
        except Exception as exc:
            return jsonify(error=friendly_error(exc)), 400


@app.get('/api/package/download')
def download_package():
    try:
        book = resolve_book(request.args.get('book'))
        path = (PACKAGES / f'{book.name}.zip').resolve()
        if not path.is_relative_to(PACKAGES.resolve()) or not path.is_file():
            raise ValueError('Paket bulunamadı.')
        return send_file(path, mimetype='application/zip', as_attachment=True,
                         download_name=f'{book.name}.zip', conditional=True)
    except ValueError as exc:
        return jsonify(error=str(exc)), 404


@app.post('/api/stop')
def cancel():
    stop.set()
    return jsonify(ok=True)


if __name__ == '__main__':
    import argparse
    import fcntl
    parser = argparse.ArgumentParser()
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--port', type=int, default=5001)
    args = parser.parse_args()
    STATE.mkdir(exist_ok=True)
    process_lock = (STATE / 'server.lock').open('a')
    try:
        fcntl.flock(process_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        parser.exit(1, 'Bu proje için bir sunucu zaten çalışıyor. http://127.0.0.1:5001\n')
    if not args.no_browser:
        threading.Timer(1, lambda: webbrowser.open(f'http://127.0.0.1:{args.port}')).start()
    app.run(host='127.0.0.1', port=args.port, debug=False, threaded=True)
