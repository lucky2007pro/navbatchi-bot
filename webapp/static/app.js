// Telegram Web App SDK initsializatsiyasi
const tg = window.Telegram?.WebApp || null;

if (tg) {
  try {
    tg.ready();
    tg.expand();
    if (tg.setHeaderColor && tg.themeParams?.bg_color) {
      tg.setHeaderColor(tg.themeParams.bg_color);
    }
  } catch (e) {
    console.error("Telegram WebApp initsializatsiya xatosi:", e);
  }
}

// Global holat (State)
let appState = {
  chatId: null,
  group: null,
  members: [],
  tasks: [],
  currentDuty: null,
  currentIndex: 0,
  isAdmin: false,

  // Moliya va Bozorlik
  fundBalance: 0,
  monthExpense: 0,
  recentExpenses: [],
  recentFund: [],
  financeFilter: "all",
  rentSettings: { total_amount: 0, due_day: 5 },
  rentStatus: [],
  shoppingItems: [],
};

// URL parametrlarini o'qish
function getUrlParam(name) {
  const params = new URLSearchParams(window.location.search);
  let val = params.get(name);
  if (!val && tg?.initDataUnsafe?.start_param) {
    val = tg.initDataUnsafe.start_param;
  }
  return val;
}

// Haptic tebranish yordamchisi
function triggerHaptic(type = "light") {
  if (tg?.HapticFeedback) {
    if (type === "success" || type === "error" || type === "warning") {
      tg.HapticFeedback.notificationOccurred(type);
    } else {
      tg.HapticFeedback.impactOccurred(type);
    }
  }
}

// Toast xabari
function showToast(message, type = "success") {
  const toast = document.getElementById("toast");
  toast.textContent = message;
  toast.className = `toast ${type}`;
  toast.classList.remove("hidden");
  triggerHaptic(type === "error" ? "error" : "success");

  setTimeout(() => {
    toast.classList.add("hidden");
  }, 3200);
}

// Modal oynalarni yopish
function closeModals() {
  document.querySelectorAll(".modal-overlay").forEach((m) => m.classList.add("hidden"));
}

// Barcha ma'lumotlarni yuklash (Guruh + Moliya)
async function loadAllData() {
  const chatId = getUrlParam("chat_id");
  if (!chatId) {
    showError("Guruh identifikatori (chat_id) topilmadi.", "Iltimos, ushbu Web App'ni botdagi tugma orqali oching.");
    return;
  }
  appState.chatId = chatId;

  const loadingSpinner = document.getElementById("loading-spinner");
  const mainContent = document.getElementById("main-content");
  const errorScreen = document.getElementById("error-screen");

  try {
    const headers = { "Content-Type": "application/json" };
    if (tg?.initData) headers["X-Telegram-Init-Data"] = tg.initData;

    // 1. Guruh va Navbatchilik ma'lumotlari
    const resGroup = await fetch(`/api/group-data?chat_id=${encodeURIComponent(chatId)}`, { headers });
    const dataGroup = await resGroup.json();
    if (!resGroup.ok || !dataGroup.success) {
      throw new Error(dataGroup.error || "Guruh ma'lumotlarini yuklab bo'lmadi.");
    }

    appState.group = dataGroup.group;
    appState.members = dataGroup.members || [];
    appState.tasks = dataGroup.tasks ? dataGroup.tasks.map((t) => t.task_text || t) : [];
    appState.currentDuty = dataGroup.current_duty;
    appState.currentIndex = dataGroup.current_index || 0;
    appState.isAdmin = Boolean(dataGroup.is_admin);

    // 2. Moliya va Bozorlik ma'lumotlari
    const resFinance = await fetch(`/api/finance-data?chat_id=${encodeURIComponent(chatId)}`, { headers });
    const dataFinance = await resFinance.json();
    if (resFinance.ok && dataFinance.success) {
      appState.fundBalance = dataFinance.fund_balance || 0;
      appState.monthExpense = dataFinance.month_expense || 0;
      appState.recentExpenses = dataFinance.recent_expenses || [];
      appState.recentFund = dataFinance.recent_fund || [];
      appState.rentSettings = dataFinance.rent_settings || { total_amount: 0, due_day: 5 };
      appState.rentStatus = dataFinance.rent_status || [];
      appState.shoppingItems = dataFinance.shopping_items || [];
    }

    renderAll();

    loadingSpinner.classList.add("hidden");
    errorScreen.classList.add("hidden");
    mainContent.classList.remove("hidden");
  } catch (err) {
    console.error("Yuklashda xatolik:", err);
    showError("Xatolik yuz berdi", err.message);
  }
}

function showError(title, desc) {
  document.getElementById("loading-spinner").classList.add("hidden");
  document.getElementById("main-content").classList.add("hidden");
  const errScreen = document.getElementById("error-screen");
  document.getElementById("error-title").textContent = title;
  document.getElementById("error-desc").textContent = desc;
  errScreen.classList.remove("hidden");
}

