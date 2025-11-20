import os
import json
import re
import time
import threading
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_url_path='', static_folder='.')

DATA_FILE = "kargolar.json"
EMAIL = "celb01tr@gratis.com.tr"
PASSWORD = "felil46-*"

def load_kargos():
    """Mevcut kargolları yükle"""
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []

def save_kargos(kargos):
    """Kargolları JSON dosyasına kaydet"""
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(kargos, f, ensure_ascii=False, indent=4)

def extract_tracking_number(text):
    """Metinden kargo numarasını çıkar"""
    # UPS formatı
    ups_match = re.search(r'1[Zz][0-9A-Za-z]{14,20}', text, re.IGNORECASE)
    if ups_match:
        return ups_match.group(0)
    
    # UPS formatı - başında 1 olmadan (Z ile başlayan) - 1 ekle
    ups_no_1_match = re.search(r'[Zz][0-9A-Za-z]{14,20}', text)
    if ups_no_1_match:
        tracking = ups_no_1_match.group(0)
        if tracking.upper().startswith('Z') and len(tracking) >= 15:
            return f"1{tracking}"  # Başına 1 ekle
    
    # Aras Kargo
    aras_match = re.search(r'[A-Z]{2}\d{9}', text)
    if aras_match:
        return aras_match.group(0)
    
    # Yurtiçi Kargo
    yurtici_match = re.search(r'\d{13}', text)
    if yurtici_match:
        return yurtici_match.group(0)
    
    # MNG Kargo
    mng_match = re.search(r'MNG\d{10}', text)
    if mng_match:
        return mng_match.group(0)
    
    return ""

