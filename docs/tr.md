# uthere Dokümantasyonu

## Proje Hakkında

uthere, Linux sistemleri için küçük bir sağlık kontrol aracıdır. Hem CLI komutu
hem de systemd ile çalışabilecek uzun ömürlü servis sağlar. IP adresleri,
domainler veya URL'ler kayıt olarak eklenebilir; her kayıt için `ping` veya HTTP
kontrolü seçilebilir.

Servis kayıtları SQLite içinde saklar ve son durum, gecikme, HTTP durum kodu,
hata mesajı ve son kontrol zamanını kaydeder. Bir kayıt sağlıksız duruma
düştüğünde uthere mail, Telegram, WhatsApp veya bu kanalların kombinasyonları
üzerinden uyarı gönderebilir.

## Temel Özellikler

- CLI ile kayıt ekleme, listeleme, düzenleme, silme ve anlık kontrol.
- Linux servisi olarak zamanlanmış kontroller.
- IP/domain erişilebilirliği için ping kontrolü.
- HTTP kontrolü ve `2xx` cevapları sağlıklı kabul etme.
- Tüm durumun SQLite içinde saklanması.
- `uthere list` çıktısında son kontrol zamanı ve son sağlık durumu.
- Kayıt değiştiğinde servisin hemen uyandırılması.
- Mail, Telegram ve WhatsApp uyarıları.
- Debian, Fedora ve Gentoo paketleme dosyası üretimi.
- Tag bazlı GitHub Actions release akışı.

## Bileşenler

### CLI

CLI giriş noktası `uthere` komutudur ve `src/uthere/cli.py` içinde uygulanır.

Önemli komutlar:

- `uthere add`: yeni monitor kaydı ekler.
- `uthere list`: kayıtları ve son durumlarını gösterir.
- `uthere edit`: hedef, tür, aralık, timeout veya aktif/pasif durumunu günceller.
- `uthere remove`: bir veya daha fazla kayıt siler.
- `uthere description` / `uthere des`: açıklama ekler, gösterir veya temizler.
- `uthere check`: kontrolleri hemen çalıştırır.
- `uthere serve`: servis zamanlayıcısını çalıştırır.
- `uthere alert-test`: ayarlı kanallara test uyarısı gönderir.

### Servis Zamanlayıcısı

Servis `uthere serve` ile başlar. Sürekli sabit aralıkla dönmez. En yakın
kontrol zamanını hesaplar ve o ana kadar uyur. CLI bir kaydı değiştirdiğinde
Unix domain socket üzerinden wake mesajı gönderir; servis uyanıp takvimi hemen
yeniden hesaplar.

### Veritabanı

Monitor kayıtları SQLite içinde tutulur. Kullanıcı seviyesindeki varsayılan yol:

```text
~/.local/state/uthere/uthere.db
```

Systemd kurulumundaki varsayılan ortak yol:

```text
/var/lib/uthere/uthere.db
```

Yol `--db` veya `UTHERE_DB` ile değiştirilebilir.

### Wake Socket

CLI, çalışan servisi Unix domain socket ile uyandırır. Varsayılan yol:

```text
/tmp/uthere.sock
```

Yol `--socket` veya `UTHERE_SOCKET` ile değiştirilebilir.

### Kontroller

Ping kontrolleri sistemdeki `ping` komutunu kullanır. HTTP kontrolleri Python
standart kütüphanesiyle yapılır ve `2xx` cevaplar sağlıklı kabul edilir.

### Uyarılar

Uyarılar environment değişkenleriyle yapılandırılır. Desteklenen kanallar:

- `mail`
- `telegram`
- `whatsapp`

Varsayılan uyarı modu `on_change` değeridir. Bu modda sadece kayıt
`healthy` veya `unknown` durumundan `unhealthy` durumuna geçtiğinde mesaj
gönderilir. Her başarısız kontrolde mesaj göndermek için
`UTHERE_ALERT_MODE=always` kullanılabilir.

### Paketleme

`uthere-packager` komutu şu dağıtımlar için paketleme dosyaları üretir:

- Debian
- Fedora
- Gentoo

### Release CI

GitHub Actions release workflow'u sadece `v*` ile eşleşen tag push olayında
çalışır. Testleri çalıştırır, tag versiyonunu `uthere.__version__` ile
karşılaştırır, paketleme dosyalarını üretir, release arşivlerini hazırlar ve
GitHub Release'e yükler. Ayrıca Docker image build edip GitHub Container
Registry'ye yayınlar.

## Kurulum

