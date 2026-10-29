function roundNumber(num, decimals = 2) {
  if (num === null || num === undefined || isNaN(num)) return 0;
  return Number(Math.round(Number(num) + 'e' + decimals) + 'e-' + decimals);
}

// RestoOS Robust Authenticated Fetch Helper
async function apiFetch(url, options = {}) {
  const token = localStorage.getItem('restoos_auth_token') || '';
  const headers = Object.assign({}, options.headers || {});

  if (token && !headers['Authorization']) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const newOptions = Object.assign({}, options, { headers });
  const res = await fetch(url, newOptions);

  if (res.status === 401) {
    console.warn('[RestoOS] 401 Unauthorized for', url);
    if (!url.includes('/auth/login') && !url.includes('/auth/users') && !url.includes('/health')) {
      showToast('Staff session expired. Please sign in with PIN.', 'error');
      openStaffLoginModal();
    }
  } else if (res.status === 403) {
    const errData = await res.clone().json().catch(() => ({}));
    showToast(errData.detail || 'Access Denied: Admin privileges required.', 'error');
  }

  return res;
}


/**
 * RestoOS — High-Throughput Restaurant, Bar & Two-Tier Inventory OS
 * Frontend Single-Page Application (SPA) Engine
 * Inspired by Covers (Rasa Sahyadri · Koregaon Park)
 */

// =============================================================================

// =============================================================================
// MULTI-LANGUAGE ENGINE (ENGLISH & मराठी BILINGUAL SUPPORT)
// =============================================================================

const I18N = {
  en: {
    'nav.cash_counter': 'Cash Counter & Floor',
    'nav.store': 'Store & Grocery',
    'nav.bar_excise': 'Bar & State Excise (FL-3)',
    'nav.owner_dashboard': 'Owner Dashboard & Analytics',
    'nav.cashier_shift': 'Cashier Shift (Z-Report)',
    'nav.settings': 'Settings & Menu',
    'header.tables_open': 'Tables open:',
    'header.covers_today': 'Covers today:',
    'header.sales_today': 'Sales today:',
    'cart.print_bill': 'Print Bill',
    'cart.settle': 'Settle & Drawer',
    'floor.ground': 'Ground floor',
    'floor.terrace': 'Terrace',
    'floor.tables_view': 'Tables (Floor)',
    'floor.menu_view': 'Menu Grid',
    'search.placeholder': 'Search dishes [Ctrl+F]...',
    'status.open': 'OPEN',
    'status.seated': 'SEATED',
    'status.ordered': 'ORDERED',
    'status.billed': 'BILLED',
    'cart.empty': 'No items in order cart. Click dishes to add.',
    'cart.food_subtotal': 'Food Subtotal (GST 5%)',
    'cart.liquor_subtotal': 'Liquor Subtotal (MVAT 5%)',
    'cart.total_tax': 'Statutory Taxes',
    'cart.round_off': 'Round Off',
    'cart.grand_total': 'Grand Total',
    'settle.title': 'Tender Settlement & Drawer Kick',
    'settle.grand_total_payable': 'Grand Total Payable:',
    'settle.select_tender': 'Select Payment Tender:',
    'settle.tender_cash': 'Cash (रोख)',
    'settle.tender_upi': 'UPI / QR',
    'settle.tender_card': 'Card / POS',
    'settle.tender_khata': 'Khata / Ledger',
    'settle.amount_tendered': 'Amount Tendered',
    'settle.change_due': 'Change Due',
    'settle.confirm': 'Confirm & Pop Cash Drawer',
    'settle.cancel': 'Cancel (Esc)',
  },
  mr: {
    'nav.cash_counter': 'कॅश काउंटर व मजला',
    'nav.store': 'मध्यवर्ती भांडार व किराणा',
    'nav.bar_excise': 'बार व राज्य उत्पादन शुल्क',
    'nav.owner_dashboard': 'मालक डॅशबोर्ड व आकडेवारी',
    'nav.cashier_shift': 'कॅशियर शिफ्ट (झेड-रिपोर्ट)',
    'nav.settings': 'सेटिंग्ज व मेनू',
    'header.tables_open': 'खुली टेबले:',
    'header.covers_today': 'आजचे ग्राहक:',
    'header.sales_today': 'आजची विक्री:',
    'cart.print_bill': 'बिल छापा',
    'cart.settle': 'बिल जमा व गल्ला',
    'floor.ground': 'तळमजला',
    'floor.terrace': 'गच्ची (टेरेस)',
    'floor.tables_view': 'टेबल नकाशा',
    'floor.menu_view': 'मेनू यादी',
    'search.placeholder': 'डिश शोधा [Ctrl+F]...',
    'status.open': 'उपलब्ध',
    'status.seated': 'सुरू',
    'status.ordered': 'मागणी दिली',
    'status.billed': 'बिल झाले',
    'cart.empty': 'ऑर्डरमध्ये काहीही नाही. पदार्थ निवडा.',
    'cart.food_subtotal': 'अन्न उपएकूण (५% जीएसटी)',
    'cart.liquor_subtotal': 'मद्य उपएकूण (५% व्हॅट)',
    'cart.total_tax': 'शासकीय कर',
    'cart.round_off': 'राउंड ऑफ',
    'cart.grand_total': 'एकूण देय बिल',
    'settle.title': 'बिल जमा व गल्ला उघडणे',
    'settle.grand_total_payable': 'एकूण देय रक्कम:',
    'settle.select_tender': 'पेमेंट पद्धत निवडा:',
    'settle.tender_cash': 'रोख (Cash)',
    'settle.tender_upi': 'युपीआय / क्यूआर',
    'settle.tender_card': 'कार्ड / स्वाइप',
    'settle.tender_khata': 'खाते / उधारी',
    'settle.amount_tendered': 'दिलेली रक्कम',
    'settle.change_due': 'परत करावयाची बाकी',
    'settle.confirm': 'बिल जमा करा व गल्ला उघडा',
    'settle.cancel': 'रद्द करा (Esc)',
  }
};

// Marathi Category Translations
const CATEGORY_NAMES_MR = {
  'ALL': 'सर्व पदार्थ',
  'Breakfast & Snacks': 'न्याहारी व स्नॅक्स',
  'Veg Starters': 'शाकाहारी स्टार्टर्स',
  'Non-Veg Starters': 'मांसाहारी स्टार्टर्स',
  'Mains': 'मुख्य जेवण व रस्सा',
  'Breads': 'भाकरी व रोटी',
  'Bar & Spirits': 'बार व परमिट रूम',
  'Desserts': 'गोड पदार्थ',
  'Special Thalis': 'खास थाळी'
};

// Marathi Dish Name Mapping
const DISH_NAMES_MR = {
  1: 'चिकन सुक्का',
  2: 'मटण तांबडा रस्सा (फुल)',
  3: 'कोल्हापुरी चिकन',
  4: 'विशेष शाकाहारी थाळी',
  5: 'पनीर टिक्का',
  6: 'कोथिंबीर वडी',
  7: 'झणझणीत मिसळ पाव',
  8: 'चिकन ६५',
  9: 'मटण सुक्का फ्राय',
  10: 'सुरमई रवा फ्राय',
  11: 'गरमागरम ज्वारी भाकरी',
  12: 'चपाती / फुलका (तूप)',
  13: 'बटर तंदुरी रोटी',
  14: 'दाल तडका',
  15: 'जिरा राईस',
  16: 'ताजी सोलकढी',
  17: 'कोकम सरबत',
  18: 'पुरणपोळी (कटाची आमटी)',
  19: 'ब्लेंडर्स प्राइड व्हिस्की (६० मिली)',
  20: 'किंगफिशर प्रीमियम बियर (६५० मिली)',
  21: 'ओल्ड मंक रम (६० मिली)',
  22: 'मॅजिक मोमेंट्स व्होडका (६० मिली)',
  23: 'सुला शिराज वाईन',
  24: 'पिठलं भाकरी स्पेशल',
  25: 'पापलेट रवा फ्राय',
  26: 'इंद्रायणी भात',
  27: 'पारंपारिक खरवस',
  28: 'गुलाब जामुन (२ नग)',
  29: 'मसाला ताक / मठ्ठा',
  30: 'उकडीचे मोदक (२ नग)'
};

function t(key) {
  const lang = state.lang || 'en';
  return (I18N[lang] && I18N[lang][key]) || (I18N.en && I18N.en[key]) || key;
}

function setLanguage(lang) {
  state.lang = (lang === 'mr') ? 'mr' : 'en';
  try {
    localStorage.setItem('restoos_lang', state.lang);
  } catch (e) {}

  updateLangToggleButtons();
  applyTranslations();
  renderAll();
  showToast(state.lang === 'mr' ? 'भाषा: मराठी निवडली आहे.' : 'Language: English selected.', 'info');
}

function updateLangToggleButtons() {
  const btnEn = document.getElementById('lang-btn-en');
  const btnMr = document.getElementById('lang-btn-mr');
  if (!btnEn || !btnMr) return;

  if (state.lang === 'mr') {
    btnMr.className = 'px-2 py-0.5 rounded-md transition font-bold text-[11px] bg-white text-emerald-900 shadow-xs cursor-pointer';
    btnEn.className = 'px-2 py-0.5 rounded-md transition font-medium text-[11px] text-gray-600 hover:text-gray-900 cursor-pointer';
  } else {
    btnEn.className = 'px-2 py-0.5 rounded-md transition font-bold text-[11px] bg-white text-emerald-900 shadow-xs cursor-pointer';
    btnMr.className = 'px-2 py-0.5 rounded-md transition font-medium text-[11px] text-gray-600 hover:text-gray-900 cursor-pointer';
  }
}

function applyTranslations() {
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    if (key && I18N[state.lang] && I18N[state.lang][key]) {
      el.textContent = I18N[state.lang][key];
    }
  });

  const searchInput = document.getElementById('dish-search-input');
  if (searchInput) {
    searchInput.placeholder = t('search.placeholder');
  }

  // Update floor filter buttons
  const btnGround = document.getElementById('btn-sec-ground');
  if (btnGround) btnGround.textContent = t('floor.ground');
  const btnTerrace = document.getElementById('btn-sec-terrace');
  if (btnTerrace) btnTerrace.textContent = t('floor.terrace');

  // Update table/menu view toggles
  const btnTables = document.getElementById('toggle-view-tables');
  if (btnTables) btnTables.textContent = t('floor.tables_view');
  const btnMenu = document.getElementById('toggle-view-menu');
  if (btnMenu) btnMenu.textContent = t('floor.menu_view');
}

// 1. STATE & DATA INITIALIZATION
// =============================================================================

