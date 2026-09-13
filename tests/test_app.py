import io
import json
import shutil
import tempfile
import unittest
import wave
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import app as a


def audio_bytes():
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(24000)
        wav.writeframes(b'\x00\x00' * 100)
    return buffer.getvalue()


class AudiobookTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.patches = [patch.object(a, name, root / name.lower())
                        for name in ('BOOKS', 'STATE', 'CACHE', 'PACKAGES')]
        for p in self.patches:
            p.start()
        a.BOOKS.mkdir()
        a.stop.clear()
        a.job.update(running=False, done=0, total=0, error='', message='',
                     preview_url='', package_url='', job_id='')

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.temp.cleanup()

    def book(self, name, text):
        path = a.BOOKS / name
        path.mkdir()
        (path / '001.txt').write_text(text, encoding='utf-8')
        return path

    def test_utf8_limit_and_exact_preservation(self):
        text = 'a' * 4999
        self.assertEqual(a.split_text(text), [text])
        for text in ('a' * 5000, 'ş' * 2500, '😀' * 1250):
            with self.assertRaises(ValueError):
                a.split_text(text)

    def test_preflight_blocks_entire_book(self):
        book = self.book('bad', 'normal')
        (book / '002.txt').write_text('ş' * 2500)
        with self.assertRaises(ValueError):
            a.plan(book, 'tr-TR-Wavenet-A')
        with patch.object(a, 'client') as google:
            response = a.app.test_client().post('/api/start', json={
                'book': 'bad', 'voice': 'tr-TR-Wavenet-A', 'language': 'tr-TR',
                'family': 'Wavenet', 'split': True,
            }, headers={'X-Local-Token': a.TOKEN})
            self.assertEqual(response.status_code, 400)
            google.assert_not_called()
        self.assertEqual(a.usage()['Wavenet']['monthly'], 0)

    def test_selected_only_output_and_resume(self):
        book = self.book('selected', 'Türkçe metin. ' * 100)
        self.book('unselected', 'NEVER SEND')
        voice = 'tr-TR-Wavenet-A'
        items = a.plan(book, voice)
        calls = []
        def synth(**kwargs):
            calls.append(kwargs['request']['input'].text)
            return SimpleNamespace(audio_content=audio_bytes())
        with patch.object(a, 'client', return_value=SimpleNamespace(synthesize_speech=synth)):
            a.convert(book, voice, 'tr-TR', items, 0, 'Wavenet')
            self.assertIn('Tamamlandı', a.job['message'])
            original_calls = len(calls)
            self.assertEqual(''.join(calls), (book / '001.txt').read_text())
            a.convert(book, voice, 'tr-TR', items, 0, 'Wavenet')
            self.assertEqual(len(calls), original_calls)
        out = a.BOOKS / 'audiobook' / 'selected' / '001.wav'
        with wave.open(str(out)) as wav:
            self.assertEqual(wav.getnframes(), 100 * original_calls)
        self.assertFalse((a.BOOKS / 'audiobook' / 'unselected').exists())
        self.assertEqual(a.usage()['Wavenet']['gross'], len(''.join(calls)))
        self.assertNotIn('audiobook', [p.name for p in a.book_paths()])

    def test_usage_limit_and_failure_reservation(self):
        a.reserve('Neural2', 900000, 0)
        with self.assertRaises(ValueError):
            a.reserve('Neural2', 100001, 0)
        with self.assertRaises(ValueError):
            a.reserve('Neural2', 1, 100000)
        self.assertEqual(a.usage()['Neural2']['monthly'], 900000)

    def test_failure_stops_without_retry(self):
        book = self.book('failure', 'Merhaba')
        service = SimpleNamespace(synthesize_speech=lambda **kwargs: (_ for _ in ()).throw(RuntimeError('offline')))
        with patch.object(a, 'client', return_value=service):
            a.convert(book, 'tr-TR-Wavenet-A', 'tr-TR', a.plan(book, 'tr-TR-Wavenet-A'), 0, 'Wavenet')
        self.assertIn('offline', a.job['message'])
        self.assertEqual(a.usage()['Wavenet']['monthly'], 7)
        self.assertFalse((a.BOOKS / 'audiobook').exists())

    def test_failure_reports_file_hint_and_detail(self):
        from google.api_core import exceptions as api
        from google.auth.exceptions import DefaultCredentialsError
        book = self.book('reason', 'Merhaba')
        (book / '002.txt').write_text('Dünya')
        voice = 'tr-TR-Wavenet-A'
        def synth(**kwargs):
            raise api.PermissionDenied('Cloud Text-to-Speech API has not been used in project 42')
        with patch.object(a, 'client', return_value=SimpleNamespace(synthesize_speech=synth)):
            a.convert(book, voice, 'tr-TR', a.plan(book, voice), 0, 'Wavenet')
        reason = a.job['error']
        self.assertIn('001.wav dosyasında durdu.', reason)
        self.assertIn('Cloud Text-to-Speech API etkin mi', reason)
        self.assertIn('has not been used in project 42', reason)
        self.assertIn(reason, a.job['message'])
        client = a.app.test_client()
        self.assertEqual(client.get('/api/status').json['error'], reason)
        self.assertIn('API-KEY-KURULUMU.md', a.friendly_error(DefaultCredentialsError('kimlik yok')))
        with patch.object(a, 'available_voices', return_value=[voice]), patch.object(a.threading, 'Thread'):
            response = client.post('/api/start', json={'book': 'reason', 'voice': voice,
                                                       'language': 'tr-TR', 'family': 'Wavenet'},
                                   headers={'X-Local-Token': a.TOKEN})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(a.job['error'], '')

    def test_monthly_gross_and_independent_limits(self):
        with patch.object(a, 'month', return_value='2026-09'):
            a.reserve('Wavenet', 4_000_000, 0)
            a.reserve('Neural2', 100, 0)
            with self.assertRaises(ValueError):
                a.reserve('Wavenet', 1, 0)
        with patch.object(a, 'month', return_value='2026-10'):
            self.assertEqual(a.usage()['Wavenet']['monthly'], 0)
            a.reserve('Wavenet', 500, 0)
            self.assertEqual(a.usage()['Wavenet']['gross'], 4_000_500)
            self.assertEqual(a.usage()['Neural2']['gross'], 100)
            self.assertEqual(a.usage()['Neural2']['monthly'], 0)
        with patch.object(a, 'client') as google:
            with self.assertRaises(ValueError):
                a.available_voices('tr-TR', 'Chirp3-HD')
            google.assert_not_called()

    def test_api_key_local_setup_and_redaction(self):
        a.atomic(a.STATE / 'google-api-key.txt', b'test-local-key')
        with patch.dict(a.os.environ, {'GOOGLE_CLOUD_TTS_API_KEY': ''}):
            with patch('google.cloud.texttospeech.TextToSpeechClient') as constructor:
                a.client()
                constructor.assert_called_once_with(client_options={'api_key': 'test-local-key'})
            self.assertNotIn('test-local-key', a.friendly_error(ValueError('bad test-local-key')))
        with patch.dict(a.os.environ, {'GOOGLE_CLOUD_TTS_API_KEY': 'test-env-key'}):
            self.assertEqual(a.configured_api_key(), 'test-env-key')

    def test_preview_selection_and_whole_book_validation(self):
        book = self.book('preview', 'Birinci')
        (book / '002.txt').write_text('İkinci')
        payload = {'book': 'preview', 'voice': 'tr-TR-Wavenet-A', 'language': 'tr-TR',
                   'family': 'Wavenet', 'file': '002.txt'}
        client = a.app.test_client()
        with patch.object(a, 'available_voices', return_value=[payload['voice']]), patch.object(a.threading, 'Thread') as thread:
            response = client.post('/api/start', json=payload, headers={'X-Local-Token': a.TOKEN})
            self.assertEqual(response.status_code, 200)
            args = thread.call_args.kwargs['args']
            self.assertEqual(len(args[3]), 1)
            self.assertEqual(args[3][0][0], Path('002.wav'))
            with patch.object(a, 'client', return_value=SimpleNamespace(synthesize_speech=lambda **kw: SimpleNamespace(audio_content=audio_bytes()))):
                a.convert(*args)
        self.assertEqual(a.usage()['Wavenet']['gross'], len('İkinci'))
        with client.get(a.job['preview_url']) as response:
            self.assertEqual(response.status_code, 200)
        self.assertFalse((a.BOOKS / 'audiobook' / 'preview' / '001.wav').exists())
        self.assertFalse((a.BOOKS / 'audiobook' / 'preview' / 'playlist.m3u').exists())
        (book / '001.txt').write_text('ş' * 2500)
        with patch.object(a, 'client') as google:
            response = client.post('/api/start', json=payload, headers={'X-Local-Token': a.TOKEN})
            self.assertEqual(response.status_code, 400)
            google.assert_not_called()

    def test_http_safety_and_selection(self):
        self.book('good', 'Merhaba')
        client = a.app.test_client()
        self.assertEqual(client.get('/').status_code, 200)
        self.assertEqual(client.get('/api/books').json['books'][0]['characters'], 7)
        self.assertEqual(client.post('/api/start', json={}).status_code, 403)
        self.assertEqual(client.get('/', headers={'Host': 'evil.example'}).status_code, 403)
        with self.assertRaises(ValueError):
            a.resolve_book('../outside')
        outside = Path(self.temp.name) / 'outside.txt'
        outside.write_text('secret')
        (a.BOOKS / 'good' / 'link.txt').symlink_to(outside)
        self.assertEqual(len(a.source_files(a.resolve_book('good'))), 1)

    def test_audio_settings_cache_and_request(self):
        source = 'A & B\n\nİkinci <paragraf>.'
        book = self.book('settings', source)
        voice = 'tr-TR-Wavenet-A'
        defaults = a.plan(book, voice)
        self.assertEqual(defaults, a.plan(book, voice, a.DEFAULT_SETTINGS, 'tr-TR'))
        options = a.audio_settings({'speaking_rate': 0.95, 'pitch': -2, 'volume_gain_db': 3})
        items = a.plan(book, voice, options, 'tr-TR')
        payload, path = items[0][1][0]
        self.assertNotEqual(path, defaults[0][1][0][1])
        # Markup and blank lines reach Google untouched; nothing is escaped or wrapped.
        self.assertEqual(payload, source)
        for setting, value in [('speaking_rate', 1.1), ('pitch', 1), ('volume_gain_db', 1)]:
            self.assertNotEqual(defaults[0][1][0][1], a.plan(book, voice, {setting: value})[0][1][0][1])
        requests = []
        def synth(**kwargs):
            requests.append(kwargs['request'])
            return SimpleNamespace(audio_content=audio_bytes())
        with patch.object(a, 'client', return_value=SimpleNamespace(synthesize_speech=synth)):
            a.convert(book, voice, 'tr-TR', items, 0, 'Wavenet', True, options)
            a.convert(book, voice, 'tr-TR', items, 0, 'Wavenet', True, options)
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0]['input'].text, source)
        self.assertFalse(requests[0]['input'].ssml)
        config = requests[0]['audio_config']
        self.assertAlmostEqual(config.speaking_rate, 0.95)
        self.assertEqual(config.pitch, -2)
        self.assertEqual(config.volume_gain_db, 3)
        self.assertEqual(a.usage()['Wavenet']['gross'], len(source))

    def test_settings_preflight_rejects_before_google(self):
        book = self.book('limits', 'a' * 4990)
        payload = {'book': book.name, 'voice': 'tr-TR-Wavenet-A', 'language': 'tr-TR',
                   'family': 'Wavenet', 'file': '001.txt'}
        invalid = [{'speaking_rate': 0}, {'pitch': 21}, {'volume_gain_db': -97},
                   {'pitch': float('nan')}, {'speaking_rate': float('inf')}, {'pitch': 'invalid'}]
        client = a.app.test_client()
        with patch.object(a, 'client') as google:
            for options in invalid:
                response = client.post('/api/start', json={**payload, 'settings': options},
                                       headers={'X-Local-Token': a.TOKEN})
                self.assertEqual(response.status_code, 400, options)
            google.assert_not_called()
        self.assertEqual(a.usage()['Wavenet']['gross'], 0)
        # Nothing inflates the payload now, so a file just under the cap is accepted.
        with patch.object(a, 'available_voices', return_value=[payload['voice']]), \
                patch.object(a.threading, 'Thread'):
            response = client.post('/api/start', json=payload, headers={'X-Local-Token': a.TOKEN})
        self.assertEqual(response.status_code, 200, response.json)

    def test_preview_history_is_immutable_and_deletable(self):
        book = self.book('history', 'Merhaba')
        voice = 'tr-TR-Wavenet-A'
        calls = []
        def synth(**kwargs):
            rate = kwargs['request']['audio_config'].speaking_rate
            calls.append(rate)
            buffer = io.BytesIO()
            with wave.open(buffer, 'wb') as wav:
                wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(24000)
                wav.writeframes(b'\x00\x00' * int(100 / rate))
            return SimpleNamespace(audio_content=buffer.getvalue())
        with patch.object(a, 'client', return_value=SimpleNamespace(synthesize_speech=synth)):
            for rate in [1, 0.5]:
                options = a.audio_settings({'speaking_rate': rate})
                a.convert(book, voice, 'tr-TR', a.plan(book, voice, options), 0, 'Wavenet', True, options)
        records = a.preview_history()
        self.assertEqual(len(records), 2)
        self.assertEqual(calls, [1, 0.5])
        client = a.app.test_client()
        with client.get(records[0]['url']) as slow, client.get(records[1]['url']) as normal:
            self.assertNotEqual(slow.data, normal.data)
            self.assertEqual(normal.headers['Cache-Control'], 'no-store')
        count = a.usage()
        response = client.post('/api/previews/delete', json={'id': records[0]['id']}, headers={'X-Local-Token': a.TOKEN})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(client.get(records[0]['url']).status_code, 404)
        self.assertEqual(len(a.preview_history()), 1)
        self.assertEqual(a.usage(), count)
        self.assertTrue((a.BOOKS / 'audiobook' / 'history' / '001.wav').exists())


    def voice_book(self, name, chapters):
        book = self.book(name, chapters[0])
        for relative, text in chapters[1].items():
            path = book / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding='utf-8')
        voice = 'tr-TR-Wavenet-A'
        service = SimpleNamespace(synthesize_speech=lambda **kw: SimpleNamespace(audio_content=audio_bytes()))
        with patch.object(a, 'client', return_value=service):
            a.convert(book, voice, 'tr-TR', a.plan(book, voice), 0, 'Wavenet')
        return book

    @unittest.skipUnless(shutil.which('afconvert') or shutil.which('ffmpeg'), 'ses dönüştürücü yok')
    def test_package_is_one_zip_of_one_flat_folder(self):
        book = self.voice_book('paket', ('Birinci bölüm.', {'alt/002.txt': 'İkinci bölüm.'}))
        a.package(book, 48000)
        self.assertEqual(a.job['error'], '')
        archive = a.PACKAGES / 'paket.zip'
        self.assertTrue(archive.is_file())
        with zipfile.ZipFile(archive) as bundle:
            names = sorted(bundle.namelist())
            self.assertEqual(names, ['paket/001.m4a', 'paket/001.txt', 'paket/alt_002.m4a',
                                     'paket/alt_002.txt', 'paket/manifest.json', 'paket/playlist.m3u'])
            # Subfolders fold into the name so everything sits in a single directory.
            self.assertTrue(all(name.count('/') == 1 for name in names))
            self.assertEqual(bundle.read('paket/alt_002.txt').decode('utf-8'), 'İkinci bölüm.')
            self.assertEqual(bundle.getinfo('paket/001.m4a').compress_type, zipfile.ZIP_STORED)
            manifest = json.loads(bundle.read('paket/manifest.json'))
            playlist = bundle.read('paket/playlist.m3u').decode('utf-8')
        self.assertEqual([c['audio'] for c in manifest['chapters']], ['001.m4a', 'alt_002.m4a'])
        self.assertEqual([c['text'] for c in manifest['chapters']], ['001.txt', 'alt_002.txt'])
        self.assertEqual(manifest['audio'], {'container': 'm4a', 'codec': 'aac', 'bitrate': 48000,
                                             'sample_rate': 24000, 'channels': 1})
        self.assertTrue(playlist.startswith('#EXTM3U\n'))
        self.assertIn('alt_002.m4a', playlist)
        self.assertFalse(list(a.PACKAGES.glob('*.tmp')))
        client = a.app.test_client()
        with client.get(a.job['package_url']) as response:
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data, archive.read_bytes())

    def test_package_requires_finished_audio_and_valid_bitrate(self):
        book = self.book('eksik', 'Birinci bölüm.')
        (book / '002.txt').write_text('Sesi üretilmemiş bölüm.', encoding='utf-8')
        client = a.app.test_client()
        self.assertEqual(client.post('/api/package', json={'book': 'eksik'}).status_code, 403)
        with patch.object(a, 'encode_audio') as encoder:
            response = client.post('/api/package', json={'book': 'eksik'},
                                   headers={'X-Local-Token': a.TOKEN})
            self.assertEqual(response.status_code, 400)
            self.assertIn('001.wav', response.json['error'])
            encoder.assert_not_called()
        self.assertFalse(a.PACKAGES.exists())
        service = SimpleNamespace(synthesize_speech=lambda **kw: SimpleNamespace(audio_content=audio_bytes()))
        with patch.object(a, 'client', return_value=service):
            a.convert(book, 'tr-TR-Wavenet-A', 'tr-TR', a.plan(book, 'tr-TR-Wavenet-A'), 0, 'Wavenet')
        with patch.object(a, 'encode_audio') as encoder:
            response = client.post('/api/package', json={'book': 'eksik', 'bitrate': 96000},
                                   headers={'X-Local-Token': a.TOKEN})
            self.assertEqual(response.status_code, 400)
            encoder.assert_not_called()
        self.assertEqual(client.get('/api/package/download?book=eksik').status_code, 404)

    def test_package_failure_names_the_file_and_leaves_no_partial_zip(self):
        book = self.voice_book('bozuk', ('Birinci bölüm.', {'002.txt': 'İkinci bölüm.'}))
        with patch.object(a, 'encode_audio', side_effect=ValueError('afconvert sesi dönüştüremedi: bozuk giriş')):
            a.package(book, 48000)
        self.assertIn('001.wav dosyasında durdu.', a.job['error'])
        self.assertIn('afconvert sesi dönüştüremedi', a.job['error'])
        self.assertFalse(a.job['running'])
        self.assertFalse((a.PACKAGES / 'bozuk.zip').exists())
        self.assertFalse(list(a.PACKAGES.glob('*.tmp')))


if __name__ == '__main__':
    unittest.main()
