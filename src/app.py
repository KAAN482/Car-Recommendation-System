from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import pandas as pd
import sqlite3
import os
import sqlalchemy as sa
from contextlib import asynccontextmanager
from preprocessing import load_and_preprocess_from_db
from recommendation import recommend_cars
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import RedirectResponse

# Global olarak veriyi saklamak için değişkenler
DF_CLEAN = None  # Orijinal arabam.csv
DF_OTOSOR = None  # Yeni otosor.csv

# Veritabanı ve CSV yolları
ARABAM_DB_PATH = "data/arabam.db"
ARABAM_CSV_PATH = "data/arabam.csv"
OTOSOR_DB_PATH = "data/otosor.db"
OTOSOR_CSV_PATH = "data/otosor.csv"

# Belirli bir CSV için veritabanını oluştur/kontrol et
def ensure_db_for_csv(csv_path: str, db_path: str, table_name: str):
    if not os.path.exists(db_path):
        if not os.path.exists(csv_path):
            print(f"Uyarı: CSV dosyası '{csv_path}' bulunamadı. Veritabanı oluşturulmadı.")
            return False
        df = pd.read_csv(csv_path)
        conn = sqlite3.connect(db_path)
        df.to_sql(table_name, conn, if_exists='replace', index=False)
        conn.close()
        print(f"Veritabanı '{db_path}' başarıyla oluşturuldu (tablo: {table_name}).")
        return True
    return True