// ==================== CHIZISH (RENDER) ====================

function renderAll() {
  renderHeader();
  renderCurrentDuty();
  renderMembers();
  renderTasks();
  renderFinance();
  renderRent();
  renderShopping();
  renderSettings();
  populateMemberSelects();
  setupPermissions();
}

function renderHeader() {
  const title = appState.group?.chat_title || "Smart Kvartira";
  document.getElementById("group-title").textContent = title;

  const roleBadge = document.getElementById("role-badge");
  if (appState.isAdmin) {
    roleBadge.textContent = "👑 Admin";
    roleBadge.className = "badge badge-admin";
  } else {
    roleBadge.textContent = "👤 A'zo";
    roleBadge.className = "badge badge-member";
  }

  const statusBadge = document.getElementById("status-badge");
  if (appState.group?.is_active) {
    statusBadge.textContent = "Faol";
    statusBadge.className = "badge badge-active";
  } else {
    statusBadge.textContent = "Nofaol";
    statusBadge.className = "badge badge-inactive";
  }
}

function renderCurrentDuty() {
  const currentMember = appState.currentDuty;
  const nameEl = document.getElementById("duty-name");
  const userEl = document.getElementById("duty-username");

  if (currentMember) {
    nameEl.textContent = currentMember.name || "Nomsiz";
    userEl.textContent = currentMember.username ? `@${currentMember.username}` : "Username kiritilmagan";
  } else {
    nameEl.textContent = "Hozircha belgilanmagan";
    userEl.textContent = "Navbatchilar ro'yxatini to'ldiring";
  }
}

function renderMembers() {
  const listEl = document.getElementById("members-list");
  const countEl = document.getElementById("members-count");
  listEl.innerHTML = "";
  countEl.textContent = appState.members.length;

  if (appState.members.length === 0) {
    listEl.innerHTML = `
      <div class="empty-state">
        <p>Hozircha navbatchilar qo'shilmagan.</p>
        ${appState.isAdmin ? '<p style="font-size:0.85rem; margin-top:4px;">Qo\'shish uchun yuqoridagi tugmani bosing.</p>' : ""}
      </div>
    `;
    return;
  }

  appState.members.forEach((m, idx) => {
    const isCurrent = idx === appState.currentIndex;
    const item = document.createElement("div");
    item.className = `list-item ${isCurrent ? "is-current" : ""}`;

    let actionsHtml = "";
    if (appState.isAdmin) {
      actionsHtml = `
        <div class="item-actions">
          <button class="btn btn-icon" onclick="moveMember(${idx}, -1)" ${idx === 0 ? "disabled" : ""} title="Yuqoriga">▲</button>
          <button class="btn btn-icon" onclick="moveMember(${idx}, 1)" ${idx === appState.members.length - 1 ? "disabled" : ""} title="Pastga">▼</button>
          <button class="btn btn-icon btn-delete" onclick="deleteMember(${idx})" title="O'chirish">🗑️</button>
        </div>
      `;
    }

    item.innerHTML = `
      <div class="item-left">
        <div class="item-order">#${idx + 1}</div>
        <div class="item-info">
          <div class="item-title">
            ${escapeHtml(m.name)}
            ${isCurrent ? '<span class="item-current-pill">🎯 Bugun</span>' : ""}
          </div>
          <div class="item-subtitle">${m.username ? `@${escapeHtml(m.username)}` : "username yo'q"}</div>
        </div>
      </div>
      ${actionsHtml}
    `;
    listEl.appendChild(item);
  });
}

function renderTasks() {
  const listEl = document.getElementById("tasks-list");
  const countEl = document.getElementById("tasks-count");
  listEl.innerHTML = "";
  countEl.textContent = appState.tasks.length;

  if (appState.tasks.length === 0) {
    listEl.innerHTML = `<div class="empty-state"><p>Kunlik vazifalar kiritilmagan.</p></div>`;
    return;
  }

  appState.tasks.forEach((task, idx) => {
    const item = document.createElement("div");
    item.className = "list-item";

    let actionsHtml = "";
    if (appState.isAdmin) {
      actionsHtml = `
        <div class="item-actions">
          <button class="btn btn-icon btn-delete" onclick="deleteTask(${idx})" title="O'chirish">🗑️</button>
        </div>
      `;
    }

    item.innerHTML = `
      <div class="item-left">
        <div class="item-order">${idx + 1}</div>
        <div class="item-info">
          <div class="item-title" style="white-space: normal;">${escapeHtml(task)}</div>
        </div>
      </div>
      ${actionsHtml}
    `;
    listEl.appendChild(item);
  });
}

