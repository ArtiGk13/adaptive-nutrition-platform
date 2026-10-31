"use strict";

/* A thin client over the REST API. It holds no state of its own beyond the user id
   typed into each panel: everything shown here is what an endpoint returned. */

/* A rejected field comes back as a list of objects naming the field and the rule it
   broke. Rendered as it arrives, the reader is shown JSON; what they need is which box
   on the form to correct. */
function readProblem(payload, fallback) {
  const detail = payload && payload.detail;
  if (typeof detail === "string") return detail;
  if (!Array.isArray(detail)) return fallback;

  return detail.map((item) => {
    const field = (item.loc || []).filter((p) => p !== "body").join(" ");
    const rule = String(item.msg || "")
      .replace(/^Value error, /, "")
      .replace(/^String should have at least 1 character$/, "cannot be empty")
      .replace(/^Input should be greater than ([\d.]+)$/, "must be more than $1")
      .replace(/^Input should be greater than or equal to ([\d.]+)$/, "must be at least $1")
      .replace(/^Input should be less than or equal to ([\d.]+)$/, "must be at most $1");
    return field ? `${field}: ${rule}` : rule;
  }).join(". ");
}

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
    throw new Error(readProblem(payload, response.statusText));
  }
  return payload;
}

const $ = (selector) => document.querySelector(selector);
const list = (value) => value.split(",").map((s) => s.trim()).filter(Boolean);
/* A mean arrives as a float — 2191.5714285714284 — and was being written to the screen
   as it stood. Nobody eats to the fourteenth decimal place.

   Rounded, not localised: toLocaleString follows the browser's language rather than the
   page's, so on a Greek machine 2192 came out as "2.192", which reads as two and a bit.
   Every other figure on these screens is written plainly, and this one matches them. */
const kcal = (value) => String(Math.round(value));

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

/* The stored value names the branch taken. Shown with the plain meaning first, because
   the code is the record and not an explanation. */
const ACTION_SAID = {
  continue: "Keep the plan as it is",
  adjust_plan: "Change the daily calorie target",
  extra_support: "Keep the plan, and offer extra support",
  refer_specialist: "Stop, and refer to a professional",
};

const said = (map, value) =>
  `${esc(map[value] || value)} <span class="raw">${esc(value)}</span>`;

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
      ${head("4", `Your plan &middot; version ${plan.version}`)}
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
   on the check that failed. */
const WHY_REFUSED = {
  declared_condition:
    "Planning around a health condition is a professional's job, not a calculation's.",
  eating_disorder_signal:
    "That is something a professional should look at before any plan is made. It is not "
    + "a diagnosis: the system refers early on purpose, because that is the safer "
    + "mistake for it to make.",
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
  /* The stored sentence names the signal after a colon — "Screening signals require
     assessment by a specialist: recent weight fluctuation" — and that tail is the part
     a reader needs: which of their own answers this was about. */
  const detail = (decision.notes.split(": ")[1] || "").trim();
  const why = decision.failed_checks.map((c) => WHY_REFUSED[c]).filter(Boolean);

  return `
    <div class="card refuse">
      ${head("!", "A plan is not the right next step")}
      ${detail ? `<p class="trigger">${esc(detail)}</p>` : ""}
      ${why.map((line) => `<p>${esc(line)}</p>`).join("")}
      <p class="hint">Nothing was saved, and no plan was made for you.</p>
    </div>`;
}


/* What the Assessment agent actually found, which is the part that is true whether or
   not a language model is available: the difficulties are computed in code. A generated
   suggestion is added underneath when there is one, and the mock provider returns the
   same fixed sentence for both kinds of text, so an identical one is not repeated. */
function supportBlock(result) {
  const found = result.assessment.detected_difficulties || [];
  const suggestion = result.support_text && result.support_text !== result.feedback_text
    ? result.support_text : null;
  if (!found.length && !suggestion) return "";

  return `<div class="support">
      <h4>What is getting in the way</h4>
      ${found.length
        ? `<ul class="plain">${found.map((d) => `<li>${esc(d)}</li>`).join("")}</ul>`
        : ""}
      ${suggestion ? `<p>${esc(suggestion)}</p>` : ""}
    </div>`;
}