def extract_and_save_data(driver, wait):
    """Inbox'tan kargo verilerini çek ve kaydet"""
    
    try:
        # Toplam öğe sayısını al
        total_items = 0
        try:
            total_element = wait.until(EC.presence_of_element_located((By.ID, "view_counter")))
            total_text = total_element.text.strip()
            # "123 öğe" formatından sayı çıkar
            total_match = re.search(r'\d+', total_text)
            if total_match:
                total_items = int(total_match.group(0))
                logger.info(f"📊 Toplam {total_items} öğe bulundu")
        except Exception as e:
            logger.warning(f"⚠️ Toplam öğe sayısı alınamadı: {e}")
            total_items = 1000  # Default
        
        # Mevcut kargolları yükle
        existing_kargos = load_kargos()
        existing_tracking = {k.get('TrackingNumber') for k in existing_kargos}
        
        # Scroll container
        scroll_container = wait.until(EC.presence_of_element_located((By.ID, "view_list_container")))
        
        processed_taleps = set()
        new_kargos = []
        scroll_iterations = 0
        no_progress_count = 0
        
        while len(processed_taleps) < total_items and scroll_iterations < 100:
            scroll_iterations += 1
            logger.info(f"🔄 Scroll Iteration #{scroll_iterations} (İşlenen: {len(processed_taleps)}/{total_items})")
            
            # Mevcut talepleri al
            try:
                talep_elements = driver.find_elements(By.CSS_SELECTOR, "div.grid-row")
                logger.info(f"   Bulunmuş talep sayısı: {len(talep_elements)}")
            except:
                logger.error("   Talep elementleri bulunamadı")
                break
            
            processed_in_iteration = 0
            
            for talep in talep_elements:
                try:
                    # Talep ID'sini al
                    talep_id = ""
                    try:
                        id_element = talep.find_element(By.CSS_SELECTOR, "div.cell-path")
                        id_text = id_element.text.strip()
                        id_match = re.search(r'\d+', id_text)
                        if id_match:
                            talep_id = id_match.group(0)
                    except:
                        continue
                    
                    if talep_id in processed_taleps:
                        continue
                    
                    # Konu al
                    konu = ""
                    try:
                        subject_element = talep.find_element(By.CSS_SELECTOR, "div.cell-subject span")
                        konu = subject_element.get_attribute("title") or subject_element.text.strip()
                    except:
                        try:
                            subject_element = talep.find_element(By.CSS_SELECTOR, "div.cell-subject")
                            konu = subject_element.text.strip()
                        except:
                            konu = ""
                    
                    # Mağaza al
                    magaza_id = ""
                    try:
                        requester_element = talep.find_element(By.CSS_SELECTOR, "div.cell-requester span")
                        magaza_id = requester_element.get_attribute("title") or requester_element.text.strip()
                        # "- Gratis" kısmını sil
                        if " - " in magaza_id:
                            magaza_id = magaza_id.split(" - ")[0].strip()
                    except:
                        magaza_id = ""
                    
                    logger.info(f"   📌 Talep {talep_id}: {konu}")
                    
                    # Talebe tıkla
                    try:
                        talep.click()
                        time.sleep(0.75)
                    except:
                        processed_taleps.add(talep_id)
                        processed_in_iteration += 1
                        continue
                    
                    # Detay sayfasının yüklenmesini bekle
                    try:
                        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "header_bar_inner")))
                        logger.info(f"      ✅ Detay sayfası yüklendi")
                    except:
                        logger.warning(f"      ❌ Detay sayfası yüklenemedi")
                        processed_taleps.add(talep_id)
                        processed_in_iteration += 1
                        try:
                            driver.back()
                            time.sleep(1)
                        except:
                            pass
                        continue
                    
                    # Notlardan kargo numarası çıkar
                    tracking_number = ""
                    try:
                        notes_elements = driver.find_elements(By.CSS_SELECTOR, "li div.note")
                        logger.info(f"      Found {len(notes_elements)} notes")
                        
                        for i, note in enumerate(notes_elements):
                            try:
                                note_text = note.text or ""
                                if note_text:
                                    found_tracking = extract_tracking_number(note_text)
                                    if found_tracking:
                                        tracking_number = found_tracking
                                        logger.info(f"      📦 Kargo bulundu: {tracking_number}")
                            except:
                                continue
                    except Exception as e:
                        logger.warning(f"      ⚠️ Notlar alınamadı: {e}")
                    
                    # Kargo ekle
                    if tracking_number and tracking_number not in existing_tracking:
                        kargo = {
                            "TrackingNumber": tracking_number,
                            "StoreId": magaza_id,
                            "RequestId": talep_id,
                            "RequestSubject": konu,
                            "Status": "Beklemede",
                            "EstimatedDelivery": "-",
                            "LastUpdated": datetime.now().isoformat()
                        }
                        new_kargos.append(kargo)
                        existing_tracking.add(tracking_number)
                        logger.info(f"      ✅ KARGO EKLENDİ: {tracking_number}")
                    elif not tracking_number and talep_id and talep_id not in existing_tracking:
                        # Kargo numarası bulunamazsa, talep ID'yi takip numarası olarak kullan
                        kargo = {
                            "TrackingNumber": f"TALEP-{talep_id}",
                            "StoreId": magaza_id,
                            "RequestId": talep_id,
                            "RequestSubject": konu,
                            "Status": "Beklemede",
                            "EstimatedDelivery": "-",
                            "LastUpdated": datetime.now().isoformat()
                        }
                        new_kargos.append(kargo)
                        existing_tracking.add(f"TALEP-{talep_id}")
                        logger.info(f"      ⚠️  KARGO NUMARASI BULUNAMADI, TALEP ID KULLANILDI: TALEP-{talep_id}")
                    
                    # Geri dön
                    try:
                        driver.back()
                        time.sleep(0.5)
                    except:
                        pass
                    
                    processed_taleps.add(talep_id)
                    processed_in_iteration += 1
                    
                except Exception as e:
                    logger.error(f"      ❌ Talep hatası: {e}")
                    try:
                        driver.back()
                        time.sleep(0.5)
                    except:
                        pass
                    continue
            
            # Scroll kontrol
            if processed_in_iteration == 0:
                no_progress_count += 1
                logger.info(f"   ⚠️ İlerleme yok ({no_progress_count}/5)")
                if no_progress_count >= 5:
                    logger.warning("   🛑 5 kere ilerleme yok, durduruluyor")
                    break
            else:
                no_progress_count = 0
            
            # Aşağı kaydır
            logger.info(f"   ↓ Aşağı kaydırılıyor...")
            driver.execute_script("arguments[0].scrollTop += 150;", scroll_container)
            time.sleep(1.5)
        
        # Son kontrol - bir kere daha talepleri işle
        logger.info(f"🔄 Son kontrol: {len(processed_taleps)}/{total_items} işlendi")
        if len(processed_taleps) < total_items:
            try:
                talep_elements = driver.find_elements(By.CSS_SELECTOR, "div.grid-row")
                logger.info(f"   Son kontrol - Bulunmuş talep sayısı: {len(talep_elements)}")
                
                for talep in talep_elements:
                    try:
                        talep_id = ""
                        try:
                            id_element = talep.find_element(By.CSS_SELECTOR, "div.cell-path")
                            id_text = id_element.text.strip()
                            id_match = re.search(r'\d+', id_text)
                            if id_match:
                                talep_id = id_match.group(0)
                        except:
                            continue
                        
                        if talep_id in processed_taleps:
                            continue
                        
                        konu = ""
                        try:
                            subject_element = talep.find_element(By.CSS_SELECTOR, "div.cell-subject span")
                            konu = subject_element.get_attribute("title") or subject_element.text.strip()
                        except:
                            try:
                                subject_element = talep.find_element(By.CSS_SELECTOR, "div.cell-subject")
                                konu = subject_element.text.strip()
                            except:
                                konu = ""
                        
                        magaza_id = ""
                        try:
                            requester_element = talep.find_element(By.CSS_SELECTOR, "div.cell-requester span")
                            magaza_id = requester_element.get_attribute("title") or requester_element.text.strip()
                            if " - " in magaza_id:
                                magaza_id = magaza_id.split(" - ")[0].strip()
                        except:
                            magaza_id = ""
                        
                        logger.info(f"   📌 Son kontrol - Talep {talep_id}: {konu}")
                        
                        try:
                            talep.click()
                            time.sleep(0.75)
                        except:
                            processed_taleps.add(talep_id)
                            continue
                        
                        try:
                            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "header_bar_inner")))
                            logger.info(f"      ✅ Detay sayfası yüklendi")
                        except:
                            logger.warning(f"      ❌ Detay sayfası yüklenemedi")
                            processed_taleps.add(talep_id)
                            try:
                                driver.back()
                                time.sleep(1)
                            except:
                                pass
                            continue
                        
                        tracking_number = ""
                        try:
                            notes_elements = driver.find_elements(By.CSS_SELECTOR, "li div.note")
                            logger.info(f"      Found {len(notes_elements)} notes")
                            
                            for i, note in enumerate(notes_elements):
                                try:
                                    note_text = note.text or ""
                                    if note_text:
                                        found_tracking = extract_tracking_number(note_text)
                                        if found_tracking:
                                            tracking_number = found_tracking
                                            logger.info(f"      📦 Kargo bulundu: {tracking_number}")
                                except:
                                    continue
                        except Exception as e:
                            logger.warning(f"      ⚠️ Notlar alınamadı: {e}")
                        
                        if tracking_number and tracking_number not in existing_tracking:
                            kargo = {
                                "TrackingNumber": tracking_number,
                                "StoreId": magaza_id,
                                "RequestId": talep_id,
                                "RequestSubject": konu,
                                "Status": "Beklemede",
                                "EstimatedDelivery": "-",
                                "LastUpdated": datetime.now().isoformat()
                            }
                            new_kargos.append(kargo)
                            existing_tracking.add(tracking_number)
                            logger.info(f"      ✅ KARGO EKLENDİ: {tracking_number}")
                        elif not tracking_number and talep_id and talep_id not in existing_tracking:
                            # Kargo numarası bulunamazsa, talep ID'yi takip numarası olarak kullan
                            kargo = {
                                "TrackingNumber": f"TALEP-{talep_id}",
                                "StoreId": magaza_id,
                                "RequestId": talep_id,
                                "RequestSubject": konu,
                                "Status": "Beklemede",
                                "EstimatedDelivery": "-",
                                "LastUpdated": datetime.now().isoformat()
                            }
                            new_kargos.append(kargo)
                            existing_tracking.add(f"TALEP-{talep_id}")
                            logger.info(f"      ⚠️ KARGO NUMARASI BULUNAMADI, TALEP ID KULLANILDI: TALEP-{talep_id}")
                        
                        try:
                            driver.back()
                            time.sleep(0.5)
                        except:
                            pass
                        
                        processed_taleps.add(talep_id)
                        
                    except Exception as e:
                        logger.error(f"      ❌ Talep hatası: {e}")
                        try:
                            driver.back()
                            time.sleep(0.5)
                        except:
                            pass
                        continue
            except:
                pass
        
        # Yeni kargolari ekle
        if new_kargos:
            all_kargos = existing_kargos + new_kargos
            save_kargos(all_kargos)
            logger.info(f"✅ {len(new_kargos)} yeni kargo kaydedildi!")
            return {"success": True, "count": len(new_kargos)}
        else:
            logger.warning("⚠️ Yeni kargo bulunamadı")
            return {"success": True, "count": 0}
        
    except Exception as e:
        logger.error(f"❌ Veri çekme hatası: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}

def check_delivery_status(tracking_number):
    """Kargo durumunu kontrol et - Aras veya UPS (kendi driver ile)"""
    
    # TALEP- ile başlayanlar kontrol edilemez
    if tracking_number.startswith('TALEP-'):
        return "Beklemede"
    
    is_ups = tracking_number.upper().startswith('1Z')
    is_aras = not is_ups and re.match(r'^\d+$', tracking_number)
    
    status = "Beklemede"  # Default
    
    # Her kontrol için ayrı bir driver oluştur - daha küçük pencere (1 ekrana 3 sayfa sığacak)
    options = ChromeOptions()
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
    options.add_argument('--window-size=640,720')  # 1 ekrana 3 sayfa sığacak şekilde
    
    driver = webdriver.Chrome(options=options)
    
    try:
        if is_aras:
            # ARAS KARGO kontrolü
            logger.info(f"Aras Kargo kontrol ediliyor: {tracking_number}")
            url = f"https://kargotakip.araskargo.com.tr/mainpage.aspx?code={tracking_number}"
            driver.get(url)
            time.sleep(6)
            
            try:
                # <span id="Son_Durum"> içindeki metni oku
                son_durum_element = driver.find_element(By.ID, "Son_Durum")
                durum_text = son_durum_element.text.strip().upper()
                
                logger.info(f"Aras Son Durum: {durum_text}")
                
                # "TESLİM EDİLDİ" yazıyorsa teslim edildi
                if "TESLIM" in durum_text and "EDILDI" in durum_text:
                    status = "Teslim Edildi"
                    logger.info(f"✅ Aras: {tracking_number} TESLİM EDİLDİ")
                else:
                    # Başka ne yazıyorsa yolda
                    status = "Yolda"
                    logger.info(f"🚚 Aras: {tracking_number} - Durum: {durum_text}")
                    
            except Exception as e:
                logger.warning(f"⚠️ Aras Son_Durum span bulunamadı: {e}")
                # Fallback: sayfa kaynağında ara
                page_source = driver.page_source
                if "teslim edild" in page_source.lower():
                    status = "Teslim Edildi"
                    logger.info(f"✅ Aras (fallback): {tracking_number} TESLİM EDİLDİ")
                else:
                    status = "Yolda"
                    logger.info(f"🚚 Aras (fallback): {tracking_number} Yolda")
                
        elif is_ups:
            # UPS K2Track kontrolü
            logger.info(f"UPS (K2Track) kontrol ediliyor: {tracking_number}")
            url = f"https://up.k2track.in/ups/tracking-res-extra#{tracking_number}"
            driver.get(url)
            time.sleep(6)
            
            try:
                # Sayfa içinde status metnini bul
                # <p class="text-2xl sm:text-3xl font-bold"> içinde "DELIVERED" aranıyor
                p_elements = driver.find_elements(By.CSS_SELECTOR, "p.font-bold")
                
                found_status = None
                for p in p_elements:
                    try:
                        text = p.text.strip().upper()
                        if text:  # Boş değilse
                            # "DELIVERED" varsa teslim edildi
                            if "DELIVERED" in text:
                                status = "Teslim Edildi"
                                logger.info(f"✅ UPS: {tracking_number} DELIVERED")
                                return status
                            # Başka bir durum yazıyorsa onu al
                            elif not found_status and text not in ["", "ESTIMATED DELIVERY", "LAST STATUS"]:
                                found_status = text
                    except:
                        continue
                
                # DELIVERED bulunamadıysa, bulduğumuz status var mı?
                if found_status and "DELIVERED" not in found_status:
                    status = "Yolda"
                    logger.info(f"🚚 UPS: {tracking_number} - Status: {found_status}")
                else:
                    status = "Yolda"
                    logger.info(f"🚚 UPS: {tracking_number} Yolda")
                    
            except Exception as e:
                logger.warning(f"⚠️ UPS sayfa parse hatası: {e}")
                status = "Yolda"
                
        else:
            logger.info(f"⚠️ {tracking_number} format kontrol edilemiyor")
            status = "Beklemede"
        
        return status
        
    except Exception as e:
        logger.error(f"Durum kontrol hatası ({tracking_number}): {e}")
        return "Beklemede"
    finally:
        try:
            driver.quit()
        except:
            pass

def update_kargo_statuses():
    """Tüm kargolarin durumunu güncelle - 3 tarayıcı paralel"""
    
    logger.info("Kargo durumları güncelleniyor (3 tarayıcı paralel)...")
    
    try:
        kargos = load_kargos()
        
        # Threading ile 3 tarayıcıyı paralel çalıştır
        max_workers = 3
        import concurrent.futures
        
        def update_single_kargo(kargo):
            """Tek bir kargonun durumunu güncelle"""
            try:
                tracking = kargo.get('TrackingNumber', '')
                if tracking:
                    status = check_delivery_status(tracking)
                    kargo['Status'] = status
                    logger.info(f"Güncellendi: {tracking} → {status}")
            except Exception as e:
                logger.error(f"Kargo güncelleme hatası: {e}")
            return kargo
        
        # ThreadPoolExecutor ile paralel işleme
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(update_single_kargo, kargo) for kargo in kargos]
            
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Thread hatası: {e}")
        
        save_kargos(kargos)
        logger.info("✅ Tüm kargolar güncellendi")
        return {"success": True, "count": len(kargos)}
        
    except Exception as e:
        logger.error(f"Güncelleme hatası: {e}")
        return {"success": False, "error": str(e)}