### Geliştirme Kurulumu

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
```

Debian/Ubuntu üzerinde `externally-managed-environment` hatası alırsanız,
`pip install` komutunu sistem Python'unda çalıştırıyorsunuz demektir. Çözüm:

```bash
su -c 'apt install python3-venv python3-full'
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
```

Python sürümüne özel paket gerekebilir:

```bash
su -c 'apt install python3.13-venv'
```

`--break-system-packages` kullanılması önerilmez; sistem Python paketlerini
bozabilir.

### Systemd Kurulumu

```bash
su -c 'cd /path/to/uthere && scripts/install-systemd.sh'
```

Kurulum betiği şunları yapar:

- Proje içinde `.venv` oluşturur.
- Paketi bu sanal ortama kurar.
- `/usr/local/bin/uthere` komutunu yazar.
- `/etc/default/uthere` dosyasını yazar.
- `/etc/systemd/system/uthere.service` dosyasını yazar.
- Servisi enable edip başlatır.

Systemd kurulumu sistem modudur. Servis varsayılan olarak `root` kullanıcısıyla
çalışır, `/var/lib/uthere/uthere.db` veritabanını kullanır ve ayarları
`/etc/default/uthere` dosyasından okur. Servis veritabanını okuyan veya yazan CLI
komutlarını root shell üzerinden çalıştırın:

```bash
su -c 'uthere add example.com --type ping --interval 60'
su -c 'uthere list'
su -c 'uthere check all'
```

Servisi farklı bir kullanıcıyla çalıştırmak için:

```bash
su -c 'cd /path/to/uthere && UTHERE_SERVICE_USER=anc scripts/install-systemd.sh'
```

### Kullanıcı Modu Kurulumu

```bash
scripts/install-systemd.sh
```

Kurulum betiği root yetkisi olmadan çalıştırılırsa sadece CLI'yi mevcut
kullanıcının home dizinine kurar:

- Binary: `~/.local/bin/uthere`
- Config: `~/.config/uthere/uthere.env`
- Veritabanı: `~/.local/state/uthere/uthere.db`

Kullanıcı modu arka plan servisi değildir. Sadece kullanıcı komut çağırdığında
çalışır. Sürekli interval kontrolü için system mode kurulumu kullanılmalıdır.

Servis durumunu kontrol etmek için:

```bash
systemctl status uthere
journalctl -u uthere -f
```

## Kullanım

### Kayıt Ekleme

```bash
uthere add example.com --type ping --interval 60 --timeout 3 --name dns
uthere add https://example.com --type http --interval 120 --timeout 5
```

Yeni kayıtlar eklendikten hemen sonra kontrol edilir.

### Kayıt Listeleme

```bash
uthere list
uthere list --all
```

### Anlık Kontrol

```bash
uthere check
uthere check all
uthere check 1
uthere check 1 2 3
```

### Kayıt Düzenleme

```bash
uthere edit 1 --interval 30 --timeout 2
uthere edit 1 --target https://example.org --type http
uthere edit 1 --disable
uthere edit 1 --enable
```

### Kayıt Silme

```bash
uthere remove 1
uthere remove 1 2 3
```

### Açıklamalar

```bash
uthere description add 1 "this description server"
uthere des add 1 "this description server"
uthere des show 1
uthere des show all
uthere des clear 1
```

### Servisi Terminalde Çalıştırma

```bash
uthere serve
```

### Veritabanı ve Socket Yolunu Değiştirme

```bash
uthere --db /path/to/uthere.db list
UTHERE_DB=/path/to/uthere.db uthere list

