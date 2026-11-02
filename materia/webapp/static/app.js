"use strict";

(() => {
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  const esc = (value) => String(value == null ? "" : value)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");

  const GROUPS = [
    { label: "Limiting amino acids", names: ["Lysine", "Methionine", "Tryptophan"] },
    { label: "Branched-chain amino acids", names: ["Isoleucine", "Leucine", "Valine"] },
    { label: "Other essential amino acids", names: ["Phenylalanine", "Histidine", "Threonine"] },
    { label: "Conditionally essential amino acids", names: ["Arginine", "Taurine"] },
    { label: "Ratios", names: ["Tryptophan/LNAA"] }
  ];
  const STATUS_LABEL = { confirmed: "Checked", ready: "Ready", review: "Needs a look" };

  // Worked examples are synthetic, labelled, and never presented as the uploaded report.
  const EXAMPLES = {
    iron: {
      label: "iron deficiency with anaemia",
      intake: { age: 42, sex: "female" },
      rows: [
        { analyte: "Ferritin", value: 8, unit: "ng/mL", ref_low: 15, ref_high: 150 },
        { analyte: "Haemoglobin", value: 105, unit: "g/L", ref_low: 120, ref_high: 160 },
        { analyte: "MCV", value: 76, unit: "fL", ref_low: 80, ref_high: 100 },
        { analyte: "CRP", value: 2, unit: "mg/L", ref_low: 0, ref_high: 5 }
      ]
    },
    b12: {
      label: "B12 deficiency with macrocytosis",
      intake: { age: 60, sex: "female" },
      rows: [
        { analyte: "Vitamin B12", value: 150, unit: "pmol/L", ref_low: 219, ref_high: 773 },
        { analyte: "MCV", value: 102, unit: "fL", ref_low: 80, ref_high: 100 }
      ]
    },
    critical: {
      label: "critical potassium",
      intake: { age: 60, sex: "male" },
      rows: [
        { analyte: "Potassium", value: 6.5, unit: "mmol/L", ref_low: 3.7, ref_high: 5.2 }
      ]
    },
    urgent: {
      label: "high calcium and severe triglycerides",
      intake: { age: 58, sex: "female" },
      rows: [
        { analyte: "Calcium", value: 2.90, unit: "mmol/L", ref_low: 2.20, ref_high: 2.58 },
        { analyte: "Triglycerides", value: 7.0, unit: "mmol/L", ref_low: 0.4, ref_high: 1.7 }
      ]
    },
    metabolic: {
      label: "dysglycaemia and elevated LDL",
      intake: { age: 52, sex: "male" },
      rows: [
        { analyte: "HbA1c", value: 5.9, unit: "%", ref_low: 4.0, ref_high: 5.6 },
        { analyte: "LDL", value: 3.8, unit: "mmol/L", ref_low: 0, ref_high: 2.6 }
      ]
    },
    liver: {
      label: "liver enzyme elevation",
      intake: { age: 50, sex: "male" },
      rows: [
        { analyte: "ALT", value: 65, unit: "U/L", ref_low: 4, ref_high: 36 },
        { analyte: "AST", value: 45, unit: "U/L", ref_low: 8, ref_high: 33 },
        { analyte: "GGT", value: 55, unit: "U/L", ref_low: 5, ref_high: 40 }
      ]
    },
    lipids: {
      label: "high triglycerides with low HDL",
      intake: { age: 45, sex: "male" },
      rows: [
        { analyte: "Triglycerides", value: 3.2, unit: "mmol/L", ref_low: 0.4, ref_high: 1.7 },
        { analyte: "HDL", value: 0.8, unit: "mmol/L", ref_low: 1.0, ref_high: 3.0 }
      ]
    }
  };

  const state = {
    report: null,
    rows: [],
    selected: 0,
    filter: "all",
    view: "review",
    status: null,
    file: null,
    busy: false,
    assessment: null,
    chat: [],
    reviews: {},
    reviewCases: null,
    reviewIndex: 0,
    reviewLabels: {}
  };

  let readingStarted = 0;
  let readingTimer = null;

  const storageKey = () => state.report ? `materia.confirmed.${state.report.session}` : "materia.confirmed.none";
  const savedConfirmations = () => {
    try { return new Set(JSON.parse(localStorage.getItem(storageKey()) || "[]")); }
    catch { return new Set(); }
  };
  const saveConfirmations = () => {
    try {
      localStorage.setItem(storageKey(), JSON.stringify(state.rows.filter(r => r.status === "confirmed").map(r => r.analyte)));
    } catch { /* private mode is fine */ }
  };

  async function api(path, options = {}) {
    const response = await fetch(path, { credentials: "same-origin", ...options });
    const type = response.headers.get("content-type") || "";
    const payload = type.includes("application/json") ? await response.json() : null;
    if (!response.ok) {
      const message = payload && payload.error ? payload.error : `Request failed (${response.status}).`;
      throw new Error(message);
    }
    return payload;
  }

  function startReading() {
    readingStarted = Date.now();
    const copy = $("#loading-copy");
    const tick = () => {
      const seconds = Math.floor((Date.now() - readingStarted) / 1000);
      const minutes = Math.floor(seconds / 60);
      const rest = String(seconds % 60).padStart(2, "0");
      copy.textContent = `The local OCR engine is reading the page. It can take several minutes on CPU. Elapsed ${minutes}:${rest}.`;
    };
    tick();
    clearInterval(readingTimer);
    readingTimer = setInterval(tick, 1000);
  }

  function stopReading() {
    clearInterval(readingTimer);
    readingTimer = null;
  }

  function toast(message, ms = 2400) {
    const node = $("#toast");
    node.textContent = message;
    node.classList.add("is-visible");
    clearTimeout(toast._timer);
    toast._timer = setTimeout(() => node.classList.remove("is-visible"), ms);
  }

  function formatValue(row) {
    if (row.value == null) return row.value_text || "—";
    return row.unit === "ratio" ? Number(row.value).toFixed(3) : String(Number(row.value));
  }
  function formatRange(row) {
    const low = row.ref_low == null ? null : (row.unit === "ratio" ? Number(row.ref_low).toFixed(3) : String(Number(row.ref_low)));
    const high = row.ref_high == null ? null : (row.unit === "ratio" ? Number(row.ref_high).toFixed(3) : String(Number(row.ref_high)));
    if (low == null && high == null) return "—";
    if (low == null) return `<${high}`;
    if (high == null) return `>${low}`;
    return `${low}–${high}`;
  }
  function formatDate(iso) {
    if (!iso) return "No collection date";
    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
    if (!m) return iso;
    const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    return `${Number(m[3])} ${months[Number(m[2]) - 1]} ${m[1]}`;
  }
  function counts() {
    const confirmed = state.rows.filter(r => r.status === "confirmed").length;
    return {
      confirmed,
      left: state.rows.length - confirmed,
      flags: state.rows.filter(r => Boolean(r.flag)).length,
      review: state.rows.filter(r => r.status === "review").length
    };
  }

  function renderHero() {
    const c = counts();
    const pct = state.rows.length ? (c.confirmed / state.rows.length) * 100 : 0;
    $("#ring").style.setProperty("--p", pct.toFixed(2));
    $("#ring-count").textContent = String(c.confirmed);
    $("#ring-total").textContent = `of ${state.rows.length}`;
    $("#count-all").textContent = String(state.rows.length);
    $("#count-finish").textContent = String(c.left);
    $("#count-notes").textContent = String(c.flags);
    const title = c.left === 0 && state.rows.length
      ? "Everything is checked."
      : c.left === state.rows.length
        ? `${state.rows.length} values to check.`
        : c.left === 1
          ? "One value left."
          : `${c.left} values left.`;
    $("#progress-title").textContent = title;
    $("#progress-sub").textContent = c.left === 0
      ? "Every number has been compared with the page."
      : c.left === state.rows.length
        ? "Start anywhere. The page stays beside you."
        : "Take your time. The checked values stay checked.";
    const finish = $("#finish-btn");
    finish.hidden = c.left === 0;
    finish.textContent = c.left === state.rows.length
      ? "Review the values"
      : c.left === 1
        ? "Finish the last one"
        : `Finish the last ${c.left}`;
    $("#review-title").textContent = `${state.rows.length} values, grouped as the lab groups them.`;
  }

  function renderMeta() {
    const doc = state.report.doc;
    const chips = [
      doc.lab || "Lab report",
      doc.collected ? formatDate(doc.collected) : "Collection date not read",
      `${state.rows.length} values`,
      doc.page_label || "Page 1"
    ];
    $("#meta-row").innerHTML = chips.map((chip) => `<span class="meta-chip">${esc(chip)}</span>`).join("");
  }

  // A multi-page report shows the page the selected value was read from.
  function selectedPage() {
    const doc = state.report && state.report.doc;
    if (!doc || doc.sample) return null;
    const row = state.rows[state.selected];
    return (row && row.page) || doc.page_number || 1;
  }

  function pageSrc() {
    const doc = state.report.doc;
    if (doc.sample) return doc.image;
    const params = new URLSearchParams({ v: state.report.session });
    const page = selectedPage();
    if (page) params.set("page", String(page));
    return `${doc.image}?${params.toString()}`;
  }

  function renderReport() {
    const doc = state.report.doc;
    $("#report-title").textContent = doc.page_label || "Report";
    const page = selectedPage();
    const image = $("#report-image");
    image.src = pageSrc();
    image.alt = doc.sample
      ? "Page 2 of the Genova Diagnostics bloodspot amino acids sample report, with results, quintile bars and the lab's reference intervals."
      : `Page ${page || 1}${doc.page_count ? ` of ${doc.page_count}` : ""} of the uploaded lab report.`;
    $("#open-full-page").href = pageSrc();
    $("#provenance-chip").textContent = doc.provenance || "Read locally";
    $("#mode-chip").textContent = doc.sample ? "Sample report" : "Your report";
    $("#footer-note").textContent = doc.sample
      ? "Sample report, not a patient · local only · no model in sample mode · not a diagnosis"
      : "Local only · uploaded file kept in a temporary folder · not a diagnosis";
  }

  function renderBands() {
    const row = state.rows[state.selected];
    if (!row || row.y == null) {
      $("#bands").innerHTML = "";
      $("#highlight-caption").textContent = row ? `${row.analyte} selected` : "—";
      const page = selectedPage();
      $("#report-help").textContent = page
        ? `This report has no row highlight. Compare ${row ? row.analyte : "the value"} with page ${page}.`
        : "This report has no row highlight. Compare the selected value with the page.";
      return;
    }
    $("#bands").innerHTML = state.rows.map((item, index) => (
      item.y == null ? "" : `<div class="band${index === state.selected ? " is-selected" : ""}" style="top:${item.y}%"></div>`
    )).join("");
    $("#highlight-caption").textContent = `Highlighted: ${row.analyte}, row ${String(state.selected + 1).padStart(2, "0")}`;
    $("#report-help").textContent = "Choose a value on the right to find its line on the page.";
  }

  function issueLabel(issue) {
    const text = String(issue || "");
    if (/collection date/i.test(text)) return ["Collection date", "not read from this report"];
    if (/plausibility table/i.test(text)) return ["Plausible range", "this analyte is not in the check table"];
    if (/outside plausible/i.test(text)) return ["Plausible range", text];
    if (/unit/i.test(text)) return ["Unit", text];
    if (/reference interval/i.test(text)) return ["Lab range", text];
    if (/no numeric/i.test(text)) return ["Number", "no numeric value was read"];
    return ["Check", text];
  }

  function checkMarkup(soft, label, text) {
    return `<div class="check${soft ? " is-soft" : ""}"><svg class="icon" aria-hidden="true"><use href="#i-${soft ? "eye" : "check"}"></use></svg><span><b>${esc(label)}</b> ${esc(text)}</span></div>`;
  }

  function detailMarkup(row, index) {
    const isReview = row.status === "review";
    const isChecked = row.status === "confirmed";
    const issues = Array.isArray(row.issues) ? row.issues : [];
    const flagged = Boolean(row.flag);
    const flagNote = row.flag_kind === "lab"
      ? "The lab's own marker. It is shown as printed."
      : "The value is outside the lab's range.";

    const copy = isChecked
      ? { kicker: "Checked by you", title: "This one has been compared.", text: "The value matches the page. It is ready to use in the note." }
      : isReview
        ? { kicker: "A closer look", title: "This one needs a closer look.", text: row.review_reason || "Compare it with the page before confirming." }
        : { kicker: "Ready to check", title: "This one read cleanly.", text: "One quick comparison with the page, then it is done." };

    const checks = [];
    if (issues.length) {
      for (const issue of issues) {
        const [label, text] = issueLabel(issue);
        checks.push(checkMarkup(true, label, text));
      }
    } else {
      checks.push(checkMarkup(false, "Plausible", "the value sits inside a wide physical range"));
      checks.push(checkMarkup(false, "Unit", `${row.unit || "unit"} is recognised`));
      checks.push(checkMarkup(false, "Lab range", (row.ref_low == null && row.ref_high == null) ? "not printed on the page" : "printed on the source page"));
      checks.push(checkMarkup(false, "Date", state.report.doc.collected ? "collection date present" : "not read from this report"));
    }
    if (flagged) checks.push(checkMarkup(true, "Lab note", flagNote));

    const actions = isChecked
      ? '<div class="detail-actions"><span class="checked-note"><svg class="icon" aria-hidden="true"><use href="#i-check"></use></svg> Checked by you</span></div>'
      : `<div class="detail-actions">
          ${isReview ? '<label class="soft-checkbox"><input type="checkbox" id="compare-check"><span class="box" aria-hidden="true"></span><span>I compared this number with the report</span></label>' : "<span></span>"}
          <button class="confirm-btn" type="button" id="confirm-value" ${isReview ? "disabled" : ""}>Looks right</button>
        </div>`;

    return `<div class="value-detail">
      <div class="detail-top">
        <div class="detail-copy"><p class="detail-kicker">${esc(copy.kicker)}</p><h3>${esc(copy.title)}</h3><p>${esc(copy.text)}</p></div>
        <div class="detail-figure"><b>${esc(formatValue(row))}</b><span>${esc(row.unit || "")}</span><p>Lab range ${esc(formatRange(row))}</p></div>
      </div>
      <div class="checks">${checks.join("")}</div>
      ${actions}
    </div>`;
  }

  function rowMarkup(row, index) {
    const open = index === state.selected;
    const statusClass = row.status === "confirmed" ? "checked" : row.status;
    return `<div class="value-row${open ? " is-open" : ""}" data-row="${index}">
      <button class="value-btn" type="button" data-select="${index}" aria-expanded="${open}">
        <span class="value-name">${esc(row.analyte)}${row.flag ? `<span class="lab-mark" title="${row.flag_kind === "lab" ? "Lab flag" : "Outside the lab's range"}">${esc(row.flag)}</span>` : ""}</span>
        <span class="value-figure">${esc(formatValue(row))}<small>${esc(row.unit || "")}</small></span>
        <span class="value-range">${esc(formatRange(row))}<small>range</small></span>
        <span class="status-pill status-pill--${statusClass}">${esc(STATUS_LABEL[row.status] || row.status)}</span>
        <svg class="icon chev" aria-hidden="true"><use href="#i-chevron"></use></svg>
      </button>
      ${open ? detailMarkup(row, index) : ""}
    </div>`;
  }

  function visibleRows() {
    return state.rows.map((row, index) => ({ row, index })).filter(({ row }) => {
      if (state.filter === "finish") return row.status !== "confirmed";
      if (state.filter === "notes") return Boolean(row.flag);
      return true;
    });
  }

  function renderList() {
    const visible = visibleRows();
    if (!state.rows.length) {
      $("#value-list").innerHTML = '<p class="value-empty">No values yet. Add a lab report, or try the sample report again.</p>';
      return;
    }
    if (!visible.length) {
      $("#value-list").innerHTML = '<p class="value-empty">Every value in this view is checked. Switch back to All to see the full panel.</p>';
    } else if (visible.some(({ row }) => row.section)) {
      // A general pathology report names its own panels ("Lipid Profile", "Haematology").
      // Use those headings, in the order the lab printed them, and keep the row order.
      let html = "";
      let heading = null;
      let bucket = [];
      const flush = () => {
        if (!bucket.length) return;
        html += `<p class="group-label">${esc(heading || "Report")}</p>`;
        html += bucket.map(({ row, index }) => rowMarkup(row, index)).join("");
        bucket = [];
      };
      for (const entry of visible) {
        const next = entry.row.section || "Report";
        if (next !== heading) { flush(); heading = next; }
        bucket.push(entry);
      }
      flush();
      $("#value-list").innerHTML = html;
    } else {
      let html = "";
      const known = new Set(GROUPS.flatMap(group => group.names));
      for (const group of GROUPS) {
        const inGroup = visible.filter(({ row }) => group.names.includes(row.analyte));
        if (!inGroup.length) continue;
        html += `<p class="group-label">${esc(group.label)}</p>`;
        html += inGroup.map(({ row, index }) => rowMarkup(row, index)).join("");
      }
      const extras = visible.filter(({ row }) => !known.has(row.analyte));
      if (extras.length) {
        if (known.size) html += '<p class="group-label">Other values</p>';
        html += extras.map(({ row, index }) => rowMarkup(row, index)).join("");
      }
      $("#value-list").innerHTML = html;
    }

    $$(".filter").forEach(button => {
      button.setAttribute("aria-pressed", String(button.dataset.filter === state.filter));
    });

    const checkbox = $("#compare-check");
    if (checkbox) {
      checkbox.addEventListener("change", () => {
        const button = $("#confirm-value");
        if (button) button.disabled = !checkbox.checked;
      });
    }
    const confirm = $("#confirm-value");
    if (confirm) confirm.addEventListener("click", () => confirmSelected());
  }

  async function confirmSelected() {
    const row = state.rows[state.selected];
    if (!row || state.busy) return;
    state.busy = true;
    try {
      await api("/api/lab/confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session: state.report.session, analyte: row.analyte })
      });
      row.status = "confirmed";
      row.review_reason = null;
      const visible = visibleRows();
      if (!visible.length) state.filter = "all";
      else if (!visible.some(({ index }) => index === state.selected)) state.selected = visible[0].index;
      saveConfirmations();
      renderAll();
      toast(`${row.analyte} checked.`);
    } catch (error) {
      toast(error.message, 4200);
    } finally {
      state.busy = false;
    }
  }

  function renderAll() {
    renderHero();
    renderMeta();
    renderReport();
    renderBands();
    renderList();
  }

  function setFilter(next) {
    state.filter = next;
    const visible = visibleRows();
    if (visible.length && !visible.some(({ index }) => index === state.selected)) {
      state.selected = visible[0].index;
    }
    renderHero();
    renderList();
  }

  function renderInterpretation() {
    const doc = state.report.doc;
    const flagged = state.rows.filter(row => Boolean(row.flag));
    const ranged = state.rows.filter(row => row.ref_low != null || row.ref_high != null);
    // A quotient printed as its own line ("Tryptophan/LNAA", "Tot Chol/HDL").
    const ratio = state.rows.find(row => row.unit === "ratio" || row.analyte.includes("/"));

    $("#interpret-title").textContent = "The lab's notes, in context.";
    $("#interpret-lede").textContent = `${state.rows.length} values are read from ${doc.page_label || "the report"}. The interpretation stays with what the report actually says.`;

    $("#interpret-flags-title").textContent = flagged.length
      ? `${flagged.length} value${flagged.length === 1 ? "" : "s"} carry a lab flag.`
      : "No lab flags were read.";
    $("#interpret-flags-lede").textContent = flagged.length
      ? "The lab's own markers, shown as printed. They are notes, not a diagnosis."
      : "This report did not produce a lab marker in the extraction.";
    $("#interpret-flags").innerHTML = flagged.length
      ? flagged.map(row => `<li><span>${esc(row.analyte)}</span><b>${esc(formatValue(row))}</b><small>Lab range ${esc(formatRange(row))} ${esc(row.unit || "")} · ${row.flag_kind === "lab" ? "lab marked " + esc(row.flag) : "outside the range"}</small></li>`).join("")
      : '<li><span>No flags on this report</span><b>—</b><small>The lab did not produce an L or H marker in the read.</small></li>';

    const can = [
      `${state.rows.length} values were read from ${doc.page_label || "the report"}.`,
      `${ranged.length} of ${state.rows.length} values have a printed lab range.`,
      ratio ? `The ${esc(ratio.analyte)} ratio is ${esc(formatValue(ratio))}, inside ${esc(formatRange(ratio))}.` : "No ratio value was present.",
      "This view applies no pattern rule. The plan step does, with citations.",
      "No corpus reference interval overrides the lab's own interval here."
    ];
    $("#interpret-can").innerHTML = can.map(item => `<li>${item}</li>`).join("");

    const cant = [
      doc.collected ? `Collection date: ${esc(formatDate(doc.collected))}.` : "No collection date was read from this report.",
      "Age- and sex-specific ranges are not read from this page.",
      "Fasting status and specimen handling are not stated.",
      doc.sample
        ? "This is a public sample report, not a patient record."
        : "This is an uploaded report. Confirm the patient and the date before use."
    ];
    $("#interpret-cant").innerHTML = cant.map(item => `<li>${item}</li>`).join("");

    const source = doc.source_url
      ? `Source: page ${doc.page_number || 1} of the public sample report. No clinical interpretation is generated. <a href="${esc(doc.source_url)}" target="_blank" rel="noopener noreferrer">Open the source ↗</a>`
      : "Source: the uploaded page. No clinical interpretation is generated.";
    $("#interpret-note").innerHTML = source;
  }

  function pill(text, variant = "") {
    return `<span class="pill${variant ? " pill--" + variant : ""}">${esc(text)}</span>`;
  }

  function renderChat() {
    const log = $("#chat-log");
    if (!log) return;
    if (!state.chat.length) {
      log.innerHTML = `<div class="chat-msg is-bot">Ask about the pattern, the dose, the safety screen, the monitoring or the evidence behind an option.</div>`;
      return;
    }
    log.innerHTML = state.chat.map(msg => {
      if (msg.role === "user") return `<div class="chat-msg is-user">${esc(msg.text)}</div>`;
      const cites = (msg.citations || []).length
        ? `<p class="meta-line">Sources: ${(msg.citations || []).map(c => `<code>${esc(c)}</code>`).join(" · ")}</p>` : "";
      const rejected = msg.mode === "rejected-model"
        ? `<p class="meta-line">A model answer was rejected because it introduced a claim outside this assessment, so the deterministic answer is shown.</p>` : "";
      return `<div class="chat-msg is-bot"><b>materia</b><br>${esc(msg.text)}${cites}${rejected}</div>`;
    }).join("");
    log.scrollTop = log.scrollHeight;
  }

  async function sendChat(event) {
    event.preventDefault();
    const input = $("#chat-input");
    const message = input.value.trim();
    if (!message || !state.assessment) return;
    state.chat.push({ role: "user", text: message });
    input.value = "";
    renderChat();
    const button = $("#chat-send");
    button.disabled = true;
    try {
      const result = await api("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message,
          assessment: state.assessment,
          history: state.chat.slice(0, -1).slice(-4).map(m => ({ role: m.role, text: m.text }))
        })
      });
      state.chat.push({ role: "bot", text: result.answer, citations: result.citations, mode: result.mode });
    } catch (error) {
      state.chat.push({ role: "bot", text: error.message, citations: [], mode: "error" });
    } finally {
      button.disabled = false;
      renderChat();
      input.focus();
    }
  }

  async function submitReview(optionId, decision) {
    if (!state.assessment) return;
    const reason = window.prompt(
      decision === "accept" ? "Why is this a good fit? (optional, stored locally)"
        : "Why not? (optional, stored locally)", ""
    );
    if (reason === null) return;
    try {
      await api("/api/review", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session: state.report ? state.report.session : "", option_id: optionId,
                               decision, reason })
      });
      state.reviews[optionId] = decision;
      renderPlan();
      toast(decision === "accept" ? "Accepted — saved locally." : decision === "reject" ? "Rejected — saved locally." : "Marked for modification — saved locally.");
    } catch (error) {
      toast(error.message, 5000);
    }
  }

  function renderPlan() {
    const a = state.assessment;
    const result = $("#plan-result");
    $("#chat-block").hidden = !a;
    if (!a) { result.hidden = true; return; }
    result.hidden = false;

    const patterns = a.patterns || [];
    const alerts = a.critical_alerts || [];
    const urgent = patterns.filter(p => p.severity === "high" || p.severity === "critical");
    const alert = $("#plan-alert");
    if (alerts.length) {
      alert.hidden = false;
      alert.innerHTML = `<b>Critical lab value</b>${alerts.map(x => `<span>${esc(x.analyte)} ${esc(x.value)} ${esc(x.unit)}: ${esc(x.action)}${x.age_note ? ` <em>${esc(x.age_note)}</em>` : ""}${x.citation ? ` <code>${esc(x.citation)}</code>` : ""}</span>`).join("<br>")}<br><span>Supplement and herb options are withheld until this is addressed. Confirm with the lab's own critical-value policy.</span>`;
    } else if (urgent.length) {
      alert.hidden = false;
      alert.innerHTML = `<b>Needs prompt clinical attention</b><span>${urgent.map(p => esc(p.label)).join("</span><span>")}</span><br><span>This is a triage flag, not a diagnosis. Confirm with the practitioner and the lab's own critical-value policy.</span>`;
    } else {
      alert.hidden = true;
      alert.innerHTML = "";
    }
    $("#plan-patterns").innerHTML = patterns.length ? patterns.map(p => {
      const support = (p.supporting || []).map(s => `<li>${esc(s.detail)}${s.note ? ` — ${esc(s.note)}` : ""}</li>`).join("");
      const against = (p.against || []).map(s => `<li class="is-against">${esc(s.detail)}${s.note ? ` — ${esc(s.note)}` : ""}</li>`).join("");
      const confirm = (p.confirm || []).map(s => `<li>${esc(s)}</li>`).join("");
      return `<article class="pattern-card is-${esc(p.severity)}">
        <h4>${esc(p.label)}</h4>
        <div class="pill-row">
          ${pill(p.status, p.status === "likely" ? "gold" : "muted")}
          ${pill(`${Math.round(p.confidence * 100)}% confidence`)}
          ${pill(p.severity, p.severity === "high" || p.severity === "critical" ? "clay" : "muted")}
        </div>
        ${support || against ? `<ul>${support}${against}</ul>` : ""}
        ${confirm ? `<ul>${confirm}</ul>` : ""}
        <p class="meta-line">${(p.citations || []).map(c => `<code>${esc(c)}</code>`).join(" · ")}</p>
      </article>`;
    }).join("") : `<div class="empty-card">No cited pattern matched this panel. That is a coverage gap, not a clean bill of health.<div class="pill-row" style="margin-top:10px"><button class="quiet-link" type="button" data-example="iron">See a worked iron example →</button><button class="quiet-link" type="button" data-example="b12">B12 example →</button><button class="quiet-link" type="button" data-example="lipids">Lipids example →</button></div></div>`;

    const options = a.recommendations || [];
    $("#plan-options").innerHTML = options.length ? `<div class="plan-grid">${options.map((o, i) => {
      const flags = (o.safety && o.safety.flags || []).map(f => pill(f, "clay")).join("");
      const notes = [...(o.notes || []), ...(((o.safety || {}).notes) || [])].map(n => `<li>${esc(n.text.slice(0, 240))} <code>${esc(n.chunk_id)}</code></li>`).join("");
      return `<article class="option-card">
        <div class="pill-row">${pill(`Option ${i + 1}`, "gold")}${pill(`grade ${o.grade}`)}${pill(`score ${Number(o.score).toFixed(2)}`, "muted")}</div>
        <h4>${esc(o.intervention)}</h4>
        <p class="meta-line">${esc(o.goal)}</p>
        ${o.dose ? `<div class="dose-line"><b>${esc(o.dose.text)}</b><br><span class="meta-line">${esc(o.dose.note || "")}</span></div>` : `<div class="dose-line"><b>No dose</b><br><span class="meta-line">A lifestyle or referral step, not a supplement.</span></div>`}
        ${flags ? `<p class="safety-line">Safety flags: ${flags}</p>` : ""}
        <p class="meta-line"><b>Monitor:</b> ${esc(o.monitoring.text || "")}</p>
        ${notes ? `<ul>${notes}</ul>` : ""}
        <p class="source-line">${o.dose ? `Dose source: <code>${esc(o.dose.chunk_id)}</code> · ` : ""}${(o.evidence || []).length} evidence source${(o.evidence || []).length === 1 ? "" : "s"}</p>
        ${(() => {
          const tiers = [...new Set((o.evidence || []).map(e => e.tier).filter(Boolean))];
          const names = { regulatory: "regulatory", primary: "primary literature", compendium: "public-domain compendium", traditional: "traditional use" };
          const notes = ((o.safety && o.safety.notes) || []).map(n => n.text || "").join(" ");
          const conflict = /conflict|not established|mixed|limited|inconsistent|not been established/i.test(notes);
          if (!tiers.length && !conflict) return "";
          return `<p class="tier-line">${tiers.length ? `Evidence: ${tiers.map(t => names[t] || t).join(" · ")}` : ""}${conflict ? ` <span class="conflict-badge">conflicting or limited evidence</span>` : ""}</p>`;
        })()}
        ${o.score_parts ? `<p class="meta-line">Score ${Number(o.score).toFixed(2)} = match ${Math.round((o.score_parts.match || 0) * 100)}% · evidence ${Math.round((o.score_parts.evidence || 0) * 100)}% · severity ${Math.round((o.score_parts.severity || 0) * 100)}% · rank ×${o.score_parts.rank_hint || 1}</p>` : ""}
        <div class="option-actions">
          ${state.reviews[o.id] ? pill(state.reviews[o.id] === "accept" ? "Accepted" : state.reviews[o.id] === "reject" ? "Rejected" : "Needs modification", state.reviews[o.id] === "accept" ? "" : "clay") : ""}
          <button class="quiet-link" type="button" data-review="accept" data-option="${esc(o.id)}">Accept</button>
          <button class="quiet-link" type="button" data-review="modify" data-option="${esc(o.id)}">Modify</button>
          <button class="quiet-link" type="button" data-review="reject" data-option="${esc(o.id)}">Reject</button>
        </div>
      </article>`;
    }).join("")}</div>` : `<div class="empty-card">No option passed the citation and safety gates for this panel.</div>`;

    const withheld = a.withheld || [];
    const critical = a.critical_alerts || [];
    $("#plan-withheld").innerHTML = withheld.length
      ? withheld.map(w => `<div class="withheld-card"><b>${esc(w.intervention)}</b>${esc(w.reason)}${w.detail ? ` — ${esc(w.detail)}` : ""}</div>`).join("")
      : critical.length
        ? `<div class="withheld-card"><b>Supplement and herb options withheld</b>A critical lab value is present. Referral and lifestyle steps remain visible.</div>`
        : `<div class="empty-card">Nothing was withheld. No veto or citation failure applied to this panel.</div>`;

    const gaps = a.gaps || [];
    $("#plan-gaps").innerHTML = gaps.length ? gaps.map(g => `<div class="empty-card"><b>${esc(g.label)}</b><br>${esc(g.reason)}</div>`).join("") : `<div class="empty-card">No pattern is currently without an option rule for this panel.</div>`;

    const seen = new Set();
    const sources = [];
    for (const o of options) {
      for (const e of [...(o.evidence || []), ...(o.notes || []), ...((o.safety && o.safety.notes) || [])]) {
        if (!e || seen.has(e.chunk_id)) continue;
        seen.add(e.chunk_id);
        sources.push(e);
      }
    }
    for (const x of critical) {
      if (!x.chunk_id || seen.has(x.chunk_id)) continue;
      seen.add(x.chunk_id);
      sources.push({ chunk_id: x.chunk_id, source: x.source, tier: "critical value", date: x.date, title: x.title, text: x.text, section: "critical value" });
    }
    $("#plan-evidence").innerHTML = sources.length ? `<div class="plan-grid">${sources.map(e => `<article class="source-card"><b>${esc(e.source)} · ${esc(e.tier)} · ${esc(formatDate(e.date))}</b><span>${esc(e.title)}</span><div class="quote">${esc((e.text || "").slice(0, 320))}</div><p class="meta-line"><code>${esc(e.chunk_id)}</code> · section ${esc(e.section)}</p></article>`).join("")}</div>` : `<div class="empty-card">No source was attached because no option was offered.</div>`;
    renderChat();
  }

  async function loadExample(name) {
    const example = EXAMPLES[name];
    if (!example) return;
    const status = $("#plan-status");
    status.textContent = "Loading a worked example — synthetic, not a patient…";
    try {
      const assessment = await api("/api/recommend", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rows: example.rows, intake: example.intake })
      });
      state.assessment = assessment;
      state.chat = [];
      state.reviews = {};
      renderPlan();
      status.textContent = `Worked example: ${example.label} — synthetic rows, not this report.`;
    } catch (error) {
      status.textContent = "";
      toast(error.message, 5000);
    }
  }

  async function buildPlan(event) {
    event.preventDefault();
    if (!state.report) { toast("Load a report first."); return; }
    const button = $("#build-plan");
    const status = $("#plan-status");
    button.disabled = true;
    status.textContent = "Matching patterns and checking citations…";
    const split = (value) => String(value || "").split(",").map(x => x.trim()).filter(Boolean);
    const intake = {
      age: $("#intake-age").value ? Number($("#intake-age").value) : null,
      sex: $("#intake-sex").value || null,
      medications: split($("#intake-medications").value),
      conditions: split($("#intake-conditions").value),
      symptoms: split($("#intake-symptoms").value)
    };
    if ($("#intake-pregnancy").checked) intake.contexts = ["pregnancy", "breastfeeding"];
    try {
      const assessment = await api("/api/recommend", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session: state.report.session, intake })
      });
      state.assessment = assessment;
      state.chat = [];
      state.reviews = {};
      renderPlan();
      status.textContent = `${assessment.patterns.length} pattern${assessment.patterns.length === 1 ? "" : "s"} matched · ${assessment.recommendations.length} option${assessment.recommendations.length === 1 ? "" : "s"} passed`;
    } catch (error) {
      status.textContent = "";
      toast(error.message, 5000);
    } finally {
      button.disabled = false;
    }
  }

  async function openReview() {
    if (!state.reviewCases) {
      $("#review-body").innerHTML = '<p class="value-empty">Loading the review set…</p>';
      setView("reviewmode");
      try {
        const payload = await api("/api/review/cases");
        state.reviewCases = payload.cases || [];
        state.reviewLabels = payload.labels || {};
        const firstUnlabelled = state.reviewCases.findIndex(c => !state.reviewLabels[c.id]);
        state.reviewIndex = firstUnlabelled >= 0 ? firstUnlabelled : state.reviewCases.length;
      } catch (error) {
        $("#review-body").innerHTML = `<p class="value-empty">${esc(error.message)}</p>`;
        return;
      }
    }
    setView("reviewmode");
  }

  function renderReviewCase() {
    const cases = state.reviewCases || [];
    if (!cases.length) {
      $("#review-body").innerHTML = '<p class="value-empty">No review cases are installed.</p>';
      return;
    }
    if (state.reviewIndex >= cases.length) {
      const ids = new Set(cases.map(c => c.id));
      const counts = { accept: 0, unsafe: 0, missing: 0, modify: 0 };
      let labelled = 0;
      for (const [id, decision] of Object.entries(state.reviewLabels || {})) {
        if (!ids.has(id)) continue;
        labelled += 1;
        counts[decision] = (counts[decision] || 0) + 1;
      }
      const skipped = cases.length - labelled;
      $("#review-body").innerHTML = `<div class="review-card-main">
        <p class="note-kicker">Review complete</p>
        <h3>${labelled} of ${cases.length} cases labelled.</h3>
        <p class="meta-line">${counts.accept} agree · ${counts.unsafe} unsafe · ${counts.missing} missing · ${counts.modify || 0} modify · ${skipped} skipped.</p>
        <p class="meta-line">Labels are in <code>~/.materia/reviews.jsonl</code>. Run <code>scripts/review_report.py</code> to see accept rates with n and a 95% CI.</p>
        <p><a class="quiet-link" href="/api/review/export" download>Download labels (JSONL)</a></p>
      </div>`;
      return;
    }
    const c = cases[state.reviewIndex];
    const a = c.assessment;
    const findings = (a.findings || []).map(f => `<div><span>${esc(f.analyte)}</span><b>${esc(f.value)} ${esc(f.unit)} <small>${esc(f.direction)}</small></b></div>`).join("");
    const patterns = (a.patterns || []).map(p => `<div><span>${esc(p.label)}</span><b>${esc(p.status)} · ${Math.round(p.confidence * 100)}% · ${esc(p.severity)}</b></div>`).join("") || "<div><span>No pattern matched</span><b>—</b></div>";
    const options = (a.recommendations || []).map(o => {
      const flags = (o.safety && o.safety.flags || []).join("; ") || "no safety flags";
      const evidence = (o.evidence || []).slice(0, 4).map(e => e.chunk_id).join(" · ");
      const monitor = (o.monitoring || {}).text || "";
      return `<div class="review-option"><b>${esc(o.intervention)}</b> — grade ${esc(o.grade)}; ${esc((o.dose || {}).text || "no dose (lifestyle/referral)")}<small>${esc(flags)}</small><small>Evidence: ${esc(evidence || "none")}</small>${monitor ? `<small>Monitor: ${esc(monitor)}</small>` : ""}</div>`;
    }).join("") || '<div class="review-option">No option passed the gates.</div>';
    const withheld = (a.withheld || []).map(w => `<div class="review-option"><b>${esc(w.intervention)}</b> — ${esc(w.reason)}</div>`).join("");
    $("#review-body").innerHTML = `<div class="review-card-main">
      <div class="review-case-head"><h3>${esc(c.id)}</h3><span class="review-progress">${state.reviewIndex + 1} of ${cases.length} · ${Object.keys(state.reviewLabels).length} labelled</span></div>
      <p class="meta-line">Intake: ${esc(JSON.stringify(c.intake || {}))}</p>
      <div class="review-findings">${findings}</div>
      <p class="note-kicker" style="margin-top:16px">Patterns</p>
      <div class="review-findings">${patterns}</div>
      <p class="note-kicker" style="margin-top:16px">Engine options</p>
      <div class="review-options">${options}${withheld}</div>
      <textarea class="review-notes" id="review-notes" rows="2" placeholder="Why / what is missing (optional)"></textarea>
      <div class="review-actions">
        <button type="button" data-case-decision="accept">Agree</button>
        <button type="button" data-case-decision="unsafe">Unsafe</button>
        <button type="button" data-case-decision="missing">Missing</button>
        <button type="button" id="review-skip">Skip</button>
      </div>
    </div>`;
  }

  async function submitCaseReview(decision) {
    const cases = state.reviewCases || [];
    const c = cases[state.reviewIndex];
    if (!c) return;
    const top = (c.assessment.recommendations || [])[0];
    const reason = ($("#review-notes") || {}).value || "";
    try {
      await api("/api/review", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          case_id: c.id,
          option_id: top ? top.id : "none",
          decision,
          reason,
          reviewer: ($("#reviewer-name") || {}).value || ""
        })
      });
      state.reviewLabels[c.id] = decision;
      state.reviewIndex += 1;
      renderReviewCase();
      toast("Label saved locally.");
    } catch (error) {
      toast(error.message, 5000);
    }
  }

  function assessmentNote() {
    const a = state.assessment;
    if (!a) return "";
    const lines = ["materia — clinical assessment", ""];
    const intake = a.intake || {};
    lines.push(`Context: age ${intake.age ?? "not supplied"}, sex ${intake.sex || "not supplied"}, contexts ${(intake.contexts || []).join(", ") || "none"}`);
    if ((a.critical_alerts || []).length) {
      lines.push("", "URGENT — CRITICAL VALUES");
      for (const x of a.critical_alerts) lines.push(`- ${x.analyte} ${x.value} ${x.unit}: ${x.action} (${x.citation})`);
    }
    lines.push("", "FINDINGS");
    for (const f of a.findings || []) lines.push(`- ${f.analyte}: ${f.value} ${f.unit} (${f.direction})`);
    lines.push("", "PATTERNS");
    for (const p of a.patterns || []) lines.push(`- ${p.label}: ${p.status}, ${Math.round(p.confidence * 100)}%, ${p.severity}`);
    lines.push("", "OPTIONS");
    for (const o of a.recommendations || []) {
      lines.push(`- ${o.intervention} [grade ${o.grade}]: ${(o.dose || {}).text || "no dose"}`);
      if ((o.safety && o.safety.flags || []).length) lines.push(`  flags: ${o.safety.flags.join("; ")}`);
      if ((o.monitoring || {}).text) lines.push(`  monitor: ${o.monitoring.text}`);
    }
    if ((a.withheld || []).length) {
      lines.push("", "WITHHELD");
      for (const w of a.withheld) lines.push(`- ${w.intervention}: ${w.reason}`);
    }
    lines.push("", "Clinical decision support only. Not a diagnosis or prescription.");
    return lines.join("\n");
  }

  async function copyPlan() {
    const note = assessmentNote();
    if (!note) { toast("Build the assessment first."); return; }
    try {
      await navigator.clipboard.writeText(note);
      toast("Assessment copied to the clipboard.");
    } catch {
      toast("Clipboard unavailable in this browser.", 4200);
    }
  }

  function downloadPlan() {
    if (!state.assessment) { toast("Build the assessment first."); return; }
    const blob = new Blob([JSON.stringify(state.assessment, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `materia-${state.report ? state.report.session : "assessment"}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  function setView(view) {
    state.view = view;
    document.body.dataset.view = view;
    $$("[data-title]").forEach(node => { node.hidden = node.dataset.title !== view; });
    $("#hero-progress").hidden = view !== "review";
    $("#review-workspace").hidden = view !== "review";
    $("#interpret-view").hidden = view !== "interpret";
    $("#plan-view").hidden = view !== "plan";
    $("#review-view").hidden = view !== "reviewmode";
    document.title = view === "plan"
      ? "materia — Plan"
      : view === "reviewmode" ? "materia — Clinician review"
      : view === "interpret" ? "materia — What this means" : "materia — Lab review";
    if (view === "interpret") {
      renderInterpretation();
      $("#interpret-view").scrollIntoView({ behavior: "smooth", block: "start" });
    } else if (view === "plan") {
      renderPlan();
      $("#plan-view").scrollIntoView({ behavior: "smooth", block: "start" });
    } else if (view === "reviewmode") {
      renderReviewCase();
      $("#review-view").scrollIntoView({ behavior: "smooth", block: "start" });
    } else {
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  }

  function applyReport(report) {
    state.report = report;
    state.assessment = null;
    $("#plan-result").hidden = true;
    $("#plan-status").textContent = "";
    state.rows = (report.rows || []).map(row => ({ ...row }));
    const confirmed = savedConfirmations();
    for (const row of state.rows) {
      if (confirmed.has(row.analyte)) {
        row.status = "confirmed";
        row.review_reason = null;
      }
    }
    const reviewIndex = state.rows.findIndex(row => row.status === "review");
    const flagIndex = state.rows.findIndex(row => Boolean(row.flag));
    state.selected = reviewIndex >= 0 ? reviewIndex : flagIndex >= 0 ? flagIndex : 0;
    state.filter = "all";
    renderAll();
  }

  async function loadSample() {
    $("#value-list").innerHTML = '<p class="value-empty">Getting the sample report ready…</p>';
    try {
      const report = await api("/api/lab/sample");
      applyReport(report);
    } catch (error) {
      $("#value-list").innerHTML = `<p class="value-empty">The local engine is not responding. ${esc(error.message)} <button class="quiet-link" type="button" data-retry="sample">Try again</button></p>`;
      toast(error.message, 5000);
    }
  }

  async function loadStatus() {
    try {
      const status = await api("/api/status");
      state.status = status;
      if (status.feedback_path) $("#feedback-path").textContent = status.feedback_path;
      const chip = $("#engine-chip");
      const text = $("#engine-text");
      if (status.ocr.healthy) {
        text.textContent = "OCR ready";
        chip.classList.remove("is-idle", "is-off");
      } else if (status.ocr.weights_present) {
        text.textContent = "OCR idle";
        chip.classList.add("is-idle");
        chip.title = "The OCR weights are installed. Uploads will start the OCR engine (and stop any reasoning server).";
      } else {
        text.textContent = "Sample only";
        chip.classList.add("is-off");
        chip.title = "The OCR weights are not installed. The sample case works without them.";
      }
    } catch {
      $("#engine-text").textContent = "Engine offline";
      $("#engine-chip").classList.add("is-off");
    }
  }

  function updateFile(file) {
    state.file = file || null;
    const name = $("#dropzone-name");
    const submit = $("#upload-submit");
    if (!file) {
      name.textContent = "No file chosen";
      submit.disabled = true;
      return;
    }
    if (!/\.(pdf|png|jpe?g)$/i.test(file.name)) {
      name.textContent = "Use a PDF, PNG, JPG, or JPEG.";
      submit.disabled = true;
      return;
    }
    if (file.size > 25 * 1024 * 1024) {
      name.textContent = "That file is larger than 25 MB.";
      submit.disabled = true;
      return;
    }
    name.textContent = `${file.name} · ${(file.size / 1024).toFixed(0)} KB`;
    $("#upload-status").textContent = "";
    submit.disabled = false;
  }

  function openUpload() {
    $("#upload-dialog").showModal();
    updateFile(null);
    const ocr = state.status && state.status.ocr;
    $("#upload-status").textContent = ocr && ocr.healthy
      ? "The OCR engine is ready."
      : ocr && ocr.weights_present
        ? "The OCR engine is asleep. It starts when you read the report, which can take a minute."
        : "OCR weights are not installed here. The sample report still works.";
  }

  async function submitUpload() {
    if (!state.file) return;
    const file = state.file;
    $("#upload-dialog").close();
    $("#loading").hidden = false;
    startReading();
    try {
      const report = await api("/api/lab/upload", {
        method: "POST",
        headers: {
          "Content-Type": file.type || "application/octet-stream",
          "X-Filename": encodeURIComponent(file.name)
        },
        body: file
      });
      applyReport(report);
      toast("Report read. Check each value against the page.");
      await loadStatus();
    } catch (error) {
      $("#upload-dialog").showModal();
      $("#upload-status").textContent = error.message + (String(error.message).includes("model") ? " Start it with `materia serve --start-ocr`." : "");
      toast(error.message, 6000);
    } finally {
      stopReading();
      $("#loading").hidden = true;
    }
  }

  async function submitFeedback(event) {
    event.preventDefault();
    const message = $("#feedback-message").value.trim();
    if (!message) return;
    const button = $("#feedback-submit");
    button.disabled = true;
    try {
      await api("/api/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message,
          contact: $("#feedback-contact").value.trim(),
          page: state.report ? state.report.doc.page_label : ""
        })
      });
      $("#feedback-dialog").close();
      $("#feedback-form").reset();
      toast("Thank you. Your note is saved locally.");
    } catch (error) {
      toast(error.message, 5000);
    } finally {
      button.disabled = false;
    }
  }

  document.addEventListener("click", event => {
    const select = event.target.closest("[data-select]");
    if (select) {
      state.selected = Number(select.dataset.select);
      renderReport();
      renderBands();
      renderList();
      return;
    }
    const filter = event.target.closest("[data-filter]");
    if (filter) { setFilter(filter.dataset.filter); return; }
    const retry = event.target.closest("[data-retry]");
    if (retry) { loadSample(); return; }
    const example = event.target.closest("[data-example]");
    if (example) { loadExample(example.dataset.example); return; }
    const review = event.target.closest("[data-review]");
    if (review) { submitReview(review.dataset.option, review.dataset.review); return; }
    if (event.target.closest("#finish-btn")) {
      state.filter = "finish";
      const next = state.rows.findIndex(row => row.status !== "confirmed");
      if (next >= 0) state.selected = next;
      renderHero();
      renderList();
      $(".review-card").scrollIntoView({ behavior: "smooth", block: "start" });
      return;
    }
    if (event.target.closest("#open-interpret")) { setView("interpret"); return; }
    if (event.target.closest("#open-plan")) { setView("plan"); return; }
    if (event.target.closest("#back-interpret")) { setView("interpret"); return; }
    if (event.target.closest("#print-plan")) { window.print(); return; }
    if (event.target.closest("#copy-plan")) { copyPlan(); return; }
    if (event.target.closest("#download-plan")) { downloadPlan(); return; }
    if (event.target.closest("#review-open")) { openReview(); return; }
    if (event.target.closest("#review-close")) { setView("plan"); return; }
    const caseDecision = event.target.closest("[data-case-decision]");
    if (caseDecision) { submitCaseReview(caseDecision.dataset.caseDecision); return; }
    if (event.target.closest("#review-skip")) { state.reviewIndex += 1; renderReviewCase(); return; }
    if (event.target.closest("#back-values")) { setView("review"); return; }
    if (event.target.closest("#upload-open")) { openUpload(); return; }
    if (event.target.closest("#upload-cancel") || event.target.closest("#upload-close")) { $("#upload-dialog").close(); return; }
    if (event.target.closest("#upload-submit")) { submitUpload(); return; }
    if (event.target.closest("#feedback-open")) { $("#feedback-dialog").showModal(); return; }
    if (event.target.closest("#feedback-cancel") || event.target.closest("#feedback-close")) { $("#feedback-dialog").close(); return; }
  });

  $("#file-input").addEventListener("change", event => updateFile(event.target.files && event.target.files[0]));
  $("#feedback-form").addEventListener("submit", submitFeedback);
  $("#intake-form").addEventListener("submit", buildPlan);
  $("#chat-form").addEventListener("submit", sendChat);

  const dropzone = $("#dropzone");
  ["dragenter", "dragover"].forEach(type => dropzone.addEventListener(type, event => {
    event.preventDefault();
    dropzone.classList.add("is-dragging");
  }));
  ["dragleave", "drop"].forEach(type => dropzone.addEventListener(type, event => {
    event.preventDefault();
    dropzone.classList.remove("is-dragging");
  }));
  dropzone.addEventListener("drop", event => {
    const file = event.dataTransfer && event.dataTransfer.files && event.dataTransfer.files[0];
    if (file) updateFile(file);
  });
  dropzone.addEventListener("keydown", event => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      $("#file-input").click();
    }
  });

  document.addEventListener("keydown", event => {
    if (state.view !== "reviewmode") return;
    if (event.target && event.target.matches("input, textarea, select")) return;
    const key = (event.key || "").toLowerCase();
    if (!["a", "u", "m", "s"].includes(key)) return;
    event.preventDefault();
    if (key === "s") { state.reviewIndex += 1; renderReviewCase(); return; }
    submitCaseReview({ a: "accept", u: "unsafe", m: "missing" }[key]);
  });

  window.addEventListener("error", () => document.documentElement.setAttribute("data-app-error", "1"));
  const initialView = () => {
    const hash = (location.hash || "").replace("#", "");
    return ["review", "interpret", "plan", "reviewmode"].includes(hash) ? hash : "review";
  };
  state.view = initialView();
  loadStatus();
  loadSample().then(() => {
    if (state.view === "reviewmode") { openReview(); return; }
    if (state.view !== "review") setView(state.view);
    const example = new URLSearchParams(location.search).get("example");
    if (example && state.view === "plan") loadExample(example);
  });
})();
