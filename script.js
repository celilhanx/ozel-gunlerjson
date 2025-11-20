// Global variables
let allKargos = [];
let filteredKargos = [];
let currentFilter = 'all';
let currentSort = { field: null, direction: 'asc' };

// Link açma counters
let deliveredTrackingCounter = 0;
let pendingTrackingCounter = 0;
let deliveredRequestCounter = 0;
let pendingRequestCounter = 0;

// Get 4me request URL
function get4meRequestUrl(talepId) {
    if (!talepId) return '#';
    return `https://gratis-it.4me.com/requests/${encodeURIComponent(talepId)}`;
}

// Get tracking URL based on tracking number format
function getTrackingUrl(takipNo) {
    if (!takipNo) return '#';
    const t = takipNo.trim();

    // UPS format: starts with 1Z
    if (/^1Z/i.test(t)) {
        return `https://www.ups.com/track?loc=tr_TR&tracknum=${encodeURIComponent(t)}`;
    }

    // Aras Kargo: numeric
    if (/^\d{9,14}$/.test(t)) {
        return `https://kargotakip.araskargo.com.tr/mainpage.aspx?code=${encodeURIComponent(t)}`;
    }

    // Default UPS
    return `https://www.ups.com/track?loc=tr_TR&tracknum=${encodeURIComponent(t)}`;
}

// Open URL in new tab
async function openInNewTab(url) {
    if (url && url !== '#') {
        return window.open(url, '_blank');
    }
    return null;
}

// Load and display kargos from API
async function loadAndDisplayKargos() {
  try {
    const response = await fetch('/api/kargo');
    allKargos = await response.json();
    filteredKargos = [...allKargos];
    
    applyFilter();
    updateCounters();
  } catch (error) {
    console.error('Error loading kargos:', error);
    document.getElementById('talepSayisi').textContent = '❌ Veriler yüklenmedi: ' + error.message;
  }
}

// Display table with colors
function displayTable(kargos) {
  const tbody = document.querySelector('#kargoTable tbody');
  
  if (!tbody) {
    console.error('❌ Hata: #kargoTable tbody bulunamadı!');
    return;
  }
  
  tbody.innerHTML = '';
  
  kargos.forEach(kargo => {
    const row = document.createElement('tr');
    
    // Renk belirle
    let bgColor = '#ffffff';
    let statusEmoji = '⏳';
    let statusText = 'Beklemede';
    
    if (kargo.Status === 'Teslim Edildi') {
      bgColor = '#dcfce7';
      statusEmoji = '✅';
      statusText = 'Teslim Edildi';
    } else if (kargo.Status === 'Yolda') {
      bgColor = '#fed7aa';
      statusEmoji = '🚚';
      statusText = 'Yolda';
    } else {
      bgColor = '#fee2e2';
      statusEmoji = '⏳';
      statusText = 'Beklemede';
    }
    
    row.style.backgroundColor = bgColor;
    row.style.borderBottom = '1px solid #e5e7eb';
    row.style.transition = 'all 0.3s ease';
    
    row.innerHTML = `
      <td style="padding: 16px; font-size: 14px; border-right: 1px solid #e5e7eb;">
        <a href="${getTrackingUrl(kargo.TrackingNumber)}" target="_blank" style="color: #2563eb; text-decoration: none; font-weight: 500;">
          ${kargo.TrackingNumber || '-'}
        </a>
      </td>
      <td style="padding: 16px; font-size: 14px; border-right: 1px solid #e5e7eb;">
        ${kargo.StoreId || '-'}
      </td>
      <td style="padding: 16px; font-size: 14px; border-right: 1px solid #e5e7eb;">
        <a href="${get4meRequestUrl(kargo.RequestId)}" target="_blank" style="color: #2563eb; text-decoration: none; font-weight: 500;">
          ${kargo.RequestId || '-'}
        </a>
      </td>
      <td style="padding: 16px; font-size: 14px; border-right: 1px solid #e5e7eb;">
        ${kargo.RequestSubject || '-'}
      </td>
      <td style="padding: 16px; font-size: 14px; border-right: 1px solid #e5e7eb; font-weight: bold;">
        ${statusEmoji} ${statusText}
      </td>
      <td style="padding: 16px; text-align: center;">
        <button style="background: none; border: none; cursor: pointer; font-size: 18px;" onclick="deleteKargo('${kargo.TrackingNumber}')">🗑️</button>
      </td>
    `;
    tbody.appendChild(row);
  });
  
  const talepSayisiEl = document.getElementById('talepSayisi');
  if (talepSayisiEl) {
    talepSayisiEl.textContent = `📊 Toplam ${kargos.length} kargo`;
  }
}

