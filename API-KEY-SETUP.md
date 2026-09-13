# Adding your own Google API key

This app generates speech through **your** Google Cloud account. No key ships
with this repository — you must create your own and store it locally before the
app can do anything. All usage is billed to your account.

*Türkçe özet en altta.*

## Before you start

- You need a Google Cloud account with **billing enabled**. Without a billing
  account attached, requests are rejected even if the key itself is valid.
- The free tier is monthly: **4,000,000 characters for WaveNet**, **1,000,000 for
  Neural2**. The app refuses to exceed those ceilings, but Google's own bill is
  what counts.
- The key never leaves your machine. It is not sent to the browser, not committed
  to git, and it is replaced with `[gizli anahtar]` in any error message.

## Method 1 — API key (recommended, no CLI needed)

### 1. Project and billing

In the [Google Cloud Console](https://console.cloud.google.com/), create or
select a project, then attach a **billing account** to it.

### 2. Enable the Text-to-Speech API

On that same project, open
[Cloud Text-to-Speech API](https://console.cloud.google.com/apis/library/texttospeech.googleapis.com)
and press **Enable**. Skipping this produces the error
"Google bu projede izin vermedi" ("Google denied permission on this project").

### 3. Create and restrict the key

On the [Credentials](https://console.cloud.google.com/apis/credentials) page
choose **Create credentials → API key**. As soon as it appears, press
**Edit API key** and restrict it:

- **API restrictions → Restrict key** → tick only **Cloud Text-to-Speech API**.
- **Application restrictions** can stay `None`; the key already never leaves this
  machine.

An unrestricted key, if leaked, works against **every** API in your project.
Do not skip this step.

### 4. Store the key locally

From the project folder:

```sh
.venv/bin/python setup_google.py
```

Paste the key into the hidden prompt and press Enter. **Nothing is echoed** and
it does not enter your shell history.

The key is written to `.state/google-api-key.txt` with owner-only read/write
permissions (`0600`). The `.state/` folder is in `.gitignore`, so it cannot be
committed by accident.

### 5. Verify

Start the app:

```sh
.venv/bin/python app.py
```

Press **Google seslerini getir** ("fetch Google voices"). If a voice list
appears, the key works. That button sends no book text and spends no quota.

## Method 2 — Environment variable

If you would rather not write the key to a file:

```sh
export GOOGLE_CLOUD_TTS_API_KEY="your-key"
.venv/bin/python app.py
```

This variable **takes priority over the file**. To make it permanent, add it to
your shell profile (`~/.zshrc`) — but note the key then sits in plain text in
that profile.

## Method 3 — Google account sign-in (no key)

You can authenticate as yourself instead of using an API key. This needs the
[Google Cloud CLI](https://cloud.google.com/sdk/docs/install):

```sh
gcloud auth login
gcloud config set project PROJECT_ID
gcloud auth application-default login
gcloud auth application-default set-quota-project PROJECT_ID
```

Your account needs the `serviceusage.services.use` permission on that project.

For a service account, keep the JSON file **outside the project folder** and
point to it by full path:

```sh
export GOOGLE_APPLICATION_CREDENTIALS="/a/safe/path/service-account.json"
```

The app checks for an API key first and falls back to these credentials.

## Changing, deleting and revoking

- **Change:** run `setup_google.py` again; it overwrites the file.
- **Delete locally:** `rm .state/google-api-key.txt`
- **Revoke:** if a key leaks, deleting the local file is **not enough**. Go to
  [Credentials](https://console.cloud.google.com/apis/credentials), delete the
  key there, then create a new one.

Do not delete `.state/usage.json` — your character counters live in it.

## Troubleshooting

The app shows failures in a red box beneath the **Seçili bölümü oluştur**
button: which file it stopped on, a plain-language explanation, and Google's
original response on an `Ayrıntı:` ("detail") line.

| Message shown in the app | Cause and fix |
| --- | --- |
| Google bu projede izin vermedi | Text-to-Speech API not enabled, or the key restriction is wrong. Recheck steps 2 and 3. |
| Google kimlik bilgisini kabul etmedi | Key mistyped, truncated or revoked. Re-enter it with `setup_google.py`. |
| Google kimlik doğrulaması eksik | Neither a key nor account credentials found. Complete Method 1 or 3. |
| Google kotası doldu | Monthly free tier exhausted, or the per-minute rate limit was hit. Check your Google Cloud quotas. |
| Google seçili sesi bulamadı | Voice name does not match the language/model. Press **Google seslerini getir** and pick from the list. |
| Google isteği geçersiz buldu | Bad language code or voice name. Use `tr-TR` for Turkish. |

If billing is not attached, most failures surface as a permission error — verify
billing first.

## Security summary

- The key lives only in `.state/google-api-key.txt`, mode `0600`.
- `.state/`, `books/`, `.audio-cache/`, `packages/`, `*credentials*.json`, `.env`
  and all `*.wav` / `*.m4a` / `*.zip` files are git-ignored.
- The key is never sent to the browser; the page only ever sees voice **names**.
- Error text has the key substituted with `[gizli anahtar]`.
- The server binds to `127.0.0.1` only and rejects requests under any other host
  name. Every POST additionally requires a per-process random token.
- Never paste your key into a chat, a screenshot, or a GitHub issue.

---

## Türkçe özet

Bu uygulama sesi **sizin** Google Cloud hesabınız üzerinden üretir. Depoda
hiçbir anahtar yoktur; kendi anahtarınızı oluşturup yerel olarak kaydetmeniz
gerekir. Ücret sizin hesabınıza işler.

**Kurulum (önerilen yol):**

1. [Google Cloud Console](https://console.cloud.google.com/) içinde proje açın
   veya seçin ve **faturalandırma hesabı** bağlayın. Faturalandırma yoksa
   anahtar geçerli olsa bile istekler reddedilir.
2. Aynı projede [Cloud Text-to-Speech API](https://console.cloud.google.com/apis/library/texttospeech.googleapis.com)
   hizmetini **etkinleştirin**.
3. [Kimlik bilgileri](https://console.cloud.google.com/apis/credentials)
   sayfasında **Create credentials → API key** deyin, ardından **Edit API key →
   API restrictions → Restrict key** altında yalnızca **Cloud Text-to-Speech
   API** işaretleyin. Kısıtlanmamış bir anahtar sızarsa projenizdeki tüm API'ler
   için kullanılabilir; bu adımı atlamayın.
4. Proje klasöründe `.venv/bin/python setup_google.py` çalıştırıp anahtarı gizli
   alana yapıştırın. Yazdığınız görünmez ve terminal geçmişine düşmez.
5. `.venv/bin/python app.py` ile uygulamayı açıp **Google seslerini getir**
   düğmesine basın. Ses listesi geliyorsa anahtar çalışıyordur; bu düğme kitap
   metni göndermez ve kota harcamaz.

**Alternatifler:** Dosya yerine `GOOGLE_CLOUD_TTS_API_KEY` ortam değişkenini
kullanabilirsiniz (dosyadan önceliklidir). Anahtar yerine `gcloud auth
application-default login` ile kendi hesabınızla da giriş yapabilirsiniz; servis
hesabı JSON dosyasını proje klasörünün **dışında** tutup
`GOOGLE_APPLICATION_CREDENTIALS` ile gösterin.

**Değiştirme ve iptal:** Değiştirmek için `setup_google.py` komutunu tekrar
çalıştırın. Anahtar sızdıysa yerel dosyayı silmek **yetmez** — Kimlik bilgileri
sayfasından anahtarı silip yenisini oluşturun. `.state/usage.json` dosyasını
silmeyin; karakter sayaçlarınız orada tutulur.

**Güvenlik:** Anahtar yalnızca `.state/google-api-key.txt` içinde `0600` izniyle
durur, `.gitignore` kapsamındadır, tarayıcıya hiç gönderilmez ve hata
metinlerinde `[gizli anahtar]` ile değiştirilir. Sunucu yalnızca `127.0.0.1`
dinler. Anahtarınızı sohbete, ekran görüntüsüne veya issue'ya yapıştırmayın.

**Sık karşılaşılan hatalar:** "Google bu projede izin vermedi" → API etkin değil
veya anahtar kısıtlaması yanlış. "Google kimlik bilgisini kabul etmedi" →
anahtar hatalı veya iptal edilmiş. "Google kotası doldu" → aylık ücretsiz hak
bitmiş. "Google seçili sesi bulamadı" → sesleri yeniden getirip listeden seçin.
Faturalandırma bağlı değilse hataların çoğu izin hatası olarak görünür; önce
faturalandırmayı doğrulayın.