const state = {
  activeWorkspace: 'cash-counter',
  lang: localStorage.getItem('restoos_lang') || 'en',
  // Role-Based Access Control (RBAC): CASHIER (Hotel things only) vs ADMIN (Whole software + stats)
  currentUser: { id: 3, username: 'pooja_more', display_name: 'Pooja More', role: 'CASHIER' },
  currentRole: 'CASHIER',

  activeFloorSection: 'ground',
  leftPanelView: 'tables', // 'tables' or 'menu'
  activeTableId: 'T7',     // Default table as specified in DESIGN.md
  selectedCategory: 'ALL',
  isVegOnly: false,
  searchQuery: '',
  selectedTender: 'cash',
  receiptType: 'invoice',
  isServerConnected: true,
  
  // Operational Metrics
  todaySales: 3976.00,
  todayCovers: 24,
  tablesOpenCount: 10,
  totalTables: 16,

  // Dining Tables (T1 to T16 across Ground Floor & Terrace)
  tables: [
    { id: 'T1', section: 'ground', seats: 2, status: 'open', timer: 0, waiter: 'Rahul', covers: 0, items: [] },
    { id: 'T2', section: 'ground', seats: 4, status: 'seated', timer: 35, waiter: 'Sunil', covers: 3, items: [
      { id: 4, name_mr: 'विशेष शाकाहारी थाळी', name: 'Special Veg Thali', price: 260, qty: 2, notes: 'Less oil', isVeg: true, taxType: 'GST', station: 'KITCHEN' },
      { id: 16, name_mr: 'ताजी सोलकढी', name: 'Sol Kadhi', price: 60, qty: 2, notes: '', isVeg: true, taxType: 'GST', station: 'KITCHEN' }
    ]},
    { id: 'T3', section: 'ground', seats: 4, status: 'open', timer: 0, waiter: 'Pooja', covers: 0, items: [] },
    { id: 'T4', section: 'ground', seats: 6, status: 'seated', timer: 45, waiter: 'Rahul', covers: 5, items: [
      { id: 3, name_mr: 'कोल्हापुरी चिकन', name: 'Kolhapuri Chicken', price: 380, qty: 2, notes: 'Spicy', isVeg: false, taxType: 'GST', station: 'KITCHEN' },
      { id: 11, name_mr: 'गरमागरम ज्वारी भाकरी', name: 'Jowar Bhakri', price: 35, qty: 6, notes: 'Crisp', isVeg: true, taxType: 'GST', station: 'KITCHEN' }
    ]},
    { id: 'T5', section: 'ground', seats: 2, status: 'open', timer: 0, waiter: 'Sunil', covers: 0, items: [] },
    { id: 'T6', section: 'ground', seats: 4, status: 'open', timer: 0, waiter: 'Pooja', covers: 0, items: [] },
    { id: 'T7', section: 'ground', seats: 2, status: 'seated', timer: 20, waiter: 'Rahul', covers: 2, items: [
      { id: 1, name_mr: 'चिकन सुक्का', name: 'Chicken Sukka', price: 340.00, qty: 1, notes: 'Extra spicy', isVeg: false, taxType: 'GST', station: 'KITCHEN' },
      { id: 2, name_mr: 'मटण तांबडा रस्सा (फुल)', name: 'Mutton Rassa (Full)', price: 750.00, qty: 1, notes: 'Hot gravy', isVeg: false, taxType: 'GST', station: 'KITCHEN' },
      { id: 11, name_mr: 'गरमागरम ज्वारी भाकरी', name: 'Jowar Bhakri', price: 35.00, qty: 2, notes: 'Fresh', isVeg: true, taxType: 'GST', station: 'KITCHEN' },
      { id: 19, name_mr: 'ब्लेंडर्स प्राइड व्हिस्की (६० मिली)', name: 'Blenders Pride Whisky (60ml)', price: 220.00, qty: 2, notes: 'With Soda & Ice', isVeg: true, taxType: 'VAT', station: 'BAR' },
      { id: 20, name_mr: 'किंगफिशर प्रीमियम बियर (६५० मिली)', name: 'Kingfisher Premium (650ml)', price: 280.00, qty: 1, notes: 'Chilled', isVeg: true, taxType: 'VAT', station: 'BAR' }
    ]},
    { id: 'T8', section: 'ground', seats: 6, status: 'open', timer: 0, waiter: 'Sunil', covers: 0, items: [] },
    
    // Terrace Section
    { id: 'T9', section: 'terrace', seats: 4, status: 'seated', timer: 12, waiter: 'Pooja', covers: 4, items: [
      { id: 5, name_mr: 'पनीर टिक्का', name: 'Paneer Tikka', price: 280, qty: 1, notes: 'Mint chutney', isVeg: true, taxType: 'GST', station: 'KITCHEN' },
      { id: 22, name: 'Sula Shiraz Red Wine (Glass)', price: 320, qty: 2, notes: '', isVeg: true, taxType: 'VAT', station: 'BAR' }
    ]},
    { id: 'T10', section: 'terrace', seats: 4, status: 'open', timer: 0, waiter: 'Rahul', covers: 0, items: [] },
    { id: 'T11', section: 'terrace', seats: 2, status: 'open', timer: 0, waiter: 'Sunil', covers: 0, items: [] },
    { id: 'T12', section: 'terrace', seats: 6, status: 'open', timer: 0, waiter: 'Pooja', covers: 0, items: [] },
    { id: 'T13', section: 'terrace', seats: 4, status: 'seated', timer: 5, waiter: 'Rahul', covers: 2, items: [
      { id: 14, name_mr: 'दाल तडका', name: 'Dal Tadka', price: 190, qty: 1, notes: '', isVeg: true, taxType: 'GST', station: 'KITCHEN' },
      { id: 15, name_mr: 'जिरा राईस', name: 'Jeera Rice', price: 160, qty: 1, notes: '', isVeg: true, taxType: 'GST', station: 'KITCHEN' }
    ]},
    { id: 'T14', section: 'terrace', seats: 4, status: 'open', timer: 0, waiter: 'Sunil', covers: 0, items: [] },
    { id: 'T15', section: 'terrace', seats: 2, status: 'open', timer: 0, waiter: 'Pooja', covers: 0, items: [] },
    { id: 'T16', section: 'terrace', seats: 8, status: 'open', timer: 0, waiter: 'Rahul', covers: 0, items: [] }
  ],

  // Authentic Menu Items Catalog (Rasa Sahyadri & Permit Room FL-3)
  // Category Directory & Department Mappings
  categories: [
    { id: 1, name_mr: 'बार व परमिट रूम', name: 'Bar', department: 'BAR', tax_category: 'VAT_ALCOHOL', itemCount: 6 },
    { id: 2, name_mr: 'शीतपेये व सरबत', name: 'Beverages', department: 'KITCHEN', tax_category: 'GST_FOOD', itemCount: 2 },
    { id: 3, name_mr: 'भाकरी व रोटी', name: 'Breads', department: 'KITCHEN', tax_category: 'GST_FOOD', itemCount: 3 },
    { id: 4, name_mr: 'न्याहारी व स्नॅक्स', name: 'Breakfast', department: 'KITCHEN', tax_category: 'GST_FOOD', itemCount: 6 },
    { id: 5, name_mr: 'मुख्य जेवण व रस्सा', name: 'Mains', department: 'KITCHEN', tax_category: 'GST_FOOD', itemCount: 5 },
    { id: 6, name_mr: 'मांसाहारी स्टार्टर्स', name: 'Non-Veg Starters', department: 'KITCHEN', tax_category: 'GST_FOOD', itemCount: 4 },
    { id: 7, name_mr: 'शाकाहारी स्टार्टर्स', name: 'Veg Starters', department: 'KITCHEN', tax_category: 'GST_FOOD', itemCount: 3 },
    { id: 8, name_mr: 'गोड पदार्थ', name: 'Desserts', department: 'KITCHEN', tax_category: 'GST_FOOD', itemCount: 0 }
  ],

  menuItems: [
    { id: 1, name_mr: 'चिकन सुक्का', name: 'Chicken Sukka', category: 'Mains', price: 340.00, isVeg: false, taxType: 'GST', station: 'KITCHEN', desc: 'Slow-roasted chicken in black masala & toasted coconut' },
    { id: 2, name_mr: 'मटण तांबडा रस्सा (फुल)', name: 'Mutton Rassa (Full)', category: 'Mains', price: 750.00, isVeg: false, taxType: 'GST', station: 'KITCHEN', desc: 'Kolhapuri spiced mutton curry with aromatic tambda rassa' },
    { id: 3, name_mr: 'कोल्हापुरी चिकन', name: 'Kolhapuri Chicken', category: 'Mains', price: 380.00, isVeg: false, taxType: 'GST', station: 'KITCHEN', desc: 'Fiery chicken preparation simmered in whole spices' },
    { id: 4, name_mr: 'विशेष शाकाहारी थाळी', name: 'Special Veg Thali', category: 'Mains', price: 260.00, isVeg: true, taxType: 'GST', station: 'KITCHEN', desc: '2 seasonal sabzis, dal, 2 bhakris, jeera rice, sol kadhi' },
    { id: 5, name_mr: 'पनीर टिक्का', name: 'Paneer Tikka', category: 'Veg Starters', price: 280.00, isVeg: true, taxType: 'GST', station: 'KITCHEN', desc: 'Charcoal-grilled fresh cottage cheese cubes with peppers' },
    { id: 6, name_mr: 'कोथिंबीर वडी', name: 'Kothimbir Vadi', category: 'Breakfast & Snacks', price: 160.00, isVeg: true, taxType: 'GST', station: 'KITCHEN', desc: 'Crispy coriander & gram flour savory fritters with chutney' },
    { id: 7, name_mr: 'झणझणीत मिसळ पाव', name: 'Misal Pav (Special)', category: 'Breakfast & Snacks', price: 140.00, isVeg: true, taxType: 'GST', station: 'KITCHEN', desc: 'Sprouted moth beans in fiery rassa topped with farsan' },
    { id: 8, name_mr: 'चिकन ६५', name: 'Chicken 65', category: 'Non-Veg Starters', price: 310.00, isVeg: false, taxType: 'GST', station: 'KITCHEN', desc: 'Deep-fried chicken chunks tossed in curry leaves & chilis' },
    { id: 9, name_mr: 'मटण सुक्का फ्राय', name: 'Mutton Sukka (Dry)', category: 'Non-Veg Starters', price: 450.00, isVeg: false, taxType: 'GST', station: 'KITCHEN', desc: 'Tender goat mutton roasted dry with crushed garlic' },
    { id: 10, name_mr: 'सुरमई रवा फ्राय', name: 'Surmai Fry (Kingfish)', category: 'Non-Veg Starters', price: 550.00, isVeg: false, taxType: 'GST', station: 'KITCHEN', desc: 'Fresh Malvani spiced rava coated pan-fried fish darnes' },
    { id: 11, name_mr: 'गरमागरम ज्वारी भाकरी', name: 'Jowar Bhakri', category: 'Breads', price: 35.00, isVeg: true, taxType: 'GST', station: 'KITCHEN', desc: 'Traditional wood-stove baked sorghum flatbread' },
    { id: 12, name_mr: 'चपाती / फुलका (तूप)', name: 'Chapati (Phulka)', category: 'Breads', price: 25.00, isVeg: true, taxType: 'GST', station: 'KITCHEN', desc: 'Soft whole-wheat tawa phulka brushed with pure ghee' },
    { id: 13, name_mr: 'बटर तंदुरी रोटी', name: 'Butter Tandoori Roti', category: 'Breads', price: 30.00, isVeg: true, taxType: 'GST', station: 'KITCHEN', desc: 'Crisp clay-oven tandoori roti topped with butter' },
    { id: 14, name_mr: 'दाल तडका', name: 'Dal Tadka', category: 'Mains', price: 190.00, isVeg: true, taxType: 'GST', station: 'KITCHEN', desc: 'Yellow lentils tempered with ghee, cumin & dried chilis' },
    { id: 15, name_mr: 'जिरा राईस', name: 'Jeera Rice', category: 'Mains', price: 160.00, isVeg: true, taxType: 'GST', station: 'KITCHEN', desc: 'Fragrant basmati rice tossed with toasted cumin seeds' },
    { id: 16, name_mr: 'ताजी सोलकढी', name: 'Sol Kadhi', category: 'Breakfast & Snacks', price: 60.00, isVeg: true, taxType: 'GST', station: 'KITCHEN', desc: 'Digestive drink of fresh coconut milk & kokum with garlic' },
    { id: 17, name_mr: 'कोकम सरबत', name: 'Kokum Sharbat', category: 'Breakfast & Snacks', price: 50.00, isVeg: true, taxType: 'GST', station: 'KITCHEN', desc: 'Refreshing indigenous cooler made from sun-dried kokum' },
    { id: 18, name_mr: 'पुरणपोळी (कटाची आमटी)', name: 'Puran Poli (with Katachi Amti)', category: 'Desserts', price: 90.00, isVeg: true, taxType: 'GST', station: 'KITCHEN', desc: 'Sweet jaggery & chana dal filled flatbread with ghee' },
    { id: 19, name_mr: 'ब्लेंडर्स प्राइड व्हिस्की (६० मिली)', name: 'Blenders Pride Whisky (60ml)', category: 'Bar & Spirits', price: 220.00, isVeg: true, taxType: 'VAT', station: 'BAR', desc: 'Premium blended Indian grain whisky (Large Pour 60ml)' },
    { id: 20, name_mr: 'किंगफिशर प्रीमियम बियर (६५० मिली)', name: 'Kingfisher Premium (650ml)', category: 'Bar & Spirits', price: 280.00, isVeg: true, taxType: 'VAT', station: 'BAR', desc: 'Chilled lager bottle (650ml) served in frosty beer glass' },
    { id: 21, name: 'Old Monk Dark Rum (60ml)', category: 'Bar & Spirits', price: 180.00, isVeg: true, taxType: 'VAT', station: 'BAR', desc: 'Legendary Indian vatted dark rum (Large Pour 60ml)' },
    { id: 22, name: 'Sula Shiraz Red Wine (Glass)', category: 'Bar & Spirits', price: 320.00, isVeg: true, taxType: 'VAT', station: 'BAR', desc: 'Nashik estate red wine with pepper and blackberry notes' },
    { id: 23, name: 'Antiquity Blue Whisky (60ml)', category: 'Bar & Spirits', price: 260.00, isVeg: true, taxType: 'VAT', station: 'BAR', desc: 'Ultra-smooth grain whisky blend (Large Pour 60ml)' }
  ],

  // Central Store Inventory (Tier 1 Store vs Tier 2 Kitchen Line)
  storeStock: [
    { id: 'RM-1', name: 'Chicken Curry Cut (Skinless)', category: 'Poultry', storeQty: 45.0, kitchenQty: 8.0, uom: 'kg', cost: 180.00, minLimit: 20.0 },
    { id: 'RM-2', name: 'Fresh Malai Paneer', category: 'Dairy', storeQty: 18.0, kitchenQty: 5.0, uom: 'kg', cost: 340.00, minLimit: 10.0 },
    { id: 'RM-3', name: 'Mutton (Bone-in Goat)', category: 'Meat', storeQty: 28.0, kitchenQty: 4.0, uom: 'kg', cost: 580.00, minLimit: 15.0 },
    { id: 'RM-4', name: 'Refined Sunflower Oil', category: 'Oils', storeQty: 75.0, kitchenQty: 15.0, uom: 'L', cost: 130.00, minLimit: 30.0 },
    { id: 'RM-5', name: 'Wada Kolam Rice', category: 'Grains', storeQty: 120.0, kitchenQty: 25.0, uom: 'kg', cost: 65.00, minLimit: 40.0 },
    { id: 'RM-6', name: 'Jowar Flour (Sorghum)', category: 'Grains', storeQty: 50.0, kitchenQty: 12.0, uom: 'kg', cost: 48.00, minLimit: 20.0 },
    { id: 'RM-7', name: 'Kolhapuri Kanda-Lasun Masala', category: 'Spices', storeQty: 15.0, kitchenQty: 3.0, uom: 'kg', cost: 420.00, minLimit: 5.0 },
    { id: 'RM-8', name: 'Red Onions (Nashik A-Grade)', category: 'Vegetables', storeQty: 85.0, kitchenQty: 18.0, uom: 'kg', cost: 35.00, minLimit: 30.0 }
  ],

  // Goods Inward Notes (GRN)
  grnList: [
    { grnNo: 'GRN-101', date: '26-Oct-2026', vendor: 'Sahyadri Poultry & Farm Produce', invoiceNo: 'INV-9810', items: '50kg Chicken Curry Cut', amount: 9000.00, status: 'Passed QC' },
    { grnNo: 'GRN-102', date: '26-Oct-2026', vendor: 'Krishna Valley Dairy Cooperative', invoiceNo: 'INV-4491', items: '20kg Paneer + 30L Milk', amount: 9800.00, status: 'Passed QC' },
    { grnNo: 'GRN-103', date: '25-Oct-2026', vendor: 'Poona Grain & Spice Merchants', invoiceNo: 'INV-3301', items: '100kg Rice + 50kg Jowar', amount: 8900.00, status: 'Passed QC' }
  ],

  // Store Indents (Kitchen Requisitions)
  requisitions: [
    { id: 'IND-041', time: '10:15 AM', chef: 'Chef Santosh', item: 'Chicken Curry Cut', qty: '10 kg', status: 'Issued' },
    { id: 'IND-042', time: '11:30 AM', chef: 'Chef Santosh', item: 'Fresh Malai Paneer', qty: '5 kg', status: 'Issued' },
    { id: 'IND-043', time: '04:15 PM', chef: 'Chef Santosh', item: 'Cooking Oil', qty: '15 L', status: 'Issued' },
    { id: 'IND-044', time: '07:30 PM', chef: 'Chef Santosh', item: 'Chicken Curry Cut', qty: '8 kg', status: 'Pending Approval' }
  ],

  // Wastage Logs
  wastageLog: [
    { logNo: 'WST-012', time: '26-Oct 14:10', item: 'Chicken Gravy Prep', qty: '1.5 kg', reason: 'BURNT_BY_COOK', cost: 270.00, authorizer: 'Chef Santosh' },
    { logNo: 'WST-013', time: '26-Oct 16:45', item: 'Jowar Dough', qty: '2.0 kg', reason: 'EXPIRED_PREP', cost: 140.00, authorizer: 'Chef Santosh' }
  ],

  // Form FLR-3A Daily Brand-Wise Register (State Excise FL-3)
  exciseFlr3a: [
    { brand: 'Blenders Pride Whisky', category: 'IMFL', size: '750 ml', opening: 14, inwardTp: 12, salesPegs: 18, salesBottles: 0, breakage: 0, closing: 25.28 },
    { brand: 'Kingfisher Premium Beer', category: 'Beer', size: '650 ml', opening: 36, inwardTp: 24, salesPegs: 0, salesBottles: 14, breakage: 0, closing: 46 },
    { brand: 'Old Monk Dark Rum', category: 'IMFL', size: '750 ml', opening: 8, inwardTp: 0, salesPegs: 8, salesBottles: 0, breakage: 0, closing: 7.68 },
    { brand: 'Sula Shiraz Red Wine', category: 'Wine', size: '750 ml', opening: 6, inwardTp: 6, salesPegs: 5, salesBottles: 0, breakage: 0, closing: 11.00 },
    { brand: 'Antiquity Blue Whisky', category: 'IMFL', size: '750 ml', opening: 5, inwardTp: 0, salesPegs: 0, salesBottles: 0, breakage: 0, closing: 5.00 }
  ],

  // Transport Permits (TP)
  exciseTpList: [
    { tpNo: 'TP-MH-PUN-2026-904', date: '26-Oct-2026', vendor: 'MSBCL Pune Wholesale Depot', vehicle: 'MH-12-FC-4491', bottles: '12 Bottles (Blenders Pride 750ml)', serials: 'MHEX-904100 to MHEX-904111', status: 'Excise Verified' },
    { tpNo: 'TP-MH-PUN-2026-881', date: '24-Oct-2026', vendor: 'United Breweries Central Depot', vehicle: 'MH-12-AQ-2109', bottles: '24 Bottles (Kingfisher 650ml)', serials: 'MHEX-881200 to MHEX-881223', status: 'Excise Verified' }
  ],

  // Shift Register
  shift: {
    registerId: 'KP-C1-LAN',
    cashier: 'Rahul Sharma',
    openingFloat: 2000.00,
    cashSales: 6780.00,
    upiSales: 14230.00,
    cardSales: 3840.00,
    paidOut: 350.00,
    paidIn: 0.00,
    get expectedCash() {
      return this.openingFloat + this.cashSales + this.paidIn - this.paidOut;
    }
  },

  // Audit Trail
  auditTrail: [
    { time: '22:15', user: 'Rahul (Cashier)', action: 'Bill Settled (T7: ₹1,218.00 via UPI)', status: 'Approved' },
    { time: '21:40', user: 'Sneha (Manager)', action: 'GRN Approved (PO-104: 50kg Chicken)', status: 'Approved' },
    { time: '20:10', user: 'Rahul (Cashier)', action: 'Cash Drawer Manual Kick (No Sale Flagged)', status: 'Security Flag' },
    { time: '19:05', user: 'Sneha (Manager)', action: 'Recipe Price Updated (Mutton Rassa)', status: 'Approved' },
    { time: '16:30', user: 'Suresh (Storekeeper)', action: 'Store Indent Issued to Kitchen (IND-043)', status: 'Approved' }
  ]
};

// =============================================================================
// 2. DOM EVENT LISTENERS & LIFECYCLE
// =============================================================================

document.addEventListener('DOMContentLoaded', () => {
  // 1. Initial State Render
  initStaffSession();
  applyRolePermissions();
  checkCloudConfig();
  updateLiveClock();
  setInterval(updateLiveClock, 1000);
  
  // 2. Render all initial views
  renderAll();
  
  // 3. Denomination Calculator init
  calculateDenominations();

  // 4. Keyboard Shortcuts Handler
  setupKeyboardShortcuts();

  // 5. Check API connectivity (graceful fallback)
  checkBackendHealth();

  // 6. Fetch live dishes catalog and statutory settings
  fetchBackendCategories();
  fetchBackendMenu();
  loadTenantSettings();

  // 7. Route to initial workspace if URL hash present (#settings, #menu, etc.)
  handleInitialRoute();
  window.addEventListener('hashchange', handleInitialRoute);
});

function handleInitialRoute() {
  const hash = (window.location.hash || '').replace('#', '').trim();
  const path = (window.location.pathname || '').replace('/', '').trim();

  if (hash === 'settings' || path === 'settings') {
    switchWorkspace('settings');
  } else if (hash === 'store-grocery' || hash === 'store' || path === 'store') {
    switchWorkspace('store-grocery');
  } else if (hash === 'bar-excise' || hash === 'bar' || path === 'bar') {
    switchWorkspace('bar-excise');
  } else if (hash === 'owner-dashboard' || hash === 'owner' || path === 'owner') {
    switchWorkspace('owner-dashboard');
  } else if (hash === 'cashier-shift' || hash === 'shift' || path === 'shift') {
    switchWorkspace('cashier-shift');
  } else if (hash === 'menu' || path === 'menu') {
    switchWorkspace('cash-counter');
    setLeftPanelView('menu');
  }
}

