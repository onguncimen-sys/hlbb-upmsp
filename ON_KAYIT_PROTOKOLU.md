# ÖN-KAYIT PROTOKOLÜ — makale tamamlama koşu paketi
**Tarih:** 2026-10-10 · **Algoritma:** v6 (etiket `v6-3j2m`, commit `11c4b28`) — DEĞİŞMEZ
**Kapsam kararı (kullanıcı):** asgari plan; Moser dış ayağı YOK, 1-124 aralığı YOK, 25 hücrelik keşif haritası YOK.
**Değişiklik kuralı:** bu dosya koşulardan önce commit'lenir (= ön-kayıt). Sonradan değişiklik yalnız
dosya sonundaki tarihli değişiklik kütüğüyle ve etkilenen koşu BAŞLAMADAN yapılabilir. Nihai kilit
commit'inden (madde 10) sonra hiçbir değişiklik yapılmaz. Koşuları kullanıcı başlatır.

## 1. Kapsam ve kapsam dışı
Kapsamda: rakip doğruluk kapısı + yeniden ayar; duyarlılık; niş geliştirme taraması; kısıt–avantaj;
ablasyon (ana-modelsiz kol dahil); tek çekirdek; CP tekrarları; kilitli saf ve kilitli niş testler; metin paketi.
Kapsam dışı: algoritma değişikliği (her türlüsü), uygunluğa özgü yeni rakip, irace/otomatik ayar,
Moser koşuları, 1-124 aralığı, 1000 örneklik tam set, alt sınır tablosu (CP'nin kendi sınır kayıtları hariç).

## 2. Veri rolleri
| rol | veri | kullanım |
|---|---|---|
| EĞİTİM | `new_dataset_sens` (niş, 8 boyut × 3 örnek) | parametre ayarı (HLBB'de yapıldı; rakipler bu protokolle) |
| GELİŞTİRME | saf: `valladapure/{50_20,100_20,150_15,200_15,250_10}/S1-99` örnek 1–10; niş: `new_dataset_niche_v2` (+ eski koşu verileri) | ablasyon, duyarlılık, taramalar, tanılar |
| KİLİTLİ SAF | aşağıdaki 4×2 hücre, örnek 1–6 | yalnız kilitli test (madde 3/9) |
| KİLİTLİ NİŞ | yeni tohumlu üreteç örnekleri (aşağıda) | yalnız kilitli test (madde 3/10) |

**Kilitli saf hücre seçimi (kural + sonuç, sonuçlara bakılmadan):** S1-99'da geliştirmede kullanılan
5 boyut dışındaki 20 boyuttan, iş/makine oranı merdiveni kuralıyla: en seyrek kullanılmamış hücre,
geliştirme orta oranlarının (5 ve 10) kullanılmamış eşleri, en yoğun kullanılmamış hücre →
**50×30 (1,67) · 150×30 (5) · 100×10 (10) · 200×10 (20)**; her hücrede yayımlı örnek **1–6**.
Aynı 4 boyut **S1-49**'da da koşulur (S1-49'un tamamı dokunulmamış). Dokunulmamışlık doğrulaması
2026-10-10: `results/` içinde bu hücrelere ait kayıt yok; `valladapure/`te bu boyutlar hiç
dönüştürülmemiş. Hazırlık: `vallada_to_hlbb.py --batch` ile bu 8 hücrenin dönüşümü (birebir, değer
değiştirmeden); dönüşüm kilitli test paketinin parçasıdır, dönüşen örneklerde hiçbir geliştirme
koşusu yapılmaz. Vallada aralık sınıfları EŞLİ DEĞİLDİR (dosya düzeyinde doğrulandı): aralıklar
arası kıyas eşsiz ve yalnız betimleyici.

**Kilitli niş hücreler:** 2 standart = üreteç 400×20 ve 800×30 (geliştirme parametreleriyle:
uygunluk p=0,5, hazır zaman katsayısı 0,2); 2 hedef rejim = madde 8'deki kurala göre geliştirme
taramasından seçilir ve kilit commit'inde buraya EK-B olarak işlenir. Her hücrede 6 örnek;
üreteç tohumları (string, deterministik): `kilit2026_<hücre>_<k>`, k=1..6. Örnekler kilit
commit'inden önce üretilir ve commit'lenir.

## 3. Koşu matrisi ve sıra
| # | paket | içerik | süre |
|---|---|---|---:|
| 1 | Rakip paketi | doğruluk kapısı → parametre dışsallaştırma + eşdeğerlik testleri → 27 kol ayar → kilit (madde 4) | ≈30–36 sa |
| 2 | Duyarlılık | 6+1 değer (makine-tarafı katsayısı dahil); v6 değişmez | ≈22 sa |
| 3 | Niş geliştirme taraması | 10 hücre: n=400, m∈{10,20,40,80} + 4 hedef rejim (madde 8) + 2 eş-oran (200×10, 800×40); hücre başına 4 örnek × 3 tekrar × {HLBB, ayarlı en güçlü rakip} | ≈13 sa |
| 4 | Kısıt–avantaj | `new_dataset_niche_b3`, 240 koşu | ≈13 sa |
| 5 | Ablasyon | ortak v6 tabanı; çıkarma+ekleme aynı koşuda; YENİ kol: ana-modelsiz (açgözlü+LKH+birleştirme); önce lockcheck düzeltmesi | ≈48 sa |
| 6 | Tek çekirdek | v6 ile büyük 30 örnek teyidi | ≈4 sa |
| 7 | CP tekrarları | 10 örnek × 3; sınır/aralık/durum/işçi kaydı | ≈2 sa |
| 8 | KİLİT | seçimler + analiz planı + EK-A/EK-B commit | — |
| 9 | Kilitli SAF | 4 boyut × {1-99, 1-49} × 6 örnek × 5 yöntem × 3 tekrar = 720 koşu | ≈40 sa |
| 10 | Kilitli NİŞ | 4 hücre × 6 örnek × 5 yöntem × 3 tekrar = 360 koşu | ≈20 sa |
Kural: ablasyon/duyarlılık/tarama sonuçları algoritmayı YENİDEN AÇMAZ; eşiği geçen atılmış bileşen
"dondurmadan sonra ölçüldü, sonraki çalışma" diye raporlanır.

## 4. Rakip doğruluk kapısı ve yeniden ayar
**Kapı (önce):** `rolim_capsule/code/gate_deltains_test.jl` — ekleme-komşuluğu hızlı delta formülünü
aynı kodun kesin yeniden hesabıyla (MachineSpan) tüm hamle kümesinde karşılaştırır. Kurallar:
(i) düzeltilmiş sürüm (DELTAINS_FIX=1) her iki algoritmada ve iki modda **mismatch=0** vermek zorunda;
(ii) sürüm seçimi performansa göre DEĞİL, yayımlı problem tanımına birebirliğe göre yapılır;
(iii) yayımlı sürümün sapması kayıt altına alınır. 2026-10-10 duman kaydı (yayımlı sürüm, saf mod,
tohum 4242): 18 785 hamlede 9 803 sapma; 644 gerçekte-iyileştiren hamle reddi; hayalet iyileştirme 0
(sapma yalnız rakibin aleyhine); niş mod: 9 971 hamlede 5 002 sapma. Raporlanan makespan her zaman
doğrudur (hamle sonrası kesin yeniden hesap var); hata yalnız aramayı yanıltır. SA'da bu komşuluk
değerlendirmesi yoktur (etkilenmez).
**Düzeltme uygulaması (kod değişikliği, kullanıcı onayı bekliyor):** HGA.jl ve GA.jl'de araya-ekleme
dalına eski komşu yayının çıkarılması, `DELTAINS_FIX` ortam değişkeni arkasında (varsayılan 0 =
yayımlı davranış); kıyas koşularında HGA/GA fix=1. Ardından eşdeğerlik testleri yeniden (bayrak
kapalıyken yayımlı sürümle birebir).
**Yeniden ayar (kapıdan sonra):** HLBB ile aynı ilke — ayrık eğitim seti, tek-değişiklik, 2SE kuralı.
Eğitim: `new_dataset_sens` {100_15, 250_20, 400_20, 800_30} × örnek 1–3 × 2 tekrar × 200 sn.
Kollar (27): yayımlı taban ×3 + tek-değişiklik ×24 —
SA: SAmax {588 314, 2 353 256}, soğutma α {0,90, 0,98}, T0 {0,5, 2};
HGA: P {10, 25}, dnn {0,6, 1,0}, dins {0,6, 1,0}, dswap {0,6, 1,0};
GA: Psize {40, 160}, Pc {0,3, 0,7}, Pm {0,3, 0,7}, Pls {0,6, 0,8}, Pressure {5, 20}.
(HGA/GA kolları fix=1 üzerinde koşar; düzeltme ayar adayı değildir.) Seçim kuralı: parametre
değişikliği yayımlı tabana göre ortalama iyileşme − 2SE > 0 veriyorsa alınır; yoksa yayımlı değer
kalır; aynı parametrede iki aday da geçerse iyileşmesi büyük olan. Seçilen ayarlar EK-A olarak bu
dosyaya işlenir ve commit'lenir; sonrasında rakip ayarı bir daha değişmez. Aynı koşularda tanı
sayaçları toplanır: ret/vazgeçme oranı, kabul oranı, nesil/değerlendirme sayısı, makine içi/arası
hamle payı (kısıtlı ve kısıtsız).

## 5. Kaynaklar, adalet, koşu kaydı
- Duvar saati bütçesi her yöntemde 200 sn; CP 1000 sn (işçi sayısı, en iyi sınır, aralık, durum kaydedilir).
- Julia koşuları AÇIK `-t 1` ile (önceki `-t auto` kusurunun düzeltilmesi); HLBB Gurobi varsayılan
  iş parçacığı; işlemci-zamanı/duvar-saati oranları ölçülüp raporlanır (mevcut adalet bölümü korunur).
- Her raporlanan koşu ortak denetleyiciden (`verify_all.py`) geçer; geçmeyen koşu rapora giremez.
- Koşu kaydı yan dosyası (her paket için): git commit hash'i, tam komut satırı, veri yolu + örnek
  listesi, tohumlar, makine. Kayıt olmadan koşu başlatılmaz.

## 6. Birincil ölçüler ve kazanan tanımı
- Analiz birimi ÖRNEK; 3 tekrar örnek içinde ortalanır (tekrarlar örneklem sayısını artırmaz).
- Birincil: örnek düzeyinde eşli fark (HLBB − rakip) ortalaması + %95 güven aralığı (t dağılımı),
  iz başına (saf/niş ayrı). İkincil: hücredeki en iyi bulunan değere göre RPD.
- Pratik eşik: |ortalama fark| < 0,5 RPD puanı → "pratikte eşdeğer" dili; üstünlük dili yalnız güven
  aralığı 0'ı dışlarsa.
- Çokluk: Holm düzeltmesi, aile = iz başına 4 rakip karşılaştırması (saf ailesi, niş ailesi ayrı).
- Kazanan cümlesi: "X kazanır" = eşli fark güven aralığı 0'ı dışlar VE işaret tutarlı; aksi hâlde
  "fark gösterilemedi".

## 7. İstatistik ayrıntıları
- Hazırlık aralıkları (1-99 / 1-49) arası kıyas: eşsiz, yalnız betimleyici (eşli fark kurulamaz —
  yayımlı sınıflar bağımsız üretilmiş). Yön tahmini önceden: HLBB avantajı 1-49'da 1-99'a göre
  azalır ama işaret korunur (rapor 2'nin öngörü sınaması); sonuç ne çıkarsa olduğu gibi raporlanır.
- Ölçek kontrolü: mutlak fark (birim) + ortak ölçekli fark (RPD) birlikte.
- Tekrarlar arası yayılım ek tabloda (yöntem kararlılığı); karar istatistiğine girmez.

## 8. Niş hedef rejimleri, seçim kuralı, çerçeve karar tablosu
Hedef rejim tanımları (üreteç parametreleriyle; taban n=400, m=20):
R1 seyrek-rastgele: uygunluk p=0,2; R2 yapılı-kümeli: p≈0,2, işler 4 aileye / makineler 2 gruba
kümeli (üreteçte küçük ek seçenek — kod değişikliği onayı gerekir); R3 büyük hazır zaman: katsayı
0,2→0,6; R4 = R2+R3. Standart kontrol: p=0,5, katsayı 0,2.
**Seçim (geliştirme taramasında):** fark-farkı I = (HLBB−rakip)_hedef − (HLBB−rakip)_standart,
RPD puanı. Aday olma eşiği: I ≥ 0,5 VE I − 2SE > 0. En yüksek iki aday kilitli nişe girer (EK-B).
Aday sayısı < 2 ise eksik yer en büyük standart hücreyle doldurulur ve çerçeve (a)'da kalır.
**Çerçeve karar tablosu:**
| koşul | sonuç |
|---|---|
| hiçbir rejim eşiği geçmez | konum (a); yeni rejim ARANMAZ; kısıtlar "pratik kapsam" olarak kalır |
| rejim geçer + kilitli nişte aynı yönde ve GA 0'ı dışlar | konum (b) YALNIZ o rejim için dar biçimde |
| ana-modelsiz ablasyon kolu tam yönteme ≤0,5 RPD yakın | "model-tabanlı" katkı atfı daraltılır |
| kilitli safta büyük boyut avantajı doğrulanmaz | üstünlük iddiası ölçülen kapsama küçültülür |
Katkı cümlesinin son hâli bu tablonun sonucuna göre, kilitli testlerden SONRA yazılır.

## 9. Arıza, yeniden koşu, durma
- Çökme/çıktısız bitiş: aynı tohumla 1 kez tekrar; yine olursa o (örnek, yöntem) çifti dışlanır ve
  raporda açıkça listelenir. Örnek ya da hücre TAKASI yapılmaz.
- Bütçe aşımı (yöntem durdurma koşulunu geç kontrol ediyorsa): ölçüldüğü gibi raporlanır (mevcut uygulama).
- Duman testi kuralı: her paketin ilk koşusunda ölçülen ana bileşenin gerçekten çalıştığı doğrulanır
  (geçmiş ders: bütçe parametresi bileşeni kapatmıştı).
- Durma: bir paketin sonucu sonraki paketi anlamsız kılarsa (ör. doğruluk kapısı geçilemezse) zincir
  durur, kullanıcıya dönülür; plan içinde kalan paketler sonuca bakılarak YENİDEN sıralanmaz.

## 10. Kilit kaydı
- Bu dosyanın ilk commit'i = ön-kayıt. Paket 1 sonunda EK-A (rakip ayarları), paket 3 sonunda EK-B
  (hedef rejimler) eklenir; her ek ayrı commit.
- Paket 7 bitince NİHAİ KİLİT commit'i: analiz planı + bütün seçimler donar; kilitli veri (saf JSON
  dönüşümleri + niş yeni-tohum örnekleri) bu commit'te ya da öncesinde depodadır.
- Kilitli test sonuçları hiçbir seçimi değiştiremez; yalnız raporlanır ve çerçeve tablosunu işletir.

## Değişiklik kütüğü
- 2026-10-10: ilk sürüm (Claude; dayanaklar: YOL_HARITASI_2026-10-08.md + EK 1/2/3, GPT tur36–39).
- 2026-10-10 (kullanıcı onayıyla, koşular başlamadan): madde 4'teki üç kod değişikliği uygulandı ve
  doğrulandı. (1) DELTAINS_FIX bayrağı (HGA.jl/GA.jl): kapı testi bayrak açık 4/4 kombinasyonda
  sıfır sapma; bayrak kapalı eşdeğerlik testleri yayımlı orijinalle birebir (SA/HGA/GA); bayrak
  açıkken davranış değişiyor (koda ulaştığının kanıtı). (2) Parametre dışsallaştırma (ortam
  değişkenleri SA_SAMAX/SA_ALPHA/SA_T0, HGA_P/HGA_DNN/HGA_DINS/HGA_DSWAP, GA_PSIZE/GA_PC/GA_PM/
  GA_PLS/GA_PRESSURE; varsayılan = yayımlı): değişken yokken birebir eski davranış, her değişken
  sürücü üzerinden etkili. (3) Üreteçte kümeli uygunluk (elig_mode="kumeli"): varsayılan yol
  bayt-aynı (3 örnek yeniden üretilip karşılaştırıldı); kümeli yoğunluk 0,200 (hedef 0,2),
  kendi-grup 0,372 / diğer-grup 0,043, deterministik, taban matrisler değişmiyor.
  Ayar koşusu betiği eklendi: `rival_tuning_benchmark.py` (27 kol, -t 1, ortak denetleyici
  kancası, kaldığı yerden devam; duman testi geçti, duman CSV'si silindi).
- 2026-10-11 (etkilenen kollar hiç koşulmadan): madde 4 tek-değişiklik listesinde HGA dnn/dins/dswap
  üst adayı 1,0 → 0,9. Gerekçe: kodda komşuluk sayısı floor(m×d) ve döngü l[1+ngh]'a erişiyor;
  d=1,0 dizin taşması veriyor (koşu 289'da BoundsError ile yakalandı, asgari örnekle tekrar
  üretildi; 0,9 tüm makine sayılarında güvenli: floor(m×0,9) ≤ m−1). 1,0 kollarının hiçbiri satır
  üretmedi; tamamlanan 288 satır etkilenmez. Ayrıca madde 9'un arıza kuralı (aynı tohumla 1 tekrar,
  olmazsa dışla+raporla) harness'a kod olarak eklendi; dışlanan çift CSV'ye "HATA" satırı olarak düşer.
- 2026-10-11 akşam: GA nüfus üst adayı 160 → 120. Gerekçe: yayımlı kodda Psize 8-bit tamsayı
  (üst sınır 127); 160 ayrıştırma aşamasında deterministik taşma hatası — hiçbir performans ölçümü
  üretmedi, 24 koşusu arıza kuralıyla "HATA" olarak dışlandı ve CSV'de kayıtlı (denetim izi).
  120 = 1,5 × yayımlı değer, tip sınırı içinde (asgari örnekle doğrulandı: temiz RESULT). Koşu
  kesintiye uğramadı; 120 kolu koşu bitiminde aynı komutla (kaldığı yerden devam) tamamlanacak.

## EK-A (2026-10-12) — RAKİP AYAR KİLİDİ (madde 4 tamamlandı)
Veri: `results/rival_tuning.csv` (672 koşu = 648 + nüfus-120 telafisi 24; 24'ü HATA/dışlandı
[geçersiz 160 adayı], 648 geçerli ölçüm; denetleyici ihlali 0). Kural: tek-değişiklik kolu yayımlı
tabana karşı örnek-bazlı eşli ortalama iyileşme − 2SE > 0 ise alınır.

**Sonuç (27 koldan 2'si geçti; yöntem başına en çok bir değişiklik → bileşim riski yok):**
- **SA: tamamen yayımlı** (SAmax=1176628, soğutma 0,96, T0=1) — 6 kolun hiçbiri geçmedi
  (en iyisi +%0,38 ± 0,65). Ana rakip kendi yayımlı ayarının en iyisi olduğunu doğruladı.
- **HGA: ekleme-komşuluğu kesri 0,8 → 0,9** (+%1,06 ± 0,62; dört boyutta pozitif; karşı yön
  −%2,62 = doz-yanıt tutarlı). Diğer parametreler yayımlı. Ortam: `HGA_DINS=0.9`.
- **GA: mutasyon olasılığı 0,5 → 0,3** (+%1,07 ± 0,91; dört boyutta pozitif; karşı yön −%1,12).
  Nüfus=120 telafi kolu +%0,08 ± 0,74 → GEÇEMEDİ, yayımlı 80 kalır. Diğerleri yayımlı.
  Ortam: `GA_PM=0.3`.
- **Düzeltme bayrağı (`DELTAINS_FIX=1`) HGA/GA'nın BÜTÜN kıyas koşularında açık** (iki hatta da;
  doğruluk meselesi, ayar değil).
- **Hat ayrımı:** SAF hat → yayımlı parametreler (literatürün Vallada setinde doğruladığı değerler;
  saf limitte kod orijinal yola düşer, eşdeğerlik kanıtlı). NİŞ hat → yukarıdaki ayarlı sürümler.
  SA'da ikisi zaten özdeş.
- GA'nın nesil-sonu durma taşması ölçüldüğü gibi raporlanır (bu koşuda nüfus-120 kolunda ort. 225 /
  en çok 284 sn); taşıyan kol fazladan süreye rağmen seçilmedi → seçim güvenli yönde.
