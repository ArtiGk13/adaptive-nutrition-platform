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

/* ────────────────────────── who you are ─────────────────────────────── */

/* There is no sign-in: the system identifies a caller by a plain id, and inventing an
   email and a passcode here would look like an account while protecting nothing. What
   the browser can honestly do is remember the id you were given, so you do not have to
   write it down and type it back. */

const whoami = $("#whoami");

function readStoredUser() {
  try {
    return JSON.parse(localStorage.getItem("user") || "null");
  } catch (error) {
    return null;
  }
}

function showStoredUser() {
  const user = readStoredUser();
  if (!user) return;
  $("#plan-user").value = user.id;
  whoami.textContent = `${user.name} · user ${user.id}`;
  whoami.hidden = false;
}

function rememberUser(user) {
  try {
    localStorage.setItem("user", JSON.stringify({ id: user.user_id, name: user.name }));
  } catch (error) {
    /* storage unavailable: the id is still shown in the message on screen */
  }
  showStoredUser();
}

showStoredUser();

/* ───────────────────────── back to the top ──────────────────────────── */

const toTop = $("#to-top");

addEventListener("scroll", () => {
  toTop.classList.toggle("on", scrollY > 320);
}, { passive: true });

toTop.addEventListener("click", () => {
  const motion = matchMedia("(prefers-reduced-motion: reduce)").matches;
  scrollTo({ top: 0, behavior: motion ? "auto" : "smooth" });
});

/* ─────────────────────────────── theme ──────────────────────────────── */

/* Without a choice the page follows whatever the browser asks for, which differs
   between one machine and the next. A demonstration needs to be able to settle it. */

const themeButton = $("#theme-toggle");

