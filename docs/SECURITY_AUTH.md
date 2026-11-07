# Authentication & MFA – design, limits, provider configuration

## What a login requires
1. **Email + password** (bcrypt, cost 12; 8–72 chars, letter + digit, common passwords refused). A correct password alone issues **no session cookie**.
2. **Second factor** – either a 6-digit code sent to the registered **email** or **mobile (SMS)**, or a registered **biometric passkey** (fingerprint / face / device screen-lock via WebAuthn, user verification *required*). Biometric is optional and only offered when the browser supports it; it is a second factor *after* the password, never a replacement for it.

New accounts are unverified until the first code is confirmed. Unverified accounts cannot log in.

## One-time-code rules (`services/otp.py`)
| Rule | Value (env var) |
|---|---|
| Code | 6 digits from `secrets` (CSPRNG) |
| Storage | **never stored** – only HMAC-SHA256(key derived from JWT_SECRET, `id:purpose:code`); hash deleted after use |
| Lifetime | 600 s (`OTP_TTL_SECONDS`), single use |
| Wrong guesses | 5 per code (`OTP_MAX_ATTEMPTS`) then locked until a new code is requested |
| Resend | 30 s cooldown, max 4 sends per challenge; a new code invalidates the previous one |
| Pending step max age | 30 min, then start again |
| Responses | unknown/used/other-purpose challenge ids look like a wrong code; the code is never in any API response or log (except the dev console provider) |
| Purpose binding | a login code cannot complete a password reset, etc. |

Other protections: login rate limit (8 / 15 min per IP+email), registration and recovery limits, dummy-hash timing equalisation for unknown emails, generic "Incorrect email or password", **forgot-password answers identically whether or not the account exists** (tested), reset needs a code on the registered channel, then **all sessions are revoked**.

## Sessions
httpOnly, SameSite=Lax cookie holding a JWT with `sid`; every request is checked against the server-side `user_sessions` row (revoked? idle > 60 min? token_version changed?). Logout revokes server-side – a copied cookie stops working (tested). Users can list devices, sign one out, or sign out everywhere. Changing/resetting a password revokes other sessions. Absolute lifetime 8 h.

## Authorisation
Every data query filters by the logged-in `user.id`; foreign object ids return 404. Verified by cross-user tests for profile, records, contacts, prescriptions, reminders, chat and sessions.

## Provider configuration (what *you* must set up)
The code in `services/otp_delivery.py` is real; the **accounts are yours**.

| Provider | Needed | Status |
|---|---|---|
| **console** (default in development) | nothing – the code is printed in the backend window | **Development only. The server refuses to start with `APP_ENV=production` unless SMTP is configured, and the console provider raises an error in production.** |
| **SMTP email** | `OTP_EMAIL_PROVIDER=smtp`, `SMTP_HOST`, `SMTP_PORT` (587), `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_STARTTLS=true` (Gmail: create an *app password*; or SES/SendGrid/Brevo SMTP) | Code path **tested against a real local SMTP server** (aiosmtpd) – *not* against Gmail/SES etc. |
| **Twilio SMS** | `OTP_SMS_PROVIDER=twilio`, `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM`. In India, SMS needs DLT registration of sender/template – a regulatory step outside this code | Request format tested with a **mocked** HTTP call only; **never sent to real Twilio** |
| **WebAuthn** | `WEBAUTHN_RP_ID` (your domain) and `WEBAUTHN_ORIGIN` (exact `https://…` origin). `localhost` works for development | Verified in headless Chromium with a *virtual authenticator*; **not tried on a physical fingerprint reader/phone** |

Production checklist: `APP_ENV=production`, strong `JWT_SECRET` & `DATA_ENCRYPTION_KEY`, `COOKIE_SECURE=true`, HTTPS, SMTP configured, WebAuthn domain set, `CORS_ORIGINS` = your site. Rate limiting is **in-memory (per process)** – with several workers use a shared store (e.g. Redis) first.

## Accessibility of the sign-in screens
Large inputs/buttons (≥ 44 px, 52–72 px for the code box), 16 px+ text with a visible "Bigger text" button, one task per screen, plain-language messages ("tries left", "works for 9:59 more"), `autocomplete="one-time-code"` so phones offer the code, show/hide password, high-contrast mode and screen-reader labels. Not yet tested with an actual screen reader or with elderly users.