// 💸 Moliya Tabini chizish
function renderFinance() {
  const balance = appState.fundBalance || 0;
  const monthExp = appState.monthExpense || 0;

  document.getElementById("fund-balance-display").textContent = `${balance.toLocaleString()} so'm`;
  document.getElementById("month-expense-display").textContent = `${monthExp.toLocaleString()} so'm`;

  const withdrawCurEl = document.getElementById("withdrawal-current-balance");
  if (withdrawCurEl) withdrawCurEl.textContent = `${balance.toLocaleString()} so'm`;

  const resetCurEl = document.getElementById("reset-current-balance");
  if (resetCurEl) resetCurEl.textContent = `${balance.toLocaleString()} so'm`;

  const listEl = document.getElementById("transactions-list");
  if (!listEl) return;
  listEl.innerHTML = "";

  // Tranzaksiyalar ro'yxatini yig'ish
  let items = [];

  // 1. Kassa harakatlari (Kirim, Chiqim/Yechish, Nollash)
  (appState.recentFund || []).forEach((tx) => {
    if (tx.type === "income") {
      items.push({
        id: tx.id,
        kind: "fund",
        type: "income",
        title: `${escapeHtml(tx.member_name)} pul tashladi`,
        subtitle: tx.note ? `${escapeHtml(tx.note)} • ${tx.created_at || ""}` : (tx.created_at || ""),
        amount: Math.abs(tx.amount),
        rawTime: tx.created_at || "",
        badge: `<span class="tx-badge income">📥 Kirim</span>`,
        amountHtml: `<span class="tx-amount-tag income">+${Math.abs(tx.amount).toLocaleString()} so'm</span>`,
      });
    } else if (tx.type === "withdrawal") {
      items.push({
        id: tx.id,
        kind: "fund",
        type: "withdrawal",
        title: `${escapeHtml(tx.member_name)} pul yechdi`,
        subtitle: tx.note ? `${escapeHtml(tx.note)} • ${tx.created_at || ""}` : (tx.created_at || ""),
        amount: Math.abs(tx.amount),
        rawTime: tx.created_at || "",
        badge: `<span class="tx-badge withdrawal">💸 Chiqim</span>`,
        amountHtml: `<span class="tx-amount-tag withdrawal">-${Math.abs(tx.amount).toLocaleString()} so'm</span>`,
      });
    } else if (tx.type === "reset") {
      items.push({
        id: tx.id,
        kind: "fund",
        type: "reset",
        title: `Kassa mablag'i 0 qilindi`,
        subtitle: `${escapeHtml(tx.note || "")} • ${tx.created_at || ""}`,
        amount: 0,
        rawTime: tx.created_at || "",
        badge: `<span class="tx-badge reset">🔄 0 qilindi</span>`,
        amountHtml: `<span class="tx-amount-tag reset">0 so'm</span>`,
      });
    }
  });

  // 2. Xarajatlar
  (appState.recentExpenses || []).forEach((exp) => {
    const isFund = exp.payment_source === "fund";
    items.push({
      id: exp.id,
      kind: "expense",
      type: "expense",
      title: escapeHtml(exp.title),
      subtitle: `${escapeHtml(exp.paid_by)} (${isFund ? "💰 Kassadan" : "👤 Shaxsiy"}) • ${exp.created_at || ""}`,
      amount: exp.amount,
      rawTime: exp.created_at || "",
      badge: `<span class="tx-badge expense">🛒 ${escapeHtml(exp.category || "Xarajat")}</span>`,
      amountHtml: `<span class="tx-amount-tag expense">-${Number(exp.amount).toLocaleString()} so'm</span>`,
    });
  });

  // Filtrlash
  const currentFilter = appState.financeFilter || "all";
  if (currentFilter === "income") {
    items = items.filter((i) => i.type === "income");
  } else if (currentFilter === "withdraw") {
    items = items.filter((i) => i.type === "withdrawal");
  } else if (currentFilter === "expense") {
    items = items.filter((i) => i.type === "expense");
  }

  // Vaqt bo'yicha saralash (eng yangi amallar tepada)
  items.sort((a, b) => {
    if (!a.rawTime) return 1;
    if (!b.rawTime) return -1;
    return b.rawTime.localeCompare(a.rawTime);
  });

  if (items.length === 0) {
    listEl.innerHTML = `<div class="empty-state"><p>Tanlangan filtr bo'yicha amallar mavjud emas.</p></div>`;
    return;
  }

  items.forEach((item) => {
    const el = document.createElement("div");
    el.className = "list-item";

    const deleteBtn = item.kind === "fund"
      ? `<button class="btn btn-icon btn-delete" onclick="deleteFundTx(${item.id})" title="O'chirish">🗑️</button>`
      : `<button class="btn btn-icon btn-delete" onclick="deleteExpenseItem(${item.id})" title="O'chirish">🗑️</button>`;

    el.innerHTML = `
      <div class="item-left">
        <div class="item-info">
          <div class="item-title" style="display:flex; align-items:center; gap:6px;">
            ${item.badge}
            <span>${item.title}</span>
          </div>
          <div class="item-subtitle">${item.subtitle}</div>
        </div>
      </div>
      <div style="display:flex; align-items:center; gap:8px;">
        ${item.amountHtml}
        ${deleteBtn}
      </div>
    `;
    listEl.appendChild(el);
  });
}

