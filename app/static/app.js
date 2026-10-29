"use strict";

/* A thin client over the REST API. It holds no state of its own beyond the user id
   typed into each panel: everything shown here is what an endpoint returned. */

async function api(method, path, body, headers) {
  const options = { method, headers: Object.assign({}, headers) };
  if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  const response = await fetch(path, options);
  const text = await response.text();
  const payload = text ? JSON.parse(text) : null;
  if (!response.ok) {
    const detail = payload && payload.detail ? payload.detail : response.statusText;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return payload;
}

const $ = (selector) => document.querySelector(selector);
const list = (value) => value.split(",").map((s) => s.trim()).filter(Boolean);
const now = () => new Date().toISOString().slice(0, 19);
const esc = (value) =>
  String(value).replace(/[&<>"]/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

function note(target, message, isError) {
  $(target).className = isError ? "note error" : "note";
  $(target).textContent = message;
}

/* ──────────────────────────────── tabs ──────────────────────────────── */

document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
    tab.classList.add("active");
    $("#" + tab.dataset.panel).classList.add("active");
  });
});

/* ───────────────────────────── rendering ────────────────────────────── */

function planCard(plan) {
  const macros = plan.macro_targets;
  const meals = plan.meal_structure
    .map((slot) => `<li>${esc(slot.slot_name)} — ${slot.target_kcal} kcal</li>`)
    .join("");
  return `
    <div class="card">
      <h3><span class="step">plan</span> Version ${plan.version}</h3>
      <p class="big">${plan.calorie_target} kcal <span class="arrow">/ day</span></p>
      <dl>
        <dt>Protein</dt><dd>${macros.protein_g} g</dd>
        <dt>Carbohydrate</dt><dd>${macros.carbs_g} g</dd>
        <dt>Fat</dt><dd>${macros.fat_g} g</dd>
        ${plan.target_weight_kg
          ? `<dt>Target weight</dt><dd>${plan.target_weight_kg} kg</dd>` : ""}
      </dl>
      <ul class="plain">${meals}</ul>
      <p class="hint">${esc(plan.rationale)}</p>
    </div>`;
}

function refusalCard(decision) {
  return `
    <div class="card refuse">
      <h3><span class="step">supervisor</span> No plan was issued</h3>
      <p>${esc(decision.notes)}</p>
      <dl>
        <dt>Decision</dt><dd>${esc(decision.decision_type)}</dd>
        <dt>Failed checks</dt><dd>${esc(decision.failed_checks.join(", ") || "none")}</dd>
      </dl>
      <p class="hint">This is not a warning attached to a plan you could still follow.
         The plan does not exist, and nothing was stored.</p>
    </div>`;
}

function cycleCards(result) {
  const a = result.assessment;
  const deviations = a.deviations.length
    ? `<ul class="plain">${a.deviations.slice(0, 5).map((d) => `<li>${esc(d)}</li>`).join("")}
       ${a.deviations.length > 5
         ? `<li>… and ${a.deviations.length - 5} more days</li>` : ""}</ul>`
    : `<p class="hint">No sustained deviation was detected.</p>`;

  const decision = result.supervisor_decision;
  const feedback = result.feedback_text
    ? `<div class="generated">
         <span class="step">generated wording</span>
         <p>${esc(result.feedback_text)}</p>
         <p class="hint">Phrased by a local language model from the decision above.
            It is explanatory only and no figure depends on it.</p>
       </div>`
    : "";

  return `
    <div class="card">
      <h3><span class="step">assessment</span> What your logs show</h3>
      <p class="big">${(a.adherence_score * 100).toFixed(0)}%
         <span class="arrow">adherence</span></p>
      <dl><dt>Average intake</dt><dd>${a.average_daily_kcal} kcal/day</dd>
          <dt>Flag</dt><dd>${esc(a.proposed_flag)}</dd></dl>
      ${deviations}
    </div>
    <div class="card">
      <h3><span class="step">adaptation</span> What it proposes</h3>
      <p><strong>${esc(result.action.action_type)}</strong></p>
      <p>${esc(result.action.reason)}</p>
    </div>
    <div class="card${decision.approved ? "" : " refuse"}">
      <h3><span class="step">supervisor</span>
          ${decision.approved ? "Approved" : "Not approved"}</h3>
      <dl>
        <dt>Decision</dt><dd>${esc(decision.decision_type)}</dd>
        <dt>Guardrails</dt>
        <dd>${decision.guardrail_checks_passed ? "all passed" : "failed"}</dd>
        <dt>Failed checks</dt><dd>${esc(decision.failed_checks.join(", ") || "none")}</dd>
      </dl>
      <p class="hint">${esc(decision.notes)}</p>
    </div>
    ${planCard(result.plan)}
    ${feedback}`;
}

/* ──────────────────────────── onboarding ────────────────────────────── */