Bu ekle birlikte rakip ayarları DONMUŞTUR; sonraki hiçbir koşuda değiştirilemez.
- 2026-10-12 (paket 2 koşu-öncesi, GPT tur42 denetimi; koşu başlamadan): duyarlılık betiğine
  üç düzeltme: (1) arıza kuralı (1 tekrar → dışla+"HATA" kaydı; başarana-kadar-deneme seçilimi
  kapandı); (2) denetim kapısı rapora bağlandı (yalnız feas=1 satırlar kalite hesabına girer;
  denetim türü "sıralı/atama" sütunu eklendi) — eski v4 koşusunda 6 ihlalin ortalamalara
  karıştığı bu süzgeçle görüldü; (3) rapor dili: "fark yok (düz)" → "fark gösterilemedi"
  (düzlük kanıtı değildir), kol lehine fark → "dondurma sonrası bulgu, v6 DEĞİŞMEZ"; bütünlük/
  benzersizlik özeti eklendi. Koşu kaydı yan dosyası (git+bütçe+tohum politikası) eklendi.
  TOHUM POLİTİKASI SABİTLENDİ: tüm kollar üretim varsayılanı tohum=0 ile; tekrarlar aynı tohum
  altındaki koşudan-koşuya oynaklığı ölçer, tohum dayanıklılığını DEĞİL (çıkarım sınırı rapora
  yazılır; rakip ayar koşusuyla "aynı tekrar tasarımı" diye sunulmaz). BİLEREK YAPILMAYAN
  (gerekçeli): kol sırası rastgeleleme (işçi başına ayrı süreç + koşu öncesi LKH temizliği
  ortamı eşitliyor), işe-özel geçici dizin/koşucu kilidi (koşular her zaman sıralı ve elle).
