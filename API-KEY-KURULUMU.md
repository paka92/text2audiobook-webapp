# Kendi Google API anahtarınızı ekleme

Bu uygulama sesi **sizin** Google Cloud hesabınız üzerinden üretir. Depoda hiçbir
anahtar yoktur; kullanmadan önce kendi anahtarınızı oluşturup yerel olarak
kaydetmeniz gerekir. Ücretlendirme sizin hesabınıza işler.

## Önce bilmeniz gerekenler

- Google Cloud hesabı ve **faturalandırma** gerekir. Faturalandırma bağlı
  değilse API anahtarı üretseniz bile istekler reddedilir.
- Ücretsiz kota aylıktır: **WaveNet 4.000.000**, **Neural2 1.000.000** karakter.
  Uygulama bu sınırların üstüne çıkmaz, ancak Google'ın faturası esastır.
- Anahtar yalnızca bu bilgisayarda kalır. Tarayıcıya gönderilmez, Git'e girmez,
  hata mesajlarında `[gizli anahtar]` olarak maskelenir.

## Yöntem 1 — API anahtarı (önerilen, CLI gerektirmez)

### 1. Proje ve faturalandırma

[Google Cloud Console](https://console.cloud.google.com/) içinde bir proje
oluşturun veya seçin, ardından projeye bir **faturalandırma hesabı** bağlayın.

### 2. Text-to-Speech API'yi etkinleştirin

Aynı projede [Cloud Text-to-Speech API](https://console.cloud.google.com/apis/library/texttospeech.googleapis.com)
sayfasını açıp **Enable** deyin. Bu adım atlanırsa uygulama
"Google bu projede izin vermedi" hatası verir.

### 3. Anahtarı oluşturun ve kısıtlayın

[Kimlik bilgileri](https://console.cloud.google.com/apis/credentials) sayfasında
**Create credentials → API key** seçin. Anahtar oluşur oluşmaz **Edit API key**
deyip kısıtlayın:

- **API restrictions → Restrict key** → yalnızca **Cloud Text-to-Speech API**
  işaretli olsun.
- **Application restrictions** kısmını `None` bırakabilirsiniz; anahtar zaten
  yalnızca bu bilgisayarda duruyor.

Kısıtlanmamış bir anahtar sızarsa projenizdeki **tüm** API'ler için kullanılabilir.
Bu adımı atlamayın.

### 4. Anahtarı yerel olarak kaydedin

Proje klasöründe:

```sh
.venv/bin/python setup_google.py
```

Anahtarı terminaldeki gizli alana yapıştırıp Enter'a basın. **Yazdığınız
görünmez** ve terminal geçmişine düşmez.

Anahtar `.state/google-api-key.txt` dosyasına yalnızca sizin okuyup
yazabileceğiniz izinle (`0600`) kaydedilir. `.state/` klasörü `.gitignore`
içindedir; kazara commit edilmez.

### 5. Doğrulayın

Uygulamayı başlatın:

```sh
.venv/bin/python app.py
```

Sayfada **Google seslerini getir** düğmesine basın. Ses listesi geliyorsa anahtar
çalışıyor demektir. Bu düğme kitap metni göndermez, karakter kotası harcamaz.

## Yöntem 2 — Ortam değişkeni

Dosyaya yazmak istemiyorsanız:

```sh
export GOOGLE_CLOUD_TTS_API_KEY="anahtarınız"
.venv/bin/python app.py
```

Bu değişken **dosyadan önceliklidir**. Kalıcı olması için kabuk profilinize
(`~/.zshrc`) ekleyin; o durumda anahtar düz metin olarak profil dosyanızda
durur.

## Yöntem 3 — Google hesabıyla giriş (anahtarsız)

API anahtarı yerine kendi hesabınızla da kimlik doğrulayabilirsiniz.
[Google Cloud CLI](https://cloud.google.com/sdk/docs/install) kurulu olmalıdır:

```sh
gcloud auth login
gcloud config set project PROJE_KIMLIGI
gcloud auth application-default login
gcloud auth application-default set-quota-project PROJE_KIMLIGI
```

Hesabınızın o projede `serviceusage.services.use` yetkisi olmalıdır.

Servis hesabı kullanacaksanız JSON dosyasını **proje klasörünün dışında** tutun
ve tam yolunu verin:

```sh
export GOOGLE_APPLICATION_CREDENTIALS="/güvenli/bir/yol/servis-hesabi.json"
```

Uygulama önce API anahtarına bakar; yoksa bu hesap bilgilerini kullanır.

## Anahtarı değiştirme veya silme

- **Değiştirmek:** `setup_google.py` komutunu tekrar çalıştırın; dosyanın üzerine
  yazılır.
- **Silmek:** `rm .state/google-api-key.txt`
- **İptal etmek:** Anahtar sızdıysa dosyayı silmek yetmez.
  [Kimlik bilgileri](https://console.cloud.google.com/apis/credentials)
  sayfasından anahtarı **Delete** ile iptal edin, sonra yenisini oluşturun.

`.state/usage.json` dosyasını silmeyin; karakter sayaçlarınız orada tutulur.

## Hata çözümleri

Uygulama hatayı **Seçili bölümü oluştur** düğmesinin altındaki kırmızı kutuda
gösterir: hangi dosyada durduğu, Türkçe açıklama ve Google'ın özgün yanıtı
(`Ayrıntı:` satırı).

| Gördüğünüz mesaj | Sebebi ve çözümü |
| --- | --- |
| Google bu projede izin vermedi | Text-to-Speech API etkin değil ya da anahtar kısıtlaması yanlış. 2. ve 3. adımı kontrol edin. |
| Google kimlik bilgisini kabul etmedi | Anahtar hatalı kopyalanmış veya iptal edilmiş. `setup_google.py` ile yeniden girin. |
| Google kimlik doğrulaması eksik | Ne anahtar ne de hesap girişi var. Yöntem 1 veya 3'ü tamamlayın. |
| Google kotası doldu | Aylık ücretsiz hak bitmiş veya istek hızı sınırı aşılmış. Google Cloud kotalarınıza bakın. |
| Google seçili sesi bulamadı | Ses adı dil/model ile uyuşmuyor. **Google seslerini getir** deyip listeden seçin. |
| Google isteği geçersiz buldu | Dil kodu veya ses adı hatalı. Türkçe için `tr-TR` kullanın. |

Faturalandırma bağlı değilse çoğu hata "izin verilmedi" olarak görünür; önce
faturalandırmayı doğrulayın.

## Güvenlik özeti

- Anahtar yalnızca `.state/google-api-key.txt` içinde, `0600` izniyle durur.
- `.state/`, `books/`, `.audio-cache/`, `packages/` ve `*credentials*.json`
  `.gitignore` içindedir.
- Anahtar tarayıcıya hiç gönderilmez; sayfa yalnızca ses **adlarını** görür.
- Hata metinlerinde anahtar `[gizli anahtar]` ile değiştirilir.
- Sunucu yalnızca `127.0.0.1` üzerinden dinler ve başka bir host adıyla gelen
  isteği reddeder.
- Anahtarınızı sohbete, ekran görüntüsüne veya issue'ya yapıştırmayın.
