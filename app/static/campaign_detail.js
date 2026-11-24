const campaignId = window.ADROBOT_CAMPAIGN_ID;
const offerList = document.getElementById('offerList');
const messageBox = document.getElementById('offerMessage');
const addButton = document.getElementById('addOfferButton');
const newOfferSelect = document.getElementById('newOffer');

function showMessage(text, isError = false) {
  messageBox.textContent = text;
  messageBox.className = `small mt-2 ${isError ? 'text-danger' : 'text-success'}`;
}

async function api(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || 'Ошибка запроса');
  return data;
}

async function loadAvailableOffers(currentIds = []) {
  const data = await api('/api/keitaro/options');
  newOfferSelect.replaceChildren(new Option('Выберите оффер...', ''));
  data.offers.forEach((offer) => {
    if (!currentIds.includes(Number(offer.id))) {
      newOfferSelect.add(new Option(`${offer.name} (ID ${offer.id})`, offer.id));
    }
  });
}

function renderOffers(data) {
  offerList.replaceChildren();
  if (!data.offers.length) {
    offerList.textContent = 'В потоке пока нет офферов.';
  }
  data.offers.forEach((offer) => {
    const row = document.createElement('div');
    row.className = 'offer-row d-flex align-items-center justify-content-between gap-3';
    const info = document.createElement('div');
    info.className = 'min-w-0';
    const name = document.createElement('div');
    name.className = 'fw-semibold text-break';
    name.textContent = offer.name;
    const id = document.createElement('div');
    id.className = 'small text-secondary';
    id.textContent = `Offer ID: ${offer.keitaro_offer_id}`;
    info.append(name, id);
    const controls = document.createElement('div');
    controls.className = 'd-flex align-items-center gap-3';
    const share = document.createElement('div');
    share.className = 'offer-share fw-semibold';
    share.textContent = `${offer.share}%`;
    const remove = document.createElement('button');
    remove.className = 'btn btn-sm btn-outline-danger';
    remove.textContent = 'Удалить';
    remove.disabled = data.offers.length === 1;
    remove.addEventListener('click', () => removeOffer(offer.keitaro_offer_id));
    controls.append(share, remove);
    row.append(info, controls);
    offerList.append(row);
  });
  document.getElementById('shareTotal').textContent = `${data.total_share}%`;
  document.getElementById('shareTotal').className = `fw-bold ${data.total_share === 100 ? 'text-success' : 'text-danger'}`;
  document.getElementById('shareProgress').style.width = `${Math.min(data.total_share, 100)}%`;
}

async function refresh() {
  try {
    const data = await api(`/api/campaigns/${campaignId}/offers`);
    renderOffers(data);
    await loadAvailableOffers(data.offers.map((offer) => offer.keitaro_offer_id));
    if (data.total_share !== 100) showMessage('Проверьте распределение долей: сумма должна быть 100%.', true);
  } catch (error) {
    offerList.textContent = error.message;
    showMessage(error.message, true);
  }
}

addButton.addEventListener('click', async () => {
  const offerId = Number(newOfferSelect.value);
  if (!offerId) return showMessage('Сначала выберите оффер.', true);
  addButton.disabled = true;
  try {
    const data = await api(`/api/campaigns/${campaignId}/offers`, {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({keitaro_offer_id: offerId})
    });
    renderOffers(data);
    await loadAvailableOffers(data.offers.map((offer) => offer.keitaro_offer_id));
    showMessage('Оффер добавлен, доли пересчитаны.');
  } catch (error) {
    showMessage(error.message, true);
  } finally {
    addButton.disabled = false;
  }
});

async function removeOffer(offerId) {
  if (!window.confirm(`Удалить оффер ${offerId} из потока?`)) return;
  try {
    const data = await api(`/api/campaigns/${campaignId}/offers/${offerId}`, {method: 'DELETE'});
    renderOffers(data);
    await loadAvailableOffers(data.offers.map((offer) => offer.keitaro_offer_id));
    showMessage('Оффер удалён, доли пересчитаны.');
  } catch (error) {
    showMessage(error.message, true);
  }
}

refresh();