- 2026-10-13: PAKET 2 (duyarlılık) TAMAMLANDI — 384/384, 0 ihlal/dışlanan. Sonuç: 15 kolun
  12'sinde fark gösterilemedi; üretim lehine iki gerçek duyarlılık: aday-makine=5 → 800×30'da
  +%33 (ölçek çöküşü; k=3 gerekçesinin ölçümü), yay=3 → her boyutta +%3,6 (K=5 dirsekte);
  havuz=40 +%0,22 (eşik üstü ama 0,5 pratik eşiğin altında). Makine-tarafı-kapalı: fark
  gösterilemedi (±0,65 gürültü; kapı etkisini görecek güçte değil — 3J2M hükmü kapı verisine
  dayanır, bu koşu yalnız "kırılgan değil" der). METİN DÜZELTMESİ: birleştirme süresi beyanı
  20 sn ≠ fiilî (21/24 kırpılma, etkin ort. 13,8 sn) → §3.5 metin paketinde düzeltilecek.
  v6 DEĞİŞMEDİ (protokole uygun). Veri: results/sensitivity_v6.csv + manifest.
- 2026-10-13 (paket 3 koşu-öncesi, GPT tur43 denetimi; koşu başlamadan): niche_dev_scan.py
  eklendi (10 hücre, 240 koşu ≈14 sa). İŞARET TANIMI netleştirildi: d = RPD(rakip) − RPD(HLBB),
  pozitif = HLBB avantajı; madde 8'deki "(HLBB−rakip)" avantaj anlamındadır, bu tanımla ölçülür.
  "Ayarlı en güçlü rakip" = SA ve EK-A gereği ayarlı SA = YAYIMLI SA (hiçbir değişiklik eşiği
  geçmemişti). Tohum = tekrar (1..3) iki yöntemde de. tur43 düzeltmeleri: arıza kuralı istisnaları
  da kapsar; kalite kümesi = denetimden geçmiş VE SIRALI denetlenmiş satırlar; eksik-veri kuralı
  ön-kayıtlı (örnek: iki yöntemde ≥2 tekrar; hücre: ≥3 örnek, yoksa ADAY OLAMAZ); çift anahtar
  hesaptan önce atılır; SA çıktı koruması (yöntem adı + sonlu değer); n=4 uyarısı rapora gömülü
  (2SE kaba tarama kuralı, %95 GA değil). BİLEREK YAPILMAYAN (gerekçeli): yöntem sırası
  dengeleme ve kilit dosyası (koşular sıralı+elle; koşu başına ayrı süreç + LKH temizliği),
  zaman-aşımı süreç-ağacı temizliği (sıralı pratikte bir sonraki koşunun temizliği karşılıyor).
  Dumanlar: HLBB 200×10 / 400×80 / 800×40 temiz (sıralı denetim dahil); SA 800×40 köprüsüyle
  temiz; sentetik rapor testi (aday/eksik-veri/çift yolları) geçti. Veri: new_dataset_devscan
  (40 örnek, tohum tarama2026_*; yoğunluklar hedefte).
- 2026-10-13 (paket 3, GPT tur44 geçerlilik denetimi; koşu başlamadan): tarama ESLİ tasarıma
  çevrildi — beş 400×20 hücresi (çapa + 4 rejim) ortak taban tohumları kullanır
  (tarama2026_400x20_k; üretecin temiz-ablasyon özelliği kodda ve diskte doğrulandı: aynı
  tohumda işlem/hazırlık sabit, yalnız kısıt kolu değişir). I artık örnek-başına eşli farktan
  (Δ_k = d_hedef,k − d_çapa,k; K≥3 geçerli çift şartı). Koşu sırası önceden belirlenmiş tohumla
  karıştırılır. YORUM SINIRLARI (rapora gömülü + metne taşınacak): I>0 "avantaj artışı"dır,
  mutlak üstünlük değil; sabit 200 sn bütçe altında ölçek davranışı ölçülür; eksen ayrıştırması
  iki kesittir (m-taraması + eş-oran), tüm etkileşimleri kapsamaz; hazırlık aralığı ve
  uygunluk–hız ilişkisi eksenleri TARANMAZ → metinde genelleme bu eksenlere kurulmaz (ek hücre
  yerine dürüst sınırlama; asgari kapsam kararı). Rejim yorumu doğru kıyaslarla yapılır:
  r1−çapa (yoğunluk), r2−r1 (kümeleme), r3−çapa (hazır-zaman), r4−r2 (bileşikte hazır-zaman).
  Kilitli niş testte payda tanımı ve yöntem listesi şimdiden sabit (madde 3/6); seçimin SA'ya
  karşı yapıldığı, hükmün 5 yöntemle verileceği nottur.
