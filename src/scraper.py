import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import os
import random
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from concurrent.futures import ThreadPoolExecutor, as_completed
import re
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Loglama ayarları
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

BASE_URL = "https://www.arabam.com/ikinci-el/otomobil?sort=price.asc&take=50&page={page}"
FILTER_URL = "https://www.arabam.com/ikinci-el?sort=price.asc&take=50"

def setup_selenium_driver():
    """Selenium WebDriver'ı başlatır."""
    options = Options()
    options.add_argument("--headless=True")  # Hız için headless mode
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver

def setup_session():
    """Retry mekanizmalı requests session oluşturur."""
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Connection": "keep-alive",
    }
    session.headers.update(headers)
    retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

def fetch_detail_page(session, url, current_page, current_index, processed_urls):
    """Detay sayfasını çeker ve verileri ayrıştırır."""
    if url in processed_urls:
        logging.info(f"[{current_page}. Sayfa] - {current_index + 1}. ilan zaten işlendi: {url}")
        return None
    processed_urls.add(url)
    logging.info(f"[{current_page}. Sayfa] - {current_index + 1}. ilan çekiliyor: {url}")
    try:
        response = session.get(url, timeout=15)
        response.raise_for_status()
        detail_soup = BeautifulSoup(response.text, 'html.parser')

        data = {}
        try:
            ilan_no_text_url = url.split("/")[-1].split("?")[0].strip()
            ilan_no_match_url = re.match(r'^(\d+)', ilan_no_text_url)
            ilan_no_from_url = ilan_no_match_url.group(1) if ilan_no_match_url else None
        except Exception as e:
            logging.warning(f"[{current_page}. Sayfa] - {current_index + 1}. ilan: URL'den İlan No çıkarılamadı: {e}")
            ilan_no_from_url = None

        try:
            props_container = detail_soup.select_one(".product-properties-details.linear-gradient")
            if props_container:
                keys = props_container.select(".property-key")
                values = props_container.select(".property-value")
                if len(keys) != len(values):
                    logging.warning(f"[{current_page}. Sayfa] - {current_index + 1}. ilan: Anahtar ve değer sayıları uyuşmuyor.")
                for k, v in zip(keys, values):
                    key = k.text.strip()
                    value = v.text.strip()
                    if value:
                        value = re.sub(r'\s+', ' ', value).strip()
                    if key == "İlan No":
                        ilan_no_match_html = re.match(r'^(\d+)', value)
                        data[key] = ilan_no_match_html.group(1) if ilan_no_match_html else pd.NA
                    else:
                        data[key] = value if value else pd.NA
            else:
                logging.warning(f"[{current_page}. Sayfa] - {current_index + 1}. ilan: Özellik konteyneri bulunamadı.")
            if "İlan No" not in data or data["İlan No"] is pd.NA and ilan_no_from_url:
                data["İlan No"] = ilan_no_from_url
        except Exception as e:
            logging.error(f"[{current_page}. Sayfa] - {current_index + 1}. ilan: Özellikler çıkarılırken hata: {e}")
            data["İlan No"] = ilan_no_from_url if ilan_no_from_url else pd.NA

        try:
            price_elem = detail_soup.select_one(".classified-detail-price, .price, .banner-price, .desktop-information-price")
            if price_elem:
                price_text = price_elem.text.strip()
                price_text = re.sub(r'[^\d]', '', price_text)
                data["Fiyat"] = price_text if price_text else pd.NA
            else:
                data["Fiyat"] = pd.NA
        except Exception as e:
            logging.warning(f"[{current_page}. Sayfa] - {current_index + 1}. ilan: Fiyat çıkarılamadı: {e}")
            data["Fiyat"] = pd.NA

        try:
            description = detail_soup.select_one(".tab-content-wrapper.tab-description")
            if description:
                description_text = description.text.strip()
                description_text = re.sub(r'\s+', ' ', description_text).strip()
                data["Açıklama"] = description_text if description_text else pd.NA
            else:
                description_alt = detail_soup.select_one(".classified-description, .description")
                data["Açıklama"] = re.sub(r'\s+', ' ', description_alt.text.strip()).strip() if description_alt else pd.NA
        except Exception as e:
            logging.warning(f"[{current_page}. Sayfa] - {current_index + 1}. ilan: Açıklama çıkarılamadı: {e}")
            data["Açıklama"] = pd.NA

        return data
    except requests.exceptions.RequestException as e:
        logging.error(f"[{current_page}. Sayfa] - {current_index + 1}. ilan: Detay sayfası çekilemedi: {e}")
        return None
    except Exception as e:
        logging.error(f"[{current_page}. Sayfa] - {current_index + 1}. ilan: İlan işlenirken genel hata: {e}")
        return None