// 🏠 Ijara Tabini chizish
function renderRent() {
  const total = appState.rentSettings.total_amount || 0;
  const dueDay = appState.rentSettings.due_day || 5;
  document.getElementById("rent-total-display").textContent = `${total.toLocaleString()} so'm`;
  document.getElementById("rent-due-day").textContent = `Har oyning ${dueDay}-kuni`;

  const membersCount = appState.members.length || 1;
  const perPerson = Math.round(total / membersCount);
  document.getElementById("rent-per-person").textContent = `${perPerson.toLocaleString()} so'm`;

  const listEl = document.getElementById("rent-members-list");
  listEl.innerHTML = "";

  if (appState.rentStatus.length === 0) {
    listEl.innerHTML = `<div class="empty-state"><p>Navbatchilar ro'yxatida xonadoshlar mavjud emas.</p></div>`;
    return;
  }

  appState.rentStatus.forEach((m) => {
    const item = document.createElement("div");
    item.className = "list-item";

    const isPaid = m.is_paid;
    const btnClass = isPaid ? "status-btn paid" : "status-btn unpaid";
    const btnText = isPaid ? "✅ To'langan" : "⏳ To'lanmagan";

    item.innerHTML = `
      <div class="item-left">
        <div class="item-info">
          <div class="item-title">${escapeHtml(m.member_name)}</div>
          <div class="item-subtitle">${Number(m.amount).toLocaleString()} so'm ${m.paid_at ? `(${m.paid_at})` : ""}</div>
        </div>
      </div>
      <div>
        <button class="${btnClass}" onclick="toggleRent('${escapeHtml(m.member_name)}', ${m.amount})">
          ${btnText}
        </button>
      </div>
    `;
    listEl.appendChild(item);
  });
}

// 🛒 Bozorlik Tabini chizish
function renderShopping() {
  const listEl = document.getElementById("shopping-list");
  listEl.innerHTML = "";

  if (appState.shoppingItems.length === 0) {
    listEl.innerHTML = `<div class="empty-state"><p>Bozorlik ro'yxati bo'sh. Mahsulot qo'shing.</p></div>`;
    return;
  }

  appState.shoppingItems.forEach((item) => {
    const el = document.createElement("div");
    el.className = `shopping-item ${item.is_bought ? "bought" : ""}`;

    el.innerHTML = `
      <div class="shopping-left" onclick="toggleShopping(${item.id})">
        <div class="shopping-check">${item.is_bought ? "✓" : ""}</div>
        <div class="shopping-title">${escapeHtml(item.title)}</div>
      </div>
      <button class="btn btn-icon btn-delete" onclick="deleteShopping(${item.id})" title="O'chirish">🗑️</button>
    `;
    listEl.appendChild(el);
  });
}

function renderSettings() {
  if (!appState.group) return;

  const timeInput = document.getElementById("setting-notify-time");
  timeInput.value = appState.group.notify_time || "08:00";

  const workDaysVal = appState.group.work_days || "workdays_sat";
  const radio = document.querySelector(`input[name="work_days"][value="${workDaysVal}"]`);
  if (radio) radio.checked = true;

  const activeCheck = document.getElementById("setting-is-active");
  activeCheck.checked = Boolean(appState.group.is_active);
}

// Xonadoshlar selectlarini to'ldirish
function populateMemberSelects() {
  const incomeSelect = document.getElementById("select-income-member");
  const withdrawalSelect = document.getElementById("select-withdrawal-member");
  const resetSelect = document.getElementById("select-reset-member");
  const expenseSelect = document.getElementById("select-expense-member");

  if (incomeSelect) incomeSelect.innerHTML = "";
  if (withdrawalSelect) withdrawalSelect.innerHTML = "";
  if (resetSelect) resetSelect.innerHTML = "";
  if (expenseSelect) expenseSelect.innerHTML = `<option value="Kassa">💰 Umumiy Kassa</option>`;

  appState.members.forEach((m) => {
    const createOption = () => {
      const opt = document.createElement("option");
      opt.value = m.name;
      opt.textContent = m.name;
      return opt;
    };

    if (incomeSelect) incomeSelect.appendChild(createOption());
    if (withdrawalSelect) withdrawalSelect.appendChild(createOption());
    if (resetSelect) resetSelect.appendChild(createOption());
    if (expenseSelect) expenseSelect.appendChild(createOption());
  });
}