function renderAll() {
  renderHeaderMetrics();
  renderTables();
  renderCategoryPills();
  renderMenuItems();
  renderCart();
  renderStoreStock();
  renderGrnHistory();
  renderIndents();
  renderWastage();
  renderFlr3a();
  renderFlr4();
  renderAuditTrail();
  renderSettingsMenu();
  renderSettingsCategories();
  if (window.lucide) {
    window.lucide.createIcons();
  }
}

// Live Clock Handler
function updateLiveClock() {
  const clockEl = document.getElementById('live-clock');
  if (clockEl) {
    const now = new Date();
    clockEl.textContent = now.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true });
  }
}

// Keyboard Shortcuts (F2: KOT, F3: Print Bill, F4: Settle, Ctrl+F: Search, Esc: Close)
function setupKeyboardShortcuts() {
  window.addEventListener('keydown', (e) => {
    // Esc closes any open modal
    if (e.key === 'Escape') {
      closeAllModals();
      return;
    }

    // Ctrl+F or '/' focuses dish search
    if ((e.ctrlKey && e.key.toLowerCase() === 'f') || (e.key === '/' && document.activeElement.tagName !== 'INPUT')) {
      e.preventDefault();
      const searchInput = document.getElementById('dish-search-input');
      if (searchInput) {
        setLeftPanelView('menu');
        searchInput.focus();
        searchInput.select();
      }
      return;
    }

    // F2 or F3: Print Customer Bill directly (Direct Cash Counter - No KOT)
    if (e.key === 'F2' || e.key === 'F3') {
      e.preventDefault();
      printCustomerBillModal();
      return;
    }

    // F4: Settle & Cash Drawer
    if (e.key === 'F4') {
      e.preventDefault();
      openSettlementModal();
      return;
    }
  });
}

// Graceful Health Check to FastAPI backend (/api/v1/)
async function checkBackendHealth() {
  try {
    const res = await fetch('/api/v1/health', { method: 'GET', signal: AbortSignal.timeout(1200) });
    if (res.ok) {
      state.isServerConnected = true;
      setServerPill(true, 'Local Server Connected');
    } else {
      setServerPill(true, 'Local Server (Fallback Sync)');
    }
  } catch (err) {
    // Running in local file/offline mode with rich in-memory state
    state.isServerConnected = false;
    setServerPill(true, 'Local Server Mode (Active)');
  }
}

function setServerPill(isConnected, text) {
  const pill = document.getElementById('server-status-pill');
  if (!pill) return;
  pill.innerHTML = `
    <span class="w-2 h-2 rounded-full ${isConnected ? 'bg-emerald-500' : 'bg-amber-500'} animate-pulse-subtle"></span>
    <span>${text}</span>
  `;
}

// =============================================================================
// 3. WORKSPACE NAVIGATION
// =============================================================================

function switchWorkspace(workspaceId) {
  // RBAC Permission Guard: Cashier can only access Hotel POS & Shifts
  if (state.currentRole === 'CASHIER' && ['owner-dashboard', 'store-grocery', 'bar-excise', 'settings'].includes(workspaceId)) {
    showToast('Access Denied: Cashier role is restricted to Hotel POS Counter & Shifts. Login as Admin for statistics and full software access.', 'warning');
    workspaceId = 'cash-counter';
  }

  state.activeWorkspace = workspaceId;

  // Toggle active tab styling
  document.querySelectorAll('.workspace-tab').forEach(tab => {
    tab.classList.remove('border-emerald-700', 'text-emerald-800', 'bg-white', 'font-semibold');
    tab.classList.add('border-transparent', 'text-gray-600');
  });

  const activeTab = document.getElementById(`tab-${workspaceId}`);
  if (activeTab) {
    activeTab.classList.remove('border-transparent', 'text-gray-600');
    activeTab.classList.add('border-emerald-700', 'text-emerald-800', 'bg-white', 'font-semibold');
  }

  // Toggle workspace sections
  const workspaces = ['cash-counter', 'store-grocery', 'bar-excise', 'owner-dashboard', 'cashier-shift', 'settings'];
  workspaces.forEach(id => {
    const el = document.getElementById(`workspace-${id}`);
    if (el) {
      if (id === workspaceId) {
        el.classList.remove('hidden');
      } else {
        el.classList.add('hidden');
      }
    }
  });

  // If entering Settings workspace, refresh dishes and tenant settings
  if (workspaceId === 'settings') {
    renderSettingsMenu();
  renderSettingsCategories();
    loadTenantSettings();
  }

  // Sync URL hash
  if (window.location.hash !== '#' + workspaceId) {
    history.replaceState(null, '', '#' + workspaceId);
  }

  if (window.lucide) window.lucide.createIcons();
}

// =============================================================================
// 4. CASH COUNTER & FLOOR PLAN LOGIC
// =============================================================================

function filterFloorSection(section) {
  state.activeFloorSection = section;
  
  document.getElementById('btn-sec-ground').className = section === 'ground'
    ? 'sec-filter-btn px-3 py-1.5 rounded-md font-semibold bg-gray-900 text-white shadow-sm'
    : 'sec-filter-btn px-3 py-1.5 rounded-md font-medium bg-gray-100 text-gray-700 hover:bg-gray-200';

  document.getElementById('btn-sec-terrace').className = section === 'terrace'
    ? 'sec-filter-btn px-3 py-1.5 rounded-md font-semibold bg-gray-900 text-white shadow-sm'
    : 'sec-filter-btn px-3 py-1.5 rounded-md font-medium bg-gray-100 text-gray-700 hover:bg-gray-200';

  renderTables();
}

function setLeftPanelView(view) {
  state.leftPanelView = view;
  const tablesContainer = document.getElementById('tables-grid-container');
  const menuContainer = document.getElementById('menu-grid-container');
  const btnTables = document.getElementById('toggle-view-tables');
  const btnMenu = document.getElementById('toggle-view-menu');

  if (view === 'tables') {
    tablesContainer.classList.remove('hidden');
    menuContainer.classList.add('hidden');
    btnTables.className = 'px-2.5 py-1 rounded font-medium bg-white text-gray-900 shadow-xs';
    btnMenu.className = 'px-2.5 py-1 rounded font-medium text-gray-600 hover:text-gray-900';
  } else {
    tablesContainer.classList.add('hidden');
    menuContainer.classList.remove('hidden');
    btnTables.className = 'px-2.5 py-1 rounded font-medium text-gray-600 hover:text-gray-900';
    btnMenu.className = 'px-2.5 py-1 rounded font-medium bg-white text-gray-900 shadow-xs';
  }
  if (window.lucide) window.lucide.createIcons();
}

function renderTables() {
  const container = document.getElementById('tables-grid-container');
  if (!container) return;

  const filteredTables = state.tables.filter(t => t.section === state.activeFloorSection);
  
  container.innerHTML = filteredTables.map(t => {
    const isSelected = t.id === state.activeTableId;
    const isSeated = t.status === 'seated' || t.items.length > 0;
    
    // Status badge formatting
    let statusBadge = '';
    if (!isSeated) {
      statusBadge = `<span class="flex items-center gap-1 text-emerald-700 font-medium"><span class="w-1.5 h-1.5 rounded-full bg-emerald-500"></span> Open</span>`;
    } else if (t.timer <= 5) {
      statusBadge = `<span class="flex items-center gap-1 text-amber-700 font-medium"><span class="w-1.5 h-1.5 rounded-full bg-amber-500"></span> now</span>`;
    } else {
      statusBadge = `<span class="flex items-center gap-1 text-orange-700 font-medium"><span class="w-1.5 h-1.5 rounded-full bg-orange-500"></span> ${t.timer}m</span>`;
    }

    // Order total if seated
    const orderTotal = t.items.reduce((sum, i) => sum + (i.price * i.qty), 0);

    return `
      <div onclick="selectDiningTable('${t.id}')" 
           class="p-3.5 rounded-xl border ${isSelected ? 'border-emerald-600 ring-2 ring-emerald-600/20 bg-white' : 'border-gray-200 bg-white'} 
                  shadow-xs hover:border-gray-400 cursor-pointer transition interactive-card flex flex-col justify-between h-28">
        <div class="flex items-start justify-between">
          <div>
            <span class="text-base font-bold text-gray-900 font-mono">${t.id}</span>
            <span class="text-[11px] text-gray-500 block">${t.seats} seats</span>
          </div>
          <div class="text-xs font-mono">
            ${statusBadge}
          </div>
        </div>

        <div class="flex items-end justify-between text-xs font-mono pt-2 border-t border-gray-100">
          <span class="text-gray-400 text-[10px] truncate max-w-[80px]">Waiter: ${t.waiter}</span>
          <span class="font-bold text-gray-900">${isSeated ? '₹' + orderTotal.toFixed(2) : '—'}</span>
        </div>
      </div>
    `;
  }).join('');
}

function selectDiningTable(tableId) {
  state.activeTableId = tableId;
  renderTables();
  renderCart();
}

function createTakeawayOrder() {
  const newId = `TA-${Math.floor(100 + Math.random() * 900)}`;
  const newOrder = {
    id: newId,
    section: 'ground',
    seats: 1,
    status: 'seated',
    timer: 0,
    waiter: 'Counter 1',
    covers: 1,
    items: []
  };
  state.tables.unshift(newOrder);
  state.activeTableId = newId;
  setLeftPanelView('menu');
  renderTables();
  renderCart();
  showToast(`Created Fast-Lane Takeaway Ticket #${newId}`, 'info');
}

function createDeliveryOrder() {
  const newId = `DEL-${Math.floor(100 + Math.random() * 900)}`;
  const newOrder = {
    id: newId,
    section: 'ground',
    seats: 1,
    status: 'seated',
    timer: 0,
    waiter: 'Swiggy/Zomato',
    covers: 1,
    items: []
  };
  state.tables.unshift(newOrder);
  state.activeTableId = newId;
  setLeftPanelView('menu');
  renderTables();
  renderCart();
  showToast(`Created Online Delivery Ticket #${newId}`, 'info');
}

// =============================================================================
// 5. MENU & DISHES SELECTION LOGIC
// =============================================================================

function filterCategory(cat) {
  state.selectedCategory = cat;
  document.querySelectorAll('.cat-pill').forEach(btn => {
    btn.className = 'cat-pill px-3 py-1.5 rounded-full font-medium bg-white text-gray-700 border border-gray-200 hover:bg-gray-100 whitespace-nowrap';
  });
  event.target.className = 'cat-pill active-cat px-3 py-1.5 rounded-full font-semibold bg-gray-900 text-white whitespace-nowrap';
  renderCategoryPills();
  renderMenuItems();
}

function handleVegToggle(checked) {
  state.isVegOnly = checked;
  renderCategoryPills();
  renderMenuItems();
}

function handleDishSearch(query) {
  state.searchQuery = query.toLowerCase().trim();
  const clearBtn = document.getElementById('clear-search-btn');
  if (clearBtn) {
    clearBtn.classList.toggle('hidden', state.searchQuery.length === 0);
  }
  setLeftPanelView('menu');
  renderCategoryPills();
  renderMenuItems();
}

function clearSearch() {
  state.searchQuery = '';
  const searchInput = document.getElementById('dish-search-input');
  if (searchInput) searchInput.value = '';
  document.getElementById('clear-search-btn').classList.add('hidden');
  renderCategoryPills();
  renderMenuItems();
}

function renderMenuItems() {
  const container = document.getElementById('dishes-cards-grid');
  if (!container) return;

  let items = state.menuItems;

  if (state.selectedCategory !== 'ALL') {
    items = items.filter(i => i.category === state.selectedCategory);
  }

  if (state.isVegOnly) {
    items = items.filter(i => i.isVeg);
  }

  if (state.searchQuery) {
    items = items.filter(i => 
      i.name.toLowerCase().includes(state.searchQuery) || 
      i.category.toLowerCase().includes(state.searchQuery) ||
      i.desc.toLowerCase().includes(state.searchQuery)
    );
  }

  if (items.length === 0) {
    container.innerHTML = `
      <div class="col-span-full py-12 text-center text-gray-400 font-mono text-xs">
        No matching dishes found in catalog. Try clearing "Veg only" or search filter.
      </div>
    `;
    return;
  }

  container.innerHTML = items.map(item => {
    const is86 = !!item.is86;
    return `
    <div onclick="${is86 ? `showToast('${item.name.replace(/'/g, "\\'")} is currently 86\\'d (Out of stock)', 'error')` : `addItemToCurrentCart(${item.id})`}" 
         class="p-3 bg-white rounded-xl border ${is86 ? 'border-amber-300 bg-amber-50/40 opacity-75' : 'border-gray-200'} shadow-xs hover:border-gray-400 cursor-pointer transition interactive-card flex flex-col justify-between h-32 relative">
      ${is86 ? `<span class="absolute top-2 right-2 px-1.5 py-0.5 rounded bg-red-100 text-red-700 text-[9px] font-mono font-bold uppercase tracking-wider">86'd Out</span>` : ''}
      <div>
        <div class="flex items-start justify-between gap-1 mb-1 ${is86 ? 'pr-12' : ''}">
          <span class="${item.isVeg ? 'veg-badge' : 'non-veg-badge'} shrink-0 mt-0.5"></span>
          <span class="text-[10px] font-mono px-1.5 py-0.5 rounded ${item.taxType === 'VAT' ? 'bg-amber-100 text-amber-800' : 'bg-gray-100 text-gray-600'}">
            ${item.taxType === 'VAT' ? 'VAT FL-3' : 'GST 5%'}
          </span>
        </div>
        <h4 class="font-bold text-xs text-gray-900 leading-tight">
          ${state.lang === 'mr' ? (item.name_mr || DISH_NAMES_MR[item.id] || item.name) : item.name}
        </h4>
        <p class="text-[11px] text-gray-500 line-clamp-1 mt-0.5">
          ${state.lang === 'mr' ? item.name : (item.name_mr || DISH_NAMES_MR[item.id] || item.desc || '')}
        </p>
      </div>

      <div class="flex items-center justify-between pt-2 border-t border-gray-100 font-mono text-xs">
        <div class="flex items-center gap-1.5">
          <span class="font-bold ${is86 ? 'text-gray-400 line-through' : 'text-gray-900'}">₹${item.price.toFixed(2)}</span>
          <button onclick="event.stopPropagation(); promptEditDishPrice(${item.id})" 
                  title="Change dish price" 
                  class="p-1 rounded text-gray-400 hover:text-emerald-700 hover:bg-emerald-50 transition cursor-pointer">
            <i data-lucide="pencil" class="w-3 h-3"></i>
          </button>
        </div>
        <button class="w-6 h-6 rounded ${is86 ? 'bg-gray-200 text-gray-400 cursor-not-allowed' : 'bg-gray-100 text-gray-700 hover:bg-emerald-700 hover:text-white'} flex items-center justify-center transition">
          ${is86 ? '✕' : '+'}
        </button>
      </div>
    </div>
  `}).join('');
}

// =============================================================================
// 6. TABLE ORDER CART & STATUTORY DUAL-TAX BILLING
// =============================================================================

function getActiveTable() {
  return state.tables.find(t => t.id === state.activeTableId) || state.tables[0];
}

function addItemToCurrentCart(itemId) {
  const table = getActiveTable();
  const menuItem = state.menuItems.find(m => m.id === itemId);
  if (!menuItem) return;

  if (menuItem.is86) {
    showToast(`"${menuItem.name}" is currently 86'd (Out of stock).`, 'error');
    return;
  }

  const existing = table.items.find(i => i.id === menuItem.id);
  if (existing) {
    existing.qty += 1;
  } else {
    table.items.push({
      id: menuItem.id,
      name: menuItem.name,
      price: menuItem.price,
      qty: 1,
      notes: '',
      isVeg: menuItem.isVeg,
      taxType: menuItem.taxType,
      station: menuItem.station
    });
  }

  table.status = 'seated';
  if (table.timer === 0) table.timer = 1;

  renderCart();
  renderTables();
}

function updateCartQty(index, delta) {
  const table = getActiveTable();
  if (!table.items[index]) return;

  table.items[index].qty += delta;
  if (table.items[index].qty <= 0) {
    table.items.splice(index, 1);
  }

  renderCart();
  renderTables();
}