$("#form-user").addEventListener("submit", async (event) => {
  event.preventDefault();
  const f = new FormData(event.target);
  const body = {
    name: f.get("name"),
    age: Number(f.get("age")),
    sex: f.get("sex"),
    height_cm: Number(f.get("height_cm")),
    weight_kg: Number(f.get("weight_kg")),
    activity_level: f.get("activity_level"),
    goal_type: f.get("goal_type"),
    history: {
      medical_conditions: list(f.get("medical_conditions") || ""),
      allergies: list(f.get("allergies") || ""),
      intolerances: list(f.get("intolerances") || ""),
      medications: list(f.get("medications") || ""),
    },
    screening: {
      recent_weight_fluctuation: f.get("recent_weight_fluctuation") === "on",
      difficult_relationship_with_food: f.get("difficult_relationship_with_food") === "on",
      perceives_self_as_overweight: f.get("perceives_self_as_overweight") === "on",
    },
  };

  try {
    const user = await api("POST", "/users", body);
    const outcome = await api("POST", `/users/${user.user_id}/plan`);
    $("#plan-user").value = user.user_id;
    $("#onboard-result").innerHTML =
      `<div class="note">Profile created — you are user ${user.user_id}.</div>` +
      (outcome.plan ? planCard(outcome.plan) : refusalCard(outcome.supervisor_decision));
  } catch (error) {
    $("#onboard-result").innerHTML = `<div class="note error">${esc(error.message)}</div>`;
  }
});

/* ───────────────────────────── the user ─────────────────────────────── */

const currentUser = () => Number($("#plan-user").value);

$("#btn-load").addEventListener("click", async () => {
  try {
    const plan = await api("GET", `/users/${currentUser()}/plan`);
    $("#plan-view").innerHTML = planCard(plan);
  } catch (error) {
    $("#plan-view").innerHTML = `<div class="note error">${esc(error.message)}</div>`;
  }
});

$("#form-meal").addEventListener("submit", async (event) => {
  event.preventDefault();
  const f = new FormData(event.target);
  try {
    await api("POST", `/users/${currentUser()}/logs/meal`, {
      timestamp: now(),
      meal_slot: f.get("meal_slot"),
      food_description: f.get("food_description"),
      estimated_kcal: Number(f.get("estimated_kcal")),
    });
    note("#log-result", `Logged ${f.get("meal_slot")}: ${f.get("food_description")}.`, false);
  } catch (error) {
    note("#log-result", error.message, true);
  }
});

$("#form-weight").addEventListener("submit", async (event) => {
  event.preventDefault();
  const f = new FormData(event.target);
  try {
    await api("POST", `/users/${currentUser()}/logs/weight`, {
      timestamp: now(),
      weight_kg: Number(f.get("weight_kg")),
    });
    note("#log-result", `Logged ${f.get("weight_kg")} kg.`, false);
  } catch (error) {
    note("#log-result", error.message, true);
  }
});

$("#btn-cycle").addEventListener("click", async () => {
  $("#cycle-view").innerHTML = `<div class="note">Running the cycle…</div>`;
  try {
    const result = await api("POST", `/users/${currentUser()}/cycle`);
    $("#cycle-view").innerHTML = cycleCards(result);
  } catch (error) {
    $("#cycle-view").innerHTML = `<div class="note error">${esc(error.message)}</div>`;
  }
});

/* ─────────────────────────── the dietitian ──────────────────────────── */

const asNutritionist = () => ({ "X-User-Id": String(Number($("#pro-user").value)) });

function overviewTable(rows) {
  if (!rows.length) return `<div class="note">No users to show.</div>`;
  const body = rows.map((r) => `
    <tr data-user="${r.user_id}">
      <td>${r.user_id}</td>
      <td>${esc(r.name)}</td>
      <td>${esc(r.goal_type)}</td>
      <td>${r.calorie_target === null ? "—" : r.calorie_target + " kcal"}</td>
      <td>${(r.adherence_level * 100).toFixed(0)}%</td>
      <td>${r.needs_referral
            ? `<span class="flag referral">needs referral</span>`
            : `<span class="flag">${esc(r.latest_flag || "ok")}</span>`}</td>
    </tr>`).join("");
  return `<table>
      <thead><tr><th>id</th><th>name</th><th>goal</th><th>target</th>
                 <th>adherence</th><th>status</th></tr></thead>
      <tbody>${body}</tbody>
    </table>
    <p class="hint">Select a row to open that user's full decision trail.</p>`;
}

async function loadOverviews(path) {
  $("#pro-history").innerHTML = "";
  try {
    const rows = await api("GET", path, undefined, asNutritionist());
    $("#pro-view").innerHTML = overviewTable(rows);
    document.querySelectorAll("#pro-view tbody tr").forEach((tr) => {
      tr.addEventListener("click", () => showHistory(tr.dataset.user));
    });
  } catch (error) {
    $("#pro-view").innerHTML = `<div class="note error">${esc(error.message)}</div>`;
  }
}

async function showHistory(userId) {
  try {
    const h = await api("GET", `/nutritionist/users/${userId}`, undefined, asNutritionist());
    const decisions = h.decisions.map((d) => `
      <tr><td>${esc(d.decision_type)}</td>
          <td>${d.approved ? "approved" : "refused"}</td>
          <td>${esc(d.notes)}</td></tr>`).join("");
    $("#pro-history").innerHTML = `
      <div class="card">
        <h3><span class="step">history</span> ${esc(h.profile.name)}</h3>
        <dl>
          <dt>Plan versions</dt><dd>${h.plans.length}</dd>
          <dt>Assessments</dt><dd>${h.assessments.length}</dd>
          <dt>Supervisor decisions</dt><dd>${h.decisions.length}</dd>
        </dl>
        <table>
          <thead><tr><th>decision</th><th>outcome</th><th>note</th></tr></thead>
          <tbody>${decisions}</tbody>
        </table>
      </div>`;
  } catch (error) {
    $("#pro-history").innerHTML = `<div class="note error">${esc(error.message)}</div>`;
  }
}

$("#btn-all").addEventListener("click", () => loadOverviews("/nutritionist/users"));
$("#btn-flagged").addEventListener("click", () => loadOverviews("/nutritionist/flagged"));
