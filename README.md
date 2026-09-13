# Text to Audiobook · Metinden Sesli Kitap

**English —** An **epub / mobi to audiobook** pipeline. Books start as ebook
files; you use an **AI chatbot** to convert and split them into numbered plain
`.txt` chapters, then this tool synthesises those chapters into speech through
**Google Cloud Text-to-Speech** (WaveNet / Neural2) and packages the result as a
single **zip of AAC/m4a audio paired with its source text** for your phone. Built
to stay inside the **free monthly character quota**: it validates the whole book
before sending anything, counts every character before spending it, and caches
finished audio so you never pay for the same text twice. The web interface is a
local Python/Flask app on `127.0.0.1`, but **synthesis is a cloud service** — it
needs an internet connection and a Google Cloud account with billing enabled.
Works with any language Google supports; the interface is Turkish.

**Türkçe —** **Epub / mobi'den sesli kitaba** dönüştürme hattı. Kitaplar e-kitap
dosyası olarak başlar; önce bir **yapay zekâ sohbet botuyla** numaralandırılmış
düz `.txt` bölümlere ayrılır, sonra bu araç o bölümleri **Google Cloud
Text-to-Speech** (WaveNet / Neural2) ile seslendirir ve telefona taşımak için her
bölümün **AAC/m4a sesini metniyle birlikte** tek bir zip'te paketler. **Ücretsiz
aylık karakter kotası** içinde kalmak üzere tasarlandı: hiçbir şey göndermeden
önce kitabın tamamını doğrular, karakterleri harcamadan önce sayar ve tamamlanmış
sesleri önbelleğe alarak aynı metin için ikinci kez ödeme yapmanızı engeller.
**Türkçe seslendirme** için hazır gelir (`tr-TR`, WaveNet). Arayüz `127.0.0.1`
üzerinde çalışan yerel bir Python/Flask uygulamasıdır; ancak **seslendirme bir
bulut hizmetidir** — internet bağlantısı ve faturalandırması açık bir Google
Cloud hesabı gerekir.

*Keywords / Anahtar kelimeler: epub to audiobook, mobi to audiobook, text to
speech, TTS, audiobook generator, sesli kitap, e-kitabı sesli kitaba çevirme,
metin okuma, Türkçe seslendirme, Turkish text to speech, Google Cloud TTS,
WaveNet, Neural2, ebook to mp3, Flask, Python.*

> The interface and its messages are in Turkish. This document and
> [API-KEY-SETUP.md](API-KEY-SETUP.md) are in English, each with a Turkish
> summary at the end. · Arayüz Türkçedir; belgeler İngilizcedir ve sonunda
> Türkçe özet vardır.

## How the pipeline works

```
  epub / mobi ebook
        │
        │   step 1 — an AI chatbot, using a formatting prompt
        ▼
  books/Book_Name/001_chapter.txt …        UTF-8 chapters, each ≤ 4,999 bytes
        │
        │   step 2 — this app → Google Cloud Text-to-Speech    (cloud, billed)
        ▼
  books/audiobook/Book_Name/*.wav          lossless 24 kHz
        │
        │   step 3 — this app → afconvert / ffmpeg             (local, free)
        ▼
  packages/Book_Name.zip                   AAC audio + text + manifest
```

**Only step 2 leaves your machine or costs anything.** Step 1 happens in whatever
chatbot you prefer, before the app is involved. Step 3 is pure local
transcoding — no network, no quota, repeatable as often as you like.

### Step 1 — preparing a book from epub or mobi

This app does not read ebook formats. It expects a folder of plain text chapters,
which you produce beforehand by having an AI chatbot convert the ebook and split
it into numbered files:

```
books/Book_Name/
├── 001_00_preface_part_01.txt
├── 002_01_intro_part_01.txt
├── 002_01_intro_part_02.txt
└── …
```

Two rules matter when splitting:

- **The limit is 4,999 UTF-8 bytes per file, not characters.** Turkish letters
  (`ş ğ ı İ ç ö ü`), accented Latin, and any non-ASCII text cost two or more
  bytes each, so a 4,900-character chapter can easily be 5,400 bytes and get
  rejected. Target roughly 4,000–4,500 characters to leave headroom.
- **Sort order is playback order.** Zero-padded numeric prefixes
  (`001_`, `002_`, …) keep chapters in sequence, since the playlist and the
  package manifest are both ordered by filename.

Split on paragraph boundaries rather than mid-sentence — each file becomes one
uninterrupted synthesis request, and a chapter cut mid-sentence will sound like
it.

## Running it

```sh
uv venv .venv
uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/python app.py
```