// Delete kargo
async function deleteKargo(trackingNumber) {
  try {
    const response = await fetch(`/api/kargo/${trackingNumber}`, {
      method: 'DELETE'
    });
    
    const result = await response.json();
    
    if (result.success) {
      allKargos = allKargos.filter(k => k.TrackingNumber !== trackingNumber);
      filteredKargos = filteredKargos.filter(k => k.TrackingNumber !== trackingNumber);
      displayTable(filteredKargos);
      updateCounters();
    } else {
      alert(`❌ Hata: ${result.message}`);
    }
  } catch (error) {
    alert(`❌ Silme hatası: ${error.message}`);
  }
}

// Filter functions
function applyFilter() {
  if (currentFilter === 'all') {
    filteredKargos = [...allKargos];
  } else if (currentFilter === 'delivered') {
    filteredKargos = allKargos.filter(k => k.Status === 'Teslim Edildi');
  } else if (currentFilter === 'pending') {
    filteredKargos = allKargos.filter(k => k.Status === 'Beklemede' || k.Status === 'Yolda');
  }
  
  applySort();
  displayTable(filteredKargos);
}

// Sort functions
function applySort() {
  if (currentSort.field) {
    filteredKargos.sort((a, b) => {
      let aVal = a[currentSort.field] || '';
      let bVal = b[currentSort.field] || '';
      
      if (currentSort.direction === 'asc') {
        return aVal.toString().localeCompare(bVal.toString());
      } else {
        return bVal.toString().localeCompare(aVal.toString());
      }
    });
  }
}

// Update counters
function updateCounters() {
  const all = allKargos.length;
  const delivered = allKargos.filter(k => k.Status === 'Teslim Edildi').length;
  const pending = allKargos.filter(k => k.Status === 'Beklemede' || k.Status === 'Yolda').length;
  
  document.querySelector('#filterAll .count').textContent = all;
  document.querySelector('#filterDelivered .count').textContent = delivered;
  document.querySelector('#filterPending .count').textContent = pending;
}

