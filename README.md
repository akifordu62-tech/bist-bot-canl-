# Net Hacim Akışı & RSI Gecikmeli Çıkış Botu (V5.1)
### Pine Script'ten Bağımsız Python (Pandas + Plotly + Telegram) BIST Tarama ve Analiz Sistemi

Bu proje, TradingView üzerinde çalışan **Net Hacim Akışı (RSI Gecikmeli Çıkış) Botu V5.1** Pine Script stratejisinin mantığını birebir koruyarak Python, Pandas ve Plotly mimarisine taşınmış sürümüdür.

---

## 🚀 Öne Çıkan Özellikler

1. **1:1 Sadık Pine Script Mantığı:**
   - **Net Hacim (Net Volume):** `close > close[1] ? volume : close < close[1] ? -volume : 0`
   - **Net Hacim Ortalaması (SMA):** 5 periyotluk SMA
   - **Negatif Akış Onayı:** Peş peşe gelen negatif net hacim mumları
   - **Wilder's RMA RSI (14):** TradingView'in `ta.rsi` fonksiyonu ile birebir özdeş hesaplama
   - **Çıkış Destek Seviyesi:** Son 5 mumun en düşüğü (`ta.lowest(low, 5)`)
   - **Gecikmeli Çıkış Mekanizması:** RSI 70 seviyesini aşağı kestikten sonra (momentum uyarısı) fiyatın son 5 barın en düşük seviyesinin altına inmesiyle pozisyonu kapatır.

2. **İnteraktif TradingView Benzeri Plotly Grafikleri:**
   - Koyu tema (Dark theme) mum grafiği
   - Çıkış destek seviyesi (Fuchsia noktalı çizgi)
   - Mumların hemen altında yeşil üçgen **AL** ve üstünde kırmızı ters üçgen **SAT** işaretleri
   - Turuncu baklava şeklinde **RSI Momentum Uyarısı**
   - Alt panellerde **Net Hacim Histogramı** ve **RSI (14)** indikatörü
   - HTML formatında kaydedilir ve tarayıcınızda açılır.

3. **BIST 100 Otomatik Tarayıcı (Scanner):**
   - BIST 100 ve BIST 30 hisselerinin günlük kapanışlarını otomatik tarar.
   - Son gün AL veya SAT sinyali veren hisseleri anında listeler.

4. **Telegram Bot Entegrasyonu:**
   - Taramada AL veya SAT sinyali veren hisse bulunduğunda Telegram telefonunuza anında şık formatlı bildirim gönderir.

5. **Gelişmiş Backtest Modülü:**
   - Stratejinin toplam getirisini, hisseyi sadece elde tutma (Buy & Hold) getirisiyle kıyaslar.
   - Kazanma oranı (Win Rate), Kar Faktörü (Profit Factor), Maksimum Çekilme (Drawdown) ve tüm geçmiş işlem listesini döker.

---

## 📁 Dosya Yapısı

- `config.py`: Strateji parametreleri (periyotlar, aşırı alım seviyesi) ve Telegram token ayarları.
- `strategy.py`: Pine Script mantığının Pandas serileri ve durum makinesiyle hesaplandığı çekirdek motor.
- `chart.py`: Plotly ile 3 panelli interaktif mum grafiği oluşturan modül.
- `scanner.py`: BIST 100 hisselerini tarayan ve sinyal tespit eden modül.
- `telegram_notifier.py`: Telegram bildirim göndericisi ve bağlantı test edicisi.
- `backtest.py`: Geçmiş işlem simülatörü ve performans raporlayıcı.
- `bist_symbols.py`: BIST 100 ve BIST 30 hisse kodları listesi (.IS uzantılı).
- `main.py`: Kullanıcı dostu etkileşimli menü ve komut satırı arayüzü (CLI).

---

## 🛠️ Kurulum

Terminalden kütüphaneleri yükleyin (zaten sisteminizde varsa kontrol eder):
```bash
python -m pip install -r requirements.txt
```

---

## 📱 Telegram Bildirimlerini Aktif Etme