Your browser opens http://127.0.0.1:5001 automatically. The server listens only
on localhost and refuses requests arriving under any other host name. Pick a
book, a model and a voice, then press **Seçili kitabı seslendir** ("synthesise
the selected book"). Listing voices never sends any book text.

## Google Cloud setup

> For the full walkthrough — creating a key, restricting it, rotating it,
> revoking it, and a table mapping every in-app error to its fix — see
> **[API-KEY-SETUP.md](API-KEY-SETUP.md)**. What follows is the short version.

### With an API key (no CLI required)

1. In the [Google Cloud Console](https://console.cloud.google.com/), create or
   select a project and attach a **billing account**.
2. Enable [Cloud Text-to-Speech API](https://console.cloud.google.com/apis/library/texttospeech.googleapis.com)
   on that same project.
3. On the [Credentials](https://console.cloud.google.com/apis/credentials) page
   choose **Create credentials → API key**, then edit it and under
   **API restrictions → Restrict key** select only **Cloud Text-to-Speech API**.
4. Run `.venv/bin/python setup_google.py` in the project folder and paste the key
   into the hidden prompt. It is never echoed to the screen or the shell history.
5. Start the app. Press **Google seslerini getir** ("fetch Google voices") to test
   the connection — this sends no book text.

The key is stored in `.state/google-api-key.txt` with owner-only permissions
(`0600`). It is git-ignored, never sent to the browser, and redacted from error
messages. To change it, run the setup command again. You may set the
`GOOGLE_CLOUD_TTS_API_KEY` environment variable instead; it takes priority over
the file. Without an API key the app falls back to account credentials below.

### With a Google account (alternative)

1. Create or select a project and attach a billing account.
2. Enable Cloud Text-to-Speech API on it.
3. Install the [Google Cloud CLI](https://cloud.google.com/sdk/docs/install).
4. Run, with your own project id:

```sh
gcloud auth login
gcloud config set project PROJECT_ID
gcloud auth application-default login
gcloud auth application-default set-quota-project PROJECT_ID
```

Your account needs `serviceusage.services.use` on that project. Alternatively,
keep a service-account JSON file outside the project folder and point
`GOOGLE_APPLICATION_CREDENTIALS` at its full path. Never paste credentials into
a chat window or the web interface.

## Voices, pricing and the usage ledger

Three voice families are offered: **WaveNet**, **Neural2** and **Chirp 3: HD**.
As of 12 September 2026 there is **no Turkish Neural2 voice** in the official
list — the app opens with Turkish and **WaveNet** preselected and warns you if
you pick a combination that does not exist. Chirp 3: HD **does** have Turkish
voices (names like `tr-TR-Chirp3-HD-Charon`). Voices are listed from the live
API, so you only ever see what actually exists. The language field can be
changed for books in other languages.

Neural2 is free for the first 1,000,000 characters per month, then $16 per
million. WaveNet is free for the first 4,000,000, then $4 per million.
Chirp 3: HD is free for the first 1,000,000, then $30 per million — the most
natural-sounding of the three and by far the most expensive past the free tier.
This is not a permanent price guarantee and billing must be enabled. Check the
current figures yourself:
[pricing](https://cloud.google.com/text-to-speech/pricing),
[voices](https://docs.cloud.google.com/text-to-speech/docs/list-voices-and-types),
[quotas](https://docs.cloud.google.com/text-to-speech/quotas).

The app enforces its own monthly ceiling — 4 million characters for WaveNet,
1 million for Neural2, 1 million for Chirp 3: HD — with a separate monthly and
all-time ("gross") counter per model. Counting is by **calendar month**: the
monthly counter restarts when the UTC calendar month changes, and the gross
counter never resets. Audio served from cache is not counted again.

`.state/usage.json` is written **before** each request is sent, so failed or
ambiguous requests still count. There are no automatic retries. This ledger does
not read your Google bill: usage from other devices, projects or applications
must be entered by hand in the corresponding model's field, where it counts
toward the monthly limit without being added to the stored counters. Standard
voices share the free SKU with WaveNet, so include that usage there too. Google's
own billing period and SKU definitions are what actually govern your bill; this
app does not guarantee a $0 invoice. **Do not delete the ledger file.**

## Previewing before you commit

Previews are kept, with the voice and settings that produced them, in the
**Ön dinlemeler · karşılaştır** ("previews · compare") list. Each has its own
player, and a new preview never replaces an old one, so you can compare voices
side by side. The **×** button deletes only that preview copy — the book output,
the reuse cache and the spent-character counters are all preserved.

Changing any setting clears the player at the top; older recordings remain
playable from the list below. When a request fails, the error stays visible and
a previous result is never presented as if it were newly generated.

Errors appear in a red box directly beneath the **Seçili bölümü oluştur**
("generate selected chapter") button. For a byte-limit failure it names the file,
its byte count and how to fix it. For a synthesis failure it reports which file
it stopped on, a plain-language explanation for recognised error types, and in
every case Google's original response on an `Ayrıntı:` ("detail") line. The API
key is redacted from that text.

Your book, chapter, voice, generation settings and last error are stored locally
in the browser and restored on reload. The API key is never part of that record.
If the server restarts, the page picks up a fresh session without needing a
reload, and does **not** silently retry the synthesis request.

### Audio controls

Speaking rate (0.25–2×), pitch (−20 to +20 semitones) and volume gain (−96 to
+16 dB) are adjustable. Defaults are 1×, 0 and 0 dB; the reset button returns to
those. Gains above +10 dB are not recommended.

**Chirp 3: HD accepts speaking rate but not the pitch or volume parameters.**
With that family selected, both must stay at 0 — the app refuses the request
before anything is sent (and counted), and the page shows a notice when the
family is picked.

Text is sent to Google exactly as it appears in the file: no SSML wrapper, no
escaping. The bytes sent are the bytes on disk, so your 4,999-byte chunking
behaves exactly as the file suggests. There is no automatic splitting. (An
inter-paragraph pause control used to exist; it was removed precisely because
its SSML tags inflated the payload past that limit.)

Generation settings are part of the cache key. Identical text, voice and settings
reuse finished audio; changing a setting and regenerating costs new characters.
Audio produced under earlier default settings stays reusable. The player's
separate **Dinleme hızı** ("playback rate") control is purely local — it sends
nothing to Google, spends no characters, and does not alter the saved file.

To preview, select a text file from the chosen book and press **Seçili bölümü
oluştur**. Only that file is synthesised. The whole book is still validated
first: if even one file exceeds 4,999 bytes, no request is sent at all. Preview
characters are added once to the model's monthly and gross counters. Running the
full book afterwards with the same voice and settings reuses that chapter.
A preview never modifies the full book's playlist.

## Files and layout

- Add each book as `books/Book_Name/*.txt`, produced by the ebook conversion in
  [step 1](#step-1--preparing-a-book-from-epub-or-mobi). Subfolders are
  preserved. A single `books/Book.txt` also works. UTF-8 is required.
- The entire selected book is validated before anything starts, and each request
  is separately checked against the **4,999 UTF-8 byte** limit.
- Oversized files block the whole book by design. There is no automatic
  splitting: if even one file exceeds the limit, nothing is sent. Fix the text
  and reload the page.
- Each `file.txt` produces a `file.wav` at 24 kHz. WAV is lossless and much
  larger than compressed formats — leave room on disk for the cache and copies.
- Finished parts live in `.audio-cache/`, keyed by a hash of voice, text and
  settings. Resuming with the same text and voice never re-sends valid parts.
- When a book completes, the audio is copied to `books/audiobook/Book_Name/`
  with a `playlist.m3u` ordered by filename. Running the same book with a
  different voice overwrites the same filenames in that output.
- The stop button takes effect after the current Google request finishes.
  Reopen the app and select the same book and voice to continue. Use Ctrl+C in
  the terminal to quit.
- Run only **one server** per working directory at a time; a lock file enforces
  this.

## Phone package

Once a book's audio is complete, section **4. Telefon paketi** ("phone package")
produces a single zip at `packages/Book_Name.zip`. Inside is one flat folder
holding each chapter's audio and text side by side:

```
Book_Name.zip
└── Book_Name/
    ├── 001_preface.m4a
    ├── 001_preface.txt
    ├── 002_intro.m4a
    ├── 002_intro.txt
    ├── manifest.json
    └── playlist.m3u
```

For books with subfolders the path folds into the filename
(`part1/002.txt` → `part1_002.m4a`), so everything stays in one directory and
names cannot collide.

WAV files are converted to AAC (`.m4a`, 24 kHz, mono). At 48 kbps the package is
roughly **8× smaller** than the source WAVs — a measured 11-hour book went from
1.77 GB to 234 MB. Quality is selectable at 32 / 48 / 64 kbps. Conversion uses
macOS's built-in `afconvert`, falling back to `ffmpeg` elsewhere. Nothing is sent
to Google and no characters are spent, so packaging is free and repeatable.

`manifest.json` is meant for a phone app to read: the ordered chapter list, each
chapter's audio and text filename, duration in seconds and byte size, plus codec,
bitrate, sample rate and channel count. `playlist.m3u` is written with `#EXTINF`
duration and title lines.

A package is only produced when **every** chapter has valid audio. If a WAV is
missing or corrupt, the app names the offending file and writes no zip. A partial
zip is never left on disk.

## Verification

```sh
.venv/bin/python -m unittest discover -s tests -v
node tests/ui.test.cjs
```

The tests never send text to Google. Against a fake service they verify the byte
limit, exact text preservation, that only the selected book is ever sent, resume
behaviour, the usage ceiling, API-key redaction, failure reporting, and the
single-folder structure of the zip package.

---

## Türkçe özet

Bu proje epub/mobi bir e-kitabı sesli kitaba çevirmek için üç adımlı bir hattır:

```
epub / mobi
    │  1. adım — yapay zekâ sohbet botu, biçimlendirme istemiyle
    ▼
books/Kitap_Adi/001_bolum.txt …       her dosya en fazla 4.999 bayt
    │  2. adım — bu uygulama → Google Cloud TTS      (bulut, ücretli)
    ▼
books/audiobook/Kitap_Adi/*.wav       kayıpsız 24 kHz
    │  3. adım — bu uygulama → afconvert / ffmpeg    (yerel, ücretsiz)
    ▼
packages/Kitap_Adi.zip                AAC ses + metin + manifest
```

**Yalnızca 2. adım bilgisayarınızdan çıkar ve ücretlendirilir.** 1. adım
uygulamaya girmeden önce, istediğiniz sohbet botunda yapılır. 3. adım tamamen
yerel dönüştürmedir: ağ yok, kota yok, istediğiniz kadar tekrarlanabilir.

Uygulama e-kitap biçimlerini okumaz; hazır `.txt` bölümleri bekler. Arayüz
`127.0.0.1` üzerinde çalışan yerel bir uygulamadır, ancak **seslendirme bulut
hizmetidir**: internet ve faturalandırması açık bir Google Cloud hesabı gerekir.
Arayüz Türkçedir; bu belge ve [API-KEY-SETUP.md](API-KEY-SETUP.md) İngilizcedir.

**Çalıştırma:** `uv venv .venv` → `uv pip install --python .venv/bin/python -r
requirements.txt` → `.venv/bin/python app.py`. Tarayıcı
http://127.0.0.1:5001 adresini açar; sunucu yalnızca bu bilgisayardan erişilebilir.

**Anahtar:** Google Cloud'da proje açıp faturalandırma bağlayın, Text-to-Speech
API'yi etkinleştirin, yalnızca bu API ile kısıtlanmış bir API anahtarı üretin ve
`.venv/bin/python setup_google.py` ile kaydedin. Ayrıntılı anlatım ve hata
çözümleri için **[API-KEY-SETUP.md](API-KEY-SETUP.md)** dosyasına bakın.

**Maliyet koruması:** Aylık ücretsiz hak WaveNet için 4.000.000, Neural2 ve
Chirp 3: HD için 1.000.000 karakterdir (Chirp 3: HD kota sonrası milyon başına
$30 ile en pahalısıdır; perde ve ses seviyesi ayarlarını desteklemez, okuma
hızını destekler). Sayaçlar takvim ayına göre işler: aylık sayaç UTC takvim ayı
değişince sıfırdan başlar, gross sayaç hiç sıfırlanmaz. Uygulama her modelin
aylık ve gross sayacını ayrı tutar,
karakterleri göndermeden **önce** `.state/usage.json` dosyasına yazar ve
başarısız istekleri de sayar. Tamamlanmış sesler önbellekten yeniden kullanılır,
ikinci kez ücretlendirilmez. Bu sayaç Google faturasını okumaz; kesin tutar için
Google Cloud Faturalandırma'yı kontrol edin. Sayaç dosyasını silmeyin.

**Bayt sınırı:** Her istek en fazla **4.999 UTF-8 bayt** olabilir. Metin Google'a
olduğu gibi gönderilir; SSML eklenmez, kaçış yapılmaz. Tek bir dosya bile sınırı
aşarsa kitabın hiçbir parçası gönderilmez. Otomatik bölme yapılmaz. Türkçe
harfler iki bayt tuttuğu için karakter sayısı değil **bayt** sayısı önemlidir.

**Ön dinleme:** Bir bölümü seçip önce dinleyebilirsiniz. Ön dinlemeler ses ve
ayar bilgisiyle saklanır, birbirinin üzerine yazılmaz; farklı sesleri
karşılaştırabilirsiniz. Hatalar kırmızı kutuda, hangi dosyada durulduğu ve
Google'ın özgün yanıtıyla birlikte gösterilir; anahtar bu metinden çıkarılır.

**Telefon paketi:** Kitabın sesi tamamlandıktan sonra **4. Telefon paketi**
bölümü `packages/Kitap_Adi.zip` üretir. Zip'in içinde tek bir klasör vardır; her
bölümün `.m4a` sesi ile `.txt` metni yan yana durur, ayrıca `manifest.json` ve
`playlist.m3u` bulunur. WAV dosyaları AAC'ye dönüştürülür ve paket yaklaşık
**8 kat küçülür** (ölçülen: 11 saatlik kitap 1,77 GB → 234 MB). Paketleme
Google'a istek göndermez, ücretsizdir ve tekrarlanabilir.

**Doğrulama:** `.venv/bin/python -m unittest discover -s tests -v` ve
`node tests/ui.test.cjs`. Testler Google'a metin göndermez.