def login_and_fetch():
    """4me'ye gir, 2FA yap ve veri çek"""
    
    options = ChromeOptions()
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
    options.add_argument('--window-size=1920,1080')
    
    driver = webdriver.Chrome(options=options)
    
    try:
        # Inbox sayfasına git
        url ="https://gratis-it.4me.com/inbox?q=&status=waiting_for&team=20982&d=9d3d25635c928d1617939effa3e350c46cef51d775f3bd844a407fbf32b7a18d&vstate=assigned_to_me&vname=inbox&vlayout=two_pane#table=true"


        logger.info(f"📍 Açılıyor: {url}")
        driver.get(url)
        time.sleep(5)
        
        wait = WebDriverWait(driver, 30)
        
        # Email gir
        logger.info("📧 Email girilmeye başlanıyor...")
        email_input = wait.until(EC.presence_of_element_located((By.ID, "i0116")))
        email_input.clear()
        email_input.send_keys(EMAIL)
        logger.info(f"✅ Email girildi: {EMAIL}")
        time.sleep(5)
        
        # Enter
        email_input.send_keys(Keys.RETURN)
        logger.info("⏳ Şifre alanı bekleniyor...")
        time.sleep(5)
        
        # Password gir
        logger.info("🔐 Şifre girilmeye başlanıyor...")
        password_input = wait.until(EC.presence_of_element_located((By.ID, "i0118")))
        password_input.clear()
        password_input.send_keys(PASSWORD)
        logger.info("✅ Şifre girildi")
        time.sleep(5)
        
        # Enter
        password_input.send_keys(Keys.RETURN)
        logger.info("🔍 2FA kontrolü...")
        time.sleep(5)
        
        # 2FA kodunu bul
        try:
            logger.info("🔢 2FA kodu aranıyor...")
            two_factor_element = wait.until(EC.presence_of_element_located((By.ID, "idRichContext_DisplaySign")))
            two_factor_code = two_factor_element.text.strip()
            
            if two_factor_code and two_factor_code.isdigit():
                logger.info(f"✅ 2FA KODU: {two_factor_code}")
                time.sleep(5)
                
                # "Evet" butonuna tıkla
                logger.info("🔘 'Evet' butonuna tıklanıyor...")
                yes_button = wait.until(EC.element_to_be_clickable((By.ID, "idSIButton9")))
                yes_button.click()
                logger.info("✅ 'Evet' butonuna tıklandı")
                time.sleep(5)
                
                # Inbox sayfasının yüklenmesini bekle
                logger.info("📊 Inbox yükleniyor...")
                time.sleep(5)
                
                # Veri çekmeye başla
                logger.info("🔄 Veriler çekiliyor...")
                result = extract_and_save_data(driver, wait)
                
                logger.info("✅ Veri çekme tamamlandı!")
                return result
            else:
                logger.warning(f"⚠️ 2FA kodu geçersiz: {two_factor_code}")
                return {"success": False, "error": "2FA kodu geçersiz"}
                
        except Exception as e:
            logger.error(f"❌ 2FA hatası: {str(e)}")
            return {"success": False, "error": f"2FA hatası: {str(e)}"}
        
    except Exception as e:
        logger.error(f"❌ HATA: {str(e)}")
        return {"success": False, "error": str(e)}
    finally:
        try:
            driver.quit()
        except:
            pass
        logger.info("✅ Chrome kapatıldı")

