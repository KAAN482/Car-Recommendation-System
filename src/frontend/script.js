document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('recommendation-form');
    const resultsContainer = document.getElementById('results');
    const statusMessage = document.getElementById('status-message');
    const toggleAdvanced = document.getElementById('toggle-advanced');
    const advancedOptions = document.getElementById('advanced-options');
    const favoritesList = document.getElementById('favorites-list');
    const clearFavoritesBtn = document.getElementById('clear-favorites');

    // Sayfalama değişkenleri
    let allCars = [];
    let currentPage = 1;
    const carsPerPage = 5;

    // Yeni marka seçimi
    const markaSelect = document.getElementById('marka-select');
    const markaOtherContainer = document.getElementById('marka-other-container');
    const markaOtherInput = document.getElementById('marka-other');

    // Gelişmiş seçenekleri göster/gizle
    toggleAdvanced.addEventListener('click', () => {
        advancedOptions.classList.toggle('hidden');
    });

    // Marka seçimi değiştiğinde
    markaSelect.addEventListener('change', () => {
        if (markaSelect.value === 'Diğer') {
            markaOtherContainer.classList.remove('hidden');
        } else {
            markaOtherContainer.classList.add('hidden');
        }
    });

    // Favorileri getir
    const fetchFavorites = async () => {
        try {
            const response = await fetch('http://127.0.0.1:8000/favorites');
            const favorites = await response.json();
            favoritesList.innerHTML = '';
            if (favorites.length > 0) {
                favorites.forEach(car => {
                    const favCard = document.createElement('div');
                    favCard.className = 'favorite-card';
                    favCard.innerHTML = `
                        <div>
                            <strong>${car.marka || ''} ${car.model || ''}</strong>
                            <p>${car.fiyat ? new Intl.NumberFormat('tr-TR', { style: 'currency', currency: 'TRY', maximumFractionDigits: 0 }).format(car.fiyat) : 'Belirtilmemiş'}</p>
                            ${car.link ? `<a href="${car.link}" target="_blank" class="car-link">İlanı Görüntüle</a>` : ''}
                        </div>
                        <button class="remove-fav-button" data-ilan-no="${car.ilan_no}">Sil</button>
                    `;
                    favoritesList.appendChild(favCard);
                });
            } else {
                favoritesList.innerHTML = '<p>Henüz favori ilan eklenmemiş.</p>';
            }
        } catch (error) {
            console.error("Favoriler alınırken hata oluştu:", error);
            favoritesList.innerHTML = '<p class="error-message">Favoriler yüklenemedi.</p>';
        }
    };
    fetchFavorites();

    // Favori silme
    favoritesList.addEventListener('click', async (e) => {
        if (e.target.classList.contains('remove-fav-button')) {
            const ilanNo = e.target.dataset.ilanNo;
            try {
                const response = await fetch(`http://127.0.0.1:8000/favorites/${ilanNo}`, { method: 'DELETE' });
                if (response.ok) {
                    await fetchFavorites();
                } else {
                    const error = await response.json();
                    alert(error.detail);
                }
            } catch (error) {
                alert("Favori silinirken bir hata oluştu.");
            }
        }
    });

    // Tüm favorileri temizleme
    clearFavoritesBtn.addEventListener('click', async () => {
        if (confirm("Tüm favorileri temizlemek istediğinize emin misiniz?")) {
            try {
                const response = await fetch('http://127.0.0.1:8000/favorites', { method: 'DELETE' });
                if (response.ok) {
                    await fetchFavorites();
                } else {
                    const error = await response.json();
                    alert(error.detail);
                }
            } catch (error) {
                alert("Favoriler temizlenirken bir hata oluştu.");
            }
        }
    });

    // Sayı formatlama
    window.formatNumber = (input) => {
        let value = input.value.replace(/\./g, '');
        if (value) {
            value = new Intl.NumberFormat('tr-TR').format(parseInt(value));
            input.value = value;
        }
    };

    // Sayfalama için gösterim
    const renderCars = () => {
        resultsContainer.innerHTML = '';
        if (allCars.length === 0) return;

        const start = (currentPage - 1) * carsPerPage;
        const end = start + carsPerPage;
        const carsToShow = allCars.slice(start, end);

        carsToShow.forEach(car => {
            const carCard = document.createElement('div');
            carCard.className = 'car-card';
            carCard.innerHTML = `
                <div class="car-details">
                    <h3>${car.marka || ''} ${car.seri || ''} ${car.model || ''}</h3>
                    <p><strong>Fiyat:</strong> ${car.fiyat ? new Intl.NumberFormat('tr-TR', { style: 'currency', currency: 'TRY', maximumFractionDigits: 0 }).format(car.fiyat) : 'Belirtilmemiş'}</p>
                    <p><strong>Yıl:</strong> ${car.yil || 'Belirtilmemiş'}</p>
                    <p><strong>Kilometre:</strong> ${car.kilometre ? new Intl.NumberFormat('tr-TR').format(car.kilometre) + ' km' : 'Belirtilmemiş'}</p>
                    <p><strong>Vites:</strong> ${car.vites_tipi || 'Belirtilmemiş'}</p>
                    <p><strong>Yakıt:</strong> ${car.yakit_tipi || 'Belirtilmemiş'}</p>
                    ${car.link ? `<a href="${car.link}" target="_blank" class="car-link">İlanı Görüntüle</a>` : ''}
                </div>
                <button class="add-to-fav-button" data-car-data='${JSON.stringify(car)}'>Favoriye Ekle</button>
            `;
            resultsContainer.appendChild(carCard);
        });

        // Sayfalama bilgisi
        const pagination = document.getElementById('pagination');
        const pageInfo = document.getElementById('page-info');
        pagination.classList.remove('hidden');
        pageInfo.textContent = `Sayfa ${currentPage} / ${Math.ceil(allCars.length / carsPerPage)}`;

        document.getElementById('prev-page').disabled = currentPage === 1;
        document.getElementById('next-page').disabled = currentPage === Math.ceil(allCars.length / carsPerPage);
    };

    // Form submit
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        statusMessage.textContent = 'En uygun araçlar aranıyor...';
        statusMessage.className = 'status-message';
        resultsContainer.innerHTML = '';
        resultsContainer.appendChild(statusMessage);

        const altFiyat = document.getElementById('alt_fiyat').value.replace(/\./g, '');
        const ustFiyat = document.getElementById('ust_fiyat').value.replace(/\./g, '');
        const minKm = document.getElementById('min_km').value.replace(/\./g, '');
        const maxKm = document.getElementById('max_km').value.replace(/\./g, '');

        let markaValue = markaSelect.value;
        if (markaValue === 'Diğer') {
            markaValue = markaOtherInput.value.trim();
        }

        const requestData = {
            marka: markaValue || null,
            seri: document.getElementById('seri').value.trim() || null,
            model: document.getElementById('model').value.trim() || null,
            vites: document.getElementById('vites').value || null,
            yakit: document.getElementById('yakit').value || null,
            ekstra: document.getElementById('ekstra').value.trim() || null,
            alt_fiyat: parseFloat(altFiyat) || null,
            ust_fiyat: parseFloat(ustFiyat) || null,
            min_km: parseFloat(minKm) || null,
            max_km: parseFloat(maxKm) || null,
            min_yil: parseInt(document.getElementById('min_yil').value) || null,
            max_yil: parseInt(document.getElementById('max_yil').value) || null,
            top_n: 100 // Daha fazla veri alıyoruz
        };

        if (!requestData.marka) {
            statusMessage.textContent = 'Marka zorunlu!';
            statusMessage.className = 'status-message error-message';
            return;
        }

        try {
            const response = await fetch('http://127.0.0.1:8000/recommend', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(requestData)
            });

            const cars = await response.json();

            if (response.ok) {
                if (cars.length > 0) {
                    allCars = cars;
                    currentPage = 1;
                    statusMessage.textContent = 'En uygun araçlar bulundu:';
                    statusMessage.className = 'status-message success-message';
                    renderCars();
                } else {
                    statusMessage.textContent = 'Belirttiğiniz kriterlere uygun araç bulunamadı.';
                    statusMessage.className = 'status-message error-message';
                }
            } else {
                statusMessage.textContent = `API hatası: ${cars.detail || 'Bilinmeyen Hata'}`;
                statusMessage.className = 'status-message error-message';
            }
        } catch (error) {
            statusMessage.textContent = `API bağlantı hatası: ${error.message}. Lütfen backend'in çalıştığından emin olun.`;
            statusMessage.className = 'status-message error-message';
            console.error('Error:', error);
        }
    });

    // Sayfalama butonları
    document.getElementById('prev-page').addEventListener('click', () => {
        if (currentPage > 1) {
            currentPage--;
            renderCars();
        }
    });

    document.getElementById('next-page').addEventListener('click', () => {
        if (currentPage < Math.ceil(allCars.length / carsPerPage)) {
            currentPage++;
            renderCars();
        }
    });

    // Favorilere ekleme
    resultsContainer.addEventListener('click', async (e) => {
        if (e.target.classList.contains('add-to-fav-button')) {
            const carData = JSON.parse(e.target.dataset.carData);
            try {
                const response = await fetch('http://127.0.0.1:8000/favorites', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(carData)
                });
                const result = await response.json();
                if (response.ok) {
                    alert(result.message);
                    await fetchFavorites();
                } else {
                    alert(result.detail);
                }
            } catch (error) {
                alert("Favorilere eklenirken bir hata oluştu.");
            }
        }
    });
});