function setupPermissions() {
  const addMemberBtn = document.getElementById("btn-add-member");
  const addTaskBtn = document.getElementById("btn-add-task");
  const nextDutyBtn = document.getElementById("btn-next-duty");
  const rentSettingsBtn = document.getElementById("btn-open-rent-settings");
  const saveBtn = document.getElementById("btn-save");

  if (!appState.isAdmin) {
    if (addMemberBtn) addMemberBtn.classList.add("hidden");
    if (addTaskBtn) addTaskBtn.classList.add("hidden");
    if (nextDutyBtn) nextDutyBtn.classList.add("hidden");
    if (rentSettingsBtn) rentSettingsBtn.classList.add("hidden");
    if (saveBtn) saveBtn.classList.add("hidden");
  } else {
    if (addMemberBtn) addMemberBtn.classList.remove("hidden");
    if (addTaskBtn) addTaskBtn.classList.remove("hidden");
    if (nextDutyBtn) nextDutyBtn.classList.remove("hidden");
    if (rentSettingsBtn) rentSettingsBtn.classList.remove("hidden");
    if (saveBtn) saveBtn.classList.remove("hidden");
  }
}

// ==================== HARAKATLAR VA HODISALAR ====================

// Tab almashtirish
document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    triggerHaptic("selection");
    document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab-pane").forEach((p) => p.classList.remove("active"));

    btn.classList.add("active");
    const targetTab = btn.getAttribute("data-tab");
    const pane = document.getElementById(`tab-${targetTab}`);
    if (pane) pane.classList.add("active");
  });
});

// Tezkor summa yordamchilari
window.addAmountToInput = function (inputId, amount) {
  triggerHaptic("selection");
  const el = document.getElementById(inputId);
  if (!el) return;
  const current = parseInt(el.value, 10) || 0;
  el.value = current + amount;
};

window.setAmountToInput = function (inputId, amount) {
  triggerHaptic("selection");
  const el = document.getElementById(inputId);
  if (!el) return;
  el.value = amount;
};

window.setAllWithdrawalAmount = function () {
  triggerHaptic("selection");
  const el = document.getElementById("input-withdrawal-amount");
  if (!el) return;
  el.value = Math.max(0, appState.fundBalance || 0);
};

// 1. Kassa Kirim
document.getElementById("btn-open-income-modal").addEventListener("click", () => {
  document.getElementById("input-income-amount").value = "";
  document.getElementById("input-income-note").value = "";
  document.getElementById("modal-income").classList.remove("hidden");
});

document.getElementById("btn-confirm-income").addEventListener("click", async () => {
  const member = document.getElementById("select-income-member").value;
  const amount = parseInt(document.getElementById("input-income-amount").value, 10);
  const note = document.getElementById("input-income-note").value.trim();

  if (!member || isNaN(amount) || amount <= 0) {
    alert("Iltimos, summani to'g'ri kiriting!");
    return;
  }

  try {
    const headers = { "Content-Type": "application/json" };
    if (tg?.initData) headers["X-Telegram-Init-Data"] = tg.initData;

    const res = await fetch("/api/add-fund-income", {
      method: "POST",
      headers,
      body: JSON.stringify({ chat_id: appState.chatId, member_name: member, amount, note }),
    });
    const data = await res.json();
    if (!res.ok || !data.success) throw new Error(data.error || "Xatolik yuz berdi");

    closeModals();
    showToast(data.message, "success");
    await loadAllData();
  } catch (err) {
    showToast(err.message, "error");
  }
});

// 2. Kassa Chiqim (Mablag' chiqarish / Yechish)
const openWithdrawalBtn = document.getElementById("btn-open-withdrawal-modal");
if (openWithdrawalBtn) {
  openWithdrawalBtn.addEventListener("click", () => {
    document.getElementById("input-withdrawal-amount").value = "";
    document.getElementById("input-withdrawal-note").value = "";
    const curBalEl = document.getElementById("withdrawal-current-balance");
    if (curBalEl) curBalEl.textContent = `${(appState.fundBalance || 0).toLocaleString()} so'm`;
    document.getElementById("modal-withdrawal").classList.remove("hidden");
  });
}

const confirmWithdrawalBtn = document.getElementById("btn-confirm-withdrawal");
if (confirmWithdrawalBtn) {
  confirmWithdrawalBtn.addEventListener("click", async () => {
    const member = document.getElementById("select-withdrawal-member").value;
    const amount = parseInt(document.getElementById("input-withdrawal-amount").value, 10);
    const note = document.getElementById("input-withdrawal-note").value.trim();

    if (!member || isNaN(amount) || amount <= 0) {
      alert("Iltimos, chiqariladigan summani to'g'ri kiriting!");
      return;
    }

    try {
      const headers = { "Content-Type": "application/json" };
      if (tg?.initData) headers["X-Telegram-Init-Data"] = tg.initData;

      const res = await fetch("/api/add-fund-withdrawal", {
        method: "POST",
        headers,
        body: JSON.stringify({ chat_id: appState.chatId, member_name: member, amount, note }),
      });
      const data = await res.json();
      if (!res.ok || !data.success) throw new Error(data.error || "Xatolik yuz berdi");

      closeModals();
      showToast(data.message, "success");
      await loadAllData();
    } catch (err) {
      showToast(err.message, "error");
    }
  });
}