# Veriyi yükle ve önbelleğe al
def load_data_and_cache():
    global DF_CLEAN, DF_OTOSOR
    try:
        # Orijinal dataset
        ensure_db_for_csv(ARABAM_CSV_PATH, ARABAM_DB_PATH, 'arabam')
        if os.path.exists(ARABAM_DB_PATH):
            with sa.create_engine(f'sqlite:///{ARABAM_DB_PATH}').connect() as conn:
                DF_CLEAN = load_and_preprocess_from_db(conn, table_name='arabam')
        else:
            DF_CLEAN = None

        # Yeni dataset (otosor)
        ensure_db_for_csv(OTOSOR_CSV_PATH, OTOSOR_DB_PATH, 'otosor')
        if os.path.exists(OTOSOR_DB_PATH):
            with sa.create_engine(f'sqlite:///{OTOSOR_DB_PATH}').connect() as conn:
                DF_OTOSOR = load_and_preprocess_from_db(conn, table_name='otosor')
        else:
            DF_OTOSOR = None

        print("Veritabanı verileri başarıyla yüklendi ve önbelleğe alındı (hem arabam hem otosor).")
    except Exception as e:
        DF_CLEAN = None
        DF_OTOSOR = None
        print(f"Veritabanı yüklenirken hata: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Uygulama başladığında veriyi yükle
    load_data_and_cache()
    yield
    # Uygulama kapandığında yapılacak işlemler (varsa)
    print("API kapatılıyor...")

app = FastAPI(
    title="Araba Öneri Sistemi API",
    description="Araba öneri sistemi backend'i (hem arabam.com hem otosor verileriyle)",
    version="1.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic modelleri
class RecommendationRequest(BaseModel):
    marka: str = Field(..., description="Zorunlu marka adı")
    seri: Optional[str] = None
    model: Optional[str] = None
    vites: Optional[str] = None
    yakit: Optional[str] = None
    ekstra: Optional[str] = None
    alt_fiyat: Optional[float] = None
    ust_fiyat: Optional[float] = None
    min_km: Optional[float] = None
    max_km: Optional[float] = None
    min_yil: Optional[int] = None
    max_yil: Optional[int] = None
    top_n: Optional[int] = 5

class CarResponse(BaseModel):
    ilan_no: Optional[int] = None
    marka: Optional[str] = None
    seri: Optional[str] = None
    model: Optional[str] = None
    fiyat: Optional[float] = None
    kilometre: Optional[float] = None
    yil: Optional[int] = None
    vites_tipi: Optional[str] = None
    yakit_tipi: Optional[str] = None
    link: Optional[str] = None

# Favoriler için in-memory depolama
FAVORITES: List[Dict[str, Any]] = []

# Statik dosyaları API rotalarından ayrı bir prefix altında sunmak
app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/")
def read_root():
    return RedirectResponse(url="/static/index.html")

@app.post("/recommend", response_model=List[CarResponse])
def get_recommendations(request: RecommendationRequest):
    if DF_CLEAN is None and DF_OTOSOR is None:
        raise HTTPException(status_code=500, detail="Veritabanı verisi belleğe yüklenemedi. Lütfen API sunucusunu kontrol edin.")

    if not request.marka.strip():
        raise HTTPException(status_code=400, detail="Marka zorunlu!")

    # İki DF'i birleştir
    combined_df = pd.DataFrame()
    if DF_CLEAN is not None:
        combined_df = pd.concat([combined_df, DF_CLEAN], ignore_index=True)
    if DF_OTOSOR is not None:
        combined_df = pd.concat([combined_df, DF_OTOSOR], ignore_index=True)

    if combined_df.empty:
        raise HTTPException(status_code=500, detail="Hiç veri yüklenemedi.")

    # Link sütununu temizle: NaN veya geçersiz değerleri None yap
    if 'link' in combined_df.columns:
        combined_df['link'] = combined_df['link'].apply(lambda x: x if isinstance(x, str) and x.strip() else None)

    user_desc = f"{request.marka} {request.seri or ''} {request.model or ''} {request.ekstra or ''}".lower().strip()

    recommended = recommend_cars(
        combined_df, user_desc, marka=request.marka, seri=request.seri, model=request.model,
        alt_fiyat=request.alt_fiyat, ust_fiyat=request.ust_fiyat, min_km=request.min_km,
        max_km=request.max_km, min_yil=request.min_yil, max_yil=request.max_yil,
        vites=request.vites, yakit=request.yakit, top_n=request.top_n
    )

    if recommended.empty:
        return []

    response_list = []
    for _, row in recommended.iterrows():
        ilan_no = int(row.get('İlan No', 0)) if pd.notna(row.get('İlan No')) else None
        # Link'i kontrol et: Yeni dataset'ten doğrudan varsa kullan, yoksa arabam.com formatı
        link = row.get('link') if pd.notna(row.get('link')) and isinstance(row.get('link'), str) else None
        if not link and ilan_no:
            link = f"https://www.arabam.com/ilan/{ilan_no}"
        response_list.append(CarResponse(
            ilan_no=ilan_no,
            marka=row.get('Marka'),
            seri=row.get('Seri'),
            model=row.get('Model'),
            fiyat=float(row.get('Fiyat')) if pd.notna(row.get('Fiyat')) else None,
            kilometre=float(row.get('Kilometre')) if pd.notna(row.get('Kilometre')) else None,
            yil=int(row.get('Yıl')) if pd.notna(row.get('Yıl')) else None,
            vites_tipi=row.get('Vites Tipi'),
            yakit_tipi=row.get('Yakıt Tipi'),
            link=link
        ))

    return response_list

@app.get("/favorites", response_model=List[CarResponse])
def get_favorites():
    return [CarResponse(**fav) for fav in FAVORITES]

@app.post("/favorites", response_model=dict)
def add_favorite(car: CarResponse):
    if any(fav.get('ilan_no') == car.ilan_no for fav in FAVORITES):
        raise HTTPException(status_code=400, detail="Bu ilan zaten favorilerde.")
    FAVORITES.append(car.dict())
    return {"message": f"{car.marka} {car.model} favorilere eklendi!"}

@app.delete("/favorites/{ilan_no}", response_model=dict)
def delete_favorite(ilan_no: int):
    global FAVORITES
    initial_len = len(FAVORITES)
    FAVORITES = [fav for fav in FAVORITES if fav.get('ilan_no') != ilan_no]
    if len(FAVORITES) < initial_len:
        return {"message": "Favorilerden silindi!"}
    raise HTTPException(status_code=404, detail="İlan favorilerde bulunamadı.")

@app.delete("/favorites", response_model=dict)
def clear_favorites():
    global FAVORITES
    FAVORITES = []
    return {"message": "Tüm favoriler temizlendi!"}