- 2026-10-14: PAKET 3 (niş geliştirme taraması) TAMAMLANDI — 240/240, 0 ihlal/dışlanan.
  SONUÇ 1 (rejim seçimi): DÖRT REJİM DE EŞİK ALTI, hepsinde I NEGATİF (−6,2…−7,8): kısıt
  sıkılaşınca HLBB avantajı KÜÇÜLÜYOR (ama hâlâ pozitif: +0,9…+2,4). Ön-kayıtlı kurala göre
  çerçeve (a)'da kalır; yeni rejim ARANMAZ. SONUÇ 2 (m-taraması, altıncı madde cevabı):
  avantaj "ölçeği" değil MAKİNE SAYISI × yoğunluk bileşimini izliyor: n=400'de m=10→+9,8,
  m=20→+8,6, m=40→−18,5 (yüksek varyans: iki örnekte çöküş, ikisinde normal), m=80→−9,8;
  eş-oran hattında (oran 20) 200×10 +3,7 / 400×20 +8,6 / 800×40 +6,0 ama m=40'ta kararsız
  (bir örnek-tekrarda 485'e savrulma). Mekanizma izi: çöken örneklerde en-iyi-zamanı ~1-40 sn
  (ana model erken donuyor) — kapalı konulardaki makine-kapanması bulgusuyla tutarlı; algoritma
  DONUK, düzeltme girişimi YOK; bulgu kapsam/sınır haritası olarak raporlanacak. EK-B kararı
  kullanıcıda: kilitli niş doldurma seçeneği (protokol kuralı "en büyük standart hücre" =
  zayıflık hücreleri çıktı; dürüst seçenek bunları BİLEREK almak). Veri: results/niche_devscan.csv.

## EK-B (2026-10-14, kullanıcı onaylı) — KİLİTLİ NİŞ TEST TASARIMI (madde 8 sonucu)
Geliştirme taraması sonucu: dört rejim de aday eşiğinin altında (I'ler negatif) → çerçeve (a);
doldurma, ön-kayıtlı "en büyük standart hücre" kuralıyla (tur45, GPT ortak; sonuç-güdümlü sapma yok).
1. **Hücreler ve roller:** 400×20 ve 800×30 = DOĞRULAYICI aile (üstünlük iddiası yalnız burada
   kurulur; 2 hücre × 4 rakip = 8 hipotez, Holm düzeltmesi, eşli fark + %95 GA, birim = örnek,
   hücre başına 6 yeni-tohum örnek, 3 tekrar örnek içinde özetlenir). 800×40 ve 400×80 =
   ÖN-BEYANLI BETİMLEYİCİ sınır hücreleri (tüm sonuçlar eksiksiz raporlanır; doğrulayıcı
   üstünlük YA DA eşdeğerlik/zayıflık hükmü kurulmaz; çokluk ailesine girmez). Ayrımın
   gerekçesi beklenen sonuç değil, iddianın kapsamıdır.
2. **Ön-beyan (geliştirme verisine dayalı, SA'ya karşı, RPD ölçüsünde):** 800×40'ta pozitif
   fakat değişken fark; 400×80'de küçük negatif fark bekliyoruz. Kilitli sonuçların bu
   beklentilerle uyumu betimlenir; uymayan sonuç da açıkça raporlanır. Beklenti kayıttır,
   kanıt değildir — "öngörülmüştü = doğrulandı" otomatiği YOK.
3. **Kapsam dili:** "m≤30 doğrulanmış bölge" DENMEZ. İddia, test edilen iki kapsam-içi
   konfigürasyonda doğrulanır; m≤30 hedef kapsam olarak anılır; sınırın ötesi ölçülmüş ayrı
   bulgudur. Geliştirme m-taraması makalede "geliştirme analizi" etiketiyle sunulur; zayıflık
   mekanizması hipotez diliyle ("erken donma, aday-liste kapanmasıyla tutarlı"), yeni deney yok.
4. **CP kuralı:** her hücrede aynı kaynak kuralıyla (1000 sn, işçi kaydı) koşulur; model-kurma
   süresi, çözme süresi, durum, geçerli çözüm, en iyi sınır ve gap kaydedilir. Çözüm yoksa
   nedeniyle "sonuç yok" raporlanır; çözüm-üretme oranı ayrı gösterilir; CP çözümsüzken o
   hücrede "bütün rakipler" dili kurulmaz. Sonda 2026-10-14: iki sınır biçiminde de model
   kuruluyor, 60 sn'de geçerli çözüm (kayıt: tur46 bölümü, ilerleme notları).
5. **Süre/analiz kuralları (kilit commit'inde kesinleşir):** bütçe-aşımı (GA nesil-sonu)
   ölçüldüğü gibi raporlanır ve bütçe-sonrası iyileşmenin birincil skora girip girmeyeceği
   kilitte yazılır; analiz tarifi (test, yön, tekrar özeti, eksik-sonuç kuralı) ve 6-örnekli
   ailenin güç/ulaşılabilir-p kontrolü kilitten önce tamamlanır; sonuç görüldükten sonra test
   değiştirilmez. Üreteç sürümü + kilit tohumları (kilit2026_*) + yöntem/ayar kimlikleri kilit
   commit'inde sabitlenir.
- 2026-10-14 (paket 4 koşu-öncesi, GPT tur47; koşu başlamadan): kısıt–avantaj deneyi (Ağustos
  tasarımı: new_dataset_niche_b3, eşli hücreler eoff_r0 ↔ e50_ron, 4 boyut × 5 örnek × 3 tohum
  × {HLBB, SA} = 240 koşu). Koşucu düzeltmeleri: Julia -t auto → **-t 1** (madde 5); EK-A ortamı
  koşucuya bağlandı (DELTAINS_FIX=1, HGA_DINS=0.9, GA_PM=0.3 — SA'da etkisiz, ileriki kilitli
  koşular için); **arıza kuralı eklendi** (1 tekrar → kalıcı dışlama yan-dosyası; devam dışlananı
  yeniden açmaz; ana CSV şeması değişmedi). Tohum-0 ve örnek/tekrar anlamları koddan doğrulandı.
  **ANALİZ ÖN-KAYDI:** birim = taban örnek (boyut başına n=5; tohumlar örnek içinde ortalanır).
  BİRİNCİL zıtlık: HAM eşli fark-farkı Δ_k = A_k,açık − A_k,kapalı; A = ort(SA) − ort(HLBB)
  (birim: makespan). Ortak-paydalı yüzde EŞLİK EDER: Δ_k / ort(SA)_k,kapalı × 100 (iki hücrede
  AYNI payda — hücre-içi RPD paydası kısıtla büyüdüğünden yüzde zıtlığı mekanik küçültür; o
  yüzden hücre-içi RPD yalnız İKİNCİL betimleyici). Belirsizlik: n=5 → t-aralığı ±2,776·SE
  (2SE "%95" DENMEZ); beş bireysel Δ da gösterilir. Eksik-çift kuralı: çiftin herhangi bir
  bileşeni eksikse çift tümüyle düşer ve raporlanır. YORUM TABLOSU (4 sonuç; eksik satır
  eklendi): kapalıda kayıp→açıkta kazanç = bağ ölçüldü; ikisinde kazanç = zayıf rejim veriye
  özgü; ikisinde kayıp = zayıflık biçimden; **kapalıda kazanç→açıkta kayıp = kısıt ALEYHTE**.
  KAPSAM SINIRI: ölçülen şey uygunluk+hazır-zaman PAKETİNİN birleşik etkisidir (hangisi ayırt
  edilmez; ara hücreler ancak sonuç köşegense koşulur, +6,7 sa, kullanıcı kararı); en büyük
  boyutta m de değişir → saf ölçek etkisi ayrışmaz; "çerçeve izolasyonu tamamen kapandı" DENMEZ.
- 2026-10-14 (koşu-öncesi kontrolde): results/niche_b3.csv'nin 2026-08-24'te ESKİ sürümle
  (v4-dönem; maliyet-hatası/birleştirme/makine-tarafı düzeltmeleri öncesi, -t auto) bir kez
  koşulmuş 240 satır içerdiği görüldü — bekleyen-iş kaydı "koşulmadı" diyordu, analiz hiç
  yapılmamış. Devam mekanizması bunları "tamam" sayıp v6 koşusunu atlayacaktı. Dosya
  results/niche_b3_ESKI_v4donem_2026-08-24.csv olarak arşivlendi; paket 4 temiz CSV ile v6
  üzerinde koşulur. (Ders: bu koşucuda taban-imza koruması yok — sürüm kimliği manifest
  satırı + bu kütükle tutuluyor; eski dosya yalnız tarihsel karşılaştırma içindir, hiçbir
  makale sayısına kaynak OLAMAZ.)
- 2026-10-15: PAKET 4 (kısıt–avantaj) TAMAMLANDI — 240/240 (4 faz × 60), 0 yeni ihlal,
  0 dışlanan, ~13,9 sa. ÖN-KAYITLI EŞLİ ANALİZ (ham Δ = A_açık − A_kapalı; birim makespan;
  n=5, t-aralığı ±2,776·SE): 50×20: A −3,3→−2,0, Δ +1,3 ±1,7 (0 içerir; KAYIP KISITLA
  KAYBOLMUYOR → zayıflık n/m=2,5 biçiminden); 100×20: +1,8→+3,1, Δ +1,3 ±2,9 (iki hücrede de
  kazanç → eski Track A kaybı veriye/sürüme özgü); 400×20: +41,1→+34,5, Δ −6,6 ±5,7
  (0 DIŞINDA: kısıt paketi avantajı anlamlı KÜÇÜLTÜYOR); 800×30: +78,9→+72,6, Δ −6,3 ±15,0
  (0 içerir, yön aynı). Ortak-paydalı %: +3,1/+1,8/−2,6/−2,0. SONUÇ: "avantaj kısıtla büyür"
  ekseni İKİNCİ bağımsız deneyde de çürüdü (paket 3 ile tutarlı); avantajın kaynağı ölçek/biçim,
  kısıtlar pratik kapsam — çerçeve (a) metni buna göre; §5.4 "weak regime appears only on the
  pure problem" cümlesi ölçüme göre YENİDEN yazılacak (kontrollü karşıtlık: 50×20 kaybı kısıtlı
  hücrede de sürüyor). ÇAPRAZ KONTROL: Ağustos'taki eski-sürüm arşivi aynı yön deseni veriyor
  (sürümden bağımsız, sağlam bulgu). Veri: results/niche_b3.csv + manifest.
- 2026-10-16 (paket 5 koşu-öncesi, GPT tur48+tur49; koşu başlamadan): ABLASYON HAZIR.
  (0) TUR48 genel durum denetiminin iki öne-çekmesi kapandı: EK-B GÜÇ KONTROLÜ YAPILDI
  (lit_gece/araclar/ekb_guc_kontrolu.py; n=6, aile=8, Holm en sıkı adım α=0,00625 → df=5
  t-eşiği 4,53; plug-in etkilerle 8/8 hipotezde güç ≈1,00, en küçük t=18,1; işaret testi
  OLSAYDI taban-p=0,03125 aileyi hiç reddedemezdi — birincil test protokol §6 gereği
  t-aralığı; girdi v4 verisi YALNIZ güç tahmini, makale sayısı değil; sonuç görülünce test
  değişmez). Makale dili daraltması kabul: paket 3–4 için "ikinci bağımsız teyit" değil
  "aynı üreteçte iki ayrı deney, tutarlı bulgu".
  (1) Kilit nöbetçisi tasarlandığı gibi tetiklendi: kopya tezgâh üretimin 4 parametre
  gerisindeydi (mach_side, mach_arc_keep, reserve_pool, spp_self_cache) → üretim bloklarının
  birebir kopyasıyla taşındı. İKİ SESSİZ SAPMA daha kapatıldı: rota-önbelleği en-iyi-koru
  düzeltmesi (2026-10-05) kopyada yoktu; trace parametresi işçi geçişiyle çakışacaktı
  (tezgâh-yönetimli anahtarlara alındı).
  (2) SADAKAT: eşdeğerlik testi GEÇTİ (deterministik, 2 geçiş: döngü+ana model 170,0=170,0;
  +birleştirme 168,0=168,0; atamalar birebir). Hedefli kontroller: makine-tarafı kuralı her
  ana model kurulumunda fiilen tetikleniyor; öz-önbellek bağlayıcı sondası (yüksek
  sütun-tekrarlı sabit havuz) makespan aynı + rotalama 0,67→0,21 sn. Ark-koruma ve
  rezerv-havuz bu koşuda ÖLÜ (taban=kapalı, hiçbir kol açmıyor) → sadakat iddiası kurulmuyor.
  (3) YENİ KOL no_master (rapor 2 R2.8 / N1): ana model hiç çözülmez; iterasyon = gürültülü
  açgözlü kurucu (üretim LPT kuralı; iş-sırası ve makine-seçimi anahtarlarına çarpımsal
  U[0,8;1,2], kol tohumundan sıralı; maliyet/yük güncellemeleri gürültüsüz) + LKH rotalama +
  havuz; dönem sonu AYNI birleştirme sözleşmesi; eşit toplam bütçe. Devre dışı (ana modele
  bağlı): ısıtma, sapma-öğrenme, derece, aday-indirgeme, no-good, çözüm-havuzu hasadı.
  YORUM ÇERÇEVESİ (önceden): kol "ana model + bağlı mekanizma paketinin eşit bütçeli
  çok-başlangıçlı kurucuya karşı katkısını" ölçer; "matematiksel modelin saf nedensel
  katkısı" DENMEZ. ±%20 aralığı kod yazılırken (duman ÖNCESİ) sabitlendi; commit duman
  sonrası — dumandan sonra hiçbir ayar değişmedi, değişmeyecek (tur49 kaydı).
  KARAR KURALI (kesin): Δ̄ = 24 örnek-hücre ortalaması dRPD(no_master − full), tekrarlar
  hücre içinde ortalanır, payda = hücre en-iyisi; Δ̄ ≤ 0,5 → "model-tabanlı" atıf daraltılır;
  boyut kırılımı + 400×20/800×30 AYRICA gösterilir; no_master ≥ full çıkarsa bulgu öne yazılır.
  GERİ-EKLEME HÜKÜM SINIRI: "donuk v6'ya bu ayar/bütçeyle eklemek yararlı/zararlı" denir;
  "bileşen genel olarak zararlı" ya da "eski atma kararı doğrulandı" DENMEZ.
  (4) DUMAN (50×10, 60 sn): no_master 5738 kurucu iterasyonu, 0 ana model izi, 5739 tekil
  atama, birleştirme MIP optimal, bütçe içi (45 sn), denetleyici 0 ihlal (sıralı). Dürüst not:
  bu duman noktasında no_master 167 < full 168 (tek koşu, ölçüm değil; küçük-boyut zayıflığı
  zaten biliniyor). Uç havuzda (11.477) birleştirme kurulumu 0,11 sn → zaman muhasebesi bütçe içi.
  (5) KOŞU HİJYENİ: iş sırası sabit-tohumlu karıştırma ("ablasyon2026"); arıza kuralı
  (1 tekrar → dışla + .dislanan.csv + raporda açık liste; CSV'ye HATA satırı yazılmaz);
  koşu kaydı (git hash + bütçe + tohum politikası) her başlatma/devamda manifest satırı;
  farklı git hash'te devam insan kararı olmadan YOK; taban-imza kilidi CSV yanında.
  (6) MATRİS: iz niche_v2 (GELİŞTİRME verisi), 14 kol × 8 boyut × 3 örnek × 3 tekrar = 1008
  koşu, bütçe 200 sn, tohum sabit 0 (tekrar = koşudan-koşuya oynaklık; analiz birimi
  örnek-hücre, tekrarlar içinde ortalanır), CSV results/ablation_v3.csv (v3 = ÜÇÜNCÜ ablasyon
  deneyi; algoritma v6 — kimlik manifest+kilitte). BÜTÇE DÜZELTMESİ (tur49): ~58 sa
  (1008 × ~207 sn); yol haritasındaki "~48 sa" ek yüksüz 864 koşu hesabıydı, 14. kolun payı
  yalnız +4 sa. Kural (tekrar): ablasyon sonucu algoritmayı YENİDEN AÇMAZ.
- 2026-10-18: PAKET 5 (ABLASYON) TAMAMLANDI — 1008/1008 (14 kol × 8 boyut × 3 örnek × 3 tekrar,
  iz niche_v2, bütçe 200 sn), 0 dışlanan, denetleyici 0 ihlal (sıralı), ~53,5 sa (bir kez
  durdurulup devam edildi; kilit/manifest izinde). Veri: results/ablation_v3.csv (+lock.json
  +manifest). SONUÇLAR (Δ = RPD(kol)−RPD(full), 24 örnek-hücre ort., tekrarlar hücre içinde):
  ÇIKARMA: no_warm +6,91±2,34SE (yük tamamen n≥400); no_degree +0,40 ve no_bias +0,25
  (belirgin katkı saptanmadı — "katkısı yok" DENMEZ); no_spp +2,37±0,24 (23/24);
  no_kmach +20,97±2,54 (24/24; 640/800'de 12 koşu yapısal çöküş İÇİNDE — oranı ayrıca
  raporlanır, ortalamadan çıkarılmaz); no_pool +1,26±0,20.
  ⭐ NO_MASTER +31,96±3,20 (22/24 kayıp, 1 eşit, 1 kazanç). ÖN-KAYITLI KARAR KURALI:
  Δ̄=+31,96 ≫ 0,5 → "model-tabanlı" atıf DARALTILMAZ. Yorum (önceden yazılan çerçeveyle):
  ana model + bağlı mekanizma paketinin eşit bütçeli çok-başlangıçlı kurucu+birleştirmeye
  karşı katkısı ~32 RPD puanı; YALITILMIŞ model etkisi DENMEZ. Boyut kırılımı (önceden
  beyanlı): 50×10 −0,11 (fark küçük; bilinen küçük-biçim zayıflığıyla tutarlı); 100×15 +18,1;
  150×15 +42,8; 200×20 +45,3; 250×20 +46,8; 400×20 +35,0; 800×30 +32,1.
  MEKANİZMA GÖZLEMİ (tüm örneklerde ölçüldü): 400×20'de no_master=no_kmach=no_warm üç örnekte
  de AÇGÖZLÜ TOHUM değerinde (ör. 592 vs full 432-441; no_master 2.542-2.685 kurucu iterasyonu +
  optimal birleştirmeye rağmen); 640/800'de no_master=no_kmach=tohum, no_warm tohumu geçiyor.
  Dil (tur50): "bu kurucu ve bütçeyle üretilen havuz büyük örneklerde optimal birleştirmeye
  rağmen tohumu iyileştiremedi"; sütun-arzı tezi DESTEKLENDİ ama ayrıştırılmadı.
  GERİ-EKLEME (6 kol, tek müdahale, v6 tabanı): beşi gürültüde (−0,18…+0,21), maliyet-sarsma
  +0,60 (2SE 0,51, sınırda zararlı). Hüküm dili: "geri eklemede belirgin yarar saptanmadı" —
  eşdeğerlik kanıtı DEĞİL; kapsam "donuk v6'ya bu ayar/bütçeyle" (tur49 sınırı).
  SE beyanı: fark örnek-hücre düzeyinde eşli, SE 24 hücre üzerinden; çıkarma etkileri
  etkileşim nedeniyle toplanamaz. deg-guard: 294/1008 (640/800'de degree'li tüm kollar).
  METİN SONUÇLARI: §5.3 + Tablo 7 tek taban/tek payda ile yeniden (dokuzuncu madde koşu
  tarafı KAPANDI; "iki panel farklı referans" notu silinir); no_bias'ın gürültüye inmesi yeni
  tablonun ölçümü olarak yazılır (mekanizma spekülasyonu YOK); ana-modelsiz kol = ikinci
  raporun "eksik taban" cevabı. ALGORİTMA DONUK — hiçbir kol yeniden açılmaz (kural gereği;
  eşiği geçen tek geri-ekleme adayı da yok). Kayıt: tur50_soru/cevap_ham.md.
  SIRADA: paket 6 (tek çekirdek v6, ~4 sa) + paket 7 (CP tekrarları, ~2 sa) hazırlığı.
- 2026-10-18 (metin turu 1, kullanıcı onayı; GPT tur51 plan denetimi): paket 1-5 sonuçları makale
  metnine işlendi (ayrıntılı döküm PAPER_STYLE.md bölüm notu). ÖNEMLİ DÜZELTME: §5.2'deki eski
  "constraint density" paragrafı ARŞİVLENMİŞ eski-sürüm B3 koşusundan üretilmiş makroları
  kullanıyordu (protokol notu "hiçbir makale sayısına kaynak OLAMAZ" ihlali tespit edilip kapatıldı);
  paper_stats.py _b3() ön-kayıtlı hücre-bazlı analize geçirildi, makrolar v6 verisinden yeniden
  üretildi ve diff ile YALNIZ o bloğun değiştiği doğrulandı. Ana sonuç tabloları (Tablo 2, Track B,
  özet sayıları) BİLEREK eski hâlinde + TODO işaretli: kilitli koşular (paket 9-10) yenileyecek.
- 2026-10-18 (paket 6+7 koşu-öncesi, GPT tur53 yerine tur52; koşular başlamadan): HAZIR.
  PAKET 6 (işlemci-adaleti, v6): tur52 şartıyla ÜÇ aşama — (0) çok-çekirdek v6 tabanı
  (8 boyut × 5 örnek × tohum 0 × 200 sn = 40 koşu; tek-çok farkı AYNI sürümle, eşli,
  örnek-başına) + (1) tek-çekirdek v6 (taskset işlemci 0, Gurobi Threads=1, Julia -t 1;
  aynı 40) + (2) kaynak ölçümü. Eski v5-dönem çıktılar *_ESKI_v5donem_2026-09-30 olarak
  arşivlendi (bayat-devam dersi). Rakip kıyası ARA teyit (kilitli koşular nihai). Duman:
  30 sn × 8 koşu, bağlılık doğrulandı, 0 ihlal. Başlatıcı: run_paket6_v6.sh (~5,5-6 sa).
  PAKET 7 (CP ek tekrarları, M11): cp_tekrar_run.py — nis kıyası CP ayarlarının aynısı
  (aynı model, 1000 sn, işçi=Auto); örnek seçimi ÖN-KAYIT: her boyutun 1. örneği +
  640×25/2 + 800×30/2 = 10; örnek başına 3 YENİ koşu (tur52: eski v4-dönem satırının
  işçi/ortam kaydı yok → tekrar SAYILMAZ, yalnız tarihsel çapraz-kontrol); 30 × 1000 sn
  ≈ 8,4 sa (yol haritasındaki "2 sa" düşük tahmindi). Kayıt: durum/alt sınır/% aralık/
  gerçekleşen işçi/çözücü süresi her satırda; çözücü sürümü manifest'te; arıza kuralı +
  devam + ayrı denetim günlüğü. YAYILIM ANALİZİ ÖN-KAYDI: örnek başına 3 ham değer +
  min–maks + örneklem ss; durum sayımı ayrı; yayılım 0 ise dil "üç gözlem arasında fark
  gözlenmedi" ("deterministik" denmez). Duman (60 sn, 50×10): durum=Feasible, sınır=80,
  işçi=14 kaydedildi — CP'nin 14 iş parçacığı kullandığı İLK KEZ ölçülüp kayda girdi.
  SIRA: önce paket 6 (boş makine), sonra paket 7; eşzamanlı koşulmaz.
- 2026-10-19: PAKET 6 (İŞLEMCİ ADALETİ, v6) TAMAMLANDI — üç aşama, 80 koşu + 20 kaynak
  ölçümü, iki denetim günlüğünde 0 ihlal, ~5,9 sa. (1) EŞLİ TEK-ÇOK (v6↔v6, aynı örnek/
  tohum, 40 çift): ortalama fark −0,00% ±0,20 SE (p=0,99; 11 kötü/17 eşit/12 iyi) —
  üstünlüğün çok-çekirdekten gelmediğinin AYNI-SÜRÜM kanıtı (tur52 şartı karşılandı).
  800×30'da tek çekirdek −0,3% (daha iyi, çözülmemiş). (2) ARA KIYAS (SA v4 satırları;
  kilitli koşular nihai): büyük 30 örnekte 30/0/0, ort. marj %7,5; SA'nın en-iyi-üç
  tohumuna karşı 30/30 (eski sürümde 28/30 idi); küçük 10'da 9/1 (%1,6) — eski sürümde
  7/10 idi, makine-tarafı kuralının küçük-boyut iyileşmesiyle tutarlı. (3) KAYNAK (v6):
  HLBB ort. 8,7 çekirdek (3,96-12,81), metasezgiseller 1,01, CP 8,4-9,5. METİN: §5.2
  Processor time paragrafı eşli-kontrol diline güncellendi, makrolar yeniden üretildi
  (paper_stats._onecore tek-çok karşıtını niche_bench_multi_v6.csv'den okur — v4
  karışıklığı kapatıldı); derleme 0 hata. Veri: niche_bench_multi_v6.csv +
  niche_bench_1core.csv (+cpu/manifest/feaslog) + kaynak_olcumu.csv.
  SIRADA: paket 7 (CP tekrarları) — komut kullanıcıda, hazır.
- 2026-10-20: PAKET 7 (CP EK TEKRARLARI) TAMAMLANDI — 30/30 (10 örnek × 3 yeni koşu,
  1000 sn, işçi=Auto), 0 dışlanan, 0 ihlal, ~8,5 sa. ÖN-KAYITLI YAYILIM ANALİZİ:
  10 hücrenin 10'unda üç gözlem BİREBİR AYNI amaç değeri (maks−min = 0, ss = 0) —
  dil (ön-kayıt gereği): "bu örneklerde üç gözlem arasında amaç değeri farkı gözlenmedi"
  ("deterministik" DENMEZ). Tarihsel çapraz-kontrol (v4-dönem satırı, tekrar SAYILMAZ):
  8/10 hücrede aynı değer; 640×25/1 576→574 ve 800×30/2 552→551 (1-2 birim, ≤%0,35 —
  dönemler arası ortam farkı; oturum içi yayılım sıfırken mutlak determinizm iddiası
  kurulamaz, mevcut "tek koşu" pratiği desteklenir). DURUM SAYIMI: Optimal 0/30,
  Feasible 30/30 — CP 1000 sn'de HİÇBİR örnekte (50×10 dahil) optimallik kanıtı
  üretemedi; ort. optimallik aralığı %51-72 (ör. 800×30/2: sınır 152 vs makespan 551 —
  alt sınır çok gevşek). İŞÇİ: 30/30 koşuda 14 (makinenin tamamı) — adalet tablosuna
  rakip LEHİNE kayıt. METİN SONUÇLARI (kapanış metin paketine): "CP deterministik, bir
  kez" cümlesi ölçülen ifadeyle değiştirilir; "exact solver" dili "bu bütçede kanıt
  üretmiyor, durum/sınır kayıtlı" nüansıyla; CP modeli + ayarları ek bölüme (madde 11
  koşu tarafı KAPANDI). Veri: results/cp_tekrar.csv (+manifest/feaslog).
  SIRADA: PAKET 8 — NİHAİ KİLİT hazırlığı.
- 2026-10-20 (kilitli saf TASARIM turları, tur53-55; kilit HENÜZ ATILMADI): Kullanıcı
  sorularıyla tasarım genişledi ve sertleşti. KARARLAR: (tur53) eski 5 geliştirme boyutu
  yeniden KOŞULMAZ (sızıntı yeniden koşmakla temizlenmez); nihai saf tablo yalnız kilitli
  hücrelerden; HGA/GA tam 3 tekrar (kullanıcı şüphesine karşı GPT+Claude ortak: seçici-kıyas
  maddesinin en savunulur cevabı); rejim anlatısı SONUÇ değil ÖN-BEYANLI beklenti. (kullanıcı)
  CP bütçesi 1000 sn KALDI (cömert-bütçe anlatısının sürekliliği; eşit-200 alternatifi
  değerlendirildi-reddedildi diye kayıtlı). (tur54) 4 boyut kalır ("6 örnek yeterli güç"
  GEREKÇE OLARAK KULLANILMAZ); ÜÇÜNCÜ ARALIK 1-9 EKLENDİ — aynı 4 boyut, tüm yöntemler,
  ÖN-BEYANLI BETİMLEYİCİ kol (şiddet doz-örüntüsü ekseni; ~%10/%50/%100 beklenen oran;
  Holm ailesine girmez; "marj şiddetle büyür, 1-9'da küçülür/kaybolur" beklentisi önceden;
  küçülme mekanizmayla UYUMLU KANIT, kanıtlanmış mekanizma değil; 1-124 test edilmediği için
  "tüm şiddetlerde" genellemesi YOK). MATRİS: 72 örnek; HLBB/SA/HGA/GA×3 tekrar×200 sn +
  CP×1×1000 sn = 936 koşu ≈ 68 sa. (tur55 — bugünkü doğrulamalar: 12 hücre×10 ham dosya
  diskte; dokunulmamışlık grep'le (tek temas: "200×10" BİÇİMİ niş-üreteç eş-oran hücresinde —
  Vallada verisi DEĞİL; GPT: hücre KALIR, iddia daraltılır, ifşa metni verildi); aralıklar
  farklı işlem matrisli ("72 FARKLI örnek" denir, "bağımsız" üretim-prosedürü kanıtı olmadan
  denmez; eşli aralık kıyası yok); dönüştürücü 12 noktada değer-koruyarak doğrulandı;
  2009 yayımlı referans dosyası 1000 örneği kapsıyor → betimleyici referans kolonu EKLENİR
  ("2009 yayımlı referansa göre fark"; algoritmalara verilmez). GPT BAŞLATMA ŞARTLARI
  (tur56'da kod+manifest üzerinde kapanacak): (i) BİRİNCİL ANALİZ KATMANLI — 4 boyut sabit
  katman, eşit ağırlıklı ortalama fark, SE=√(Σs_h²/6)/4, Welch-Satterthwaite sd; düz 24-örnek
  eşli t ÖN-BEYANLI duyarlılık analizi (sonuca göre seçilmez); hedef dili "seçilmiş dört
  boyutun eşit ağırlıklı ortalaması". (ii) TEK aile m=8 (4 rakip × 2 aralık), çift yönlü,
  d=RPD(rakip)−RPD(HLBB) pozitif=HLBB lehine, tekil GA'lar düzeltmesiz + karar Holm p'de;
  0,5 pratik eşik AYRI raporlanır ("≥0,5 üstünlük doğrulandı" hipotezi KURULMAZ). (iii) ARIZA
  MATRİSİ: altyapı arızası→aynı kimlik/tohumla yeniden (tüm denemeler saklanır) / algoritma
  çökmesi→yöntem-başarısızlığı kaydı (örnek dışlanmaz, çift eşli analizden düşer, sayılar
  görünür) / bütçe-içi incumbent kuralı / geçersiz çözüm→başarısız. (iv) GA bütçe aşımı:
  ölçülen değer + fiilî süre + tbest kaydı; tbest>bütçe satırları ayrı sayılır (rakip lehine
  muhafazakâr). (v) KAYIT listesi: çözümün kendisi (atama+sıra) saklanır; ham/dönüşmüş veri
  hash; etkin parametreler (ENV istenen+okunan); kaynak/çıkış kodu; deneme geçmişi; CP'nin
  200. saniyedeki incumbent/sınırı (log yakalama, betimleyici). (vi) DUMAN BATARYASI:
  72 dosya yapısal ayrıştırma; bilinen-değerli sentetik denetleyici sınaması (bekleyen süreç
  işi burada kapanır); büyük-boyut kaynak testi; ZORLA kesme+devam testi (çoğaltma yok);
  tek-koşucu kilidi; görev listesi dosyaya yazılır, devamda yeniden üretilmez. (vii) BİTİŞ
  İŞARETİ doğrulama-temelli: 936 kimlik × kabul edilmiş durum × denetim geçişi sağlanmadan
  "kosu bitti" yazılmaz. RPD paydası birincil analizde AÇIKÇA beyan (koşu-içi en iyi;
  sonuca bağlı normalizasyon ifşası). Kayıtlar: tur53/54/55_soru+cevap_ham.md.

- 2026-10-22: KİLİTLİ SAF TEST TAMAMLANDI — 936/936 (~65,8 sa), bitiş doğrulaması GEÇTİ
  (936=sonuç∪başarısız, başarısız 0, çift 0, hepsi deneme=1, hepsi sıralı-denetimli,
  936/936 uygunluk kabul kapısından; bağımsız `dogrula` alt komutu da GEÇTİ). BİRİNCİL
  (ön-kayıt birebir; katmanlı Δ̂, Holm m=8): 8/8 doğrulayıcı hipotez HLBB lehine REDDEDİLDİ —
  S1-49: SA +1,21 [0,37;2,05] p_Holm=8,9e-03; HGA +12,10; GA +11,36; CP +9,80;
  S1-99: SA +2,63 [1,29;3,98] p_Holm=2,1e-03; HGA +16,86; GA +14,93; CP +13,17
  (hepsi RPD puanı, + = HLBB lehine; CI'lar düzeltmesiz). PRATİK EŞİK 0,5: nokta
  kestirimi 8/8 geçti; CI-alt-sınırıyla 7/8 (S1-49 SA alt sınır 0,37<0,5 — "pratik
  üstünlük istatistiksel gösterildi" S1-49 SA için DENMEZ; GPT tur57 şartı). DUYARLILIK
  (ön-beyanlı düz 24-örnek eşli t): HGA/GA/CP 6'sında p<2e-4 uyumlu; SA'da SAPMA —
  S1-49 p=0,101, S1-99 p=0,110 (boyut heterojenliği: 50×30'da SA önde, büyük oranlarda
  HLBB; eşit katman ağırlığı nedeniyle nokta kestirim iki analizde AYNI, belirsizlik
  farklı). DİL KURALI (tur57): "8/8" manşeti SA nitelemesiyle AYNI yerde verilir;
  "analiz seçimine dayanıklı üstünlük" iddiası SA için kurulamaz. BETİMLEYİCİLER:
  doz örüntüsü 4 rakipte de ön-beyanla uyumlu monoton (SA −4,5→+1,2→+2,6; HGA
  2,8→12,1→16,9; GA 3,4→11,4→14,9; CP 1,8→9,8→13,2) — "uyumlu kanıt" denir,
  "mekanizma doğrulandı" DENMEZ (nokta kestirim monotonluğu ayrıca sınanmış trend
  değil; oran n ve m ile karışık). S1-9 SA kaybı AÇIK yazılır: Δ̂=−4,51 [−5,21;−3,81],
  doğrulayıcı aile dışı; "incelenen düşük-şiddet örneklerinde eşit boyut-ağırlıklı
  ortalamada SA önde" denebilir, tüm düşük-şiddet hücrelerine GENELLENMEZ (150×30
  S1-9'da HLBB önde). Rejim ön-beyanı gerçekleşti: CP'nin 14 optimallik kanıtının
  14'ü 50×30 (oran 1,7); 50×30 S1-49/S1-99 hücrelerini SA/CP alıyor (ön-kabullü
  50×30 kaybı); oran ≥5 + şiddet ≥S1-49 hücrelerinin tamamında HLBB hücre-en-iyisi.
  2009 yayımlı referans (betimleyici): koşu en-iyisi 12/12 hücrede referans altında
  (−3,5 ile −27,8); HLBB tek başına 11/12 (istisna 200×10 S1-9 +11,6); "üstünlük"
  dili YOK (bütçe/donanım dönem farkı). CP: 14 Optimal / 58 Feasible, Feasible'da
  ort. gap %68 (gap = çözücü raporu, 100×(amaç−alt sınır)/amaç), işçi 14/14 koşu.
  AYRI SAYIMLAR: sirali=0 satır 0; zaman-aşımı kurtarması 0; deneme>1 satır 0;
  GA tbest raporlamıyor (−1, 216/216; aşım tespiti duvardan, tbest>bütçe 0).
  BÜTÇE AYRIMI (tur57 şartı): yapılandırılan stokastik 200 sn kapsül-içi arama
  bütçesi — gerçekleşen duvar maks 203,9 sn (fark ≤3,9 sn JIT/başlatma/GÇ; kabul
  gerekçesi: arama bütçe içinde, tbest>200 yok); CP 1000 sn, çözücü maks 1000,2 sn.
  SAĞLAMA: tüm istatistikler pandas/scipy'siz bağımsız ikinci kod yoluyla yeniden
  türetildi (csv+statistics+öz t-dağılımı) — 8 hipotezde Δ̂/SE/ν/p/Holm 6 anlamlı
  basamakta BİREBİR; GPT tur57 hücre ortalamalarından Δ̂'ları ayrıca yeniden üretti
  ("hesapta belirgin hata yok"). İDDİA SINIRLARI (tur57): "her boyutta üstün",
  "oran arttıkça nedensel iyileşme", "optimuma daha yakın", "2009 yönteminden kesin
  üstün" YAZILMAZ; RPD paydası koşu-içi en iyi ortalama (optimum DEĞİL) her tabloda
  beyanlı. VERİ: results/kilitli_saf.csv (+feaslog, denemeler, gorevler, manifest,
  KILIT, kilitli_saf_cozumler/cozumler.jsonl; CP günlükleri ~766M diskte, git dışı).
  ANALİZ: lit_gece/araclar/kilit_saf_analiz.py → kilitli_saf_sonuclar_2026-10-22.xlsx
  (7 sayfa; kullanıcıya teslim). Kayıtlar: tur57_soru.md + tur57_cevap_ham.md.
  SIRADA: kilitli NİŞ kilidi hazırlığı (EK-B koşusu), sonra kapanış metin paketi.

- 2026-10-22 (metin turu 2 — SAF; kullanıcı onayı "olur hazırla"; GPT tur58 liste + tur59 plan
  UYGULA + tur60 teslim onayı): Kilitli saf sonuçları makaleye işlendi. Kapsam: §4.1 (geliştirme/
  test ayrımı + kilit beyanı), §4.2 (izlere özgü ön-kayıtlı payda — eski global koşu-min tanım
  KALKTI; istatistik paragrafı izlere ayrıldı; CP cümlesi ölçülen-kapsamlı; duvar/yayılım makrodan),
  §4.3 (HGA/GA safta, yayımlı parametre), §5.1 KOMPLE (2009 betimleyici tek cümle; 8/8 Holm + SA
  çift nitelemesi aynı yerde; pratik eşik nokta 8/8 / CI-alt 7/8; rejim + doz betimleyici; Adan
  "qualitatively consistent"), §5.4 (statLow keşifsel/geliştirme etiketi, yeniden koşu YOK;
  oran≠şiddet ayrımı), özet/giriş/sonuç saf cümleleri, ek per-instance 72×5, bulunabilirlik.
  ÜRETİM: statKS* makroları paper_stats._kilitlisaf() (scipy.t; üçüncü bağımsız yol — 6 basamak
  birebir); tab_tracka_cells/conf + fig_regime (iki panel) gen_tracka_tables.py; ek tablo
  gen_appendix_tables.py (payda=en-iyi-ortalama); 2009 referansı results/ref2009_large.csv
  (ref2009_cevir.py). Eski statA*/track_a.csv makale zincirinden ÇIKTI. DENETİM: bölüm formu
  (ort. cümle 19,1; 34+ cümle 0; em dash 0; yeni metinde 1 "rather than" düzeltildi); derleme
  0 hata/0 undefined, 39 sayfa; çapraz süpürme (eski 50-örnek/5-boyut/Wilcoxon-A izleri 0; Track B
  ve tartışmadaki 2 bayat çapraz-iddia düzeltildi). TESLİM: makale_2026-10-22.zip +
  makale_fark_2026-10-22.pdf (latexdiff; PICTUREENV+=tikzpicture,longtable). NİŞ sayıları (Tablo
  3-6, tab_trackB, özet niş cümleleri, statB*) ESKİ koşudan — kilitli niş koşusu yenileyecek.
  Kayıtlar: tur58/59/60 soru+cevap_ham.md.

- 2026-10-22 (KİLİTLİ NİŞ tasarım genişletmesi — kullanıcı kararı + GPT tur61; kilit commit'i
  ve koşu HENÜZ YOK, hiçbir sonuç görülmeden): Kullanıcı EK-B kapsamını genişletti ("daha
  geniş veri daha doğru"): YENİ MATRİS = 8 standart boyut (50×10, 100×15, 150×15, 200×20,
  250×20, 400×20, 640×25, 800×30; τ=1-99) + 2 sınır hücresi (800×40, 400×80; τ=1-99) +
  DOZ EKSENİ (400×20 ve 800×30'da τ=1-9 ve τ=1-49) = 14 hücre × 6 yeni-tohum örnek =
  84 örnek; 4 sezgisel × 3 tohum × 200 sn + CP × 1000 sn = 1092 koşu; nominal seri bütçe
  ≈79 sa (takvim taahhüdü değil). TUR61 HÜKÜMLERİ: (1) DOĞRULAYICI AİLE DEĞİŞMEZ — m=8 =
  {400×20, 800×30} × 4 rakip, τ=1-99 (hedef iddia bu iki ölçek hücresinde; ortalama-üstünlük
  hücre-başarısızlığını örtebilir diye katmanlıya dönülMEdi); 6 ek boyut + sınır + doz
  hücrelerinin TAMAMI ön-beyanlı betimleyici ("sekiz boyut kapsamı ve ölçek eğrisini betimler;
  doğrulama önceden seçilmiş iki hücreye yöneliktir"). (2) Payda = beş yöntemin örnekteki en
  iyi TEKRAR-ORTALAMASI (saf tanımla aynı; CP yalnız geçerli çözümle girer, çözümsüzse "sonuç
  yok" + paydaya girmez; ham amaç farkları da saklanır; eski koşu-min Track B tablosuyla
  sayısal eğilim kıyası kurulmaz). (3) τ aralıkları arası EŞLEME YOK (bağımsız hücreler;
  hücre içinde yöntemler aynı örneklerde eşli; doz farkı "aynı örnekte şiddeti artırmanın
  etkisi" DİYE YORUMLANMAZ). (4) GA nesil-sonu aşımı ölçüldüğü gibi birincil skora girer;
  fiilî süre + aşım oranı + maks aşım raporlanır; dil "nominal 200 sn durdurma kuralı
  kıyası"; 200. sn incumbent'i donmuş kapsül koduna dokunmadan kaydedilemez → beyanlı sınır.
  (5) CP tam kapsam (14 hücre × 6), işçi politikası Auto + kayıt. (6) Güç kontrolü aile
  aynı kaldığı için taşınır; birincil test parametrik t-aralığı (işaret testi n=6'da Holm
  başlangıcını asla geçemez — ekb_guc_kontrolu kaydı); tekil CI'lar eşzamanlı güvence diye
  sunulmaz. (7) Koşucu saf mimari + EK: periyodik CSV yedeği, koşu-kimliği, ayrı hata
  günlüğü; sıra önceden karıştırılır; ara kontroller tamamlanma/süre/sağlıkla sınırlı;
  sonuçlara bakıp örnek ekleme/ayar değişikliği/erken durdurma YOK. Tohumlar kilit2026_*
  (geliştirmede kullanılan (parametre,tohum) çiftleriyle çakışmadığı üretimde doğrulanır).
  Kayıtlar: tur61_soru.md + tur61_cevap_ham.md. SIRADA: örnek üretimi + değer denetimi +
  koşucu uyarlaması + duman bataryası + GPT başlatma denetimi + NİHAİ KİLİT commit'i.

## EK-C: KİLİTLİ SAF TEST — NİHAİ ÖN-KAYIT (2026-10-20; tur53-56; GPT BAŞLATMA ONAYLI)
Bu bölüm kilit commit'iyle DONAR; koşu başladıktan sonra hiçbir madde değişmez.
1. VERİ: Vallada&Ruiz yayımlı büyük set; 4 boyut (50×30, 150×30, 100×10, 200×10) × 3 aralık
   (S1-9, S1-49, S1-99) × örnek 1-6 = 72 örnek. Ham + dönüşmüş sha256 listeleri
   valladapure_kilit/{HAM,JSON}_SHA256.txt; koşucu her başlatmada 144 hash'i YENİDEN
   hesaplayıp doğrular. Dönüşüm 72/72 TAM-değer doğrulamalı
   (lit_gece/araclar/kilit_saf_veri_denetimi.py; gözlenen işlem aralığı 1-100 — yayımlı
   dosya gerçeği, değerler aynen; hazırlıklar sınıf tanımına tam uygun). İFŞA: "200×10"
   BİÇİMİ geliştirmede yalnız kendi niş-üretecimizin örnekleriyle incelendi (Vallada
   dosyaları değil); "tamamen görülmemiş biçim" iddiası kurulmaz. "72 FARKLI örnek" denir;
   aralıklar arası eşli kıyas yok.
2. KOŞU: HLBB/SA/HGA/GA × tohum {0,1,2} × 200 sn + CP × 1 × 1000 sn = 936 koşu.
   Saf rejim: yayımlı parametreler (HGA_DINS/GA_PM ortamdan SİLİNİR — Julia-içi okunuş
   dumanla kanıtlı), DELTAINS_FIX=1 herkeste, Julia -t 1. CP bütçe gerekçesi: yayımlı
   tablonun "cömert bütçe" sürekliliği (eşit-200 değerlendirildi-reddedildi, tur53).
   Koşucu: kilitli_saf_run.py (kabul kapısı = ortak denetim dönüşü; arıza matrisi
   altyapı/yöntem ayrımıyla; görev listesi dosyada; flock + artık-süreç taraması;
   hesap/kayıt fazları ayrık, kayıt hatası algoritmayı yeniden koşturmaz; zaman-aşımında
   kısmi çıktı yalnız denetimden geçerse kabul; bitiş işareti doğrulama-temelli:
   çift-yok + 936=sonuç∪başarısız + sonuç↔denetim↔saklanmış-çözüm bire bir).
3. BİRİNCİL ANALİZ (doğrulayıcı): birim örnek; tekrarlar örnek içinde ortalanır
   (başarısız tekrar: ortalama başarılı tekrarlardan, sayısı raporda; 3'ten ≥2 başarısızsa
   çift başarısız). d = RPD(rakip) − RPD(HLBB), + = HLBB lehine; RPD paydası = örnekte bu
   koşudaki beş yöntemin en iyi ortalaması (sonuca bağlı normalizasyon — açıkça beyan).
   KATMANLI kestirim: Δ̂ = (1/4)Σ_h d̄_h; SE = (1/4)·√(Σ_h s_h²/n_h); ν Welch–Satterthwaite
   = (Σ s_h²/n_h)² / Σ (s_h²/n_h)²/(n_h−1); çift yönlü. n_h<2 olan hipotez doğrulayıcı
   sonuç ÜRETMEZ; Holm ailesi m=8 KALIR (üretilmeyen = reddedilmemiş). TEK aile m=8:
   {SA,HGA,GA,CP} × {S1-49,S1-99}; karar Holm p; tekil %95 aralıklar "düzeltmesiz"
   etiketiyle. Pratik eşik 0,5 RPD puanı AYRI raporlanır ("≥0,5 doğrulandı" hipotezi yok).
   Düz 24-örnek eşli t = ÖN-BEYANLI duyarlılık analizi (sonuca göre seçilmez).
   Hedef dili: "seçilmiş dört boyutun eşit ağırlıklı ortalaması" (ızgara/orana genelleme yok).
4. BETİMLEYİCİLER (hüküm dili yok): S1-9 kolu tamamen betimleyici; ön-beyan: marj hazırlık
   şiddetiyle büyür, S1-9'da küçülür/kaybolur ("aralıklar boyunca betimleyici örüntü";
   monotonluk şartı yok; küçülme mekanizmayla UYUMLU kanıt). Rejim ön-beyanı: düşük oranda
   CP/SA rekabetçi, yüksek oranda HLBB; görünmezse "beklenen örüntü desteklenmedi" yazılır.
   2009 yayımlı referans kolonu: "veri setinin 2009 yayımlı referansına göre fark (%)";
   negatifler korunur; algoritmalara hedef/başlangıç olarak VERİLMEDİ; "güncel en iyi" veya
   "optimum" DENMEZ. Hücre(boyut)-düzeyi satırlar betimleyici. Boyut başına kayıp/kazanç
   saklanmaz (50×30 kaybı olasılığı önceden kabul). sirali=0 satırlar, zaman-aşımından
   kurtarılanlar ve başarısızlık sayıları raporda AYRI görünür.
5. SINAMA KAYDI (hepsi geçti, 2026-10-20): 72/72 veri; uçtan uca duman 5 yöntem; SIGKILL
   kesme+devam (çift=0); bozuk-çözüm denetleyici sınaması 4/4; etkin-ENV kanıtı; en büyük
   hücre sondası 5/5; T1 denetim-dosyası-yok→bitiş reddi; T2 flock; T3 çift-satır tespiti;
   T4a sahte-iddialı kısmi çıktı→denetim kapısı; T4b çıktısız zaman-aşımı→başarısızlık;
   T6 kayıt-hatası→koşucu durur. GPT tur56b: BAŞLATMA ONAYI (bildirilen kanıtlara dayalı;
   nihai kabul bitiş doğrulamasına bağlı). Kayıtlar: tur56_soru.md + tur56_cevap_ham.md
   + tur56b (soru2/cevap2).

## EK-D: KİLİTLİ NİŞ TEST — NİHAİ ÖN-KAYIT (2026-10-22; tur61-62; GPT BAŞLATMA ONAYLI)
Bu bölüm kilit commit'iyle DONAR; koşu başladıktan sonra hiçbir madde değişmez.
1. VERİ: kendi üretecimiz (niche_generator.py; işlem U[1,99] + hazırlık U[1,τ] Vallada şeması,
   uygunluk 0,5 rastgele Moser/Ekici, hazır-zaman U[0, 0.2·(n/m)·p̄]); 14 hücre × 6 YENİ-tohum
   örnek = 84 (tohumlar kilit2026_{n}x{m}_t{tau}_{i}; 49 geliştirme tohumuyla çakışmaz,
   üretimde doğrulandı). Hücreler: 8 standart boyut (50_10, 100_15, 150_15, 200_20, 250_20,
   400_20, 640_25, 800_30; t99) + 2 sınır (800_40, 400_80; t99) + doz (400_20, 800_30 ×
   t9, t49). Kimlik: nis_kilit2026/manifest.json + 168 SHA-256 (84 JSON + 84 nbin) —
   koşucu her başlatmada yeniden hesaplar. Doğrulama 84/84: yapısal + (parametre,tohum)dan
   BAYT-BAYT yeniden-üretim + ikili-köprü eşdeğerliği (kilit_nis_veri_denetimi.py).
2. KOŞU: HLBB/SA/HGA/GA × tohum {0,1,2} × 200 sn + CP × 1 × 1000 sn = 1092 koşu; nominal
   ~80 sa (takvim taahhüdü değil). NİŞ REJİMİ (EK-A): DELTAINS_FIX=1 + HGA_DINS=0.9 +
   GA_PM=0.3 (etkin-ENV kanıtı: HGA.jl:690, GA.jl:550, DELTAINS_FIX her ikisinde; EK-A
   sürücü-başına dinamik kanıt); Julia -t 1; CP işçi Auto + kayıt. Koşucu kilitli_nis_run.py
   (sha 9d8daa9a6a294070): saf koşucu mimarisi aynen (kabul kapısı, arıza matrisi, faz
   ayrımı, flock+artık-süreç, hash kapısı, doğrulama-temelli bitiş) + tur61 ekleri
   (koşu-kimliği; her 25 kabul edilen sonuçta yedek results/kilitli_nis_yedek/; CP
   çözümsüzse başarısızlık kaydı + "sonuç yok" raporu). Kapsül .nbin köprüsü (run_one.jl
   niş modu); HLBB/CP/denetçi JSON (compatibility=True, workload=True).
3. BİRİNCİL ANALİZ (doğrulayıcı; tur61 ile SABİT): aile m=8 = {400_20, 800_30} × {SA, HGA,
   GA, CP}, YALNIZ t99; DEĞİŞMEZ. Birim örnek; tekrarlar örnek içinde ortalanır; d =
   RPD(rakip) − RPD(HLBB), + = HLBB lehine; payda = beş yöntemin örnekteki en iyi
   TEKRAR-ORTALAMASI (saf tanımla aynı; CP yalnız geçerli çözümle girer, çözümsüz CP
   paydaya girmez ve "sonuç yok" sayılır); eşli fark + t-aralığı, tek Holm ailesi m=8,
   çift yönlü; güç kontrolü EK-B'den taşınır (aile ve test aynı; işaret testi n=6'da Holm
   başlangıcını geçemez — birincil test parametrik t). HAM amaç farkları da saklanır.
   1092 ANAHTARIN TAMAMI MUHASEBE EDİLİR: sonuç/başarısızlık sayıları yöntem × hücre
   bazında raporlanır; başarısız tekrar ortalamadan düşer (3'ten ≥2 başarısızsa çift
   başarısız, eksik-sonuç kuralı); "bitiş doğrulandı" ≠ "1092 başarılı çözüm".
4. BETİMLEYİCİLER (hüküm dili yok): 6 küçük/orta boyut + 2 sınır hücresi + 4 doz hücresi
   TAMAMEN betimleyici ("sekiz boyut kapsamı ve ölçek eğrisini betimler; doğrulama önceden
   seçilmiş iki hücreye yöneliktir"). Ön-beyan (SA'ya karşı, geliştirme verisine dayalı):
   800_40 pozitif/değişken, 400_80 küçük negatif; uymayan sonuç da raporlanır. Doz hücreleri
   aralıklar-arası EŞLEMESİZ; "aynı örnekte şiddeti artırmanın etkisi" DENMEZ. Kapsam dili:
   "m≤30 doğrulanmış bölge" DENMEZ. GA aşımı: ölçülen değer birincil skora girer; fiilî
   süre + aşım oranı + maks aşım raporlanır; dil "nominal 200 sn durdurma kuralı kıyası" —
   kapsülün son çözümü 200. sn incumbent'i DEĞİLDİR, "eşit 200 sn'de kalite" iddiası
   kurulamaz; GA tbest=-1 eksik bilgi olarak beyanlı. Eski koşu-min paydalı Track B
   tablosuyla sayısal eğilim kıyası kurulmaz.
5. SINAMA KAYDI (hepsi 2026-10-22, kilit öncesi; sonrasında tasarım/ayar DEĞİŞMEDİ):
   duman 5 yöntem uçtan uca (50_10/t99, 25/40 sn; 5/5, doğrulama 0 sorun); bozuk-çözüm
   denetleyici 4/4 (temiz True; eksik-iş/uygunsuz-makine/sahte-iddia False); doğrulama
   kapısı 5/5 (çift satır, silinmiş denetim, değiştirilmiş iddia, silinmiş çözüm → bitiş
   reddi); flock reddi; kayıt-hatası → koşucu durdu; SIGKILL+devam (2 var → 3 kalan →
   5/5, çift 0); büyük-hücre sondası 60 sn (800_40: HLBB 470 sıralı / SA 387 / CP Feasible
   sınır 109 işçi 14; 400_80: 102 / 89 / CP Feasible sınır 39; hepsi kabul kapısından;
   sonda ölçüm değildir, sınır-hücre ön-beyanıyla uyumlu yönde görüldü — beyan edildi).
   TEK-NOKTA RİSKİ (tur62): yedek klasörü aynı diskte; disk kaybına karşı kullanıcıya
   başka diske/makineye periyodik kopya önerildi (başlatma engeli değil).
   GPT tur62: BAŞLATMA ONAYI (bildirilen kanıtlara dayalı; nihai kabul bitiş
   doğrulamasına bağlı). Kayıtlar: tur62_soru.md + tur62_cevap_ham.md.

- 2026-10-22 (tur63, KOŞU BAŞLAMADAN, hiçbir sonuç görülmeden): Kullanıcı sorusu — doz
  ekseninin yalnız iki boyutta olması makalede asimetri/seçici-ölçüm izlenimi yaratır mı?
  GPT hükmü: (d) MATRİS DEĞİŞMEZ; görsel asimetri yöntem kusuru değil; gerçek sınır "doz
  nişte yalnız iki boyutta ölçüldü → bütün boyutlara genellenemez" ve bu İDDİA KAPSAMI
  olarak yazılır. Tam genişleme (+67 sa) gerekli değil; orta yol (+22 sa) yalnız küçük/orta
  boyut doz davranışı ayrı bilimsel hedefse. SUNUM (kapanış metin paketine): Track B ana
  tablosu 1-99'daki 10 hücre; doz AYRI küçük tabloda (iki boyut × ÜÇ aralık, 1-99 hücreleri
  referans olarak dahil; başlık "iki seçili boyutta betimleyici doz kontrolü"); §4.1'de
  hedefli seçim + maliyet + genelleme sınırı. m=8 ailesi her durumda değişmez.
  Kayıtlar: tur63_soru.md + tur63_cevap_ham.md.

## KİLİTLİ NİŞ TEST TAMAMLANDI (2026-10-26; paket 10 kapanış kaydı)
- BİTİŞ: 1092/1092 kabul, 0 başarısızlık; anahtar kümesi beklenen kümeyle birebir
  (analiz betiği bağımsız doğruladı); koşucu doğrulama-temelli bitişi geçti.
- DENETÇİ: 1092/1092 çözüm ortak denetçiden geçti (kapsama/uygunluk/sıra/rota OK);
  sahte iddia 0; denetçinin LKH yeniden-rotalaması 453 koşuda iddiadan iyi rota buldu
  (ihlal değil: rakip sıraları LKH-altı; puanlama beyan edilen doğrulanmış değerle).
- DOĞRULAYICI (m=8, EK-D birebir; betik lit_gece/araclar/kilit_nis_analiz.py):
  8/8 HLBB lehine, tüm Holm p < 2.1e-4, tüm karşılaştırmalar 6/0/0.
  400_20/t99: SA +8.98 [7.85,10.10], HGA +16.95, GA +16.06, CP +20.74;
  800_30/t99: SA +14.01 [10.27,17.75], HGA +24.87, GA +23.65, CP +19.55.
  Ham makespan farkları +38.5 … +114.8 birim.
- BETİMLEYİCİLER: 8 standart boyut (t99) 48/48 örnekte HLBB en iyi tekrar-ortalaması;
  SA ikinciliği boyutla 2.9→14.0 RPD açılıyor. DOZ (eşlemesiz): t9'da SA önde
  (400_20: HLBB +10.9; 800_30: +1.6), t49 ve t99'da HLBB önde — şiddet ekseni saf
  testle aynı yönde. SINIR ön-beyan: 800_40 SA−HLBB = +1.8 (beyan "pozitif/değişken" ✓);
  400_80 = −13.1 (beyan "küçük negatif": YÖN ✓, BÜYÜKLÜK beyandan büyük — aynen raporlanır).
- CP: 84/84 geçerli çözüm; tek optimallik kanıtı 50_10/t99 i5; kalan 83 Feasible.
- SÜRELER: HLBB duvar maks 198.4 sn (bütçe içi); SA/HGA maks 204.8; GA maks 265.2
  (nominal 200 sn durdurma-kuralı kıyası dili; GA tbest=-1 eksik-bilgi beyanı).
- ÇIKTI: kilitli_nis_sonuclar_2026-10-26.xlsx (9 sayfa). Metin paketi ayrı adım.
