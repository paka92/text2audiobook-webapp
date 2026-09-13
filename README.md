# Kitapları sesli kitaba dönüştür

## Çalıştırma

```sh
uv venv .venv
uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/python app.py
```

Tarayıcı otomatik olarak http://127.0.0.1:5001 adresini açar. Uygulama yalnızca
bu bilgisayardan erişilebilir. Sayfada bir kitap, model ve ses seçip **Seçili
kitabı seslendir** düğmesine basın. Listeleme sırasında metin gönderilmez.

## Google Cloud kurulumu

> Kendi anahtarınızı oluşturma, kısıtlama, değiştirme ve hata çözümleri için
> ayrıntılı rehber: **[API-KEY-KURULUMU.md](API-KEY-KURULUMU.md)**. Aşağısı
> aynı adımların kısa özetidir.

### API anahtarıyla (CLI gerektirmez)

1. [Google Cloud Console](https://console.cloud.google.com/) içinde proje seçin
   veya oluşturun ve faturalandırma hesabı bağlayın.
2. Aynı projede [Cloud Text-to-Speech API](https://console.cloud.google.com/apis/library/texttospeech.googleapis.com)
   hizmetini etkinleştirin.
3. [Kimlik bilgileri](https://console.cloud.google.com/apis/credentials) sayfasında
   **Create credentials → API key** seçin. **API restrictions → Restrict key**
   altında yalnızca **Cloud Text-to-Speech API** seçerek kaydedin.
4. Proje klasöründe `.venv/bin/python setup_google.py` çalıştırın ve anahtarı
   terminaldeki gizli giriş alanına yapıştırın. Anahtar ekranda görünmez.
5. Uygulamayı `.venv/bin/python app.py` ile açın; zaten çalışıyorsa sayfayı
   yenileyin. **Google seslerini getir** düğmesi bağlantıyı metin göndermeden sınar.

Anahtar `.state/google-api-key.txt` dosyasında yalnızca kullanıcıya okuma/yazma
izniyle tutulur; Git'e dahil edilmez ve tarayıcıya gönderilmez. Anahtarı değiştirmek
için kurulum komutunu tekrar çalıştırın. İsterseniz dosya yerine
`GOOGLE_CLOUD_TTS_API_KEY` ortam değişkenini kullanabilirsiniz; bu değişken önceliklidir.
API anahtarı yoksa aşağıdaki hesapla giriş yöntemi kullanılır.

### Google hesabıyla (alternatif)

1. [Google Cloud Console](https://console.cloud.google.com/) içinde bir proje
   oluşturun/seçin ve faturalandırma hesabı bağlayın.
2. O projede [Cloud Text-to-Speech API](https://console.cloud.google.com/apis/library/texttospeech.googleapis.com)
   hizmetini etkinleştirin.
3. [Google Cloud CLI](https://cloud.google.com/sdk/docs/install) yükleyin.
4. Terminalde kendi proje kimliğinizle çalıştırın:

```sh
gcloud auth login
gcloud config set project PROJE_KIMLIGI
gcloud auth application-default login
gcloud auth application-default set-quota-project PROJE_KIMLIGI
```

Hesabınızın bu projede API kullanma (`serviceusage.services.use`) yetkisi olmalıdır.
Kimlik bilgileri sohbet veya web arayüzüne yapıştırılmaz. Alternatif olarak kendi
servis hesabınızın JSON dosyasını proje dışında tutup `GOOGLE_APPLICATION_CREDENTIALS`
ortam değişkenini o dosyanın tam yoluna ayarlayabilirsiniz.

## Ses ve ücretsiz kullanım

12 Eylül 2026 tarihinde resmi listede **Türkçe Neural2 sesi yok**. Uygulama Türkçe
ve **WaveNet** seçili olarak açılır. Listede yalnızca WaveNet ve Neural2 bulunur.
Sesler API üzerinden gerçek kullanılabilirliklerine
göre listelenir. Dil alanı farklı kitaplar için değiştirilebilir.

Neural2 aylık ilk 1.000.000 karakter için $0, sonrası milyon karakter başına $16.
WaveNet ilk 4.000.000 karakter ücretsiz, sonrası milyon başına $4.
Bu kalıcı bir fiyat garantisi değildir. Faturalandırmanın etkin olması gerekir.
Diğer modellerin güncel fiyatlarını ayrıca kontrol edin:
[fiyatlandırma](https://cloud.google.com/text-to-speech/pricing),
[sesler](https://docs.cloud.google.com/text-to-speech/docs/list-voices-and-types),
[istek sınırları](https://docs.cloud.google.com/text-to-speech/quotas).

Uygulama WaveNet için ayda 4 milyon, Neural2 için ayda 1 milyon karakter sınırı
uygular. Her modelin ayrı aylık ve gross (tüm zamanlar) sayacı vardır. Aylık
sayaç yeni ayda sıfırdan başlar; gross geçmiş aylarla birlikte toplamı korur.
Önbellekten kullanılan sesler yeniden sayılmaz. `.state/usage.json` UTC takvim ayına göre gönderimden **önce**
güncellenir. Hatalı/belirsiz istekler de sayılır; otomatik API tekrarı yapılmaz.
Bu sayaç Google faturasını okumaz; başka cihaz/proje/uygulamadaki kullanımları
modeline ait alana ayrıca girin; bu değerler sayaçlara eklenmez, aylık sınır
hesabında dikkate alınır. WaveNet ile aynı ücretsiz SKU kapsamındaki Standard
kullanımını da diğer WaveNet kullanımına dahil edin. Google'ın faturalandırma dönemi ve SKU kapsamı esas
alınır; uygulama $0 fatura garantisi vermez. Sayaç dosyasını silmeyin.

## Ön dinleme

Ön dinlemeler, üretildikleri ses ve ayarlarla birlikte **Ön dinlemeler · karşılaştır**
listesinde saklanır. Her kaydın bağımsız oynatıcısı vardır. Yeni bir üretim eskisini
değiştirmez. **×** düğmesi yalnızca o ön dinleme kopyasını siler; kitap çıktısı,
yeniden kullanım önbelleği ve tüketilmiş karakter sayacı korunur.
Ayarları değiştirince üstteki oynatıcı temizlenir; eski kayıtları alttaki listeden
dinleyebilirsiniz. Başarısız bir gönderimde hata görünür kalır; önceki sonuç
yeni üretilmiş gibi gösterilmez.

Hatalar **Seçili bölümü oluştur** düğmesinin hemen altında kırmızı kutuda gösterilir.
Bayt sınırı hatasında dosyanın adı, gönderilecek bayt sayısı ve düzeltme yolu yazılır.
Seslendirme sırasında bir istek başarısız olursa kutuda hangi dosyada durulduğu,
bilinen hata türleri için Türkçe açıklama ve her durumda Google'ın döndürdüğü özgün
yanıt (`Ayrıntı:` satırı) gösterilir. Anahtar bu metinden çıkarılır.
Arayüz açıklama metinleri yerine bu belgeyi kullanır.
Kitap, bölüm, ses, üretim ayarları ve son hata tarayıcıda yerel olarak saklanır;
sayfa yenilendiğinde geri yüklenir. API anahtarı bu kayda dahil edilmez.
Sunucu yeniden başlatılınca sayfa yenilemeden güncel yerel oturum alınır;
bu işlem seslendirme isteğini otomatik tekrarlamaz.

### Ses kontrolleri

Arayüzde okuma hızı (0,25–2×), ses perdesi (-20–20 yarım ton) ve ses seviyesi
(-96–16 dB) ayarlanabilir. Varsayılanlar 1× hız, 0 perde ve 0 dB'dir. Sıfırla
düğmesi bu değerlere döner. +10 dB üzerinde ses artışı önerilmez.

Metin Google'a olduğu gibi gönderilir: SSML etiketi eklenmez, kaçış yapılmaz.
Gönderilen bayt sayısı dosyanın kendi boyutudur, bu yüzden 4.999 baytlık
bölümleme dosyada ne yazıyorsa ona göre çalışır. Otomatik bölme yapılmaz.
Paragraflar arası ek duraklama ayarı bu nedenle kaldırılmıştır.

Üretim ayarları önbellek anahtarına dahildir. Aynı metin, ses ve ayarlar için
tamamlanmış sesler yeniden kullanılır; ayarları değiştirerek üretmek yeni
karakter kullanımıdır. Önceki varsayılan ayarlarla üretilmiş sesler korunur.
Oynatıcının ayrı **Dinleme hızı** seçimi Google'a istek göndermez, sayaçları
artırmaz ve kayıtlı dosyayı değiştirmez.

Seçili kitaptan bir metin dosyası seçip **Seçili bölümü oluştur** düğmesine basın.
Yalnızca o dosya seslendirilir; sonuç sayfadaki oynatıcıdan dinlenir. Ön dinleme
öncesinde de kitabın tamamı kontrol edilir: tek dosya bile 4.999 baytı aşarsa
hiçbir istek gönderilmez. Ön dinleme karakterleri modelin aylık ve gross sayacına
bir kez eklenir. Kitabın tamamını aynı ses ve ayarlarla başlatınca hazır bölüm yeniden
kullanılır. Ön dinleme, tam kitabın çalma listesini değiştirmez.

## Dosyalar

- Her kitabı `books/Kitap_Adi/*.txt` düzeninde ekleyin. Alt klasörler korunur.
  Doğrudan `books/Kitap.txt` de desteklenir. UTF-8 gerekir.
- Başlamadan bütün seçili kitap kontrol edilir. Her API isteği ayrıca en fazla
  **4.999 UTF-8 bayt** olacak şekilde kontrol edilir.
- Sınırı aşan dosyalar varsayılan olarak kitabın gönderilmesini engeller.
  Otomatik bölme yapılmaz. Tek dosya bile sınırı aşarsa hiçbir dosya gönderilmez.
  Hatalı metinleri düzeltip sayfayı yenileyin.
- Her `dosya.txt` için `dosya.wav` üretilir. WAV 24 kHz, kayıpsız ve MP3'ten
  büyüktür. Diskte ses önbelleği ve kopyalar için yeterli boş alan bırakın.
- Tamamlanan parçalar `.audio-cache/` altında tutulur. Aynı metin ve aynı sesle
  devam edildiğinde geçerli parçalar yeniden gönderilmez.
- Bütün kitap tamamlanınca sesler `books/audiobook/Kitap_Adi/` içine kopyalanır;
  dosya adına göre sıralı `playlist.m3u` eklenir. Aynı kitabı başka sesle çalıştırmak
  bu çıktıdaki aynı adlı dosyaları değiştirir.
- Durdur düğmesi mevcut Google isteği bittikten sonra durur. Uygulamayı yeniden
  açınca aynı kitap/sesi seçerek devam edin. Çıkış için terminalde Ctrl+C kullanın.
- Aynı çalışma klasöründe aynı anda yalnızca **bir sunucu** çalıştırın.

## Telefon paketi

Kitabın sesi tamamlandıktan sonra **4. Telefon paketi** bölümünden tek bir zip
üretilir: `packages/Kitap_Adi.zip`. Zip'in içinde tek bir klasör vardır ve her
bölümün sesi ile metni yan yana durur:

```
Kitap_Adi.zip
└── Kitap_Adi/
    ├── 001_onsoz.m4a
    ├── 001_onsoz.txt
    ├── 002_giris.m4a
    ├── 002_giris.txt
    ├── manifest.json
    └── playlist.m3u
```

Alt klasörlü kitaplarda yol adı dosya adına katlanır (`bolum1/002.txt` →
`bolum1_002.m4a`), böylece her şey tek klasörde kalır ve ad çakışması olmaz.

WAV dosyaları AAC'ye (`.m4a`, 24 kHz, mono) dönüştürülür. 48 kbps'de paket
kaynak WAV'ların yaklaşık **8 katı küçüktür**; 14 saatlik bir kitap ~2,4 GB
yerine ~300 MB olur. Kalite 32 / 48 / 64 kbps arasından seçilir. Dönüştürme
macOS'un `afconvert` aracıyla yapılır; yoksa `ffmpeg` kullanılır. Google'a istek
gönderilmez, karakter sayaçları artmaz — paketleme ücretsizdir ve istediğiniz
kadar tekrarlanabilir.

`manifest.json` telefon uygulaması içindir: sıralı bölüm listesi, her bölümün ses
ve metin dosya adı, saniye cinsinden süresi ve bayt boyutu, ayrıca kodek bilgisi.
`playlist.m3u` süre ve başlık içeren `#EXTINF` satırlarıyla yazılır.

Paket yalnızca kitabın **bütün** bölümlerinin sesi hazırsa üretilir; eksik veya
bozuk bir WAV varsa hangi dosyanın eksik olduğu söylenir ve zip oluşturulmaz.
Yarım kalan zip diske bırakılmaz.

## Doğrulama

```sh
.venv/bin/python -m unittest discover -s tests -v
node tests/ui.test.cjs
```

Testler Google'a metin göndermez; bayt sınırı, metin bütünlüğü, sadece seçili
kitabın gönderilmesi, yeniden başlatma, kullanım sınırı, hata bildirimi ve
paketin tek klasörlü zip yapısını sahte servisle doğrular.