/* Which limits were tested and what each found. The Supervisor runs them all and used
   to report only the failures, so a passing decision could say that limits had been
   checked without saying which. */
function checkList(decision) {
  const checks = decision.checks || [];
  if (!checks.length) {
    return `<p>${esc(decision.notes)}</p>`;
  }
  const failures = checks.filter((c) => !c.passed).length;
  const headline = failures
    ? `${failures} of ${checks.length} limits were not met.`
    : `All ${checks.length} limits were met.`;
  return `
    <p>${headline}</p>
    <ul class="checks">
      ${checks.map((c) => `<li class="${c.passed ? "ok" : "no"}">
        <span aria-hidden="true">${c.passed ? "&#10003;" : "&#10007;"}</span>
        ${esc(c.message)}</li>`).join("")}
    </ul>`;
}

function cycleCards(result) {
  const a = result.assessment;
  const deviations = a.deviations.length
    ? `<ul class="plain">${a.deviations.slice(0, 5).map((d) => `<li>${esc(d)}</li>`).join("")}
       ${a.deviations.length > 5
         ? `<li>… and ${a.deviations.length - 5} more days</li>` : ""}</ul>`
    : `<p class="hint">You stayed close to your plan throughout.</p>`;

  const decision = result.supervisor_decision;

  const pct = Math.round(a.adherence_score * 100);

  /* What actually happened, in one line, before any of the detail. A reader should not
     have to assemble it from four cards and a code. */
  const before = result.action.reason.match(/from (\d+) to (\d+)/);
  const headline = before
    ? `Your daily target moved from ${before[1]} to ${before[2]} kcal.`
    : result.action.action_type === "continue"
      ? "Your plan stays as it is."
      : "Your plan was reviewed and kept, with extra support suggested.";

  return `
    <div class="card summary">
      <h3>${esc(headline)}</h3>
      <p class="hero">${pct}<span class="hero-unit">% adherence</span></p>
      <div class="meter"><span style="width:${pct}%"></span></div>
      <div class="meter-foot"><span>0%</span><span>plan followed exactly</span></div>
      <p class="lede">${esc(result.feedback_text || result.action.reason)}</p>
      ${supportBlock(result)}
    </div>

    <details class="review">
      <summary><span>How this was decided</span>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
             stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="m6 9 6 6 6-6"/></svg></summary>
    <div class="card">
      ${head("1", "Your log")}
      <div class="tiles">
        <div class="tile"><div class="k">Average intake</div>
             <div class="v">${kcal(a.average_daily_kcal)} <small>kcal/day</small></div></div>
        <div class="tile"><div class="k">Days off target</div>
             <div class="v">${a.deviations.length}</div></div>
      </div>
      ${deviations}
    </div>
    <div class="card">
      ${head("2", "The decision")}
      <p>${esc(result.action.reason)}</p>
    </div>
    <div class="card${decision.approved ? "" : " refuse"}">
      ${head(decision.approved ? "3" : "!", "Safety checks")}
      ${checkList(decision)}

    </div>
    ${planCard(result.plan)}

    </details>`;
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
    fillPicker();
    $("#onboard-result").innerHTML =
      `<div class="note">Profile created — you are user ${user.user_id}.</div>` +
      (outcome.plan ? planCard(outcome.plan) : refusalCard(outcome.supervisor_decision));
  } catch (error) {
    $("#onboard-result").innerHTML = `<div class="note error">${esc(error.message)}</div>`;
  }
});

/* ───────────────────────────── the user ─────────────────────────────── */

const currentUser = () => Number($("#plan-user").value);

$("#btn-load").addEventListener("click", () => loadHome());





$("#btn-cycle").addEventListener("click", async () => {
  if (!currentUser()) {
    $("#cycle-view").innerHTML =
      `<div class="note error">Choose who this is for first.</div>`;
    return;
  }
  $("#cycle-view").innerHTML = `<div class="note">Reviewing your plan…</div>`;
  try {
    const result = await api("POST", `/users/${currentUser()}/cycle`);
    $("#cycle-view").innerHTML = cycleCards(result);
    /* The answer appears below everything already on the page; without this the reader
       is left looking at the button they just pressed. The jump is deliberate rather
       than animated: a smooth scroll is silently a no-op where the browser will not
       animate, and the page then does not move at all. */
    $("#cycle-view").scrollIntoView({ block: "start" });
  } catch (error) {
    $("#cycle-view").innerHTML = `<div class="note error">${esc(error.message)}</div>`;
  }
});