// 3. Kassa Mablag'ini 0 Qilish (Reset)
const openResetFundBtn = document.getElementById("btn-open-reset-fund-modal");
if (openResetFundBtn) {
  openResetFundBtn.addEventListener("click", () => {
    const curBalEl = document.getElementById("reset-current-balance");
    if (curBalEl) curBalEl.textContent = `${(appState.fundBalance || 0).toLocaleString()} so'm`;
    document.getElementById("modal-reset-fund").classList.remove("hidden");
  });
}

const confirmResetFundBtn = document.getElementById("btn-confirm-reset-fund");
if (confirmResetFundBtn) {
  confirmResetFundBtn.addEventListener("click", async () => {
    const modeRadio = document.querySelector('input[name="reset_fund_mode"]:checked');
    const clearAll = modeRadio ? modeRadio.value === "clear" : false;
    const member = document.getElementById("select-reset-member")?.value || "Xonadosh";

    try {
      const headers = { "Content-Type": "application/json" };
      if (tg?.initData) headers["X-Telegram-Init-Data"] = tg.initData;

      const res = await fetch("/api/reset-fund", {
        method: "POST",
        headers,
        body: JSON.stringify({ chat_id: appState.chatId, clear_all: clearAll, reset_by: member }),
      });
      const data = await res.json();
      if (!res.ok || !data.success) throw new Error(data.error || "Xatolik yuz berdi");

      closeModals();
      showToast(data.message, "success");
      await loadAllData();
    } catch (err) {
      showToast(err.message, "error");
    }
  });
}

// 4. Tarix Filtrlari
document.querySelectorAll(".history-filter-tabs .filter-chip").forEach((chip) => {
  chip.addEventListener("click", () => {
    triggerHaptic("selection");
    document.querySelectorAll(".history-filter-tabs .filter-chip").forEach((c) => c.classList.remove("active"));
    chip.classList.add("active");
    appState.financeFilter = chip.dataset.filter || "all";
    renderFinance();
  });
});

// 5. Kassa va Xarajatlarni o'chirish (Delete)
window.deleteFundTx = async function (txId) {
  if (!confirm("Ushbu kassa amalini o'chirmoqchimisiz?")) return;
  triggerHaptic("warning");
  try {
    const headers = { "Content-Type": "application/json" };
    if (tg?.initData) headers["X-Telegram-Init-Data"] = tg.initData;

    const res = await fetch("/api/delete-fund-transaction", {
      method: "POST",
      headers,
      body: JSON.stringify({ chat_id: appState.chatId, tx_id: txId }),
    });
    const data = await res.json();
    if (!res.ok || !data.success) throw new Error(data.error || "O'chirishda xatolik");

    showToast("Amal o'chirildi", "success");
    await loadAllData();
  } catch (err) {
    showToast(err.message, "error");
  }
};

window.deleteExpenseItem = async function (expenseId) {
  if (!confirm("Ushbu xarajatni o'chirmoqchimisiz?")) return;
  triggerHaptic("warning");
  try {
    const headers = { "Content-Type": "application/json" };
    if (tg?.initData) headers["X-Telegram-Init-Data"] = tg.initData;

    const res = await fetch("/api/delete-expense", {
      method: "POST",
      headers,
      body: JSON.stringify({ chat_id: appState.chatId, expense_id: expenseId }),
    });
    const data = await res.json();
    if (!res.ok || !data.success) throw new Error(data.error || "O'chirishda xatolik");

    showToast("Xarajat o'chirildi", "success");
    await loadAllData();
  } catch (err) {
    showToast(err.message, "error");
  }
};

// 2. Xarajat Chiqim
document.getElementById("btn-open-expense-modal").addEventListener("click", () => {
  document.getElementById("input-expense-title").value = "";
  document.getElementById("input-expense-amount").value = "";
  document.getElementById("modal-expense").classList.remove("hidden");
});