1. Telegram'da **@BotFather** botuna gidin ve `/newbot` komutuyla yeni bir bot oluşturup **API Token**'ınızı alın.
2. Botunuzu başlatmak için oluşturduğunuz bota Telegram'dan `/start` mesajı atın.
3. Chat ID'nizi öğrenmek için Telegram'da **@userinfobot** veya **@getmyid_bot** botuna mesaj atarak `Id` numaranızı alın.
4. `config.py` dosyasını açıp bilgilerinizi girin:
   ```python
   TELEGRAM_CONFIG = {
       "enabled": True,  # Aktif etmek için True yapın
       "token": "BOT_TOKEN_BURAYA",
       "chat_id": "CHAT_ID_BURAYA"
   }
   ```
## 🖥️ Web Kontrol Paneli (TradingView Benzeri Tam Arayüz)

Artık TradingView'e hiç ihtiyacınız yok! Projenize tek tıkla açılan interaktif bir **Web Dashboard (Streamlit)** kurulmuştur.

### 🌟 Nasıl Başlatılır?
1. Masaüstündeki `tradingwiew code` klasörüne girip [**`baslat.bat`**](file:///c:/Users/Akif/Desktop/tradingwiew%20code/baslat.bat) dosyasına çift tıklayın.
2. Veya terminalden:
   ```bash
   python -m streamlit run app.py
   ```
Tarayıcınızda otomatik olarak açılır (`http://localhost:8501`).

### 🎯 Panelde Neler Var?
- **📈 Hisse Grafiği & Sinyaller:** Açılır menüden istediğiniz BIST 100 hissesini seçip anında Plotly mum grafiğini, indikatörleri ve AL/SAT sinyallerini inceleyebilirsiniz.
- **🔍 Canlı Piyasa Taraması (Scanner):** Tek tıkla BIST 30 veya BIST 100 hisselerini taratıp bugün AL/SAT veren hisseleri listeleyebilir ve Telegram'a gönderebilirsiniz.
- **🧪 Backtest & Performans:** Seçtiğiniz hissenin geçmiş kârlılığını, getiri eğrisini (Equity Curve) ve gerçekleşen tüm işlemlerini görebilirsiniz.
- **⚙️ Ayarlar & Telegram:** Strateji periyotlarını ve Telegram bot ayarlarınızı arayüzden test edip güncelleyebilirsiniz.

### 1. Etkileşimli Menü Modu (En Kolay Yol)
Doğrudan `main.py` dosyasını çalıştırın:
```bash
python main.py
```
Açılan menüden seçim yapabilirsiniz:
```text
  1. BIST 100 Günlük Tarama Yap (Tüm Hisseler)
  2. BIST 30 Hızlı Tarama Yap
  3. Tek Hisse İçin Plotly İnteraktif Grafik Çiz
  4. Tek Hisse İçin Backtest / Getiri Analizi
  5. Telegram Bot Bağlantısını Test Et
  0. Çıkış
```

### 2. Komut Satırı Kısayolları (Hızlı Çalıştırma)

- **BIST 100 Taraması:**
  ```bash
  python main.py --scan
  ```

- **BIST 30 Hızlı Taraması:**
  ```bash
  python main.py --scan-bist30
  ```

- **Tek Bir Hissenin İnteraktif Grafiğini Görme:**
  ```bash
  python main.py --chart THYAO.IS
  ```
  *(Grafik `charts/THYAO_chart.html` konumuna kaydedilir ve tarayıcınızda otomatik açılır)*

- **Hisse Backtest Analizi:**
  ```bash
  python main.py --backtest ASELS.IS
  ```

---

## ⏰ Günlük Otomatik Çalıştırma (Windows Görev Zamanlayıcı)

Günlük işlem yaptığınız için borsa kapandıktan sonra (örneğin her gün saat **18:15**'te) taramanın otomatik çalışıp sinyalleri Telegram'ınıza göndermesini sağlayabilirsiniz:

1. Windows Başlat menüsüne **Görev Zamanlayıcı (Task Scheduler)** yazıp açın.
2. Sağ menüden **Temel Görev Oluştur** seçin.
3. Görev adına `BIST Sinyal Botu` yazın, sıklığı **Günlük**, saati **18:15** olarak ayarlayın.
4. Eylem olarak **Program Başlat** seçin:
   - **Program/komut dosyası:** `python` (veya python.exe tam yolu)
   - **Bağımsız değişkenler ekle:** `main.py --scan`
   - **Başlangıç yeri:** `C:\Users\Akif\Desktop\tradingwiew code`
5. Kaydedin. Artık her akşam borsa kapanışında bilgisayarınız otomatik tarama yapıp sinyal varsa telefonunuza iletecektir.