/* ─────────────────────────── the dietitian ──────────────────────────── */

const asNutritionist = () => ({ "X-User-Id": String(Number($("#pro-user").value)) });

/* The stored value names the branch the Supervisor took. These say the same thing in
   the words a dietitian reading a caseload would use; the stored value is still shown
   in the last column, because that is the record. */
const DECISION_SAID = {
  approve_plan: "Issued the first plan",
  approve_adjustment: "Reviewed the plan",
  hold: "Held the plan unchanged",
  flag_referral: "Refused, and referred",
};

/* What the last assessment concluded, in the words a dietitian scanning a caseload
   would use rather than the value stored. */
const FLAG_SAID = {
  continue: "on track",
  adjust: "target needs adjusting",
  extra_support: "needs support",
  refer_specialist: "needs a professional",
};

function overviewTable(rows) {
  if (!rows.length) return `<div class="note plain">No users to show.</div>`;
  const body = rows.map((r) => `
    <tr data-user="${r.user_id}">
      <td class="num">${r.user_id}</td>
      <td>${esc(r.name)}</td>
      <td>${esc(r.goal_type.replace(/_/g, " "))}</td>
      <td class="num">${r.calorie_target === null ? "—" : r.calorie_target + " kcal"}</td>
      ${/* nothing to adhere to without a plan: a zero here reads as a failure to keep
             to one */""}
      <td class="num">${r.calorie_target === null
          ? "—" : (r.adherence_level * 100).toFixed(0) + "%"}</td>
      <td>${r.needs_referral
            ? `<span class="chip bad">&#9888; needs referral</span>`
            : `<span class="chip">${esc(FLAG_SAID[r.latest_flag]
              || r.latest_flag || "no decision yet")}</span>`}</td>
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
      <tr><td class="num">${esc(d.cycle_timestamp.slice(0, 10))}</td>
          <td>${esc(DECISION_SAID[d.decision_type] || d.decision_type)}</td>
          <td><span class="chip ${d.approved ? "good" : "bad"}">
              ${d.approved ? "&#10003; approved" : "&#9888; refused"}</span></td>
          <td class="recorded-cell">${esc(d.notes)}</td></tr>`).join("");
    $("#pro-history").innerHTML = `
      <div class="card">
        ${head("&#9733;", esc(h.profile.name))}
        <dl>
          <dt>Plan versions</dt><dd>${h.plans.length}</dd>
          <dt>Assessments</dt><dd>${h.assessments.length}</dd>
          <dt>Decisions recorded</dt><dd>${h.decisions.length}</dd>
        </dl>
        <table>
          <thead><tr><th>when</th><th>what the system did</th><th>outcome</th>
                     <th>recorded</th></tr></thead>
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

/* ─────────────────── what you have actually been eating ─────────────── */

/* A line against a baseline, which is the form for "how far above or below a target",
   drawn from the logs the API already returns. One series, so no legend; the target is
   the reference, not a second series. Only the last point is labelled — a value on
   every point is noise — and each carries a title for the pointer. */

function dailyIntake(logs) {
  const byDay = new Map();
  for (const entry of logs) {
    if (entry.type !== "meal") continue;
    const day = entry.timestamp.slice(0, 10);
    byDay.set(day, (byDay.get(day) || 0) + (entry.details.estimated_kcal || 0));
  }
  return [...byDay.entries()].sort().map(([day, value]) => ({ day, value }));
}

/* One chart for both series: a line against a baseline. opts carries what differs —
   the heading, the unit, the label on the baseline, and the sentence above it. */
function lineChart(days, target, opts) {
  if (days.length < 2) {
    return days.length === 1
      ? `<div class="note plain">${esc(opts.needMore)}</div>`
      : "";
  }

  const W = 640, H = 200, L = 46, R = 14, T = 16, B = 26;

  /* Energy per day is read against zero, so the axis starts there. Body weight is not:
     a scale from zero flattens the whole series into one line, because the number never
     goes near zero and the movement that matters is a kilo or two. */
  const values = [...days.map((d) => d.value), target];
  const seen = { lo: Math.min(...values), hi: Math.max(...values) };
  const pad = (seen.hi - seen.lo) * 0.3 || seen.hi * 0.05;
  const hi = opts.fromZero ? seen.hi * 1.12 : seen.hi + pad;
  const lo = opts.fromZero ? 0 : Math.max(0, seen.lo - pad);

  const x = (i) => L + (i * (W - L - R)) / (days.length - 1);
  const y = (v) => T + (1 - (v - lo) / (hi - lo)) * (H - T - B);
  const tick = (v) => (hi < 300 ? v.toFixed(1) : Math.round(v));

  const line = days.map((d, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(d.value).toFixed(1)}`)
    .join(" ");
  const area = `${line} L${x(days.length - 1).toFixed(1)} ${y(lo)} L${x(0).toFixed(1)} ${y(lo)} Z`;
  const last = days[days.length - 1];
  const over = days.filter((d) => d.value > target).length;

  const ticks = [lo, (lo + hi) / 2, hi]
    .map((v) => `<line x1="${L}" y1="${y(v).toFixed(1)}" x2="${W - R}" y2="${y(v).toFixed(1)}"
                   stroke="var(--line)" stroke-width="1"/>
                 <text x="${L - 8}" y="${(y(v) + 4).toFixed(1)}" text-anchor="end"
                   font-size="10" fill="var(--muted)">${tick(v)}</text>`).join("");

  const dots = days.map((d, i) =>
    `<circle cx="${x(i).toFixed(1)}" cy="${y(d.value).toFixed(1)}" r="7" fill="transparent">
       <title>${esc(d.day)} — ${opts.fromZero ? kcal(d.value) : d.value} ${esc(opts.unit)}</title></circle>`).join("");

  return `
    <div class="card">
      ${head(opts.mark, opts.title)}
      <p class="hint">${esc(opts.caption(over, days.length, target))}</p>
      <svg class="chart" viewBox="0 0 ${W} ${H}" role="img"
           aria-label="${esc(opts.caption(over, days.length, target))}">

        ${ticks}
        <path d="${area}" fill="var(--meter-fill)" opacity="0.10"/>
        <line x1="${L}" y1="${y(target).toFixed(1)}" x2="${W - R}" y2="${y(target).toFixed(1)}"
              stroke="var(--ink-2)" stroke-width="1" stroke-dasharray="4 3"/>
        <text x="${W - R}" y="${(y(target) - 7).toFixed(1)}" text-anchor="end"
              font-size="10" fill="var(--ink-2)">${esc(opts.baselineLabel)}</text>
        <path d="${line}" fill="none" stroke="var(--meter-fill)" stroke-width="2"
              stroke-linejoin="round" stroke-linecap="round"/>
        <circle cx="${x(days.length - 1).toFixed(1)}" cy="${y(last.value).toFixed(1)}" r="4"
                fill="var(--meter-fill)" stroke="var(--surface)" stroke-width="2"/>
        <text x="${(x(days.length - 1) - 8).toFixed(1)}" y="${(y(last.value) - 10).toFixed(1)}"
              text-anchor="end" font-size="11" fill="var(--ink)">${opts.fromZero ? kcal(last.value) : last.value}</text>
        ${dots}
        <text x="${L}" y="${H - 8}" font-size="10" fill="var(--muted)">${esc(days[0].day)}</text>
        <text x="${W - R}" y="${H - 8}" font-size="10" fill="var(--muted)"
              text-anchor="end">${esc(last.day)}</text>
      </svg>
    </div>`;
}

function weightSeries(logs) {
  return logs.filter((e) => e.type === "weight")
    .map((e) => ({ day: e.timestamp.slice(0, 10), value: e.details.weight_kg }))
    .sort((a, b) => a.day.localeCompare(b.day));
}

/* A month of logging is a few hundred rows. Showing the last eight of them hid
   everything older with no way back; showing all of them would be a page of scrolling.
   Grouped by day instead, each day a line that opens — which is also how a person
   thinks about what they ate. */

function describeEntry(e) {
  if (e.type === "meal") {
    return [`${e.details.meal_slot} — ${e.details.food_description}`,
            `${e.details.estimated_kcal} kcal`];
  }
  if (e.type === "weight") return ["weight", `${e.details.weight_kg} kg`];
  return [e.details.activity_type || "activity",
          `${e.details.duration_min} min`];
}

function entriesCard(logs, showAll) {
  if (!logs.length) {
    return `<div class="card">${head("☰", "What you logged")}
      <p class="hint">Nothing logged yet.</p></div>`;
  }

  const byDay = new Map();
  for (const entry of logs) {
    const day = entry.timestamp.slice(0, 10);
    if (!byDay.has(day)) byDay.set(day, []);
    byDay.get(day).push(entry);
  }

  const days = [...byDay.entries()].sort((a, b) => b[0].localeCompare(a[0]));
  const shown = showAll ? days : days.slice(0, 7);

  const body = shown.map(([day, entries], index) => {
    const kcal = entries.filter((e) => e.type === "meal")
      .reduce((sum, e) => sum + (e.details.estimated_kcal || 0), 0);
    const rows = entries.map((e) => {
      const [what, value] = describeEntry(e);
      return `<div class="meal">${esc(what)}<span>${esc(value)}</span></div>`;
    }).join("");
    return `<details class="day"${index === 0 ? " open" : ""}>
        <summary>
          <span class="when">${esc(day)}</span>
          <span class="count">${entries.length}
            ${entries.length === 1 ? "entry" : "entries"}</span>
          <span class="total">${kcal ? kcal + " kcal" : ""}</span>
        </summary>
        <div class="meals">${rows}</div>
      </details>`;
  }).join("");

  const more = days.length > 7
    ? `<button type="button" id="btn-more-days" class="more">${showAll
        ? "Show recent days only"
        : `Show all ${days.length} days`}</button>`
    : "";

  return `<div class="card">${head("☰", "What you logged")}
    <div class="days">${body}</div>${more}</div>`;
}

let allDays = false;

/* Re-rendered in place when the toggle is used, rather than refetching the lot. */
function renderEntries(logs) {
  $("#entries-view").innerHTML = entriesCard(logs, allDays);
  const moreButton = $("#btn-more-days");
  if (moreButton) {
    moreButton.addEventListener("click", () => {
      allDays = !allDays;
      renderEntries(logs);
    });
  }
}

async function loadHome() {
  const id = currentUser();
  if (!id) {
    $("#plan-view").innerHTML = `<div class="note plain">Choose who this is for above,
      or create a profile on the New user screen.</div>`;
    $("#intake-view").innerHTML = "";
    $("#weight-view").innerHTML = "";
    $("#entries-view").innerHTML = "";
    return;
  }
  showProfile(id);
  let plan = null;
  try {
    plan = await api("GET", `/users/${id}/plan`);
    $("#plan-view").innerHTML = planCard(plan);
  } catch (error) {
    $("#plan-view").innerHTML = `<div class="note plain">${esc(error.message)}</div>`;
  }
  try {
    const logs = await api("GET", `/users/${id}/logs`);

    $("#intake-view").innerHTML = plan ? lineChart(dailyIntake(logs), plan.calorie_target, {
      mark: "↗", title: "What you have been eating", unit: "kcal", fromZero: true,
      needMore: "One day logged so far. Meals on the same day are added together, so "
        + "log something on another day and the trend appears here.",
      baselineLabel: `target ${plan.calorie_target}`,
      caption: (over, total, target) =>
        `${over} of ${total} days above the target of ${target} kcal.`,
    }) : "";

    const weights = weightSeries(logs);
    $("#weight-view").innerHTML = plan && plan.target_weight_kg ? lineChart(
      weights, plan.target_weight_kg, {
        mark: "⚖", title: "Your weight", unit: "kg",
        needMore: "One weigh-in so far. Add another and the trend appears here.",
        baselineLabel: `target ${plan.target_weight_kg} kg`,
        caption: (over, total, target) => over
          ? `${total} weigh-ins, still ${(weights[weights.length - 1].value - target).toFixed(1)} kg above the target of ${target} kg.`
          : `${total} weigh-ins, at or below the target of ${target} kg.`,
      }) : "";

    renderEntries(logs);
  } catch (error) {
    $("#entries-view").innerHTML = `<div class="note error">${esc(error.message)}</div>`;
  }
}

/* arriving on the screen should show what is there, not an empty page and a button */
document.querySelector('[data-panel="panel-plan"]').addEventListener("click", loadHome);
if (readStoredUser()) loadHome();

/* ───────────── the rest of what the API offers ───────────── */

/* Choosing from the people on the system rather than remembering a number. With no
   authentication there is nothing to scope this to, which is the same limitation the
   dietitian screen states; it is a convenience over an endpoint that already lists
   them, not a new liberty. */
async function fillPicker() {
  try {
    const users = await api("GET", "/users");
    const pick = $("#plan-pick");
    pick.innerHTML = `<option value="">choose…</option>` + users
      .filter((u) => u.role === "user")
      .map((u) => `<option value="${u.user_id}">${esc(u.name)} · ${u.user_id}</option>`)
      .join("");
  } catch (error) {
    /* the picker is a shortcut; typing an id still works */
  }
}

$("#plan-pick").addEventListener("change", (event) => {
  if (!event.target.value) return;
  $("#plan-user").value = event.target.value;
  loadHome();
});

/* The screen should say whose plan it is, not only which number it belongs to. */
async function showProfile(id) {
  try {
    const user = await api("GET", `/users/${id}`);
    whoami.textContent = `${user.name} · ${user.goal_type.replace("_", " ")}`;
    whoami.hidden = false;
  } catch (error) {
    whoami.hidden = true;
  }
}



/* Whether the server is answering at all, which is the difference between an empty
   screen and a broken one. */
async function checkHealth() {
  const el = $("#status");
  try {
    const body = await api("GET", "/health");
    el.className = "status ok";
    el.lastElementChild.textContent = body.status === "ok" ? "Connected" : body.status;
  } catch (error) {
    el.className = "status down";
    el.lastElementChild.textContent = "Server not responding";
  }
}

checkHealth();
setInterval(checkHealth, 30000);
fillPicker();

/* ─────────────────────── logging, in one place ──────────────────────── */

/* Three cards for three kinds of entry left the page full of gaps and the same button
   repeated. One card, with the fields for whichever kind is chosen. */

const logForm = $("#form-log");
let logKind = "meal";

function showFields(kind) {
  logKind = kind;
  logForm.querySelectorAll(".seg-btn").forEach((b) =>
    b.classList.toggle("active", b.dataset.kind === kind));
  logForm.querySelectorAll(".fields").forEach((group) => {
    group.hidden = group.dataset.kind !== kind;
    /* only the visible fields are required, or the browser blocks a hidden one */
    group.querySelectorAll("input, select").forEach((f) => { f.required = !group.hidden; });
  });
}

logForm.querySelectorAll(".seg-btn").forEach((b) =>
  b.addEventListener("click", () => showFields(b.dataset.kind)));

/* One entry per kind, each naming its own endpoint. A single call with the kind
   interpolated into the path would read more neatly and would hide all three from the
   test that checks the client against the published API. */
const LOG_CALL = {
  meal: (id, f) => api("POST", `/users/${id}/logs/meal`, {
    timestamp: now(),
    meal_slot: f.get("meal_slot"),
    food_description: f.get("food_description"),
    estimated_kcal: Number(f.get("estimated_kcal")),
  }),
  weight: (id, f) => api("POST", `/users/${id}/logs/weight`, {
    timestamp: now(),
    weight_kg: Number(f.get("weight_kg")),
  }),
  activity: (id, f) => api("POST", `/users/${id}/logs/activity`, {
    timestamp: now(),
    activity_type: f.get("activity_type"),
    duration_min: Number(f.get("duration_min")),
    estimated_kcal_burned: Number(f.get("estimated_kcal_burned")),
  }),
};

logForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!currentUser()) {
    note("#log-result", "Choose who this is for first.", true);
    return;
  }
  const f = new FormData(logForm);
  try {
    await LOG_CALL[logKind](currentUser(), f);
    note("#log-result", "Added. Your plan is checked against your log when you press "
      + "\u201cReview my plan\u201d.", false);
    loadHome();
  } catch (error) {
    note("#log-result", error.message, true);
  }
});

showFields("meal");