function effectiveTheme() {
  const stamped = document.documentElement.getAttribute("data-theme");
  if (stamped === "light" || stamped === "dark") return stamped;
  return matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function showThemeState() {
  const next = effectiveTheme() === "dark" ? "light" : "dark";
  themeButton.dataset.next = next;
  themeButton.setAttribute("aria-pressed", String(effectiveTheme() === "dark"));
  themeButton.querySelector(".theme-label").textContent =
    next === "dark" ? "Dark theme" : "Light theme";
}

themeButton.addEventListener("click", () => {
  const next = themeButton.dataset.next;
  document.documentElement.setAttribute("data-theme", next);
  try {
    localStorage.setItem("theme", next);
  } catch (error) {
    /* storage unavailable: the choice holds for this page view only */
  }
  showThemeState();
});

matchMedia("(prefers-color-scheme: dark)").addEventListener("change", showThemeState);
showThemeState();

/* ──────────────────────────────── tabs ──────────────────────────────── */

document.querySelectorAll(".nav-item").forEach((item) => {
  item.addEventListener("click", () => {
    document.querySelectorAll(".nav-item").forEach((n) => n.classList.remove("active"));
    document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
    item.classList.add("active");
    $("#" + item.dataset.panel).classList.add("active");
    window.scrollTo({ top: 0 });
  });
});

/* ───────────────────────────── rendering ────────────────────────────── */


/* The codes and the stored decision are the audit trail, and worth showing; they are
   not what someone reading their own plan needs first. Folded away, open on request. */
const tech = (inner) =>
  `<details class="tech"><summary>Technical detail</summary>${inner}</details>`;

const head = (mark, title) =>
  `<div class="card-head"><span class="stage">${mark}</span><h3>${title}</h3></div>`;

/* The macro split is a genuine part-to-whole: at 4, 4 and 9 kcal per gram the three
   segments reconstruct the calorie target, so the percentages are the energy shares
   the dietitian's accepted ranges are expressed in. */
function macroSplit(macros) {
  const energy = {
    protein: macros.protein_g * 4,
    carbs: macros.carbs_g * 4,
    fat: macros.fat_g * 9,
  };
  const total = energy.protein + energy.carbs + energy.fat;
  const parts = [
    ["Protein", "protein", macros.protein_g, energy.protein],
    ["Carbohydrate", "carbs", macros.carbs_g, energy.carbs],
    ["Fat", "fat", macros.fat_g, energy.fat],
  ];
  const share = (kcal) => Math.round((kcal / total) * 100);

  return `
    <div class="stack" role="img"
         aria-label="${parts.map(([n, , , k]) => `${n} ${share(k)}%`).join(", ")}">
      ${parts.map(([, slot, , kcal]) =>
        `<i style="flex:${kcal};background:var(--${slot})"></i>`).join("")}
    </div>
    <div class="keys">
      ${parts.map(([name, slot, grams, kcal]) => `
        <span class="key">
          <b style="background:var(--${slot})"></b>
          <span class="n">${name} ${share(kcal)}%</span>
          <span class="g">${grams} g</span>
        </span>`).join("")}
    </div>`;
}

function planCard(plan) {
  const m = plan.macro_targets;
  const meals = plan.meal_structure
    .map((slot) => `<div class="meal">${esc(slot.slot_name)}
                      <span>${slot.target_kcal} kcal</span></div>`)
    .join("");
  return `
    <div class="card">
      ${head("4", `Plan &middot; version ${plan.version}`)}
      <div class="tiles">
        <div class="tile"><div class="k">Daily energy</div>
             <div class="v">${plan.calorie_target} <small>kcal</small></div></div>
        ${plan.target_weight_kg
          ? `<div class="tile"><div class="k">Target weight</div>
               <div class="v">${plan.target_weight_kg} <small>kg</small></div></div>` : ""}
        <div class="tile"><div class="k">Meals</div>
             <div class="v">${plan.meal_structure.length}</div></div>
      </div>
      ${macroSplit(m)}
      <div class="meals">${meals}</div>
      <p class="hint">${esc(plan.rationale)}</p>
    </div>`;
}

/* The system records why it refused in its own terms, which is what the stored decision
   needs to say. These translate the same thing for the person reading the screen, keyed
   on the check that failed; the recorded wording is shown underneath, unaltered. */
const WHY_REFUSED = {
  declared_condition:
    "You told us about a health condition. Planning around one is a professional's "
    + "job, not a calculation's.",
  eating_disorder_signal:
    "One of your answers is something a professional should look at before any plan is "
    + "made. This is not a diagnosis, and it does not mean anything is wrong — the "
    + "system refers early on purpose, because that is the safer mistake for it to make.",
  age_out_of_range:
    "The figures this system works from were established for adults between 18 and 65. "
    + "Outside that range they do not apply.",
  underweight_weight_loss:
    "Your weight is already below the healthy range for your height, so this system "
    + "will not build a plan to lose more.",
  target_weight_reached:
    "You have reached the weight this system would have set as the target, so it will "
    + "not plan for further loss.",
  rapid_weight_loss:
    "You have been losing weight faster than is considered safe to continue.",
  min_calories:
    "A plan for your goal would need a daily target below the safe minimum.",
  max_deficit:
    "Your goal would need a larger cut than is considered safe to sustain.",
  macro_distribution:
    "A plan could not be built that stays within the accepted nutrient ranges.",
};

function refusalCard(decision) {
  const why = decision.failed_checks.map((c) => WHY_REFUSED[c]).filter(Boolean);
  return `
    <div class="card refuse">
      ${head("!", "A plan is not the right next step")}
      ${why.map((line) => `<p>${esc(line)}</p>`).join("")}
      <p class="recorded">${esc(decision.notes)}</p>
      <dl>
        <dt>Decision</dt>
        <dd><span class="chip bad">&#9888; ${esc(decision.decision_type)}</span></dd>
        <dt>Failed checks</dt><dd>${esc(decision.failed_checks.join(", ") || "none")}</dd>
      </dl>
      <p class="hint">Nothing was saved and no plan was made. What you have told us
         needs a person to look at it, not a calculation.</p>
    </div>`;
}

function cycleCards(result) {
  const a = result.assessment;
  const deviations = a.deviations.length
    ? `<ul class="plain">${a.deviations.slice(0, 5).map((d) => `<li>${esc(d)}</li>`).join("")}
       ${a.deviations.length > 5
         ? `<li>… and ${a.deviations.length - 5} more days</li>` : ""}</ul>`
    : `<p class="hint">You stayed close to your plan throughout.</p>`;

  const decision = result.supervisor_decision;
  const feedback = result.feedback_text
    ? `<div class="generated">
         <span class="k">Generated wording</span>
         <p>${esc(result.feedback_text)}</p>
         <p class="hint">Written to explain the change above. It does not affect any of
            your numbers.</p>
       </div>`
    : "";

  const pct = Math.round(a.adherence_score * 100);

  return `
    <div class="card">
      ${head("1", "How the past weeks went")}
      <p class="hero">${pct}<span class="hero-unit">% adherence</span></p>
      <div class="meter"><span style="width:${pct}%"></span></div>
      <div class="meter-foot"><span>0%</span><span>plan followed exactly</span></div>
      <div class="tiles" style="margin-top:18px">
        <div class="tile"><div class="k">Average intake</div>
             <div class="v">${a.average_daily_kcal} <small>kcal/day</small></div></div>
        <div class="tile"><div class="k">Days off target</div>
             <div class="v">${a.deviations.length}</div></div>
      </div>
      ${deviations}
    </div>
    <div class="card">
      ${head("2", result.action.action_type === "continue"
                  ? "Nothing needs to change" : "What changes")}
      <p>${esc(result.action.reason)}</p>
      ${tech(`<dl><dt>Action</dt><dd>${esc(result.action.action_type)}</dd></dl>`)}
    </div>
    <div class="card${decision.approved ? "" : " refuse"}">
      ${head(decision.approved ? "3" : "!",
             decision.approved ? "Safety check passed" : "Safety check stopped this")}
      <p>${decision.approved
            ? "Every safety limit was checked before this was saved."
            : esc(decision.notes)}</p>
      ${tech(`<dl>
        <dt>Decision</dt>
        <dd><span class="chip ${decision.approved ? "good" : "bad"}">
            ${decision.approved ? "&#10003;" : "&#9888;"}
            ${esc(decision.decision_type)}</span></dd>
        <dt>Guardrails</dt>
        <dd>${decision.guardrail_checks_passed ? "all passed" : "failed"}</dd>
        <dt>Failed checks</dt><dd>${esc(decision.failed_checks.join(", ") || "none")}</dd>
        <dt>Recorded</dt><dd>${esc(decision.notes)}</dd>
      </dl>`)}
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
    rememberUser(user);
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
  if (!rows.length) return `<div class="note plain">No users to show.</div>`;
  const body = rows.map((r) => `
    <tr data-user="${r.user_id}">
      <td class="num">${r.user_id}</td>
      <td>${esc(r.name)}</td>
      <td>${esc(r.goal_type)}</td>
      <td class="num">${r.calorie_target === null ? "—" : r.calorie_target + " kcal"}</td>
      <td class="num">${(r.adherence_level * 100).toFixed(0)}%</td>
      <td>${r.needs_referral
            ? `<span class="chip bad">&#9888; needs referral</span>`
            : `<span class="chip">${esc(r.latest_flag || "no decision yet")}</span>`}</td>
    </tr>`).join("");
  return `<div class="sheet"><table>
      <thead><tr><th>id</th><th>name</th><th>goal</th><th>target</th>
                 <th>adherence</th><th>status</th></tr></thead>
      <tbody>${body}</tbody>
    </table>
    <p class="hint">Select a row to see everything that happened for that person.</p></div>`;
}

/* The API answers with the rule it enforced. Here that reads as a rebuff to someone
   who has simply arrived on the wrong screen, so it is said in full and with the way
   out. */
function proProblem(message) {
  if (/nutritionist role/i.test(message)) {
    return "That id belongs to someone following a plan, not to a dietitian. This "
      + "screen is only for the dietitian account — there is one button along from "
      + "here that will create one.";
  }
  if (/Unknown user/i.test(message)) {
    return "No account has that id yet.";
  }
  return message;
}

async function loadOverviews(path) {
  $("#pro-history").innerHTML = "";
  if (!$("#pro-user").value) {
    $("#pro-view").innerHTML =
      `<div class="note plain">Enter the dietitian's id, or create one.</div>`;
    return;
  }
  try {
    const rows = await api("GET", path, undefined, asNutritionist());
    $("#pro-view").innerHTML = overviewTable(rows);
    document.querySelectorAll("#pro-view tbody tr").forEach((tr) => {
      tr.addEventListener("click", () => showHistory(tr.dataset.user));
    });
  } catch (error) {
    $("#pro-view").innerHTML =
      `<div class="note error">${esc(proProblem(error.message))}</div>`;
  }
}

