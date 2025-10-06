# recommendation.py
import pandas as pd
from features import compute_tfidf, compute_similarity

def recommend_cars(df, user_desc, marka, seri=None, model=None,
                   alt_fiyat=None, ust_fiyat=None, min_km=None, max_km=None,
                   min_yil=None, max_yil=None, vites=None, yakit=None, top_n=5):
    """
    Araba öneri fonksiyonu: Filtreleme + TF-IDF similarity.
    """
    df = df.copy()

    # Filtreleme
    mask = df['Marka'].str.lower() == marka.lower()
    if seri:
        mask &= df['Seri'].str.contains(seri, case=False, na=False)
    if model:
        mask &= df['Model'].str.contains(model, case=False, na=False)
    if alt_fiyat is not None:
        mask &= (df['Fiyat'] >= alt_fiyat) & df['Fiyat'].notna()
    if ust_fiyat is not None:
        mask &= (df['Fiyat'] <= ust_fiyat) & df['Fiyat'].notna()
    if min_km is not None:
        mask &= (df['Kilometre'] >= min_km) & df['Kilometre'].notna()
    if max_km is not None:
        mask &= (df['Kilometre'] <= max_km) & df['Kilometre'].notna()
    if min_yil is not None:
        mask &= (df['Yıl'] >= min_yil) & df['Yıl'].notna()
    if max_yil is not None:
        mask &= (df['Yıl'] <= max_yil) & df['Yıl'].notna()
    if vites:
        mask &= df['Vites Tipi'].str.lower() == vites.lower()
    if yakit:
        mask &= df['Yakıt Tipi'].str.contains(yakit, case=False, na=False)

    filtered_df = df[mask].copy()

    if filtered_df.empty:
        return pd.DataFrame()

    # TF-IDF hesaplaması ve benzerlik
    tfidf_matrix, vectorizer = compute_tfidf(filtered_df)

    # Kullanıcı açıklaması boş değilse benzerlik hesapla, aksi halde varsayılan bir değer kullan.
    if user_desc.strip():
        similarities = compute_similarity(vectorizer, tfidf_matrix, user_desc)
        # Hata kontrolü
        if len(similarities) == len(filtered_df):
            filtered_df.loc[:, 'similarity'] = similarities
        else:
            filtered_df.loc[:, 'similarity'] = 0.5  # Hata durumunda varsayılan değer
    else:
        # Ekstra bilgi yoksa, tüm sonuçlara eşit ağırlık ver
        filtered_df.loc[:, 'similarity'] = 1.0

    # Sonuçları benzerliğe göre sırala
    recommended = filtered_df.sort_values(by='similarity', ascending=False).head(top_n)

    # Çıktı için sütunları seç
    cols = ['İlan No', 'Marka', 'Seri', 'Model', 'Fiyat', 'Kilometre', 'Yıl', 'Vites Tipi', 'Yakıt Tipi', 'link']
    available_cols = [col for col in cols if col in recommended.columns]

    return recommended[available_cols]