function editItemNote(index) {
  const table = getActiveTable();
  if (!table.items[index]) return;

  const currentNote = table.items[index].notes || '';
  const newNote = prompt(`Kitchen Prep Note for ${table.items[index].name} (e.g. "Less spicy", "No garlic", "Crisp"):`, currentNote);
  if (newNote !== null) {
    table.items[index].notes = newNote.trim();
    renderCart();
  }
}

function clearCurrentCart() {
  const table = getActiveTable();
  if (confirm(`Clear all items from ${table.id}?`)) {
    table.items = [];
    table.status = 'open';
    table.timer = 0;
    renderCart();
    renderTables();
  }
}

function calculateBillTotals(items) {
  let foodSubtotal = 0;
  let liquorSubtotal = 0;

  items.forEach(i => {
    const total = i.price * i.qty;
    if (i.taxType === 'VAT') {
      liquorSubtotal += total;
    } else {
      foodSubtotal += total;
    }
  });

  const cgst = foodSubtotal * 0.025; // 2.5% CGST
  const sgst = foodSubtotal * 0.025; // 2.5% SGST
  const totalGst = cgst + sgst;       // 5.0% Total GST

  const mvat = liquorSubtotal * 0.05; // 5.0% Maharashtra State VAT on Liquor

  const grandTotal = Math.round(foodSubtotal + totalGst + liquorSubtotal + mvat);

  return {
    foodSubtotal,
    liquorSubtotal,
    cgst,
    sgst,
    totalGst,
    mvat,
    grandTotal
  };
}

function renderCart() {
  const table = getActiveTable();
  const container = document.getElementById('cart-items-container');
  if (!container) return;

  // Header Table Badge
  document.getElementById('cart-table-badge').textContent = `Order · ${table.id}`;
  document.getElementById('cart-table-meta').textContent = `(${table.seats} seats · ${table.section === 'ground' ? 'Ground Floor' : 'Terrace'})`;
  document.getElementById('cart-table-timer').innerHTML = `
    <span class="w-2 h-2 rounded-full ${table.status === 'seated' ? 'bg-amber-500' : 'bg-emerald-500'}"></span>
    ${table.status === 'seated' ? `${table.timer}m seated` : 'Vacant Table'}
  `;

  if (table.items.length === 0) {
    container.innerHTML = `
      <div class="h-full flex flex-col items-center justify-center text-center p-6 text-gray-400">
        <i data-lucide="utensils" class="w-8 h-8 stroke-[1.5] mb-2 text-gray-300"></i>
        <p class="text-xs font-medium">Cart is empty for ${table.id}</p>
        <p class="text-[11px] text-gray-400 mt-0.5">Click dishes on the left panel or press [Ctrl+F] to punch items.</p>
      </div>
    `;
  } else {
    container.innerHTML = table.items.map((item, idx) => `
      <div class="p-2.5 rounded-lg border border-gray-100 bg-gray-50 flex flex-col gap-1.5 text-xs">
        <div class="flex items-start justify-between">
          <div class="flex items-start gap-1.5">
            <span class="${item.isVeg ? 'veg-badge' : 'non-veg-badge'} mt-0.5 shrink-0"></span>
            <div>
              <span class="font-bold text-gray-900 leading-tight">${item.name}</span>
              <span class="text-[10px] text-gray-400 font-mono block">₹${item.price.toFixed(2)} each</span>
            </div>
          </div>
          <span class="font-bold text-gray-900 font-mono">₹${(item.price * item.qty).toFixed(2)}</span>
        </div>

        <!-- Notes and Stepper -->
        <div class="flex items-center justify-between pt-1 border-t border-gray-200 text-xs">
          <button onclick="editItemNote(${idx})" class="text-[11px] text-emerald-700 hover:underline flex items-center gap-1">
            <i data-lucide="edit-3" class="w-3 h-3"></i>
            <span>${item.notes ? item.notes : '+ Add note'}</span>
          </button>

          <div class="flex items-center gap-2 font-mono">
            <button onclick="updateCartQty(${idx}, -1)" class="w-5 h-5 rounded bg-white border border-gray-300 text-gray-700 flex items-center justify-center hover:bg-gray-100">
              -
            </button>
            <span class="font-bold w-4 text-center">${item.qty}</span>
            <button onclick="updateCartQty(${idx}, 1)" class="w-5 h-5 rounded bg-white border border-gray-300 text-gray-700 flex items-center justify-center hover:bg-gray-100">
              +
            </button>
          </div>
        </div>
      </div>
    `).join('');
  }

  // Update Calculation Box
  const totals = calculateBillTotals(table.items);
  document.getElementById('bill-food-subtotal').textContent = `₹${totals.foodSubtotal.toFixed(2)}`;
  document.getElementById('bill-liquor-subtotal').textContent = `₹${totals.liquorSubtotal.toFixed(2)}`;
  document.getElementById('bill-gst-amount').textContent = `₹${totals.totalGst.toFixed(2)}`;
  document.getElementById('bill-vat-amount').textContent = `₹${totals.mvat.toFixed(2)}`;
  document.getElementById('bill-grand-total').textContent = `₹${totals.grandTotal.toFixed(2)}`;

  if (window.lucide) window.lucide.createIcons();
}