/* Nothing here is authentication: the system has none and says so. This only creates a
   user carrying the second role the proposal described, so the screen can be reached. */
$("#btn-make-pro").addEventListener("click", async () => {
  try {
    const pro = await api("POST", "/users", {
      name: "Dietitian", age: 40, sex: "female", height_cm: 170, weight_kg: 65,
      activity_level: "moderate", goal_type: "maintenance", role: "nutritionist",
    });
    $("#pro-user").value = pro.user_id;
    $("#pro-view").innerHTML =
      `<div class="note">Dietitian account created — id ${pro.user_id}. `
      + `Now choose one of the two lists.</div>`;
  } catch (error) {
    $("#pro-view").innerHTML = `<div class="note error">${esc(error.message)}</div>`;
  }
});

async function showHistory(userId) {
  try {
    const h = await api("GET", `/nutritionist/users/${userId}`, undefined, asNutritionist());
    const decisions = h.decisions.map((d) => `
      <tr><td>${esc(d.decision_type)}</td>
          <td><span class="chip ${d.approved ? "good" : "bad"}">
              ${d.approved ? "&#10003; approved" : "&#9888; refused"}</span></td>
          <td>${esc(d.notes)}</td></tr>`).join("");
    $("#pro-history").innerHTML = `
      <div class="card">
        ${head("&#9733;", esc(h.profile.name))}
        <dl>
          <dt>Plan versions</dt><dd>${h.plans.length}</dd>
          <dt>Assessments</dt><dd>${h.assessments.length}</dd>
          <dt>Decisions recorded</dt><dd>${h.decisions.length}</dd>
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

/* ───────────────────────── the example ──────────────────────────────── */

const EXAMPLE = {
  name: "Maria Georgiou", age: 35, sex: "female", height_cm: 165, weight_kg: 78,
  activity_level: "light", goal_type: "weight_loss",
};

$("#fill-example").addEventListener("click", () => {
  const form = $("#form-user");
  for (const [field, value] of Object.entries(EXAMPLE)) {
    const input = form.elements[field];
    if (input) input.value = value;
  }
  form.elements.name.focus();
});