document.getElementById("btn-confirm-expense").addEventListener("click", async () => {
  const title = document.getElementById("input-expense-title").value.trim();
  const amount = parseInt(document.getElementById("input-expense-amount").value, 10);
  const paidBy = document.getElementById("select-expense-member").value;
  const source = document.getElementById("select-expense-source").value;
  const category = document.getElementById("select-expense-category").value;

  if (!title || isNaN(amount) || amount <= 0) {
    alert("Iltimos, xarajat nomi va summasini kiriting!");
    return;
  }

  try {
    const headers = { "Content-Type": "application/json" };
    if (tg?.initData) headers["X-Telegram-Init-Data"] = tg.initData;

    const res = await fetch("/api/add-expense", {
      method: "POST",
      headers,
      body: JSON.stringify({
        chat_id: appState.chatId,
        title,
        amount,
        paid_by: paidBy,
        payment_source: source,
        category,
      }),
    });
    const data = await res.json();
    if (!res.ok || !data.success) throw new Error(data.error || "Xatolik yuz berdi");

    closeModals();
    showToast(data.message, "success");
    await loadAllData();
  } catch (err) {
    showToast(err.message, "error");
  }
});

// 3. Ijara sozlamalari
document.getElementById("btn-open-rent-settings").addEventListener("click", () => {
  if (!appState.isAdmin) return;
  document.getElementById("input-rent-total").value = appState.rentSettings.total_amount || "";
  document.getElementById("input-rent-due-day").value = appState.rentSettings.due_day || 5;
  document.getElementById("modal-rent-settings").classList.remove("hidden");
});

document.getElementById("btn-confirm-rent-settings").addEventListener("click", async () => {
  const total = parseInt(document.getElementById("input-rent-total").value, 10);
  const dueDay = parseInt(document.getElementById("input-rent-due-day").value, 10);

  if (isNaN(total) || isNaN(dueDay)) {
    alert("Iltimos, ma'lumotlarni to'g'ri kiriting!");
    return;
  }

  try {
    const headers = { "Content-Type": "application/json" };
    if (tg?.initData) headers["X-Telegram-Init-Data"] = tg.initData;

    const res = await fetch("/api/update-rent-settings", {
      method: "POST",
      headers,
      body: JSON.stringify({ chat_id: appState.chatId, total_amount: total, due_day: dueDay }),
    });
    const data = await res.json();
    if (!res.ok || !data.success) throw new Error(data.error || "Xatolik");

    closeModals();
    showToast(data.message, "success");
    await loadAllData();
  } catch (err) {
    showToast(err.message, "error");
  }
});

// 4. Xonadosh ijara to'lovini belgilash
window.toggleRent = async function (memberName, amount) {
  if (!appState.isAdmin) {
    showToast("Faqat admin to'lov holatini belgilashi mumkin", "error");
    return;
  }
  triggerHaptic("selection");

  try {
    const headers = { "Content-Type": "application/json" };
    if (tg?.initData) headers["X-Telegram-Init-Data"] = tg.initData;

    const monthYear = new Date().toISOString().slice(0, 7);

    const res = await fetch("/api/toggle-rent-payment", {
      method: "POST",
      headers,
      body: JSON.stringify({ chat_id: appState.chatId, member_name: memberName, amount, month_year: monthYear }),
    });
    const data = await res.json();
    if (!res.ok || !data.success) throw new Error(data.error || "Xatolik");

    showToast(`${memberName}: ${data.message}`, "success");
    await loadAllData();
  } catch (err) {
    showToast(err.message, "error");
  }
};

// 5. Bozorlik qo'shish
document.getElementById("btn-add-shopping").addEventListener("click", async () => {
  const input = document.getElementById("input-shopping-title");
  const title = input.value.trim();
  if (!title) return;

  try {
    const headers = { "Content-Type": "application/json" };
    if (tg?.initData) headers["X-Telegram-Init-Data"] = tg.initData;

    const res = await fetch("/api/shopping-item", {
      method: "POST",
      headers,
      body: JSON.stringify({ chat_id: appState.chatId, action: "add", title }),
    });
    const data = await res.json();
    if (!res.ok || !data.success) throw new Error(data.error || "Xatolik");

    input.value = "";
    triggerHaptic("success");
    await loadAllData();
  } catch (err) {
    showToast(err.message, "error");
  }
});

window.toggleShopping = async function (itemId) {
  triggerHaptic("selection");
  try {
    const headers = { "Content-Type": "application/json" };
    if (tg?.initData) headers["X-Telegram-Init-Data"] = tg.initData;

    await fetch("/api/shopping-item", {
      method: "POST",
      headers,
      body: JSON.stringify({ chat_id: appState.chatId, action: "toggle", item_id: itemId }),
    });
    await loadAllData();
  } catch (err) {
    showToast(err.message, "error");
  }
};

window.deleteShopping = async function (itemId) {
  triggerHaptic("warning");
  try {
    const headers = { "Content-Type": "application/json" };
    if (tg?.initData) headers["X-Telegram-Init-Data"] = tg.initData;

    await fetch("/api/shopping-item", {
      method: "POST",
      headers,
      body: JSON.stringify({ chat_id: appState.chatId, action: "delete", item_id: itemId }),
    });
    await loadAllData();
  } catch (err) {
    showToast(err.message, "error");
  }
};