# --- Flask Routes ---

@app.route('/')
def serve_index():
    """index.html aç"""
    return send_from_directory('.', 'index.html')

@app.route('/api/kargo', methods=['GET'])
def get_kargos():
    """Tüm kargolari getir"""
    return jsonify(load_kargos()), 200

@app.route('/api/kargo/fetch-from-4me', methods=['POST'])
def fetch_from_4me():
    """Buton tıklanınca 4me'den veri çek"""
    try:
        logger.info("4me veri çekme başlatılıyor...")
        
        result = login_and_fetch()
        
        return jsonify({
            "success": result.get("success", False),
            "message": f"{result.get('count', 0)} kargo eklendi" if result.get("success") else result.get("error", "Hata"),
            "count": result.get("count", 0)
        }), 200
        
    except Exception as e:
        logger.error(f"Hata: {str(e)}")
        return jsonify({
            "success": False,
            "message": f"Hata: {str(e)}"
        }), 500

@app.route('/api/kargo/update-statuses', methods=['POST'])
def update_statuses():
    """Tüm kargolarin durumunu güncelle"""
    try:
        logger.info("Durum güncelleme başlatılıyor...")
        
        result = update_kargo_statuses()
        
        return jsonify({
            "success": result.get("success", False),
            "message": f"{result.get('count', 0)} kargo güncellendi" if result.get("success") else result.get("error", "Hata"),
            "count": result.get("count", 0)
        }), 200
        
    except Exception as e:
        logger.error(f"Hata: {str(e)}")
        return jsonify({
            "success": False,
            "message": f"Hata: {str(e)}"
        }), 500