// Initialize event listeners when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
  // Form submit - add new cargo
  document.getElementById('kargoForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const takipNo = document.getElementById('takipNo').value.trim();
    const magazaID = document.getElementById('magazaID').value.trim();
    const talepID = document.getElementById('talepID').value.trim();
    
    if (!takipNo) {
      alert('❌ Takip numarası gereklidir!');
      return;
    }
    
    try {
      const response = await fetch('/api/kargo', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          TrackingNumber: takipNo,
          StoreId: magazaID,
          RequestId: talepID,
          RequestSubject: '-'
        })
      });
      
      const result = await response.json();
      
      if (result.success) {
        alert(`✅ Kargo başarıyla eklendi: ${takipNo}`);
        document.getElementById('kargoForm').reset();
        loadAndDisplayKargos();
      } else {
        alert(`❌ Hata: ${result.message}`);
      }
    } catch (error) {
      alert(`❌ Bağlantı hatası: ${error.message}`);
    }
  });

  // Button click - trigger 4me fetch
  document.getElementById('loadFrom4me').addEventListener('click', async () => {
    const button = document.getElementById('loadFrom4me');
    button.disabled = true;
    button.textContent = '⏳ Yükleniyor...';

    try {
      const response = await fetch('/api/kargo/fetch-from-4me', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });

      const result = await response.json();
      
      if (result.success) {
        alert(`✅ ${result.count} kargo başarıyla eklendi!`);
        loadAndDisplayKargos();
      } else {
        alert(`❌ Hata: ${result.message}`);
      }
    } catch (error) {
      alert(`❌ Bağlantı hatası: ${error.message}`);
    } finally {
      button.disabled = false;
      button.textContent = '📥 4me\'den Yükle';
    }
  });

  // Delete all kargos
  document.getElementById('deleteAllKargos').addEventListener('click', async () => {
    try {
      const response = await fetch('/api/kargo/delete-all', {
        method: 'DELETE'
      });
      
      const result = await response.json();
      
      if (result.success) {
        allKargos = [];
        filteredKargos = [];
        displayTable([]);
        updateCounters();
      } else {
        alert(`❌ Hata: ${result.message}`);
      }
    } catch (error) {
      alert(`❌ Silme hatası: ${error.message}`);
    }
  });

  // Filter buttons
  document.getElementById('filterAll').addEventListener('click', () => {
    currentFilter = 'all';
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    document.getElementById('filterAll').classList.add('active');
    applyFilter();
  });

  document.getElementById('filterDelivered').addEventListener('click', () => {
    currentFilter = 'delivered';
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    document.getElementById('filterDelivered').classList.add('active');
    applyFilter();
  });

  document.getElementById('filterPending').addEventListener('click', () => {
    currentFilter = 'pending';
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    document.getElementById('filterPending').classList.add('active');
    applyFilter();
  });



  // Bulk open tracking links - Teslim Edilenlerin Kargo Linklerini Aç
  document.getElementById('openDeliveredTrackingLinks').addEventListener('click', async () => {
    const delivered = filteredKargos.filter(k => k.Status === 'Teslim Edildi');
    const start = deliveredTrackingCounter;
    const end = Math.min(deliveredTrackingCounter + 5, delivered.length);
    
    if (start >= delivered.length) {
      alert('✅ Tüm teslim edilen kargo linkleri açıldı!');
      deliveredTrackingCounter = 0;
      return;
    }
    
    let openedCount = 0;
    for (let i = start; i < end; i++) {
      const url = getTrackingUrl(delivered[i].TrackingNumber);
      window.open(url, '_blank');
      openedCount++;
      if (i < end - 1) {
        await new Promise(resolve => setTimeout(resolve, 500));
      }
    }
    
    deliveredTrackingCounter = end;
    const remaining = delivered.length - deliveredTrackingCounter;
    
    if (remaining === 0) {
      alert(`✅ Son ${openedCount} link açıldı. Tüm linkler açıldı!`);
      deliveredTrackingCounter = 0;
    } else {
      alert(`✅ ${openedCount} link açıldı. Kalan: ${remaining}`);
    }
  });

  // Bulk open tracking links - Bekleyenlerin Kargo Linklerini Aç
  document.getElementById('openPendingTrackingLinks').addEventListener('click', async () => {
    const pending = filteredKargos.filter(k => k.Status === 'Beklemede' || k.Status === 'Yolda');
    const start = pendingTrackingCounter;
    const end = Math.min(pendingTrackingCounter + 5, pending.length);
    
    if (start >= pending.length) {
      alert('✅ Tüm bekleyen kargo linkleri açıldı!');
      pendingTrackingCounter = 0;
      return;
    }
    
    let openedCount = 0;
    for (let i = start; i < end; i++) {
      const url = getTrackingUrl(pending[i].TrackingNumber);
      window.open(url, '_blank');
      openedCount++;
      if (i < end - 1) {
        await new Promise(resolve => setTimeout(resolve, 500));
      }
    }
    
    pendingTrackingCounter = end;
    const remaining = pending.length - pendingTrackingCounter;
    
    if (remaining === 0) {
      alert(`✅ Son ${openedCount} link açıldı. Tüm linkler açıldı!`);
      pendingTrackingCounter = 0;
    } else {
      alert(`✅ ${openedCount} link açıldı. Kalan: ${remaining}`);
    }
  });

  // Bulk open request links - Teslim Edilen Talepleri Aç
  document.getElementById('openDeliveredRequestLinks').addEventListener('click', async () => {
    const delivered = filteredKargos.filter(k => k.Status === 'Teslim Edildi');
    const start = deliveredRequestCounter;
    const end = Math.min(deliveredRequestCounter + 5, delivered.length);
    
    if (start >= delivered.length) {
      alert('✅ Tüm teslim edilen talep linkleri açıldı!');
      deliveredRequestCounter = 0;
      return;
    }
    
    let openedCount = 0;
    for (let i = start; i < end; i++) {
      const url = get4meRequestUrl(delivered[i].RequestId);
      window.open(url, '_blank');
      openedCount++;
      if (i < end - 1) {
        await new Promise(resolve => setTimeout(resolve, 500));
      }
    }
    
    deliveredRequestCounter = end;
    const remaining = delivered.length - deliveredRequestCounter;
    
    if (remaining === 0) {
      alert(`✅ Son ${openedCount} link açıldı. Tüm linkler açıldı!`);
      deliveredRequestCounter = 0;
    } else {
      alert(`✅ ${openedCount} link açıldı. Kalan: ${remaining}`);
    }
  });

  // Bulk open request links - Bekleyen Talepleri Aç
  document.getElementById('openPendingRequestLinks').addEventListener('click', async () => {
    const pending = filteredKargos.filter(k => k.Status === 'Beklemede' || k.Status === 'Yolda');
    const start = pendingRequestCounter;
    const end = Math.min(pendingRequestCounter + 5, pending.length);
    
    if (start >= pending.length) {
      alert('✅ Tüm bekleyen talep linkleri açıldı!');
      pendingRequestCounter = 0;
      return;
    }
    
    let openedCount = 0;
    for (let i = start; i < end; i++) {
      const url = get4meRequestUrl(pending[i].RequestId);
      window.open(url, '_blank');
      openedCount++;
      if (i < end - 1) {
        await new Promise(resolve => setTimeout(resolve, 500));
      }
    }
    
    pendingRequestCounter = end;
    const remaining = pending.length - pendingRequestCounter;
    
    if (remaining === 0) {
      alert(`✅ Son ${openedCount} link açıldı. Tüm linkler açıldı!`);
      pendingRequestCounter = 0;
    } else {
      alert(`✅ ${openedCount} link açıldı. Kalan: ${remaining}`);
    }
  });

  // Search function
  document.getElementById('searchInput').addEventListener('input', (e) => {
    const query = e.target.value.toLowerCase();
    filteredKargos = allKargos.filter(k => 
      k.TrackingNumber.toLowerCase().includes(query) ||
      k.StoreId.toLowerCase().includes(query) ||
      k.RequestId.toLowerCase().includes(query)
    );
    displayTable(filteredKargos);
  });

  // Dark mode toggle
  document.getElementById('toggleDark').addEventListener('click', () => {
    document.documentElement.classList.toggle('dark');
  });

  // Update button - check all cargo statuses
  document.getElementById('updateKargos').addEventListener('click', async () => {
    const button = document.getElementById('updateKargos');
    button.disabled = true;
    button.textContent = '🔄 Güncelleniyor...';

    try {
      const response = await fetch('/api/kargo/update-statuses', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });

      const result = await response.json();
      
      if (result.success) {
        alert(`✅ ${result.count} kargo durumu güncellendi!`);
        loadAndDisplayKargos();
      } else {
        alert(`❌ Hata: ${result.message}`);
      }
    } catch (error) {
      alert(`❌ Bağlantı hatası: ${error.message}`);
    } finally {
      button.disabled = false;
      button.textContent = '🔄 Güncelle';
    }
  });

  // Initial load
  loadAndDisplayKargos();
});