def save_intermediate_data(data, page, file_path="data/deneme/cars_scraped_intermediate.csv"):
    """Ara verileri diske kaydeder."""
    if data:
        df = pd.DataFrame(data)
        if not df.empty and not df.columns.empty:
            preferred_columns = ["İlan No", "Fiyat", "İlan Tarihi", "Marka", "Seri", "Model", "Yıl", "Kilometre", "Açıklama"]
            other_columns = [col for col in df.columns if col not in preferred_columns]
            final_columns = preferred_columns + other_columns
            df = df.reindex(columns=[col for col in final_columns if col in df])
            mode = 'a' if os.path.exists(file_path) else 'w'
            df.to_csv(file_path, index=False, encoding="utf-8-sig", mode=mode, header=not os.path.exists(file_path))
            logging.info(f"[{page}. Sayfa]: Ara veriler '{file_path}' dosyasına kaydedildi. Toplam {len(df)} ilan.")

def scrape_listings_with_filter(max_pages=50, max_workers=10):
    os.makedirs("data/deneme", exist_ok=True)
    all_data = []
    processed_urls = set()  # Aynı URL'lerin tekrar işlenmesini önlemek için
    min_price = 10000  # İlk minimum fiyat 100 TL
    total_count = 0

    session = setup_session()
    driver = setup_selenium_driver()
    try:
        while True:
            logging.info(f"Minimum fiyat {min_price} TL ile ilanlar çekiliyor...")
            driver.get(FILTER_URL)
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder='Min TL']")))

            # Çerez popup kapatma
            try:
                logging.info("Çerez popup kontrol ediliyor...")
                cookie_button = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, '//button[contains(text(), "Kabul Et")]'))
                )
                driver.execute_script("arguments[0].click();", cookie_button)
                logging.info("Çerez popup kapatıldı.")
                time.sleep(0.5)  # Bekleme süresi azaltıldı
            except:
                logging.info("Çerez popup bulunamadı veya zaten kapalı.")

            # Filtre formunu aç
            try:
                logging.info("Filtre formu açılıyor...")
                facet_button = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "facet-button.closed"))
                )
                driver.execute_script("arguments[0].click();", facet_button)
                logging.info("Filtre formu açıldı.")
                time.sleep(0.5)  # Bekleme süresi azaltıldı
            except Exception as e:
                logging.error(f"Filtre formu açılamadı: {e}")

            # Minimum fiyatı gir
            try:
                logging.info(f"Min TL alanına {min_price} yazılıyor...")
                min_price_input = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "input[placeholder='Min TL'][maxlength='9']"))
                )
                driver.execute_script("arguments[0].scrollIntoView(true);", min_price_input)
                min_price_input.clear()
                min_price_input.send_keys(str(min_price))
                logging.info(f"Minimum fiyat olarak {min_price} TL girildi.")
                time.sleep(0.5)  # Bekleme süresi azaltıldı
            except Exception as e:
                logging.error(f"Min TL alanına yazılırken hata: {e}")
                break

            # Arama butonuna tıkla
            try:
                logging.info("Arama butonuna tıklanıyor...")
                search_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn.btn-search"))
                )
                driver.execute_script("arguments[0].click();", search_button)
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".listing-list-item"))
                )
                logging.info("Arama yapıldı, sonuçlar yüklendi.")
                time.sleep(1)  # Bekleme süresi azaltıldı
            except Exception as e:
                logging.error(f"Arama butonuna tıklanırken hata: {e}")
                break

            page = 1
            page_data = []
            while page <= max_pages:
                url = f"{driver.current_url}&page={page}"
                logging.info(f"[{page}. Sayfa] Ana liste sayfası çekiliyor (Min fiyat: {min_price} TL)...")
                try:
                    response = session.get(url, timeout=15)
                    response.raise_for_status()
                    soup = BeautifulSoup(response.text, 'html.parser')
                except requests.exceptions.RequestException as e:
                    logging.error(f"[{page}. Sayfa]: Ana liste sayfası çekilemedi: {e}")
                    save_intermediate_data(page_data, page)
                    break

                listing_urls = []
                listing_elements = soup.select(".listing-list-item")
                if not listing_elements:
                    logging.info(f"[{page}. Sayfa]: İlan bulunamadı, döngüden çıkılıyor.")
                    save_intermediate_data(page_data, page)
                    break

                for listing in listing_elements:
                    link_elem = listing.select_one("a")
                    if link_elem and "href" in link_elem.attrs:
                        link = link_elem["href"]
                        if not link.startswith("http"):
                            link = "https://www.arabam.com" + link
                        listing_urls.append((link, page, total_count))
                        total_count += 1

                logging.info(f"[{page}. Sayfa]: {len(listing_urls)} adet ilan linki bulundu. Toplamda {total_count} ilan...")

                # Paralel olarak detay sayfalarını çek
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    future_to_url = {executor.submit(fetch_detail_page, session, url, page, idx, processed_urls): url for url, page, idx in listing_urls}
                    for future in as_completed(future_to_url):
                        data = future.result()
                        if data:
                            page_data.append(data)

                # Her sayfa sonunda ara kaydetme
                save_intermediate_data(page_data, page)
                all_data.extend(page_data)
                page_data = []  # Hafızayı temizle

                # Sonraki sayfaya geçmeden önce bekle
                time.sleep(random.uniform(1, 3))  # Bekleme süresi optimize edildi
                page += 1

            # Bu döngüde toplanan verilerden en yüksek fiyatı bul
            if all_data:
                df_temp = pd.DataFrame(all_data)
                if "Fiyat" in df_temp.columns:
                    df_temp["Fiyat"] = pd.to_numeric(df_temp["Fiyat"], errors="coerce")
                    max_price = df_temp["Fiyat"].max()
                    if pd.isna(max_price):
                        logging.warning("Fiyatlar arasında geçerli bir maksimum bulunamadı, döngüden çıkılıyor.")
                        break
                    min_price = int(max_price) + 1  # Yeni minimum fiyat
                    logging.info(f"Yeni minimum fiyat: {min_price} TL")
                else:
                    logging.warning("Fiyat sütunu bulunamadı, döngüden çıkılıyor.")
                    break
            else:
                logging.info("Hiç veri çekilemedi, döngüden çıkılıyor.")
                break

            # Tüm veriler bittiyse çık
            if not listing_urls:
                logging.info("Tüm ilanlar çekildi, döngü tamamlandı.")
                break

        # Final verileri kaydet
        if all_data:
            df = pd.DataFrame(all_data)
            if not df.empty and not df.columns.empty:
                preferred_columns = ["İlan No", "Fiyat", "İlan Tarihi", "Marka", "Seri", "Model", "Yıl", "Kilometre", "Açıklama"]
                other_columns = [col for col in df.columns if col not in preferred_columns]
                final_columns = preferred_columns + other_columns
                df = df.reindex(columns=[col for col in final_columns if col in df])
                file_path = "data/deneme/cars_scraped_final.csv"
                df.to_csv(file_path, index=False, encoding="utf-8-sig")
                logging.info(f"Toplam {len(df)} ilan çekildi ve '{file_path}' dosyasına kaydedildi. Bulunan özellikler: {list(df.columns)}")
            else:
                logging.warning("Hiç veri çekilemedi. Final CSV dosyası oluşturulmadı.")
        else:
            logging.warning("Hiç veri çekilemedi. Final CSV dosyası oluşturulmadı.")

    except Exception as e:
        logging.error(f"Genel hata oluştu: {e}")
        save_intermediate_data(all_data, "final")
    finally:
        driver.quit()

if __name__ == "__main__":
    scrape_listings_with_filter(max_pages=50, max_workers=10)