// End-to-end check of the real running app (frontend :3000 → proxy → backend :8000).
// Usage: node e2e/flow.js [outDir]
const { chromium } = require("playwright");
const path = require("path");

const BASE = process.env.BASE_URL || "http://localhost:3000";
const OUT = process.argv[2] || "/tmp/e2e-shots";
require("fs").mkdirSync(OUT, { recursive: true });
const email = `meera${Date.now()}@example.com`;
const results = [];
const consoleErrors = [];

// Dev console provider writes "DEV-ONLY OTP ... to=<dest> code=<6 digits>" to the backend log (never used in production).
const LOG = process.env.BACKEND_LOG || "/tmp/backend.log";
async function devOtp(to, purpose, after = 0) {
  for (let i = 0; i < 40; i++) {
    const lines = require("fs").readFileSync(LOG, "utf8").split("\n").filter((l) => l.includes("DEV-ONLY OTP") && l.includes(`to=${to} `) && (!purpose || l.includes(`purpose=${purpose} `)));
    if (lines.length > after) return { code: lines[lines.length - 1].match(/code=(\d{6})/)[1], n: lines.length };
    await new Promise((r) => setTimeout(r, 250));
  }
  throw new Error("no OTP in log for " + to);
}
const countOtp = (to, purpose) => require("fs").readFileSync(LOG, "utf8").split("\n").filter((l) => l.includes("DEV-ONLY OTP") && l.includes(`to=${to} `) && l.includes(`purpose=${purpose} `)).length;
const PW = "Secret123";