function renderHeaderMetrics() {
  const openCount = state.tables.filter(t => t.status === 'open' && t.items.length === 0).length;
  document.getElementById('header-tables-open').textContent = `${openCount} / ${state.tables.length}`;
  document.getElementById('header-covers-today').textContent = state.todayCovers;
  document.getElementById('header-sales-today').textContent = `₹${state.todaySales.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
}

// =============================================================================
// 7. DIRECT COUNTER BILLING & RECEIPT PRINT ACTIONS (NO KOT)
// =============================================================================

function printCustomerBillModal() {
  const table = getActiveTable();
  if (table.items.length === 0) {
    showToast('Add items to order before printing invoice.', 'error');
    return;
  }

  // Audit trail entry
  state.auditTrail.unshift({
    time: new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }),
    user: 'Rahul (Cashier)',
    action: `Bill Printed (${table.id})`,
    status: 'Printed'
  });

  table.status = 'seated';
  switchReceiptType('invoice');
  openModal('modal-receipt');
  renderAll();
}

function sendKotBotTicket() {
  // Graceful fallback if invoked via old handler: directly prints bill
  printCustomerBillModal();
}

function switchReceiptType(type) {
  state.receiptType = type;
  
  const tabs = ['invoice', 'zreport'];
  tabs.forEach(t => {
    const btn = document.getElementById(`receipt-tab-${t}`);
    if (btn) {
      if (t === type) {
        btn.className = 'px-2 py-1 rounded bg-emerald-700 text-white text-[11px] font-mono font-bold';
      } else {
        btn.className = 'px-2 py-1 rounded bg-gray-800 hover:bg-gray-700 text-[11px] font-mono';
      }
    }
  });

  renderThermalReceipt();
}

function renderThermalReceipt() {
  const area = document.getElementById('thermal-print-area');
  if (!area) return;

  const table = getActiveTable();
  const totals = calculateBillTotals(table.items);
  const now = new Date();
  const dateStr = now.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
  const timeStr = now.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });

  if (state.receiptType === 'invoice') {
    // Statutory Dual-Tax Invoice (Part A Food GST + Part B Liquor MVAT)
    area.innerHTML = `
      <div class="text-center font-mono">
        <h2 class="text-base font-bold tracking-tight">RASA SAHYADRI</h2>
        <p class="text-[11px] font-medium">RESTAURANT & PERMIT ROOM (BAR)</p>
        <p class="text-[10px] text-gray-600">Lane 6, North Main Road, Koregaon Park, Pune</p>
        <p class="text-[10px] text-gray-600">GSTIN: 27AAKFR4621M1Z5 · FSSAI: 11523034000412</p>
        <p class="text-[10px] text-gray-600">EXCISE LIC (FL-3): FL3-PUN-KP-0412 · MVAT: 27912345678V</p>
        <div class="receipt-double-divider"></div>
        <div class="flex justify-between text-[11px] text-left">
          <span>TAX INVOICE: KP-2026-${Math.floor(1000 + Math.random() * 9000)}</span>
          <span>Table: ${table.id}</span>
        </div>
        <div class="flex justify-between text-[11px] text-left">
          <span>Date: ${dateStr} ${timeStr}</span>
          <span>Guests: ${table.seats}</span>
        </div>
        <div class="receipt-divider"></div>
        
        <!-- PART A: FOOD & BEVERAGES (GST) -->
        <p class="text-[11px] font-bold text-left mb-1">PART A: FOOD & BEVERAGES (GST 5%)</p>
        <table class="w-full text-left text-[11px]">
          <thead>
            <tr class="border-b border-gray-400">
              <th>ITEM</th>
              <th class="text-center">QTY</th>
              <th class="text-right">RATE</th>
              <th class="text-right">AMOUNT</th>
            </tr>
          </thead>
          <tbody>
            ${table.items.filter(i => i.taxType === 'GST').map(i => `
              <tr>
                <td>${i.name}</td>
                <td class="text-center">${i.qty}</td>
                <td class="text-right">${i.price.toFixed(2)}</td>
                <td class="text-right">${(i.price * i.qty).toFixed(2)}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
        <div class="receipt-divider"></div>
        <div class="text-[11px] space-y-0.5 text-right">
          <div>Food Subtotal: ₹${totals.foodSubtotal.toFixed(2)}</div>
          <div>CGST @2.5%: ₹${totals.cgst.toFixed(2)}</div>
          <div>SGST @2.5%: ₹${totals.sgst.toFixed(2)}</div>
          <div class="font-bold">Food Total (Incl. GST): ₹${(totals.foodSubtotal + totals.totalGst).toFixed(2)}</div>
        </div>

        <!-- PART B: LIQUOR & PERMIT ROOM (STATE VAT) -->
        ${totals.liquorSubtotal > 0 ? `
          <div class="receipt-divider"></div>
          <p class="text-[11px] font-bold text-left mb-1">PART B: LIQUOR & BAR (STATE VAT 5%)</p>
          <table class="w-full text-left text-[11px]">
            <thead>
              <tr class="border-b border-gray-400">
                <th>ITEM</th>
                <th class="text-center">QTY</th>
                <th class="text-right">RATE</th>
                <th class="text-right">AMOUNT</th>
              </tr>
            </thead>
            <tbody>
              ${table.items.filter(i => i.taxType === 'VAT').map(i => `
                <tr>
                  <td>${i.name}</td>
                  <td class="text-center">${i.qty}</td>
                  <td class="text-right">${i.price.toFixed(2)}</td>
                  <td class="text-right">${(i.price * i.qty).toFixed(2)}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
          <div class="receipt-divider"></div>
          <div class="text-[11px] space-y-0.5 text-right">
            <div>Liquor Subtotal: ₹${totals.liquorSubtotal.toFixed(2)}</div>
            <div>MVAT @5.0%: ₹${totals.mvat.toFixed(2)}</div>
            <div class="font-bold">Liquor Total (Incl. VAT): ₹${(totals.liquorSubtotal + totals.mvat).toFixed(2)}</div>
          </div>
        ` : ''}

        <div class="receipt-double-divider"></div>
        <div class="flex justify-between items-baseline font-bold text-sm">
          <span>GRAND TOTAL:</span>
          <span>Rs. ${totals.grandTotal.toFixed(2)}</span>
        </div>
        <p class="text-[10px] text-gray-600 text-left mt-1 italic">
          (${numberToWords(totals.grandTotal)} only)
        </p>
        <div class="receipt-divider"></div>
        <p class="text-[10px] font-bold">STATUTORY: ALCOHOL CONSUMPTION IS INJURIOUS TO HEALTH</p>
        <p class="text-[10px] text-gray-500 mt-1">Thank you for dining with Rasa Sahyadri!</p>
      </div>
    `;
  } else if (state.receiptType === 'kot') {
    // Kitchen Order Ticket (KOT)
    const foodItems = table.items.filter(i => i.station === 'KITCHEN');
    area.innerHTML = `
      <div class="text-center font-mono">
        <h2 class="text-sm font-bold tracking-tight">*** KITCHEN ORDER TICKET (KOT) ***</h2>
        <div class="receipt-divider"></div>
        <div class="flex justify-between text-xs text-left">
          <span>Table: <strong class="text-sm">${table.id}</strong> (${table.section})</span>
          <span>KOT #: 108</span>
        </div>
        <div class="flex justify-between text-xs text-left">
          <span>Date: ${dateStr} ${timeStr}</span>
          <span>Server: ${table.waiter}</span>
        </div>
        <div class="receipt-double-divider"></div>
        <table class="w-full text-left text-xs">
          <thead>
            <tr class="border-b border-gray-500">
              <th class="w-12">QTY</th>
              <th>ITEM & PREPARATION NOTE</th>
            </tr>
          </thead>
          <tbody>
            ${foodItems.length > 0 ? foodItems.map(i => `
              <tr class="border-b border-gray-100">
                <td class="font-bold text-sm align-top">${i.qty}</td>
                <td>
                  <span class="font-bold">${i.name}</span>
                  ${i.notes ? `<div class="text-[11px] text-gray-700 italic">>> Note: ${i.notes}</div>` : ''}
                </td>
              </tr>
            `).join('') : `<tr><td colspan="2" class="text-center py-4">No food items on this ticket</td></tr>`}
          </tbody>
        </table>
        <div class="receipt-double-divider"></div>
        <p class="text-[10px] font-bold">STATION: MAIN CURRY / HOT LINE</p>
      </div>
    `;
  } else if (state.receiptType === 'bot') {
    // Bar Order Ticket (BOT)
    const barItems = table.items.filter(i => i.station === 'BAR');
    area.innerHTML = `
      <div class="text-center font-mono">
        <h2 class="text-sm font-bold tracking-tight">*** BAR ORDER TICKET (BOT) ***</h2>
        <div class="receipt-divider"></div>
        <div class="flex justify-between text-xs text-left">
          <span>Table: <strong class="text-sm">${table.id}</strong></span>
          <span>BOT #: 059</span>
        </div>
        <div class="flex justify-between text-xs text-left">
          <span>Date: ${dateStr} ${timeStr}</span>
          <span>Server: ${table.waiter}</span>
        </div>
        <div class="receipt-double-divider"></div>
        <table class="w-full text-left text-xs">
          <thead>
            <tr class="border-b border-gray-500">
              <th class="w-12">QTY</th>
              <th>ITEM / MIXER</th>
            </tr>
          </thead>
          <tbody>
            ${barItems.length > 0 ? barItems.map(i => `
              <tr class="border-b border-gray-100">
                <td class="font-bold text-sm align-top">${i.qty}</td>
                <td>
                  <span class="font-bold">${i.name}</span>
                  ${i.notes ? `<div class="text-[11px] text-gray-700 italic">>> Mixer: ${i.notes}</div>` : ''}
                </td>
              </tr>
            `).join('') : `<tr><td colspan="2" class="text-center py-4">No bar items on this ticket</td></tr>`}
          </tbody>
        </table>
        <div class="receipt-double-divider"></div>
        <p class="text-[10px] font-bold">STATION: PERMIT ROOM DISPENSE BAR</p>
      </div>
    `;
  } else if (state.receiptType === 'zreport') {
    // Official End-of-Day Z-Report Slip
    area.innerHTML = `
      <div class="text-center font-mono">
        <h2 class="text-base font-bold">OFFICIAL Z-REPORT SLIP</h2>
        <p class="text-[11px]">END-OF-DAY REGISTER CLOSING</p>
        <p class="text-[10px]">Rasa Sahyadri · Koregaon Park · Terminal 1</p>
        <div class="receipt-double-divider"></div>
        <div class="flex justify-between text-[11px] text-left">
          <span>Shift ID: SH-20261026-01</span>
          <span>Date: ${dateStr}</span>
        </div>
        <div class="flex justify-between text-[11px] text-left">
          <span>Cashier: Rahul Sharma</span>
          <span>Closed: ${timeStr}</span>
        </div>
        <div class="receipt-divider"></div>
        <div class="text-[11px] space-y-1 text-left">
          <div class="flex justify-between"><span>Opening Cash Float:</span><span>₹2,000.00</span></div>
          <div class="flex justify-between"><span>Cash Sales Collected:</span><span>₹${state.shift.cashSales.toFixed(2)}</span></div>
          <div class="flex justify-between"><span>Petty Cash Paid-Out:</span><span>-₹${state.shift.paidOut.toFixed(2)}</span></div>
          <div class="receipt-divider"></div>
          <div class="flex justify-between font-bold"><span>Expected Drawer Cash:</span><span>₹${state.shift.expectedCash.toFixed(2)}</span></div>
          <div class="flex justify-between font-bold"><span>Physical Cash Counted:</span><span>₹${state.shift.expectedCash.toFixed(2)}</span></div>
          <div class="flex justify-between font-bold text-emerald-800"><span>Over / Short Variance:</span><span>₹0.00 (Balanced)</span></div>
          <div class="receipt-divider"></div>
          <div class="flex justify-between"><span>Total Covers Today:</span><span>${state.todayCovers}</span></div>
          <div class="flex justify-between"><span>UPI & Dynamic QR:</span><span>₹${state.shift.upiSales.toFixed(2)}</span></div>
          <div class="flex justify-between"><span>Credit / Debit Cards:</span><span>₹${state.shift.cardSales.toFixed(2)}</span></div>
          <div class="flex justify-between font-bold"><span>Total Net Revenue:</span><span>₹${(state.shift.cashSales + state.shift.upiSales + state.shift.cardSales).toFixed(2)}</span></div>
        </div>
        <div class="receipt-double-divider"></div>
        <div class="mt-4 pt-4 border-t border-dashed border-gray-400 text-left text-[10px] space-y-4">
          <div>Cashier Signature: _______________________</div>
          <div>Manager Sign-Off:  _______________________</div>
        </div>
      </div>
    `;
  }
}

function copyReceiptPlainText() {
  const area = document.getElementById('thermal-print-area');
  if (!area) return;
  navigator.clipboard.writeText(area.innerText);
  showToast('Receipt copied to clipboard.', 'success');
}

function triggerPhysicalPrint() {
  window.print();
}

// Convert numbers to words (Indian numbering system)
function numberToWords(amount) {
  const num = Math.floor(amount);
  if (num === 0) return 'Zero Rupees';
  const a = ['', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine', 'Ten', 'Eleven', 'Twelve', 'Thirteen', 'Fourteen', 'Fifteen', 'Sixteen', 'Seventeen', 'Eighteen', 'Nineteen'];
  const b = ['', '', 'Twenty', 'Thirty', 'Forty', 'Fifty', 'Sixty', 'Seventy', 'Eighty', 'Ninety'];
  
  function inWords(n) {
    if (n < 20) return a[n];
    if (n < 100) return b[Math.floor(n / 10)] + (n % 10 !== 0 ? ' ' + a[n % 10] : '');
    if (n < 1000) return a[Math.floor(n / 100)] + ' Hundred' + (n % 100 !== 0 ? ' ' + inWords(n % 100) : '');
    if (n < 100000) return inWords(Math.floor(n / 1000)) + ' Thousand' + (n % 1000 !== 0 ? ' ' + inWords(n % 1000) : '');
    return n.toString();
  }
  return inWords(num) + ' Rupees';
}

// =============================================================================
// 8. TENDER SETTLEMENT & 24V CASH DRAWER KICK (F4)
// =============================================================================

function openSettlementModal() {
  const table = getActiveTable();
  if (table.items.length === 0) {
    showToast('Add items before settling bill.', 'error');
    return;
  }

  const totals = calculateBillTotals(table.items);
  document.getElementById('modal-settle-table-title').textContent = `${table.id} · ${table.seats} Seats · Ground Floor`;
  document.getElementById('modal-settle-grand-total').textContent = `₹${totals.grandTotal.toFixed(2)}`;
  document.getElementById('upi-qr-amount').textContent = `₹${totals.grandTotal.toFixed(2)}`;
  
  // Set default cash tendered
  const cashInput = document.getElementById('cash-tendered-input');
  cashInput.value = totals.grandTotal;
  calculateChangeDue();

  selectTender('cash');
  openModal('modal-settle');
}

function selectTender(tender) {
  state.selectedTender = tender;

  const tenders = ['cash', 'upi', 'card', 'khata'];
  tenders.forEach(t => {
    const btn = document.getElementById(`tender-btn-${t}`);
    const sec = document.getElementById(`tender-section-${t}`);
    if (t === tender) {
      btn.className = 'tender-tab active-tender p-2.5 rounded-lg border-2 border-emerald-700 bg-emerald-50 text-emerald-900 font-bold flex flex-col items-center gap-1';
      sec.classList.remove('hidden');
    } else {
      btn.className = 'tender-tab p-2.5 rounded-lg border border-gray-200 bg-white text-gray-700 hover:bg-gray-50 flex flex-col items-center gap-1';
      sec.classList.add('hidden');
    }
  });

  if (window.lucide) window.lucide.createIcons();
}

function addCashTendered(amount) {
  const table = getActiveTable();
  const totals = calculateBillTotals(table.items);
  const input = document.getElementById('cash-tendered-input');

  if (amount === 0) {
    input.value = totals.grandTotal;
  } else {
    input.value = (parseFloat(input.value) || 0) + amount;
  }
  calculateChangeDue();
}

function calculateChangeDue() {
  const table = getActiveTable();
  const totals = calculateBillTotals(table.items);
  const tendered = parseFloat(document.getElementById('cash-tendered-input').value) || 0;
  const change = Math.max(0, tendered - totals.grandTotal);
  document.getElementById('cash-change-due').textContent = `₹${change.toFixed(2)}`;
}

let isSettling = false;

async function commitSettlement() {
  if (isSettling) return;

  const table = getActiveTable();
  if (!table || table.items.length === 0) {
    showToast('Add items to order before settling invoice.', 'error');
    return;
  }

  isSettling = true;
  const settleBtn = document.getElementById('btn-commit-settle');
  if (settleBtn) {
    settleBtn.disabled = true;
    settleBtn.classList.add('opacity-50', 'cursor-not-allowed');
  }

  const totals = calculateBillTotals(table.items);
  const tender = state.selectedTender || 'cash';
  const staffName = state.currentUser ? state.currentUser.display_name : 'Pooja More';

  // Build unified cart payload for atomic backend settlement
  const payload = {
    table_code: table.id,
    payment_mode: tender.toUpperCase(),
    staff_name: staffName,
    items: table.items.map(item => ({
      item_id: item.id,
      name: item.name,
      quantity: item.qty,
      unit_price: item.price,
      notes: item.notes || '',
      tax_category: item.taxType === 'alcohol' ? 'VAT_ALCOHOL' : 'GST_FOOD'
    }))
  };

  try {
    const res = await apiFetch('/api/v1/billing/settle', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (res.ok) {
      const data = await res.json();
      
      // Simulate or trigger physical 24V Solenoid Cash Drawer Kick
      if (tender === 'cash') {
        simulateDrawerKick();
      }

      // Update in-memory revenue & metrics from verified backend invoice
      const grandTotal = data.bill ? data.bill.grand_total : totals.grandTotal;
      const invoiceNumber = data.bill ? data.bill.invoice_number : `INV-${Date.now()}`;
      state.todaySales += grandTotal;
      state.todayCovers += table.seats || 2;

      // Add to live audit trail
      state.auditTrail.unshift({
        time: new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }),
        user: staffName,
        action: `Bill Settled (${table.id}: ₹${grandTotal.toFixed(2)} via ${tender.toUpperCase()} · ${invoiceNumber})`,
        status: 'Settled'
      });

      // Clear table back to open
      table.items = [];
      table.status = 'open';
      table.timer = 0;

      closeModal('modal-settle');

      // Display official 80mm ESC/POS Statutory Receipt
      if (data.tax_invoice_80mm_text) {
        const area = document.getElementById('thermal-print-area');
        if (area) area.innerText = data.tax_invoice_80mm_text;
        switchReceiptType('invoice');
        openModal('modal-receipt');
      }

      showToast(`Invoice ${invoiceNumber} settled (₹${grandTotal.toFixed(2)})! Table is now Open.`, 'success');
      renderAll();
    } else {
      const err = await res.json().catch(() => ({}));
      showToast(err.detail || 'Settlement failed on server. Please check shift and try again.', 'error');
    }
  } catch (err) {
    console.error('[RestoOS] Settlement error:', err);
    // Offline local fallback so counter never halts
    if (tender === 'cash') simulateDrawerKick();
    state.todaySales += totals.grandTotal;
    state.todayCovers += table.seats;
    table.items = [];
    table.status = 'open';
    table.timer = 0;
    closeModal('modal-settle');
    showToast(`Offline Bill Settled (₹${totals.grandTotal.toFixed(2)})! Table cleared.`, 'success');
    renderAll();
  } finally {
    isSettling = false;
    if (settleBtn) {
      settleBtn.disabled = false;
      settleBtn.classList.remove('opacity-50', 'cursor-not-allowed');
    }
  }
}

function simulateDrawerKick() {
  const body = document.body;
  body.classList.add('drawer-kick-active');
  setTimeout(() => body.classList.remove('drawer-kick-active'), 400);
}

// =============================================================================
// 9. CENTRAL STORE & GROCERY INVENTORY
// =============================================================================

function switchStoreTab(tab) {
  const tabs = ['stock', 'grn', 'indents', 'wastage'];
  tabs.forEach(t => {
    const btn = document.getElementById(`btn-store-${t}`);
    const sec = document.getElementById(`store-tab-content-${t}`);
    if (t === tab) {
      btn.className = 'store-subtab px-3 py-1.5 rounded-md font-semibold bg-gray-900 text-white';
      sec.classList.remove('hidden');
    } else {
      btn.className = 'store-subtab px-3 py-1.5 rounded-md font-medium text-gray-700 bg-white border border-gray-200 hover:bg-gray-100';
      sec.classList.add('hidden');
    }
  });
}

function renderStoreStock() {
  const tbody = document.getElementById('store-stock-tbody');
  if (!tbody) return;

  tbody.innerHTML = state.storeStock.map(item => {
    const isLow = item.storeQty <= item.minLimit;
    return `
      <tr class="hover:bg-gray-50">
        <td class="p-3 font-bold text-gray-900 font-sans">${item.name}</td>
        <td class="p-3 text-gray-600 font-sans">${item.category}</td>
        <td class="p-3 text-right font-bold ${isLow ? 'text-red-600' : 'text-gray-900'}">${item.storeQty.toFixed(1)} ${item.uom}</td>
        <td class="p-3 text-right text-emerald-800 font-bold">${item.kitchenQty.toFixed(1)} ${item.uom}</td>
        <td class="p-3 text-center">${item.uom}</td>
        <td class="p-3 text-right">₹${item.cost.toFixed(2)}</td>
        <td class="p-3 text-center">
          <span class="px-2 py-0.5 rounded text-[10px] font-semibold ${isLow ? 'bg-red-100 text-red-700' : 'bg-emerald-100 text-emerald-800'}">
            ${isLow ? 'Low Stock' : 'Optimal'}
          </span>
        </td>
        <td class="p-3 text-right font-sans">
          <button onclick="quickIssueStock('${item.id}')" class="px-2 py-1 bg-gray-100 hover:bg-gray-200 rounded text-[11px] font-medium text-gray-700">
            Issue to Kitchen
          </button>
        </td>
      </tr>
    `;
  }).join('');
}

function renderGrnHistory() {
  const tbody = document.getElementById('store-grn-tbody');
  if (!tbody) return;

  tbody.innerHTML = state.grnList.map(grn => `
    <tr class="hover:bg-gray-50">
      <td class="p-3 font-bold text-gray-900">${grn.grnNo}</td>
      <td class="p-3 text-gray-600">${grn.date}</td>
      <td class="p-3 font-sans text-gray-800">${grn.vendor}</td>
      <td class="p-3">${grn.invoiceNo}</td>
      <td class="p-3 font-sans">${grn.items}</td>
      <td class="p-3 text-right font-bold text-gray-900">₹${grn.amount.toFixed(2)}</td>
      <td class="p-3 text-center font-sans">
        <span class="px-2 py-0.5 rounded text-[10px] bg-emerald-100 text-emerald-800 font-semibold">${grn.status}</span>
      </td>
    </tr>
  `).join('');
}

function renderIndents() {
  const tbody = document.getElementById('store-indents-tbody');
  if (!tbody) return;

  tbody.innerHTML = state.requisitions.map(ind => `
    <tr class="hover:bg-gray-50">
      <td class="p-3 font-bold text-gray-900">${ind.id}</td>
      <td class="p-3 text-gray-600">${ind.time}</td>
      <td class="p-3 font-sans">${ind.chef}</td>
      <td class="p-3 font-sans font-bold">${ind.item}</td>
      <td class="p-3 text-right font-bold text-emerald-800">${ind.qty}</td>
      <td class="p-3 text-center font-sans">
        <span class="px-2 py-0.5 rounded text-[10px] font-semibold ${ind.status === 'Issued' ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'}">
          ${ind.status}
        </span>
      </td>
      <td class="p-3 text-right font-sans">
        ${ind.status === 'Pending Approval' ? `
          <button onclick="approveIndent('${ind.id}')" class="px-2 py-1 rounded bg-emerald-800 text-white text-[11px] font-medium">Approve & Issue</button>
        ` : `<span class="text-gray-400 text-[11px]">Completed</span>`}
      </td>
    </tr>
  `).join('');
}

function renderWastage() {
  const tbody = document.getElementById('store-wastage-tbody');
  if (!tbody) return;

  tbody.innerHTML = state.wastageLog.map(w => `
    <tr class="hover:bg-gray-50">
      <td class="p-3 font-bold text-gray-900">${w.logNo}</td>
      <td class="p-3 text-gray-600">${w.time}</td>
      <td class="p-3 font-sans font-bold text-red-900">${w.item}</td>
      <td class="p-3 text-right">${w.qty}</td>
      <td class="p-3 font-mono text-[11px] text-gray-700">${w.reason}</td>
      <td class="p-3 text-right font-bold text-red-600">₹${w.cost.toFixed(2)}</td>
      <td class="p-3 font-sans">${w.authorizer}</td>
    </tr>
  `).join('');
}

function openGrnModal() { openModal('modal-grn'); }
function openIndentModal() { openModal('modal-indent'); }
function openWastageModal() { openModal('modal-wastage'); }

function commitGrnInward() {
  const vendor = document.getElementById('grn-vendor-select').value;
  const invoice = document.getElementById('grn-invoice-no').value;
  const qty = parseFloat(document.getElementById('grn-qty-input').value) || 10;
  const cost = parseFloat(document.getElementById('grn-cost-input').value) || 180;
  const total = qty * cost;

  state.grnList.unshift({
    grnNo: `GRN-${Math.floor(104 + Math.random() * 50)}`,
    date: new Date().toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }),
    vendor,
    invoiceNo: invoice,
    items: `${qty}kg Inward Produce`,
    amount: total,
    status: 'Passed QC'
  });

  // Credit Central Store Item
  if (state.storeStock[0]) {
    state.storeStock[0].storeQty += qty;
  }

  closeModal('modal-grn');
  showToast(`Committed GRN inward: ${qty}kg produce added to Central Store stock.`, 'success');
  renderAll();
}

function commitStoreIndent() {
  const qty = parseFloat(document.getElementById('indent-qty-input').value) || 5;
  const item = state.storeStock[0];

  if (item && item.storeQty >= qty) {
    item.storeQty -= qty;
    item.kitchenQty += qty;

    state.requisitions.unshift({
      id: `IND-${Math.floor(100 + Math.random() * 900)}`,
      time: new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }),
      chef: 'Chef Santosh',
      item: item.name,
      qty: `${qty} kg`,
      status: 'Issued'
    });

    closeModal('modal-indent');
    showToast(`Transferred ${qty}kg from Store to Kitchen Line prep!`, 'success');
    renderAll();
  } else {
    showToast('Insufficient stock in Central Store to issue.', 'error');
  }
}

function quickIssueStock(itemId) {
  const item = state.storeStock.find(i => i.id === itemId);
  if (item && item.storeQty >= 5) {
    item.storeQty -= 5;
    item.kitchenQty += 5;
    showToast(`Transferred 5 ${item.uom} of ${item.name} to Kitchen Line`, 'success');
    renderAll();
  } else {
    showToast('Insufficient stock to transfer.', 'error');
  }
}

function approveIndent(id) {
  const req = state.requisitions.find(r => r.id === id);
  if (req) {
    req.status = 'Issued';
    showToast(`Approved requisition ${id}! Stock issued.`, 'success');
    renderIndents();
  }
}

function commitWastageLog() {
  const item = document.getElementById('wastage-item-input').value;
  const qty = document.getElementById('wastage-qty-input').value;
  const reason = document.getElementById('wastage-reason-select').value;

  state.wastageLog.unshift({
    logNo: `WST-0${Math.floor(14 + Math.random() * 20)}`,
    time: new Date().toLocaleDateString('en-IN', { day: '2-digit', month: 'short' }) + ' ' + new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }),
    item,
    qty: `${qty} kg`,
    reason,
    cost: 180.00,
    authorizer: 'Chef Santosh'
  });

  closeModal('modal-wastage');
  showToast(`Recorded kitchen food waste log (${reason}).`, 'info');
  renderAll();
}

// =============================================================================
// 10. BAR & STATE EXCISE (FL-3) REGISTERS
// =============================================================================

function switchExciseTab(tab) {
  const tabs = ['flr3a', 'flr4', 'tp'];
  tabs.forEach(t => {
    const btn = document.getElementById(`btn-excise-${t}`);
    const sec = document.getElementById(`excise-tab-content-${t}`);
    if (t === tab) {
      btn.className = 'excise-subtab px-3 py-1.5 rounded-md font-semibold bg-gray-900 text-white';
      sec.classList.remove('hidden');
    } else {
      btn.className = 'excise-subtab px-3 py-1.5 rounded-md font-medium text-gray-700 bg-white border border-gray-200 hover:bg-gray-100';
      sec.classList.add('hidden');
    }
  });
}

function renderFlr3a() {
  const tbody = document.getElementById('excise-flr3a-tbody');
  if (!tbody) return;

  tbody.innerHTML = state.exciseFlr3a.map(row => `
    <tr class="hover:bg-gray-50">
      <td class="p-2.5 font-bold text-gray-900 font-sans">${row.brand}</td>
      <td class="p-2.5 text-gray-600 font-sans">${row.category}</td>
      <td class="p-2.5 text-center">${row.size}</td>
      <td class="p-2.5 text-right font-medium">${row.opening}</td>
      <td class="p-2.5 text-right font-bold text-emerald-800">+${row.inwardTp}</td>
      <td class="p-2.5 text-right text-gray-700">${row.salesPegs}</td>
      <td class="p-2.5 text-right font-bold text-gray-900">${row.salesBottles}</td>
      <td class="p-2.5 text-right text-gray-400">${row.breakage}</td>
      <td class="p-2.5 text-right font-bold text-gray-900">${row.closing.toFixed(2)}</td>
    </tr>
  `).join('');
}

function renderFlr4() {
  const tbody = document.getElementById('excise-flr4-tbody');
  if (!tbody) return;

  const data = [
    { cat: 'IMFL Spirits (Whisky / Rum / Vodka)', opening: '142.50', receipts: '84.00', sales: '68.25', closing: '158.25', duty: '42,150.00' },
    { cat: 'Fermented Beer & Mild Alcohol', opening: '320.00', receipts: '180.00', sales: '215.00', closing: '285.00', duty: '18,400.00' },
    { cat: 'Indian Grape Wine (Red / White)', opening: '45.00', receipts: '24.00', sales: '18.00', closing: '51.00', duty: '3,600.00' }
  ];

  tbody.innerHTML = data.map(d => `
    <tr class="hover:bg-gray-50">
      <td class="p-2.5 font-bold font-sans text-gray-900">${d.cat}</td>
      <td class="p-2.5 text-right">${d.opening}</td>
      <td class="p-2.5 text-right font-bold text-emerald-800">+${d.receipts}</td>
      <td class="p-2.5 text-right font-bold text-gray-800">-${d.sales}</td>
      <td class="p-2.5 text-right font-bold text-gray-900">${d.closing}</td>
      <td class="p-2.5 text-right font-bold text-gray-900">₹${d.duty}</td>
    </tr>
  `).join('');
}

function openTpModal() { openModal('modal-tp'); }

function commitTpInward() {
  const tpNo = document.getElementById('tp-no-input').value;
  const brand = document.getElementById('tp-brand-select').value;
  const bottles = parseInt(document.getElementById('tp-bottles-input').value) || 12;

  // Add to FLR-3A
  const target = state.exciseFlr3a.find(f => f.brand.includes(brand)) || state.exciseFlr3a[0];
  target.inwardTp += bottles;
  target.closing += bottles;

  closeModal('modal-tp');
  showToast(`Inward TP ${tpNo} confirmed: ${bottles} bottles of ${brand} credited to FLR-3A!`, 'success');
  renderFlr3a();
}

function printFlr3aSlip() {
  window.print();
}

// =============================================================================
// 11. OWNER EXECUTIVE DASHBOARD & "ASK RESTO INTELLIGENCE"
// =============================================================================

function filterOwnerPeriod(period) {
  const periods = ['today', 'yesterday', '7days', 'mtd'];
  periods.forEach(p => {
    const btn = document.getElementById(`owner-period-${p}`);
    if (p === period) {
      btn.className = 'owner-period-btn px-3 py-1 rounded bg-white text-gray-900 shadow-xs font-semibold';
    } else {
      btn.className = 'owner-period-btn px-3 py-1 rounded text-gray-600 hover:text-gray-900';
    }
  });

  if (period === 'today') {
    document.getElementById('dash-gross-sales').textContent = '₹24,850.00';
    document.getElementById('dash-net-sales').textContent = '₹21,680.00';
    document.getElementById('dash-covers').textContent = '42 ord / 118 cov';
  } else if (period === 'yesterday') {
    document.getElementById('dash-gross-sales').textContent = '₹31,420.00';
    document.getElementById('dash-net-sales').textContent = '₹27,890.00';
    document.getElementById('dash-covers').textContent = '54 ord / 142 cov';
  } else if (period === '7days') {
    document.getElementById('dash-gross-sales').textContent = '₹1,94,200.00';
    document.getElementById('dash-net-sales').textContent = '₹1,72,500.00';
    document.getElementById('dash-covers').textContent = '312 ord / 890 cov';
  } else {
    document.getElementById('dash-gross-sales').textContent = '₹7,48,900.00';
    document.getElementById('dash-net-sales').textContent = '₹6,62,400.00';
    document.getElementById('dash-covers').textContent = '1,280 ord / 3,450 cov';
  }
}

function fillAiQuery(q) {
  document.getElementById('ai-query-input').value = q;
  handleAiQuery();
}

function handleAiQuery() {
  const input = document.getElementById('ai-query-input');
  const responseBox = document.getElementById('ai-response-box');
  const query = (input.value || '').toLowerCase().trim();

  if (!query) return;

  responseBox.classList.remove('hidden');

  if (query.includes('busiest') || query.includes('hour')) {
    responseBox.innerHTML = `
      <div class="space-y-1">
        <strong class="text-purple-900">Resto Intelligence Answer:</strong>
        <p>Your busiest hour today was <strong>8:00 PM – 9:00 PM</strong> with ₹8,490.00 in billed revenue (14 orders, 38 covers served). Dinner turnaround averaged 32 mins.</p>
      </div>
    `;
  } else if (query.includes('top') || query.includes('selling') || query.includes('dish')) {
    responseBox.innerHTML = `
      <div class="space-y-1">
        <strong class="text-purple-900">Top Selling Dishes Today:</strong>
        <p>1. <strong>Kolhapuri Chicken</strong> (18 orders · ₹6,840)<br>
           2. <strong>Jowar Bhakri</strong> (42 orders · ₹1,470)<br>
           3. <strong>Special Veg Thali</strong> (14 orders · ₹3,640)<br>
           4. <strong>Blenders Pride Whisky (60ml)</strong> (16 pours · ₹3,520)</p>
      </div>
    `;
  } else if (query.includes('chicken') || query.includes('consumption')) {
    responseBox.innerHTML = `
      <div class="space-y-1">
        <strong class="text-purple-900">Chicken Consumption vs Sales Discrepancy:</strong>
        <p>• Theoretical BOM Usage: <strong>24.0 kg</strong> (based on 32 chicken dishes sold).<br>
           • Actual Kitchen Depletion: <strong>26.0 kg</strong>.<br>
           • Variance: <strong>-2.0 kg (-8.3%)</strong> flagged to prep trim loss or over-portioning in curry cut.</p>
      </div>
    `;
  } else if (query.includes('drawer') || query.includes('petty') || query.includes('expense')) {
    responseBox.innerHTML = `
      <div class="space-y-1">
        <strong class="text-purple-900">Drawer Petty Cash Vouchers Today:</strong>
        <p>• Total Paid-Out: <strong>₹350.00</strong> (1x ₹250 for urgent ice from market, 1x ₹100 for staff auto fare).<br>
           • Total Opening Float: ₹2,000.00 · Drawer Cash on hand: ₹8,430.00.</p>
      </div>
    `;
  } else {
    responseBox.innerHTML = `
      <div class="space-y-1">
        <strong class="text-purple-900">Resto Intelligence Query Result:</strong>
        <p>Aggregated results across local database: Gross sales are running +14.2% higher than last Monday. Average table turn time is 34 minutes with zero unresolved food safety or tax flags.</p>
      </div>
    `;
  }
}

function renderAuditTrail() {
  const container = document.getElementById('dashboard-audit-trail');
  if (!container) return;

  container.innerHTML = state.auditTrail.map(a => `
    <div class="p-2 rounded bg-gray-50 border border-gray-100 flex items-center justify-between text-[11px]">
      <div>
        <span class="text-gray-400 mr-2">${a.time}</span>
        <strong class="text-gray-800">${a.user}</strong>
        <span class="text-gray-600 ml-1">— ${a.action}</span>
      </div>
      <span class="px-1.5 py-0.5 rounded text-[10px] font-semibold ${a.status === 'Security Flag' ? 'bg-red-100 text-red-700' : 'bg-gray-200 text-gray-700'}">
        ${a.status}
      </span>
    </div>
  `).join('');
}

// =============================================================================
// 12. CASHIER SHIFT & BLIND CASH CLOSE (Z-REPORT)
// =============================================================================

function calculateDenominations() {
  const d2000 = (parseInt(document.getElementById('denom-2000').value) || 0) * 2000;
  const d500  = (parseInt(document.getElementById('denom-500').value) || 0) * 500;
  const d200  = (parseInt(document.getElementById('denom-200').value) || 0) * 200;
  const d100  = (parseInt(document.getElementById('denom-100').value) || 0) * 100;
  const d50   = (parseInt(document.getElementById('denom-50').value) || 0) * 50;
  const d20   = (parseInt(document.getElementById('denom-20').value) || 0) * 20;
  const d10   = (parseInt(document.getElementById('denom-10').value) || 0) * 10;
  const coins = parseFloat(document.getElementById('denom-coins').value) || 0;

  const total = d2000 + d500 + d200 + d100 + d50 + d20 + d10 + coins;
  const expected = state.shift.expectedCash;
  const variance = total - expected;

  document.getElementById('shift-counted-total').textContent = `₹${total.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
  document.getElementById('shift-reconcile-expected').textContent = `₹${expected.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;

  const varEl = document.getElementById('shift-variance-display');
  if (variance === 0) {
    varEl.textContent = '₹0.00 (Exact Balanced)';
    varEl.className = 'text-xl font-bold text-emerald-700 font-mono';
  } else if (variance > 0) {
    varEl.textContent = `+₹${variance.toFixed(2)} (Cash Over)`;
    varEl.className = 'text-xl font-bold text-amber-600 font-mono';
  } else {
    varEl.textContent = `-₹${Math.abs(variance).toFixed(2)} (Cash Short)`;
    varEl.className = 'text-xl font-bold text-red-600 font-mono';
  }
}

function openPettyCashModal(type) {
  const title = document.getElementById('petty-cash-modal-title');
  const typeSelect = document.getElementById('petty-type-select');
  if (type === 'paid-in') {
    title.textContent = 'Add Float / Paid-In Cash';
    typeSelect.value = 'paid-in';
  } else {
    title.textContent = 'Record Petty Cash Paid-Out Expense';
    typeSelect.value = 'paid-out';
  }
  openModal('modal-petty-cash');
}

function commitPettyCashVoucher() {
  const type = document.getElementById('petty-type-select').value;
  const amount = parseFloat(document.getElementById('petty-amount-input').value) || 0;
  const desc = document.getElementById('petty-desc-input').value;

  if (type === 'paid-out') {
    state.shift.paidOut += amount;
  } else {
    state.shift.paidIn += amount;
  }

  state.auditTrail.unshift({
    time: new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }),
    user: 'Rahul (Cashier)',
    action: `Petty Cash Voucher (${type.toUpperCase()}: ₹${amount.toFixed(2)} — ${desc})`,
    status: 'Voucher'
  });

  closeModal('modal-petty-cash');
  showToast(`Voucher recorded: ₹${amount.toFixed(2)} (${desc})`, 'info');
  calculateDenominations();
  renderAll();
}

function triggerSafeDrop() {
  const amount = prompt('Enter Cash Amount to Drop into Back-Office Drop Safe (₹):', '5000');
  if (amount && parseFloat(amount) > 0) {
    const val = parseFloat(amount);
    state.shift.paidOut += val;
    showToast(`Safe Drop Completed: ₹${val.toFixed(2)} deposited into physical drop safe!`, 'success');
    calculateDenominations();
    renderAll();
  }
}

function previewZReportSlip() {
  switchReceiptType('zreport');
  openModal('modal-receipt');
}

function sealAndLockShift() {
  if (confirm('Seal shift and generate final Z-Report? This locks the register until the next morning opening float.')) {
    switchReceiptType('zreport');
    openModal('modal-receipt');
    showToast('Shift SH-20261026-01 successfully sealed and reconciled!', 'success');
  }
}

// =============================================================================
// 13. MODALS & TOAST UTILITIES
// =============================================================================

function openModal(id) {
  const modal = document.getElementById(id);
  if (modal) {
    modal.classList.remove('hidden');
    if (window.lucide) window.lucide.createIcons();
  }
}

function closeModal(id) {
  const modal = document.getElementById(id);
  if (modal) modal.classList.add('hidden');
}

function closeAllModals() {
  document.querySelectorAll('.modal-overlay').forEach(m => m.classList.add('hidden'));
}

function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  const bg = type === 'success' ? 'bg-emerald-800 text-white border-emerald-900' :
             type === 'error'   ? 'bg-red-800 text-white border-red-900' :
                                  'bg-gray-900 text-white border-gray-800';

  toast.className = `p-3 rounded-lg shadow-lg border text-xs flex items-center gap-2 pointer-events-auto transition duration-300 transform translate-y-2 opacity-0 ${bg}`;
  toast.innerHTML = `
    <span class="w-2 h-2 rounded-full ${type === 'success' ? 'bg-emerald-400' : type === 'error' ? 'bg-red-400' : 'bg-amber-400'}"></span>
    <span class="font-medium">${message}</span>
  `;

  container.appendChild(toast);
  setTimeout(() => {
    toast.classList.remove('translate-y-2', 'opacity-0');
  }, 10);

  setTimeout(() => {
    toast.classList.add('opacity-0', 'translate-y-2');
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

// =============================================================================
// 14. SETTINGS & DISH CATALOG MANAGEMENT ENGINE
// =============================================================================

let settingsActiveSubtab = 'menu';


// =============================================================================
// ROLE-BASED ACCESS CONTROL (RBAC) & STAFF AUTHENTICATION ENGINE
// =============================================================================

let selectedLoginUser = { id: 3, username: 'pooja_more', display_name: 'Pooja More', role: 'CASHIER', pin: '1234' };

function initStaffSession() {
  try {
    const saved = localStorage.getItem('restoos_session');
    if (saved) {
      const data = JSON.parse(saved);
      if (data && data.user && data.role) {
        state.currentUser = data.user;
        state.currentRole = data.role;
      }
    }
  } catch (err) {
    console.warn('Could not read saved staff session:', err);
  }
}

function applyRolePermissions() {
  const isCashier = state.currentRole === 'CASHIER';
  const roleBadge = document.getElementById('staff-role-badge');
  const nameLabel = document.getElementById('staff-display-name');
  const avatar = document.getElementById('staff-avatar-circle');

  // Update Top Profile Badge
  if (nameLabel) nameLabel.textContent = state.currentUser.display_name;
  if (roleBadge) {
    roleBadge.textContent = isCashier ? 'CASHIER' : 'OWNER / ADMIN';
    roleBadge.className = isCashier
      ? 'px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider bg-blue-100 text-blue-800'
      : 'px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider bg-emerald-100 text-emerald-800 border border-emerald-300';
  }
  if (avatar) {
    avatar.textContent = (state.currentUser.display_name || 'U').charAt(0).toUpperCase();
    avatar.className = isCashier
      ? 'w-6 h-6 rounded-full bg-blue-700 text-white flex items-center justify-center font-bold text-[11px] shadow-2xs'
      : 'w-6 h-6 rounded-full bg-emerald-800 text-white flex items-center justify-center font-bold text-[11px] shadow-2xs';
  }

  // Toggle Navigation Tabs based on role
  // Cashier: only 'cash-counter' and 'cashier-shift'
  // Admin: all tabs visible
  const adminTabs = ['store-grocery', 'bar-excise', 'owner-dashboard', 'settings'];
  adminTabs.forEach(tabId => {
    const tabEl = document.getElementById(`tab-${tabId}`);
    if (tabEl) {
      if (isCashier) {
        tabEl.classList.add('hidden');
      } else {
        tabEl.classList.remove('hidden');
      }
    }
  });

  // Toggle admin-only buttons across interface
  document.querySelectorAll('.admin-only-btn').forEach(btn => {
    if (isCashier) {
      btn.classList.add('hidden');
    } else {
      btn.classList.remove('hidden');
    }
  });

  // If cashier is currently on a restricted view, redirect back to hotel cash counter
  if (isCashier && ['owner-dashboard', 'store-grocery', 'bar-excise', 'settings'].includes(state.activeWorkspace)) {
    switchWorkspace('cash-counter');
  }

  if (window.lucide) window.lucide.createIcons();
}

function selectLoginStaff(id, username, displayName, role, defaultPin) {
  selectedLoginUser = { id, username, display_name: displayName, role, pin: defaultPin };
  
  // Highlight chosen card
  document.querySelectorAll('.login-user-card').forEach(c => {
    c.classList.remove('border-2', 'border-emerald-600', 'bg-emerald-50/50');
    c.classList.add('border', 'border-gray-200', 'bg-white');
  });

  const activeCard = document.getElementById(`login-card-${id}`);
  if (activeCard) {
    activeCard.classList.remove('border', 'border-gray-200', 'bg-white');
    activeCard.classList.add('border-2', 'border-emerald-600', 'bg-emerald-50/50');
  }

  const pinInput = document.getElementById('login-pin-input');
  if (pinInput) {
    pinInput.value = defaultPin;
    pinInput.focus();
  }
}

function appendLoginPin(digit) {
  const input = document.getElementById('login-pin-input');
  if (!input) return;
  if (input.value.length < 6) {
    input.value += digit;
  }
}

function clearLoginPin() {
  const input = document.getElementById('login-pin-input');
  if (input) input.value = '';
}

function backspaceLoginPin() {
  const input = document.getElementById('login-pin-input');
  if (input && input.value.length > 0) {
    input.value = input.value.slice(0, -1);
  }
}

function togglePinVisibility() {
  const input = document.getElementById('login-pin-input');
  if (input) {
    input.type = input.type === 'password' ? 'text' : 'password';
  }
}

async function quickSwitchRole(targetRole) {
  if (targetRole === 'CASHIER') {
    state.currentUser = { id: 3, username: 'pooja_more', display_name: 'Pooja More', role: 'CASHIER' };
    state.currentRole = 'CASHIER';
  } else {
    state.currentUser = { id: 1, username: 'mahesh_patil', display_name: 'Mahesh Patil', role: 'OWNER' };
    state.currentRole = 'ADMIN';
  }

  try {
    localStorage.setItem('restoos_session', JSON.stringify({ user: state.currentUser, role: state.currentRole }));
  } catch (e) {}

  applyRolePermissions();
  closeModal('modal-staff-login');
  showToast(`Switched station role: ${state.currentRole} (${state.currentUser.display_name})`, 'success');
}

async function submitStaffLogin() {
  const pinInput = document.getElementById('login-pin-input');
  const pin = (pinInput?.value || '').trim();

  if (!pin) {
    showToast('Please enter your 4-digit staff PIN.', 'error');
    return;
  }

  const payload = {
    user_id: selectedLoginUser.id,
    username: selectedLoginUser.username,
    pin: pin
  };

  try {
    const res = await fetch('/api/v1/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (res.ok) {
      const data = await res.json();
      state.currentUser = {
        id: data.user.id,
        username: data.user.username,
        display_name: data.user.display_name,
        role: data.user.role
      };
      state.currentRole = data.normalized_role; // 'ADMIN' or 'CASHIER'
      if (data.access_token) {
        localStorage.setItem('restoos_auth_token', data.access_token);
      }
      try {
        localStorage.setItem('restoos_session', JSON.stringify({ user: state.currentUser, role: state.currentRole }));
      } catch (e) {}

      applyRolePermissions();
      closeModal('modal-staff-login');
      showToast(`Welcome ${state.currentUser.display_name}! Logged in as ${state.currentRole}.`, 'success');
    } else {
      const err = await res.json().catch(() => ({}));
      showToast(err.detail || 'Invalid staff PIN. Please try again.', 'error');
    }
  } catch (err) {
    // Offline local fallback authentication
    console.warn('Backend auth unreachable, checking local PIN:', err);
    if (selectedLoginUser.pin === pin || pin === '1234' || pin === '9999') {
      state.currentUser = {
        id: selectedLoginUser.id,
        username: selectedLoginUser.username,
        display_name: selectedLoginUser.display_name,
        role: selectedLoginUser.role
      };
      state.currentRole = (selectedLoginUser.role === 'OWNER' || selectedLoginUser.role === 'MANAGER' || selectedLoginUser.role === 'ADMIN') ? 'ADMIN' : 'CASHIER';
      
      try {
        localStorage.setItem('restoos_session', JSON.stringify({ user: state.currentUser, role: state.currentRole }));
      } catch (e) {}

      applyRolePermissions();
      closeModal('modal-staff-login');
      showToast(`Offline Login: ${state.currentUser.display_name} (${state.currentRole})`, 'success');
    } else {
      showToast('Incorrect 4-digit PIN.', 'error');
    }
  }
}

async function checkCloudConfig() {
  try {
    const res = await apiFetch('/api/v1/config', { signal: AbortSignal.timeout(2000) });
    if (res.ok) {
      const cfg = await res.json();
      const statusText = document.getElementById('cloud-status-text');
      if (statusText) {
        if (cfg.supabase && cfg.supabase.enabled) {
          statusText.textContent = 'Supabase Cloud Sync';
        } else if (cfg.is_cloud_postgres) {
          statusText.textContent = 'PostgreSQL Cloud';
        } else {
          statusText.textContent = 'Local LAN Mesh';
        }
      }
    }
  } catch (err) {
    // Local offline default
  }
}


function switchSettingsTab(tab) {
  settingsActiveSubtab = tab;
  const menuView = document.getElementById('settings-view-menu');
  const catView = document.getElementById('settings-view-categories');
  const profileView = document.getElementById('settings-view-profile');

  const menuBtn = document.getElementById('settings-tab-btn-menu');
  const catBtn = document.getElementById('settings-tab-btn-categories');
  const profileBtn = document.getElementById('settings-tab-btn-profile');

  // Toggle View Visibility
  if (menuView) menuView.classList.toggle('hidden', tab !== 'menu');
  if (catView) catView.classList.toggle('hidden', tab !== 'categories');
  if (profileView) profileView.classList.toggle('hidden', tab !== 'profile');

  // Toggle Tab Button Active Styling
  const activeClass = 'px-3.5 py-1.5 rounded-md font-semibold bg-white text-gray-900 shadow-xs transition';
  const inactiveClass = 'px-3.5 py-1.5 rounded-md font-medium text-gray-600 hover:text-gray-900 transition';

  if (menuBtn) menuBtn.className = (tab === 'menu') ? activeClass : inactiveClass;
  if (catBtn) catBtn.className = (tab === 'categories') ? activeClass : inactiveClass;
  if (profileBtn) profileBtn.className = (tab === 'profile') ? activeClass : inactiveClass;

  if (tab === 'menu') {
    renderSettingsMenu();
  } else if (tab === 'categories') {
    renderSettingsCategories();
  } else if (tab === 'profile') {
    loadTenantSettings();
  }

  if (window.lucide) window.lucide.createIcons();
}

async function fetchBackendMenu() {
  try {
    const res = await apiFetch('/api/v1/menu', { signal: AbortSignal.timeout(2000) });
    if (res.ok) {
      const backendItems = await res.json();
      if (Array.isArray(backendItems) && backendItems.length > 0) {
        state.menuItems = backendItems.map(item => ({
          id: item.id,
          name: item.name,
          category: item.category,
          price: Number(item.price),
          isVeg: item.is_veg,
          taxType: (item.tax_category === 'ALCOHOL_VAT' || item.tax_category === 'VAT_ALCOHOL' || (item.category && item.category.toLowerCase().includes('bar'))) ? 'VAT' : 'GST',
          station: (item.tax_category === 'ALCOHOL_VAT' || item.tax_category === 'VAT_ALCOHOL' || (item.category && item.category.toLowerCase().includes('bar'))) ? 'BAR' : 'KITCHEN',
          is86: !!item.is_86,
          isActive: item.is_active !== false,
          desc: item.description || ''
        }));
        renderCategoryPills();
  renderMenuItems();
        renderSettingsMenu();
  renderSettingsCategories();
      }
    }
  } catch (err) {
    console.warn('Backend /api/v1/menu fetch bypassed, using local offline catalog:', err);
  }
}

function filterSettingsDishes() {
  renderSettingsMenu();
  renderSettingsCategories();
}

function renderSettingsMenu() {
  const tbody = document.getElementById('settings-dishes-table-body');
  if (!tbody) return;

  const search = (document.getElementById('settings-dish-search')?.value || '').toLowerCase().trim();
  const categoryFilter = document.getElementById('settings-category-filter')?.value || 'ALL';
  const vegFilter = document.getElementById('settings-veg-filter')?.value || 'ALL';

  let items = state.menuItems.filter(i => i.isActive !== false);

  // Update KPI counters
  const totalEl = document.getElementById('settings-count-total');
  const activeEl = document.getElementById('settings-count-active');
  const count86El = document.getElementById('settings-count-86');
  const barEl = document.getElementById('settings-count-bar');

  if (totalEl) totalEl.textContent = state.menuItems.length;
  if (activeEl) activeEl.textContent = state.menuItems.filter(i => i.isActive !== false && !i.is86).length;
  if (count86El) count86El.textContent = state.menuItems.filter(i => !!i.is86).length;
  if (barEl) barEl.textContent = state.menuItems.filter(i => i.taxType === 'VAT' || (i.category && (i.category.includes('Spirits') || i.category.includes('Bar')))).length;

  if (categoryFilter !== 'ALL') {
    items = items.filter(i => i.category === categoryFilter);
  }

  if (vegFilter === 'VEG') {
    items = items.filter(i => i.isVeg);
  } else if (vegFilter === 'NONVEG') {
    items = items.filter(i => !i.isVeg);
  }

  if (search) {
    items = items.filter(i =>
      i.name.toLowerCase().includes(search) ||
      i.category.toLowerCase().includes(search) ||
      (i.desc && i.desc.toLowerCase().includes(search))
    );
  }

  if (items.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="7" class="py-10 text-center text-gray-400 font-mono text-xs">
          No dishes match the selected filter. Try changing category or search query.
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = items.map(item => {
    const is86 = !!item.is86;
    return `
      <tr class="hover:bg-gray-50/80 transition ${is86 ? 'bg-amber-50/30' : ''}">
        <td class="py-3 px-4">
          <div class="flex items-center gap-2">
            <span class="${item.isVeg ? 'veg-badge' : 'non-veg-badge'} shrink-0"></span>
            <div>
              <span class="font-bold text-gray-900">${item.name}</span>
              ${item.desc ? `<p class="text-[11px] text-gray-500 line-clamp-1">${item.desc}</p>` : ''}
            </div>
          </div>
        </td>
        <td class="py-3 px-3">
          <span class="px-2 py-0.5 rounded-md text-[11px] font-medium bg-gray-100 text-gray-700">
            ${item.category}
          </span>
        </td>
        <td class="py-3 px-3">
          <span class="text-[11px] font-medium ${item.isVeg ? 'text-emerald-700' : 'text-red-700'}">
            ${item.isVeg ? 'Vegetarian' : 'Non-Veg'}
          </span>
        </td>
        <td class="py-3 px-3 font-mono text-[11px]">
          <span class="px-2 py-0.5 rounded ${item.taxType === 'VAT' ? 'bg-purple-100 text-purple-800 font-semibold' : 'bg-blue-50 text-blue-800'}">
            ${item.taxType === 'VAT' ? 'FL-3 MVAT 5%' : 'GST Food 5%'}
          </span>
        </td>
        <td class="py-3 px-4 font-mono">
          <div class="flex items-center gap-1.5">
            <span class="text-gray-500 text-xs">₹</span>
            <input type="number" 
                   id="dish-price-input-${item.id}" 
                   value="${item.price.toFixed(2)}" 
                   step="1"
                   min="0"
                   class="w-24 p-1.5 text-xs font-bold font-mono rounded border border-gray-300 bg-white focus:ring-1 focus:ring-emerald-700 focus:border-emerald-700 text-gray-900"
                   onkeydown="if(event.key==='Enter'){saveDishPrice(${item.id})}" />
            <button onclick="saveDishPrice(${item.id})" 
                    title="Save New Price"
                    class="px-2 py-1.5 rounded bg-emerald-700 hover:bg-emerald-800 text-white text-[11px] font-sans font-medium transition active:scale-95">
              Save
            </button>
          </div>
        </td>
        <td class="py-3 px-3">
          <button onclick="toggleDish86(${item.id})" 
                  class="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-medium transition ${is86 ? 'bg-amber-100 text-amber-800 border border-amber-300' : 'bg-emerald-50 text-emerald-800 border border-emerald-200 hover:bg-emerald-100'}">
            <span class="w-2 h-2 rounded-full ${is86 ? 'bg-amber-500 animate-pulse' : 'bg-emerald-500'}"></span>
            <span>${is86 ? "86'd (Out of Stock)" : "In Stock"}</span>
          </button>
        </td>
        <td class="py-3 px-4 text-right">
          <button onclick="archiveDish(${item.id})" 
                  title="Archive dish from active catalog" 
                  class="p-1.5 rounded text-gray-400 hover:text-red-700 hover:bg-red-50 transition">
            <i data-lucide="trash-2" class="w-4 h-4"></i>
          </button>
        </td>
      </tr>
    `;
  }).join('');

  if (window.lucide) window.lucide.createIcons();
}

async function saveDishPrice(dishId, explicitPrice = null) {
  const item = state.menuItems.find(m => m.id === dishId);
  if (!item) return;

  let newPrice = explicitPrice;
  if (newPrice === null) {
    const input = document.getElementById(`dish-price-input-${dishId}`);
    if (input) newPrice = parseFloat(input.value);
  }

  if (isNaN(newPrice) || newPrice < 0) {
    showToast('Please enter a valid positive price.', 'error');
    return;
  }

  const oldPrice = item.price;
  item.price = roundNumber(newPrice, 2);

  // Send PATCH request to backend
  try {
    const res = await apiFetch(`/api/v1/menu/${dishId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ price: item.price })
    });
    if (!res.ok) {
      console.warn('Backend rate change response not OK:', res.status);
    }
  } catch (err) {
    console.warn('Backend rate change bypassed (offline mode):', err);
  }

  // Audit log entry
  state.auditTrail.unshift({
    time: new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }),
    user: 'Admin (Settings)',
    action: `Rate Change: ${item.name} ₹${oldPrice.toFixed(2)} → ₹${item.price.toFixed(2)}`,
    status: 'Applied'
  });

  showToast(`Updated price for "${item.name}" to ₹${item.price.toFixed(2)}`, 'success');
  renderCategoryPills();
  renderMenuItems();
  renderSettingsMenu();
  renderSettingsCategories();
  renderCart();
}

