import pandas as pd
import sqlite3
import nltk
from nltk.corpus import stopwords
import re

# NLTK stopwords ve punkt'u bir kez indirmek için
try:
    nltk.data.find('corpora/stopwords')
    nltk.data.find('tokenizers/punkt')
except LookupError:
    try:
        nltk.download('stopwords')
        nltk.download('punkt')
    except Exception as e:
        print(f"Uyarı: NLTK indirme hatası: {e}. Stopwords kullanılmayacak.")

def load_and_preprocess_from_db(conn, table_name='arabam'):
    """
    SQLite bağlantısından veriyi yükle ve preprocess et.

    Args:
        conn: SQLAlchemy veya sqlite3 bağlantı objesi.
        table_name: Veritabanındaki tablo adı ('arabam' veya 'otosor').

    Returns:
        pd.DataFrame: Temizlenmiş ve normalize edilmiş DataFrame.
    """
    query = f"SELECT * FROM {table_name}"
    df = pd.read_sql_query(query, conn)

    # Kolon isimlerini normalleştir (otosor için)
    column_mapping = {
        'Yıl': 'Yıl',
        'KM': 'Kilometre',
        'Vites': 'Vites Tipi',
        'Yakıt': 'Yakıt Tipi',
        'Fiyat': 'Fiyat',
        'İlan No': 'İlan No',
        'Marka': 'Marka',
        'Seri': 'Seri',
        'Model': 'Model',
        'İlan Linki': 'link'  # otosor için link
    }
    df = df.rename(columns={k: v for k, v in column_mapping.items() if k in df.columns})

    # Eksik kolonları NaN ile doldur
    expected_cols = ['İlan No', 'Marka', 'Seri', 'Model', 'Fiyat', 'Kilometre', 'Yıl', 'Vites Tipi', 'Yakıt Tipi', 'Açıklama', 'link']
    for col in expected_cols:
        if col not in df.columns:
            df[col] = pd.NA

    # Fiyat temizleme
    if 'Fiyat' in df.columns:
        df['Fiyat'] = df['Fiyat'].astype(str).str.replace(r'[^\d]', '', regex=True).str.strip()
        df['Fiyat'] = pd.to_numeric(df['Fiyat'], errors='coerce').astype('Int64')
        # Yalnızca arabam tablosu için fiyatı 10'a böl
        if table_name == 'arabam':
            df['Fiyat'] = df['Fiyat'] / 10

    # Yıl temizleme
    if 'Yıl' in df.columns:
        df['Yıl'] = pd.to_numeric(df['Yıl'], errors='coerce').astype('Int64')  # Int64

    # Kilometre temizleme
    if 'Kilometre' in df.columns:
        df['Kilometre'] = df['Kilometre'].astype(str).str.replace(r'[^\d]', '', regex=True).str.strip()
        df['Kilometre'] = pd.to_numeric(df['Kilometre'], errors='coerce').astype('Int64')  # Int64

    # Açıklama temizleme
    if 'Açıklama' in df.columns:
        df['Açıklama'] = df['Açıklama'].fillna('').str.lower().str.strip()
        try:
            stop_words = set(stopwords.words("turkish"))
            df['cleaned_description'] = df['Açıklama'].apply(
                lambda x: ' '.join([w for w in re.findall(r'\w+', x) if w not in stop_words])
            )
        except Exception:
            df['cleaned_description'] = df['Açıklama'].apply(
                lambda x: ' '.join(re.findall(r'\w+', x))
            )
            print("Uyarı: Stopwords kullanılamadı, basit tokenization uygulandı.")

    # Link temizleme: NaN veya geçersiz değerleri None yap
    if 'link' in df.columns:
        df['link'] = df['link'].apply(lambda x: x if isinstance(x, str) and x.strip() else None)

    # Sonuç için sadece gerekli kolonları döndür
    return df[expected_cols + ['cleaned_description']]