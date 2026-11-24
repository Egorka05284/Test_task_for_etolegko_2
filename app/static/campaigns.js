const createForm = document.getElementById('createCampaignForm');
const importForm = document.getElementById('importCampaignForm');
const message = document.getElementById('createMessage');

function showMessage(element, text, isError = false) {
  element.textContent = text;
  element.className = `small ${isError ? 'text-danger' : 'text-success'}`;
}

function fillSelect(id, rows, labelKey = 'name') {
  const select = document.getElementById(id);
  select.replaceChildren(new Option('Выберите...', ''));
  rows.forEach((row) => {
    const label = row[labelKey] ?? `ID ${row.id}`;
    select.add(new Option(`${label} (ID ${row.id})`, row.id));
  });
}

async function loadOptions() {
  try {
    const response = await fetch('/api/keitaro/options');
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'Не удалось загрузить данные Keitaro');
    fillSelect('domain', data.domains);
    fillSelect('group', data.groups);
    fillSelect('source', data.traffic_sources);
    fillSelect('offer', data.offers);
    if (data.defaults) {
      if (data.defaults.domain_id) document.getElementById('domain').value = String(data.defaults.domain_id);
      if (data.defaults.group_id) document.getElementById('group').value = String(data.defaults.group_id);
      if (data.defaults.traffic_source_id) document.getElementById('source').value = String(data.defaults.traffic_source_id);
    }
  } catch (error) {
    ['domain', 'group', 'source', 'offer'].forEach((id) => {
      document.getElementById(id).replaceChildren(new Option('Ошибка загрузки', ''));
    });
    showMessage(message, error.message, true);
  }
}

createForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const button = document.getElementById('createButton');
  button.disabled = true;
  showMessage(message, 'Создание кампании в Keitaro...');
  const form = new FormData(createForm);
  const payload = Object.fromEntries(form.entries());
  ['domain_id', 'group_id', 'traffic_source_id', 'keitaro_offer_id'].forEach((key) => payload[key] = Number(payload[key]));
  payload.geo_code = payload.geo_code.toUpperCase();
  try {
    const response = await fetch('/api/campaigns', {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'Не удалось создать кампанию');
    window.location.href = `/campaigns/${data.id}/edit`;
  } catch (error) {
    showMessage(message, error.message, true);
    button.disabled = false;
  }
});

importForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const button = document.getElementById('importButton');
  const output = document.getElementById('importMessage');
  button.disabled = true;
  const payload = {keitaro_campaign_id: Number(document.getElementById('importCampaignId').value)};
  const streamValue = document.getElementById('importStreamId').value;
  if (streamValue) payload.offer_stream_id = Number(streamValue);
  try {
    const response = await fetch('/api/campaigns/import', {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'Не удалось импортировать кампанию');
    window.location.href = `/campaigns/${data.id}/edit`;
  } catch (error) {
    showMessage(output, error.message, true);
    button.disabled = false;
  }
});

document.getElementById('reloadCampaigns').addEventListener('click', () => window.location.reload());
loadOptions();