document.getElementById("btn-clear-bought").addEventListener("click", async () => {
  if (!confirm("Olingan barcha mahsulotlar ro'yxatdan o'chirilsinmi?")) return;
  triggerHaptic("warning");
  try {
    const headers = { "Content-Type": "application/json" };
    if (tg?.initData) headers["X-Telegram-Init-Data"] = tg.initData;

    await fetch("/api/shopping-item", {
      method: "POST",
      headers,
      body: JSON.stringify({ chat_id: appState.chatId, action: "clear_bought" }),
    });
    showToast("Tozalandi", "success");
    await loadAllData();
  } catch (err) {
    showToast(err.message, "error");
  }
});

// 6. Navbatchilik boshqaruvi
window.moveMember = function (index, direction) {
  triggerHaptic("selection");
  const newIndex = index + direction;
  if (newIndex < 0 || newIndex >= appState.members.length) return;

  const temp = appState.members[index];
  appState.members[index] = appState.members[newIndex];
  appState.members[newIndex] = temp;
  renderMembers();
};

window.deleteMember = function (index) {
  triggerHaptic("warning");
  if (!confirm("Ushbu a'zoni o'chirmoqchimisiz?")) return;
  appState.members.splice(index, 1);
  renderMembers();
};

window.deleteTask = function (index) {
  triggerHaptic("warning");
  appState.tasks.splice(index, 1);
  renderTasks();
};

document.getElementById("btn-next-duty").addEventListener("click", async () => {
  if (!appState.isAdmin) return;
  triggerHaptic("medium");

  try {
    const headers = { "Content-Type": "application/json" };
    if (tg?.initData) headers["X-Telegram-Init-Data"] = tg.initData;

    const res = await fetch("/api/next-duty", {
      method: "POST",
      headers,
      body: JSON.stringify({ chat_id: appState.chatId }),
    });
    const data = await res.json();
    if (!res.ok || !data.success) throw new Error(data.error || "Xatolik");

    showToast(data.message, "success");
    await loadAllData();
  } catch (err) {
    showToast(err.message, "error");
  }
});

// Modallarni ochish (A'zo va Vazifa)
document.getElementById("btn-add-member").addEventListener("click", () => {
  document.getElementById("input-member-name").value = "";
  document.getElementById("input-member-username").value = "";
  document.getElementById("modal-member").classList.remove("hidden");
});

document.getElementById("btn-add-task").addEventListener("click", () => {
  document.getElementById("input-task-text").value = "";
  document.getElementById("modal-task").classList.remove("hidden");
});

document.getElementById("btn-confirm-add-member").addEventListener("click", () => {
  const name = document.getElementById("input-member-name").value.trim();
  const username = document.getElementById("input-member-username").value.trim().replace(/^@/, "");

  if (!name) {
    alert("Iltimos, ismni kiriting!");
    return;
  }

  appState.members.push({ name, username });
  closeModals();
  renderMembers();
  populateMemberSelects();
  triggerHaptic("success");
});

document.getElementById("btn-confirm-add-task").addEventListener("click", () => {
  const taskText = document.getElementById("input-task-text").value.trim();
  if (!taskText) {
    alert("Iltimos, vazifa matnini kiriting!");
    return;
  }

  appState.tasks.push(taskText);
  closeModals();
  renderTasks();
  triggerHaptic("success");
});

// Sozlamalarni saqlash
document.getElementById("btn-save").addEventListener("click", async () => {
  if (!appState.isAdmin) return;
  triggerHaptic("medium");

  const notifyTime = document.getElementById("setting-notify-time").value || "08:00";
  const selectedRadio = document.querySelector('input[name="work_days"]:checked');
  const workDays = selectedRadio ? selectedRadio.value : "workdays_sat";
  const isActive = document.getElementById("setting-is-active").checked ? 1 : 0;

  const payload = {
    chat_id: appState.chatId,
    members: appState.members,
    tasks: appState.tasks,
    settings: {
      notify_time: notifyTime,
      work_days: workDays,
      is_active: isActive,
    },
  };

  const saveBtn = document.getElementById("btn-save");
  const originalText = saveBtn.textContent;
  saveBtn.disabled = true;
  saveBtn.textContent = "⏳ Saqlanmoqda...";

  try {
    const headers = { "Content-Type": "application/json" };
    if (tg?.initData) headers["X-Telegram-Init-Data"] = tg.initData;

    const res = await fetch("/api/save-group-data", {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok || !data.success) throw new Error(data.error || "Saqlashda xatolik");

    showToast("✅ Barcha o'zgarishlar saqlandi!", "success");
    await loadAllData();
  } catch (err) {
    showToast(`❌ ${err.message}`, "error");
  } finally {
    saveBtn.disabled = false;
    saveBtn.textContent = originalText;
  }
});

function escapeHtml(text) {
  if (!text) return "";
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

// Boshlang'ich yuklash
document.addEventListener("DOMContentLoaded", loadAllData);
