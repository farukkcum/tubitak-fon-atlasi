# TÜBİTAK Fon Atlası

TÜBİTAK'ın bütün destek programlarını tek sayfada toplayan atlas. Son başvuru
takvimi her sabah TÜBİTAK duyurularından otomatik olarak taranır.

- `index.html`: atlas. Açılışta ve **Takvimi güncelle** butonuna basıldığında `takvim.json`'u okur.
- `takvim.json`: güncel son başvuru tarihleri. Her gün otomatik yenilenir; elle düzenlemeyin.
- `scripts/tara.py`: TÜBİTAK duyurularını ve program sayfalarını tarayan betik.
- `.github/workflows/takvim.yml`: betiği her gün 07:00'de çalıştırıp siteyi yeniden yayınlayan GitHub Actions görevi.

## Kurulum (bir kez)

1. **Depoyu oluşturun.** GitHub'da *New repository* ile `tubitak-fon-atlasi` adında **Public** bir depo açın.
2. **Dosyaları yükleyin.** *Add file → Upload files* ekranına zip'ten çıkan klasörün içeriğini sürükleyin.
   `.github` klasörü gizli olduğu için sürüklemede görünmeyebilir. Görünmezse *Add file → Create new file*
   ile dosya adı kutusuna `.github/workflows/takvim.yml` yazıp `takvim.yml` dosyasının içeriğini yapıştırın.
3. **GitHub Pages'i açın.** *Settings → Pages → Build and deployment → Source* alanında **GitHub Actions**'ı seçin.
4. **İlk taramayı çalıştırın.** *Actions* sekmesinde **Takvimi güncelle** iş akışını seçip *Run workflow*'a basın.
   Birkaç dakika sonra atlas `https://KULLANICI-ADINIZ.github.io/tubitak-fon-atlasi/` adresinde yayında olur.

## Google Sites'a yerleştirme

Sayfayı düzenlerken sağdaki menüden *Ekle → Yerleştir (Embed) → URL ile* seçeneğini açın ve
yukarıdaki GitHub Pages adresini yapıştırın. *Sayfanın tamamı* görünümünü seçip ekleyin,
ardından kutuyu sayfa genişliğine ve istediğiniz yüksekliğe çekin. Atlas kutunun içinde kendi
kaydırma çubuğuyla gezilir.

## Nasıl çalışır?

- Her sabah GitHub sunucusu `scripts/tara.py`'yi çalıştırır. Betik TÜBİTAK duyuru listesinin son 8 sayfasını
  tarar. Başlığı atlastaki bir programla eşleşen çağrı, uzatma ve güncelleme duyurularından son başvuru, e-imza
  ve uluslararası son tarihleri ayıklar. Duyurusu olmayan programlar için resmî program sayfalarına bakar.
- Sonuç `takvim.json`'a yazılır ve site yeniden yayınlanır.
- Ziyaretçinin bastığı **Takvimi güncelle** butonu bu dosyanın en yeni halini yükler. TÜBİTAK sitesini
  ziyaretçinin tarayıcısından taramak mümkün değildir; tarayıcılar başka sitelerin içeriğini okumayı engeller.
- `takvim.json` okunamazsa atlas, 26 Ekim 2026'da derlenen tarihlerle açılır.

## Bakım

- **Taramayı elle tetiklemek** için *Actions → Takvimi güncelle → Run workflow* yeterli.
- **Tarama başarısız olursa** (TÜBİTAK sitesi erişilemezse ya da yurt dışı bağlantıları engellerse) iş akışı
  uyarı verir. Bu durumda önceki takvim yayında kalır, sayfadaki "Son tarama" bilgisi de eski tarihi gösterir.
- **Zamanlanmış görev durdurulursa** GitHub uzun süre işlem görmeyen depolarda zamanlanmış görevleri durdurup
  e-posta gönderebilir. *Actions* sekmesinden yeniden etkinleştirmek yeterli.
- **Yeni bir program eklemek için:** `index.html`'deki `D` listesine kart ekleyin, `scripts/tara.py`'deki
  `RULES` listesine aynı `no` değeriyle bir kural ekleyin.