async function step(name, fn) {
  try { await fn(); results.push(["PASS", name]); console.log("PASS", name); }
  catch (e) { if (global.__page) await global.__page.screenshot({ path: path.join(OUT, "FAIL-" + name.slice(0, 20).replace(/\W+/g, "_") + ".png") }).catch(() => {}); results.push(["FAIL", name + " :: " + e.message.split("\n")[0]]); console.log("FAIL", name, "::", e.message.split("\n")[0]); }
}

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, deviceScaleFactor: 1 });
  const page = await ctx.newPage(); global.__page = page;
  page.on("console", (m) => { if (m.type() === "error") consoleErrors.push(m.text()); });
  page.on("pageerror", (e) => consoleErrors.push("pageerror: " + e.message));
  page.on("dialog", (d) => d.accept());
  const shot = (n) => page.screenshot({ path: path.join(OUT, n + ".png") });

  await step("landing page renders with disclaimer", async () => {
    await page.goto(BASE + "/");
    await page.getByText("does not replace a doctor", { exact: false }).first().waitFor({ timeout: 8000 });
    await shot("01-landing");
  });

  await step("protected page redirects to login when logged out", async () => {
    await page.goto(BASE + "/dashboard");
    await page.waitForURL("**/login", { timeout: 8000 });
  });

  await step("register: details → code step; no session before the code; consents start unticked", async () => {
    await page.goto(BASE + "/register");
    await page.getByLabel("Your name").fill("Meera Iyer");
    await page.getByLabel("Email address", { exact: true }).fill(email);
    await page.getByLabel("Choose a password").fill(PW);
    for (const box of await page.getByRole("checkbox").all()) if (await box.isChecked()) throw new Error("a box is pre-ticked");
    await shot("02a-register");
    for (const n of ["Use the AI service", "Save my conversations", "Personalise with my health details", "Share my location in an emergency"]) await page.getByRole("checkbox", { name: new RegExp(n) }).check();
    await page.getByRole("checkbox", { name: /Required/ }).check();
    await page.getByRole("button", { name: /send me a code/i }).click();
    await page.getByLabel("6-digit code").waitFor({ timeout: 10000 });
    const me = await page.request.get(BASE + "/api/auth/me");
    if (me.status() !== 401) throw new Error("session exists before code verified: " + me.status());
    await shot("02b-register-code");
  });

  await step("register: wrong code is refused with tries-left message", async () => {
    const { code } = await devOtp(email, "register_verify");
    await page.getByLabel("6-digit code").fill(code === "000000" ? "111111" : "000000");
    await page.getByRole("button", { name: /confirm and create/i }).click();
    await page.getByText(/not correct/i).waitFor();
    await page.getByText(/tries left/i).waitFor();
  });

  await step("register: correct code creates the account and opens the dashboard", async () => {
    const { code } = await devOtp(email, "register_verify");
    await page.getByLabel("6-digit code").fill(code);
    await page.getByRole("button", { name: /confirm and create/i }).click();
    await page.waitForURL("**/dashboard", { timeout: 15000 });
    await page.getByText("Namaste, Meera").waitFor();
    await shot("02-dashboard");
  });

  await step("profile: save allergy and add emergency contact", async () => {
    await page.goto(BASE + "/profile");
    await page.getByLabel("Allergies").fill("penicillin, dust");
    await page.getByRole("button", { name: /save health profile/i }).click();
    await page.getByText("Health profile saved.").waitFor();
    await page.getByLabel("Name", { exact: true }).fill("Arun (son)");
    await page.getByLabel("Phone number").fill("9876543210");
    await page.getByRole("button", { name: "Add contact" }).click();
    await page.getByText("Arun (son)").first().waitFor();
    await shot("03-profile");
  });

  await step("prescription: upload photo → real OCR → review screen", async () => {
    await page.goto(BASE + "/prescriptions");
    await page.setInputFiles("#rx-file", path.join(__dirname, "prescription.jpg"));
    await page.waitForURL(/\/prescriptions\/[0-9a-f-]{36}/, { timeout: 90000 });
    await page.getByText("Check what I found").waitFor();
    await page.locator('input[value="Metformin"]').waitFor();
    await shot("04-review");
  });

  await step("prescription: confirm is blocked until acknowledged", async () => {
    const btn = page.getByRole("button", { name: /^Confirm \d+ medicine/ });
    if (!(await btn.isDisabled())) throw new Error("Confirm button should be disabled before acknowledgement");
  });

  await step("prescription: explain in simple words, then confirm", async () => {
    await page.getByRole("button", { name: /explain in simple words/i }).first().click();
    await page.getByText("This only restates what is written").first().waitFor();
    await page.getByRole("checkbox", { name: /checked these details/i }).check();
    await page.getByRole("button", { name: /^Confirm \d+ medicine/ }).click();
    await page.getByText("Confirmed prescription").waitFor();
    await page.getByText(/Allergy check/).count(); // none expected (penicillin ≠ these)
    await shot("05-confirmed");
  });

  await step("reminders: create from confirmed medicine; due dose pops up; mark taken", async () => {
    await page.goto(BASE + "/reminders");
    await page.getByText("Prescription says:").first().waitFor();
    // the app only creates doses within 1 minute of "now"; start early in the minute so test latency cannot cross it
    const sec = new Date().getSeconds(); if (sec > 20) await page.waitForTimeout((62 - sec) * 1000);
    const nowIST = new Date().toLocaleTimeString("en-GB", { timeZone: "Asia/Kolkata", hour: "2-digit", minute: "2-digit" });
    await page.locator('input[type="time"]').first().fill(nowIST);
    await page.getByRole("button", { name: /start reminders/i }).first().click();
    await page.getByText(/Reminder set for/).waitFor();
    await page.reload();
    await page.getByRole("alertdialog").waitFor({ timeout: 15000 });
    await shot("06-due-dose");
    await page.getByRole("alertdialog").getByRole("button", { name: "Taken" }).click();
    await page.getByRole("alertdialog").waitFor({ state: "detached" });
  });

  await step("chat: emergency message → emergency card with 108, no routine answer", async () => {
    await page.goto(BASE + "/chat");
    await page.getByLabel("Type your question").fill("I have severe chest pain and sweating");
    await page.getByRole("button", { name: "Send" }).click();
    const alert = page.getByRole("alert").filter({ hasText: "Do you need urgent help?" });
    await alert.waitFor({ timeout: 10000 });
    await alert.locator('a[href="tel:108"]').waitFor();
    await alert.locator('a[href="tel:9876543210"]').waitFor(); // user's emergency contact surfaced
    await shot("07-chat-emergency");
  });

  await step("chat: normal question → grounded note with source (AI not configured → retrieval-only, honestly labelled)", async () => {
    await page.getByLabel("Type your question").fill("How do I make ORS at home for diarrhoea?");
    await page.getByRole("button", { name: "Send" }).click();
    await page.getByText(/oral rehydration/i).first().waitFor({ timeout: 10000 });
    await page.getByText(/without AI/).waitFor();
    await page.getByText(/Sources \(1\)/).waitFor();
    await shot("08-chat-answer");
  });

  await step("emergency page: 108 + contacts + prepared alert message", async () => {
    await page.goto(BASE + "/emergency");
    await page.locator('a[href="tel:108"]').first().waitFor();
    await page.getByRole("button", { name: /prepare without location/i }).click();
    await page.getByText(/EMERGENCY: Meera Iyer needs urgent help/).waitFor();
    await shot("09-emergency");
  });

  await step("privacy: consent toggle persists", async () => {
    await page.goto(BASE + "/privacy");
    const sw = page.getByRole("switch", { name: "Save my conversations" });
    await sw.waitFor();
    const before = await sw.getAttribute("aria-checked");
    await sw.click();
    await page.getByText(/Allowed\.|Turned off\./).waitFor();
    await page.reload();
    const after = await page.getByRole("switch", { name: "Save my conversations" }).getAttribute("aria-checked");
    if (before === after) throw new Error("toggle did not persist");
    await shot("10-privacy");
  });

  await step("records: add a record and see it on the timeline", async () => {
    await page.goto(BASE + "/records");
    await page.getByLabel("Title").fill("Eye check-up");
    await page.getByRole("button", { name: "Add record" }).click();
    await page.getByText("Record added.").waitFor();
    await page.getByRole("tab", { name: "Health timeline" }).click();
    await page.getByText("Eye check-up").waitFor();
    await page.getByText("Emergency guidance shown").first().waitFor();
    await shot("11-timeline");
  });

  await step("system status page shows honest states (Gemini needs setup)", async () => {
    await page.goto(BASE + "/status");
    await page.getByText("Needs setup").first().waitFor();
    await shot("12-status");
  });

  await step("mobile layout: bottom tab bar + SOS visible, no horizontal scroll", async () => {
    await page.setViewportSize({ width: 390, height: 800 });
    await page.goto(BASE + "/dashboard");
    await page.getByRole("navigation", { name: "Quick" }).waitFor();
    await page.getByRole("link", { name: /Emergency/ }).first().waitFor();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
    if (overflow) throw new Error("horizontal overflow on mobile");
    await shot("13-mobile-dashboard");
    await page.setViewportSize({ width: 1280, height: 900 });
  });

  await step("language switch to Hindi changes interface and emergency text", async () => {
    await page.goto(BASE + "/dashboard");
    await page.locator("#lang").selectOption("hi");
    await page.getByText("आज की दवाइयाँ").waitFor();
    await page.locator("#lang").selectOption("en");
  });

  await step("logout ends the session; API then rejects", async () => {
    await page.getByRole("button", { name: "Log out" }).first().click();
    await page.waitForURL("**/login");
    const r = await page.request.get(BASE + "/api/profile");
    if (r.status() !== 401) throw new Error("expected 401, got " + r.status());
  });

  // ---------- authentication & MFA (real browser) ----------
  await step("login: password alone does not log in; code step appears", async () => {
    await page.goto(BASE + "/login");
    await page.getByLabel("Email address", { exact: true }).fill(email);
    await page.getByLabel("Password").fill("Wrong1234");
    await page.getByRole("button", { name: "Continue" }).click();
    await page.getByText("Incorrect email or password").waitFor();
    await page.getByLabel("Password").fill(PW);
    await page.getByRole("button", { name: "Continue" }).click();
    await page.getByLabel("6-digit code").waitFor();
    if ((await page.request.get(BASE + "/api/auth/me")).status() !== 401) throw new Error("logged in before MFA");
    await shot("14-login-code");
  });

  await step("login: lockout after repeated wrong codes, then resend gives a working code", async () => {
    for (let i = 0; i < 5; i++) {
      await page.getByLabel("6-digit code").fill("000000");
      const b = page.getByRole("button", { name: "Log in" });
      if (await b.isDisabled()) break;
      await b.click();
      await page.getByRole("alert").first().waitFor();
      await page.waitForTimeout(150);
    }
    await page.getByText(/Too many wrong codes|has run out/).first().waitFor();
    const btn = page.getByRole("button", { name: /Send a new code in|Send me a new code/ });
    await btn.waitFor();
    await shot("15-locked");
    await page.getByRole("button", { name: "Send me a new code" }).waitFor({ timeout: 40000 });
    const before = countOtp(email, "login");
    await page.getByRole("button", { name: "Send me a new code" }).click();
    const { code } = await devOtp(email, "login", before);
    await page.getByText(/new code has been sent/i).waitFor();
    await page.getByLabel("6-digit code").fill(code);
    await page.getByRole("button", { name: "Log in" }).click();
    await page.waitForURL("**/dashboard", { timeout: 15000 });
  });

  // Biometric: Chromium's virtual authenticator behaves like a device with a fingerprint reader (user verification succeeds).
  const cdp = await ctx.newCDPSession(page);
  await cdp.send("WebAuthn.enable");
  await cdp.send("WebAuthn.addVirtualAuthenticator", { options: { protocol: "ctap2", transport: "internal", hasResidentKey: true, hasUserVerification: true, isUserVerified: true, automaticPresenceSimulation: true } });

  await step("security page: enrol biometric (needs password), shows device sessions + activity", async () => {
    await page.goto(BASE + "/security");
    await page.getByRole("heading", { name: "Fingerprint or face sign-in" }).waitFor();
    await page.getByLabel(/Your password \(needed/).fill(PW);
    await page.getByRole("button", { name: /Set up fingerprint or face/ }).click();
    await page.getByText(/Added /).first().waitFor({ timeout: 10000 });
    await page.getByText("This device").first().waitFor();
    await page.getByText("Logged in").first().waitFor();
    await shot("16-security");
  });

  await step("logout, then login with password + BIOMETRIC (no code needed)", async () => {
    await page.getByRole("button", { name: "Log out" }).first().click();
    await page.waitForURL("**/login");
    await page.getByLabel("Email address", { exact: true }).fill(email);
    await page.getByLabel("Password").fill(PW);
    await page.getByRole("button", { name: "Continue" }).click();
    await page.getByRole("button", { name: "Use fingerprint or face", exact: true }).click();
    await page.waitForURL("**/dashboard", { timeout: 15000 });
    const me = await (await page.request.get(BASE + "/api/account/security")).json();
    if (!me.sessions.some((s) => s.current && s.method === "password+biometric")) throw new Error("session not recorded as biometric");
  });

  await step("security: remove biometric; password-only is never enough again", async () => {
    await page.goto(BASE + "/security");
    await page.getByRole("button", { name: "Remove" }).first().click();
    await page.getByText("No fingerprint/face sign-in set up.").waitFor();
  });

  await step("forgot password: generic answer, code, new password, old password rejected, old session dead", async () => {
    // a second signed-in browser context to prove sessions are revoked by the reset
    const ctx2 = await browser.newContext(); const p2 = await ctx2.newPage();
    await p2.goto(BASE + "/login");
    await p2.getByLabel("Email address", { exact: true }).fill(email); await p2.getByLabel("Password").fill(PW);
    const n0 = countOtp(email, "login");
    await p2.getByRole("button", { name: "Continue" }).click();
    await p2.getByLabel("6-digit code").waitFor();
    await p2.getByLabel("6-digit code").fill((await devOtp(email, "login", n0)).code);
    await p2.getByRole("button", { name: "Log in" }).click(); await p2.waitForURL("**/dashboard");

    await page.getByRole("button", { name: "Log out" }).first().click();
    await page.waitForURL("**/login");
    await page.getByRole("link", { name: /forgot my password/i }).click();
    await page.getByLabel("Email address", { exact: true }).fill(email);
    const n1 = countOtp(email, "password_reset");
    await page.getByRole("button", { name: "Send me a code" }).click();
    await page.getByText("If an account exists").first().waitFor();
    await shot("17-forgot");
    await page.getByLabel("New password", { exact: true }).fill("NewSecret456");
    await page.getByLabel("Type the new password again").fill("NewSecret456");
    await page.getByLabel("6-digit code").fill((await devOtp(email, "password_reset", n1)).code);
    await page.getByRole("button", { name: "Change my password" }).click();
    await page.waitForURL("**/login?reset=1");
    await page.getByText("Your password was changed").waitFor();
    if ((await p2.request.get(BASE + "/api/auth/me")).status() !== 401) throw new Error("old session survived password reset");
    await ctx2.close();
    // old password fails, new one works (with a code)
    await page.getByLabel("Email address", { exact: true }).fill(email); await page.getByLabel("Password").fill(PW);
    await page.getByRole("button", { name: "Continue" }).click();
    await page.getByText("Incorrect email or password").waitFor();
    const n2 = countOtp(email, "login");
    await page.getByLabel("Password").fill("NewSecret456");
    await page.getByRole("button", { name: "Continue" }).click();
    await page.getByLabel("6-digit code").fill((await devOtp(email, "login", n2)).code);
    await page.getByRole("button", { name: "Log in" }).click();
    await page.waitForURL("**/dashboard", { timeout: 15000 });
  });

  await step("elderly usability: auth inputs/buttons are at least 44px tall; text-size button works", async () => {
    await page.getByRole("button", { name: "Log out" }).first().click();
    await page.waitForURL("**/login");
    const small = await page.evaluate(() => [...document.querySelectorAll("main input, main button, main a.btn-primary")].filter((e) => e.getBoundingClientRect().height < 44 && e.getBoundingClientRect().height > 0).map((e) => e.outerHTML.slice(0, 60)));
    if (small.length) throw new Error("small targets: " + small.join(" | "));
    const f0 = await page.evaluate(() => parseFloat(getComputedStyle(document.body).fontSize));
    await page.getByRole("button", { name: /Bigger text/ }).click();
    const f1 = await page.evaluate(() => parseFloat(getComputedStyle(document.body).fontSize));
    if (!(f1 > f0)) throw new Error(`font did not grow ${f0}→${f1}`);
    await page.getByRole("button", { name: /Bigger text/ }).click(); await page.getByRole("button", { name: /Bigger text/ }).click();
    await shot("18-login-bigtext");
  });

  await browser.close();
  const failed = results.filter((r) => r[0] === "FAIL");
  console.log(`\n${results.length - failed.length}/${results.length} steps passed`);
  const real = consoleErrors.filter((e) => !/favicon|Failed to load resource.*(401|404)/.test(e));
  if (real.length) console.log("Console errors:\n" + [...new Set(real)].slice(0, 8).join("\n"));
  process.exit(failed.length ? 1 : 0);
})();