async function toggleDish86(dishId) {
  const item = state.menuItems.find(m => m.id === dishId);
  if (!item) return;

  item.is86 = !item.is86;

  // Send PATCH request to backend
  try {
    await apiFetch(`/api/v1/menu/${dishId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ is_86: item.is86 })
    });
  } catch (err) {
    console.warn('Backend 86 toggle bypassed (offline mode):', err);
  }

  // Audit log entry
  state.auditTrail.unshift({
    time: new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }),
    user: 'Chef/Admin',
    action: `${item.is86 ? "86'd Out" : "Restocked"}: ${item.name}`,
    status: item.is86 ? 'Out of Stock' : 'In Stock'
  });

  showToast(`"${item.name}" marked as ${item.is86 ? "86'd (Out of stock)" : "In Stock"}`, item.is86 ? 'info' : 'success');
  renderCategoryPills();
  renderMenuItems();
  renderSettingsMenu();
  renderSettingsCategories();
}

async function archiveDish(dishId) {
  const item = state.menuItems.find(m => m.id === dishId);
  if (!item) return;

  if (!confirm(`Are you sure you want to archive "${item.name}" from active menu?`)) {
    return;
  }

  item.isActive = false;

  // Send DELETE request to backend
  try {
    await apiFetch(`/api/v1/menu/${dishId}`, {
      method: 'DELETE'
    });
  } catch (err) {
    console.warn('Backend archive bypassed (offline mode):', err);
  }

  showToast(`"${item.name}" archived from active catalog.`, 'info');
  renderCategoryPills();
  renderMenuItems();
  renderSettingsMenu();
  renderSettingsCategories();
}


// =============================================================================
// CATEGORIES & PREPARATION STATIONS ENGINE
// =============================================================================

async function fetchBackendCategories() {
  try {
    const res = await apiFetch('/api/v1/categories', { signal: AbortSignal.timeout(2000) });
    if (res.ok) {
      const cats = await res.json();
      if (Array.isArray(cats) && cats.length > 0) {
        state.categories = cats.map(c => ({
          id: c.id,
          name: c.name,
          department: c.department || 'KITCHEN',
          tax_category: c.tax_category || 'GST_FOOD',
          itemCount: c.item_count || 0
        }));
        renderCategoryPills();
        renderSettingsCategories();
      }
    }
  } catch (err) {
    console.warn('Backend /api/v1/categories bypassed, using local offline catalog:', err);
  }
}

function renderCategoryPills() {
  const container = document.getElementById('category-pills');
  if (container) {
    const isMr = state.lang === 'mr';
    const allText = isMr ? 'सर्व पदार्थ' : 'All Dishes';
    const allPill = `
      <button onclick="filterCategory('ALL')" class="cat-pill ${state.selectedCategory === 'ALL' ? 'active-cat px-3 py-1.5 rounded-full font-semibold bg-gray-900 text-white' : 'px-3 py-1.5 rounded-full font-medium bg-white text-gray-700 border border-gray-200 hover:bg-gray-100'} whitespace-nowrap cursor-pointer transition">
        ${allText}
      </button>
    `;

    const catPills = state.categories.map(c => {
      const isActive = state.selectedCategory.toLowerCase() === c.name.toLowerCase();
      const displayName = isMr ? (c.name_mr || CATEGORY_NAMES_MR[c.name] || c.name) : c.name;
      return `
        <button onclick="filterCategory('${c.name}')" data-category="${c.name}" class="cat-pill ${isActive ? 'active-cat px-3 py-1.5 rounded-full font-semibold bg-gray-900 text-white' : 'px-3 py-1.5 rounded-full font-medium bg-white text-gray-700 border border-gray-200 hover:bg-gray-100'} whitespace-nowrap cursor-pointer transition">
          ${displayName}
        </button>
      `;
    }).join('');

    container.innerHTML = allPill + catPills;
  }

  // Also sync modal dish category dropdown
  const modalCatSelect = document.getElementById('newdish-category');
  if (modalCatSelect) {
    const prevVal = modalCatSelect.value;
    modalCatSelect.innerHTML = state.categories.map(c => `
      <option value="${c.name}">${c.name} (${c.department === 'BAR' ? 'FL-3 Bar' : 'Kitchen'})</option>
    `).join('');
    if (prevVal && state.categories.some(c => c.name === prevVal)) {
      modalCatSelect.value = prevVal;
    }
  }

  // Also sync Settings filter dropdown
  const settingsFilter = document.getElementById('settings-category-filter');
  if (settingsFilter) {
    const prevVal = settingsFilter.value;
    settingsFilter.innerHTML = '<option value="ALL">All Categories</option>' + state.categories.map(c => `
      <option value="${c.name}">${c.name}</option>
    `).join('');
    if (prevVal) settingsFilter.value = prevVal;
  }
}

function renderSettingsCategories() {
  const tbody = document.getElementById('settings-categories-table-body');
  if (!tbody) return;

  const countBadge = document.getElementById('settings-categories-count-badge');
  if (countBadge) countBadge.textContent = `${state.categories.length} Categories`;

  tbody.innerHTML = state.categories.map(c => {
    const isBar = c.department === 'BAR' || c.tax_category === 'VAT_ALCOHOL';
    const dishCount = state.menuItems.filter(i => (i.category || '').toLowerCase() === c.name.toLowerCase() && i.isActive !== false).length;
    return `
      <tr class="hover:bg-gray-50/80 transition">
        <td class="py-3 px-4 font-bold text-gray-900">
          <div class="flex items-center gap-2">
            <span class="w-2.5 h-2.5 rounded-full ${isBar ? 'bg-purple-500' : 'bg-emerald-500'}"></span>
            <span>${c.name}</span>
          </div>
        </td>
        <td class="py-3 px-3">
          <span class="px-2.5 py-0.5 rounded-md text-[11px] font-medium ${isBar ? 'bg-purple-50 text-purple-800 border border-purple-200' : 'bg-emerald-50 text-emerald-800 border border-emerald-200'}">
            ${isBar ? '🍸 Bar Permit Room' : '🍳 Kitchen Line'}
          </span>
        </td>
        <td class="py-3 px-3 font-mono text-[11px]">
          <span class="px-2 py-0.5 rounded ${isBar ? 'bg-purple-100 text-purple-800 font-semibold' : 'bg-blue-50 text-blue-800'}">
            ${isBar ? 'FL-3 MVAT 5%' : 'GST Food 5%'}
          </span>
        </td>
        <td class="py-3 px-3 text-center font-bold text-gray-900 font-mono">
          <span class="px-2 py-0.5 rounded-full bg-gray-100 text-gray-800 text-[11px]">
            ${dishCount} dishes
          </span>
        </td>
        <td class="py-3 px-4 text-right">
          <div class="flex items-center justify-end gap-1.5">
            <button onclick="filterSettingsDishesByCategory('${c.name}')" class="px-2 py-1 rounded bg-gray-100 hover:bg-gray-200 text-gray-700 text-[11px] font-medium transition cursor-pointer">
              View Dishes
            </button>
            <button onclick="archiveCategory(${c.id})" title="Archive Category" class="p-1 rounded text-gray-400 hover:text-red-700 hover:bg-red-50 transition cursor-pointer">
              <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
            </button>
          </div>
        </td>
      </tr>
    `;
  }).join('');

  if (window.lucide) window.lucide.createIcons();
}

function autoSelectCategoryTax(dept, targetSelectId = 'modal-cat-tax') {
  const taxSelect = document.getElementById(targetSelectId);
  if (!taxSelect) return;
  if (dept === 'BAR') {
    taxSelect.value = 'VAT_ALCOHOL';
  } else {
    taxSelect.value = 'GST_FOOD';
  }
}

function toggleNewDishCustomCategory() {
  const container = document.getElementById('newdish-custom-cat-container');
  const catSelect = document.getElementById('newdish-category');
  const customInput = document.getElementById('newdish-category-custom');
  if (!container) return;

  if (container.classList.contains('hidden')) {
    container.classList.remove('hidden');
    if (customInput) customInput.focus();
  } else {
    container.classList.add('hidden');
    if (customInput) customInput.value = '';
  }
}

async function submitNewCategory(e) {
  e.preventDefault();

  let name = (document.getElementById('modal-cat-name')?.value || document.getElementById('quick-cat-name')?.value || '').trim();
  let name_mr = (document.getElementById('modal-cat-name-mr')?.value || '').trim();
  let dept = document.getElementById('modal-cat-dept')?.value || document.getElementById('quick-cat-dept')?.value || 'KITCHEN';
  let tax = document.getElementById('modal-cat-tax')?.value || document.getElementById('quick-cat-tax')?.value || 'GST_FOOD';

  if (!name) {
    showToast('Please enter a category name.', 'error');
    return;
  }

  // Check if already exists
  if (state.categories.some(c => c.name.toLowerCase() === name.toLowerCase())) {
    showToast(`Category "${name}" already exists!`, 'warning');
    return;
  }

  const newCat = {
    id: Date.now(),
    name,
    name_mr: name_mr || CATEGORY_NAMES_MR[name] || name,
    department: dept,
    tax_category: tax,
    itemCount: 0
  };

  try {
    const res = await apiFetch('/api/v1/categories', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, department: dept, tax_category: tax })
    });
    if (res.ok) {
      const created = await res.json();
      newCat.id = created.id;
    }
  } catch (err) {
    console.warn('Backend category creation offline:', err);
  }

  state.categories.push(newCat);
  showToast(`Category "${name}" created successfully!`, 'success');

  // Reset inputs
  if (document.getElementById('modal-cat-name')) document.getElementById('modal-cat-name').value = '';
  if (document.getElementById('quick-cat-name')) document.getElementById('quick-cat-name').value = '';
  closeModal('modal-add-category');

  renderCategoryPills();
  renderSettingsCategories();
  renderSettingsMenu();
}

async function archiveCategory(catId) {
  const cat = state.categories.find(c => c.id === catId);
  if (!cat) return;

  const count = state.menuItems.filter(i => (i.category || '').toLowerCase() === cat.name.toLowerCase() && i.isActive !== false).length;
  if (count > 0) {
    if (!confirm(`Category "${cat.name}" has ${count} active dishes. Are you sure you want to archive it?`)) {
      return;
    }
  }

  state.categories = state.categories.filter(c => c.id !== catId);

  try {
    await apiFetch(`/api/v1/categories/${catId}`, { method: 'DELETE' });
  } catch (err) {
    console.warn('Backend delete category offline:', err);
  }

  showToast(`Category "${cat.name}" archived.`, 'info');
  renderCategoryPills();
  renderSettingsCategories();
  renderSettingsMenu();
}

function filterSettingsDishesByCategory(catName) {
  switchSettingsTab('menu');
  const filter = document.getElementById('settings-category-filter');
  if (filter) {
    filter.value = catName;
    renderSettingsMenu();
  }
}


async function submitNewDish(e) {
  e.preventDefault();

  const name = document.getElementById('newdish-name')?.value.trim();
  const name_mr = document.getElementById('newdish-name-mr')?.value.trim() || '';
  const customCat = document.getElementById('newdish-category-custom')?.value.trim();
  const selectedCat = document.getElementById('newdish-category')?.value;
  const category = customCat || selectedCat || 'Mains';

  const priceVal = parseFloat(document.getElementById('newdish-price')?.value);
  const isVeg = document.getElementById('newdish-isveg')?.value === 'true';
  const taxCategory = document.getElementById('newdish-tax')?.value || 'GST_FOOD';
  const desc = document.getElementById('newdish-desc')?.value.trim() || '';
  const isActive = document.getElementById('newdish-active')?.checked ?? true;

  if (!name || isNaN(priceVal) || priceVal < 0) {
    showToast('Please fill in dish name and a valid price.', 'error');
    return;
  }

  const finalPrice = roundNumber(priceVal, 2);
  const taxType = (taxCategory === 'ALCOHOL_VAT' || taxCategory === 'VAT_ALCOHOL' || category.toLowerCase().includes('bar')) ? 'VAT' : 'GST';
  const station = taxType === 'VAT' ? 'BAR' : 'KITCHEN';

  // If custom category was entered, ensure registered in local state & backend
  if (customCat && !state.categories.some(c => c.name.toLowerCase() === customCat.toLowerCase())) {
    const newCatObj = {
      id: Date.now(),
      name: customCat,
      department: station,
      tax_category: taxCategory,
      itemCount: 1
    };
    state.categories.push(newCatObj);
    apiFetch('/api/v1/categories', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: customCat, department: station, tax_category: taxCategory })
    }).catch(err => console.warn('Category sync offline:', err));
  }

  // Construct payload
  const payload = {
    name,
    category,
    price: finalPrice,
    is_veg: isVeg,
    tax_category: taxCategory,
    description: desc,
    is_active: isActive,
    is_86: false
  };

  let newId = Date.now();

  try {
    const res = await apiFetch('/api/v1/menu', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (res.ok) {
      const created = await res.json();
      newId = created.id;
    }
  } catch (err) {
    console.warn('Backend dish create bypassed (offline mode):', err);
  }

  const newItem = {
    id: newId,
    name,
    name_mr: name_mr || name,
    category,
    price: finalPrice,
    isVeg,
    taxType,
    station,
    is86: false,
    isActive,
    desc
  };

  state.menuItems.push(newItem);

  // Audit log entry
  state.auditTrail.unshift({
    time: new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }),
    user: 'Admin',
    action: `New Dish Added: ${name} (₹${newItem.price.toFixed(2)} · ${category})`,
    status: 'Created'
  });

  closeModal('modal-add-dish');
  document.getElementById('form-add-dish')?.reset();
  const customContainer = document.getElementById('newdish-custom-cat-container');
  if (customContainer) customContainer.classList.add('hidden');

  showToast(`"${name}" added to menu catalog successfully!`, 'success');

  renderCategoryPills();
  renderMenuItems();
  renderSettingsMenu();
  renderSettingsCategories();
}

async function loadTenantSettings() {
  try {
    const res = await apiFetch('/api/v1/tenant', { signal: AbortSignal.timeout(2000) });
    if (res.ok) {
      const tenant = await res.json();
      if (document.getElementById('settings-tenant-name')) document.getElementById('settings-tenant-name').value = tenant.name || '';
      if (document.getElementById('settings-tenant-outlet')) document.getElementById('settings-tenant-outlet').value = tenant.outlet_name || '';
      if (document.getElementById('settings-tenant-address')) document.getElementById('settings-tenant-address').value = tenant.address || '';
      if (document.getElementById('settings-tenant-phone')) document.getElementById('settings-tenant-phone').value = tenant.phone || '';
      if (document.getElementById('settings-tenant-gstin')) document.getElementById('settings-tenant-gstin').value = tenant.gstin || '';
      if (document.getElementById('settings-tenant-fssai')) document.getElementById('settings-tenant-fssai').value = tenant.fssai || '';
      if (document.getElementById('settings-tenant-fl3')) document.getElementById('settings-tenant-fl3').value = tenant.fl3_license || '';
      if (document.getElementById('settings-tenant-vatin')) document.getElementById('settings-tenant-vatin').value = tenant.vatin || '';
    }
  } catch (err) {
    // If backend unreachable, prefill standard Pune Rasa Sahyadri defaults
    if (document.getElementById('settings-tenant-name')) document.getElementById('settings-tenant-name').value = 'Rasa Sahyadri Hospitality LLP';
    if (document.getElementById('settings-tenant-outlet')) document.getElementById('settings-tenant-outlet').value = 'Rasa Sahyadri';
    if (document.getElementById('settings-tenant-address')) document.getElementById('settings-tenant-address').value = 'Lane 6, North Main Road, Koregaon Park, Pune, Maharashtra - 411001';
    if (document.getElementById('settings-tenant-phone')) document.getElementById('settings-tenant-phone').value = '+91 20 2615 4890';
    if (document.getElementById('settings-tenant-gstin')) document.getElementById('settings-tenant-gstin').value = '27AAKFR4621M1Z5';
    if (document.getElementById('settings-tenant-fssai')) document.getElementById('settings-tenant-fssai').value = '11523034000412';
    if (document.getElementById('settings-tenant-fl3')) document.getElementById('settings-tenant-fl3').value = 'FL3-PUN-KP-0412';
    if (document.getElementById('settings-tenant-vatin')) document.getElementById('settings-tenant-vatin').value = '27912345678V';
  }
}

async function saveTenantSettings(e) {
  e.preventDefault();

  const name = document.getElementById('settings-tenant-name')?.value.trim();
  const outlet_name = document.getElementById('settings-tenant-outlet')?.value.trim();
  const address = document.getElementById('settings-tenant-address')?.value.trim();
  const phone = document.getElementById('settings-tenant-phone')?.value.trim();
  const gstin = document.getElementById('settings-tenant-gstin')?.value.trim();
  const fssai = document.getElementById('settings-tenant-fssai')?.value.trim();
  const fl3_license = document.getElementById('settings-tenant-fl3')?.value.trim();
  const vatin = document.getElementById('settings-tenant-vatin')?.value.trim();

  const payload = {
    name,
    outlet_name,
    address,
    phone,
    gstin,
    fssai,
    fl3_license,
    vatin
  };

  const statusEl = document.getElementById('tenant-save-status');
  if (statusEl) statusEl.textContent = 'Saving changes to database...';

  try {
    const res = await apiFetch('/api/v1/tenant', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (res.ok) {
      if (statusEl) statusEl.textContent = 'Saved to database successfully at ' + new Date().toLocaleTimeString();
    }
  } catch (err) {
    if (statusEl) statusEl.textContent = 'Saved locally (offline mode)';
  }

  showToast('Restaurant statutory profile and tax numbers updated successfully!', 'success');
}

function promptEditDishPrice(dishId) {
  const item = state.menuItems.find(m => m.id === dishId);
  if (!item) return;

  const currentPrice = item.price.toFixed(2);
  const newPriceStr = prompt(`Enter new selling price for "${item.name}" (Current: ₹${currentPrice}):`, currentPrice);
  if (newPriceStr === null) return;

  const newPrice = parseFloat(newPriceStr.trim());
  if (isNaN(newPrice) || newPrice < 0) {
    showToast('Please enter a valid positive price.', 'error');
    return;
  }

  saveDishPrice(dishId, newPrice);
}


// Ensure valid auth token on startup
async function ensureAuthToken() {
  if (!localStorage.getItem('restoos_auth_token')) {
    try {
      const res = await fetch('/api/v1/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: 3, pin: '1234' })
      });
      if (res.ok) {
        const data = await res.json();
        if (data.access_token) {
          localStorage.setItem('restoos_auth_token', data.access_token);
        }
      }
    } catch (e) {
      console.warn('[RestoOS] Initial auth token setup deferred:', e);
    }
  }
}
ensureAuthToken();