@app.route('/api/kargo', methods=['POST'])
def add_kargo():
    """Yeni kargo ekle"""
    try:
        data = request.json
        tracking_number = data.get('TrackingNumber', '').strip()
        
        if not tracking_number:
            return jsonify({"success": False, "message": "Takip numarası gereklidir"}), 400
        
        kargos = load_kargos()
        
        # Aynı tracking number var mı kontrol et
        if any(k.get('TrackingNumber') == tracking_number for k in kargos):
            return jsonify({"success": False, "message": "Bu takip numarası zaten mevcut"}), 400
        
        new_kargo = {
            "TrackingNumber": tracking_number,
            "StoreId": data.get('StoreId', '').strip(),
            "RequestId": data.get('RequestId', '').strip(),
            "RequestSubject": data.get('RequestSubject', '-'),
            "Status": "Beklemede",
            "EstimatedDelivery": "-",
            "LastUpdated": datetime.now().isoformat()
        }
        
        kargos.append(new_kargo)
        save_kargos(kargos)
        
        logger.info(f"Yeni kargo eklendi: {tracking_number}")
        return jsonify({"success": True, "message": "Kargo başarıyla eklendi", "kargo": new_kargo}), 201
        
    except Exception as e:
        logger.error(f"Ekleme hatası: {str(e)}")
        return jsonify({"success": False, "message": f"Hata: {str(e)}"}), 500

@app.route('/api/kargo/<tracking_number>', methods=['DELETE'])
def delete_kargo(tracking_number):
    """Tek kargo sil"""
    try:
        kargos = load_kargos()
        kargos = [k for k in kargos if k.get('TrackingNumber') != tracking_number]
        save_kargos(kargos)
        
        logger.info(f"Kargo silindi: {tracking_number}")
        return jsonify({"success": True, "message": f"{tracking_number} silindi"}), 200
        
    except Exception as e:
        logger.error(f"Silme hatası: {str(e)}")
        return jsonify({"success": False, "message": f"Hata: {str(e)}"}), 500

@app.route('/api/kargo/delete-all', methods=['DELETE'])
def delete_all():
    """Tüm kargolari sil"""
    try:
        save_kargos([])
        
        logger.info("Tüm kargolar silindi")
        return jsonify({"success": True, "message": "Tüm kargolar silindi"}), 200
        
    except Exception as e:
        logger.error(f"Silme hatası: {str(e)}")
        return jsonify({"success": False, "message": f"Hata: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, threaded=True)