uthere --socket /path/to/uthere.sock add example.com --type ping
UTHERE_SOCKET=/path/to/uthere.sock uthere serve
```

## Uyarı Yapılandırması

### Kanal Seçimi

```bash
UTHERE_ALERT_CHANNELS=mail
UTHERE_ALERT_CHANNELS=telegram
UTHERE_ALERT_CHANNELS=whatsapp
UTHERE_ALERT_CHANNELS=mail,telegram,whatsapp
```

Aynı uyarıyı birden fazla kanala göndermek için kanalları virgülle ayırın. Bir
kanal hata verirse uthere o kanal hatasını loglar ve kalan kanalları denemeye
devam eder.

### Uyarı Modu

```bash
UTHERE_ALERT_MODE=on_change
UTHERE_ALERT_MODE=always
```

### Mail

```bash
UTHERE_ALERT_CHANNELS=mail
UTHERE_MAIL_HOST=smtp.example.com
UTHERE_MAIL_PORT=587
UTHERE_MAIL_TLS=starttls
UTHERE_MAIL_USER=user@example.com
UTHERE_MAIL_PASSWORD=secret
UTHERE_MAIL_FROM=uthere@example.com
UTHERE_MAIL_TO=ops@example.com,admin@example.com
```

### Telegram

```bash
UTHERE_ALERT_CHANNELS=telegram
UTHERE_TELEGRAM_BOT_TOKEN=123456:token
UTHERE_TELEGRAM_CHAT_ID=123456789
```

`UTHERE_ALERT_CHANNELS=telegram` zorunludur. Sadece bot token ve chat ID yazmak
Telegram kanalını aktif etmez.

### WhatsApp

WhatsApp desteği Meta WhatsApp Cloud API formatını kullanır.

```bash
UTHERE_ALERT_CHANNELS=whatsapp
UTHERE_WHATSAPP_TOKEN=secret
UTHERE_WHATSAPP_PHONE_NUMBER_ID=123456789
UTHERE_WHATSAPP_TO=905xxxxxxxxx
UTHERE_WHATSAPP_API_VERSION=v20.0
```

### Uyarı Testi

```bash
uthere alert-test
```

Systemd kurulumunda bu değişkenler `/etc/default/uthere` dosyasına yazılır ve
sonrasında servis yeniden başlatılır:

```bash
su -c 'systemctl restart uthere'
```

CLI ayrıca `/etc/default/uthere`, `/etc/sysconfig/uthere` ve
`/etc/conf.d/uthere` dosyalarını okur. Bu yüzden hatalı bir kayıt beklemeden
`uthere alert-test` ile aynı uyarı ayarlarını test edebilirsiniz.

## Test

```bash
PYTHONPATH=src pytest -q
```

Test grupları:

- `tests/unit`: repository, alert kararları ve paketleme dosyası üretimi.
- `tests/integration`: CLI akışları ve servis wake socket davranışı.

## Paketleme

Tüm paketleme dosyalarını üretmek için:

```bash
PYTHONPATH=src python3 -m uthere.packager all
```

Kurulumdan sonra:

```bash
uthere-packager all
```

Tek dağıtım hedefleri:

```bash
uthere-packager debian
uthere-packager fedora
uthere-packager gentoo
```

Varsayılan çıktı dizini:

```text
dist/packages
```

Üretilen yapılar:

- Debian: `dist/packages/debian/uthere-<version>/debian`
- Fedora: `dist/packages/fedora/SPECS/uthere.spec` ve `dist/packages/fedora/SOURCES/uthere-<version>.tar.gz`
- Gentoo: `dist/packages/gentoo/uthere-<version>.ebuild` ve `dist/packages/gentoo/files`

Native build araçları kuruluysa:

```bash
uthere-packager all --build
```

## Release CI

Release workflow sadece tag push ile çalışır:

```bash
git tag v0.1.0
git push origin v0.1.0
```

Tag versiyonu `uthere.__version__` ile aynı olmalıdır. `1.0.1-beta` gibi beta
tag'leri Python paket versiyonu olan `1.0.1b0` değerine normalize edilir.

Workflow ayrıca GitHub Container Registry'ye Docker image yayınlar:

```text
ghcr.io/<owner>/<repo>:v0.1.0
ghcr.io/<owner>/<repo>:0.1.0
ghcr.io/<owner>/<repo>:latest
```

## Docker

```bash
docker build -t uthere:latest .
docker volume create uthere-data
docker run -d --name uthere --restart unless-stopped -v uthere-data:/var/lib/uthere uthere:latest
```

Container `uthere serve` komutunu foreground executable olarak çalıştırır.
Container çalıştığı sürece kayıtları sürekli kontrol eder.
Unhealthy veya hatalı kayıtlar container'ı durdurmamalıdır; veritabanına
`unhealthy` olarak ve hata mesajıyla kaydedilir.

Kayıt eklemek/listelemek için çalışan container üzerinde `docker exec` kullanın:

```bash
docker exec uthere uthere add example.com --type ping --interval 60
docker exec uthere uthere list
docker exec uthere uthere check all
docker exec -it uthere sh
```

Container içine girmek için ikinci bir `docker run` kullanmayın; bu yeni bir
container oluşturur. Yeni container aynı `uthere-data` volume'unu mount etmezse
yeni ve boş bir SQLite veritabanı kullanır.

Docker Compose:

```bash
docker compose up -d
docker compose exec uthere uthere add example.com --type ping --interval 60
docker compose exec uthere uthere list
docker compose logs -f uthere
```

Release image'ları GitHub Container Registry'ye yayınlanır:

```text
ghcr.io/<owner>/<repo>:v0.1.0
ghcr.io/<owner>/<repo>:0.1.0
ghcr.io/<owner>/<repo>:latest
```
