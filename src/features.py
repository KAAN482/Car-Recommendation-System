# features.py
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import pandas as pd

def combine_features(df):
    """
    Özellikle metin tabanlı sütunları birleştirerek TF-IDF için tek bir metin oluşturur.
    """
    combined = []
    # Temizlenmiş açıklama sütununu tercih et
    desc_col = 'cleaned_description' if 'cleaned_description' in df.columns else 'Açıklama'

    # Sadece ilgili sütunları birleştir
    for _, row in df.iterrows():
        text_parts = []
        # Marka, Seri ve Model kesinlikle dahil edilsin
        if pd.notna(row.get('Marka')):
            text_parts.append(row['Marka'])
        if pd.notna(row.get('Seri')):
            text_parts.append(row['Seri'])
        if pd.notna(row.get('Model')):
            text_parts.append(row['Model'])
        # Açıklama metni en önemli kısım, bunu da ekle
        if desc_col in df.columns and pd.notna(row[desc_col]):
            text_parts.append(row[desc_col])

        combined.append(" ".join(text_parts))
    return combined

def compute_tfidf(df):
    """
    DataFrame için TF-IDF matrisi ve vektörleyiciyi hesaplar.
    """
    combined_texts = combine_features(df)
    vectorizer = TfidfVectorizer(max_features=2000, stop_words='english', token_pattern=r'\b\w+\b')  # Performans için limit artırıldı ve daha iyi tokenizasyon için
    tfidf_matrix = vectorizer.fit_transform(combined_texts)
    return tfidf_matrix, vectorizer

def compute_similarity(vectorizer, tfidf_matrix, user_input):
    """
    Kullanıcı girdisinin TF-IDF vektörünü oluşturur ve mevcut matrisle benzerliğini hesaplar.
    """
    # Kullanıcı girdisini bir liste olarak transform et
    user_vec = vectorizer.transform([user_input])
    similarities = cosine_similarity(user_vec, tfidf_matrix).flatten()
    return similarities