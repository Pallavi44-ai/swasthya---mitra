# API reference

Base path `/api`. Interactive docs (development only): http://127.0.0.1:8000/docs  (disabled when `APP_ENV=production`).
Authentication is an httpOnly cookie `sm_session` set only after **password + second factor**. Every route except the ones marked *public* needs it and returns **401** without it. Every record route is scoped to the logged-in user's id; another user's object ids return 404.

## Login flow (all public until the last step)
1. `POST /auth/register` → creates an *unverified* account, sends a code → `{challenge_id, destination_masked, expires_in, resend_in, sends_left, max_attempts}`
2. `POST /auth/register/verify {challenge_id, code}` → account confirmed, session cookie set
3. `POST /auth/login {email, password}` → **no cookie**; returns `{mfa_required:true, methods:["otp"|"biometric"], challenge…}`. Unconfirmed accounts get 403 `verification_required`.
4. `POST /auth/mfa/verify {challenge_id, code}` → cookie set. Or biometric: `POST /auth/webauthn/login/options` then `/login/verify`.
5. `POST /auth/mfa/send {challenge_id}` → (re)send; 429 `resend_wait` / `too_many_sends`.
6. Recovery: `POST /auth/forgot-password {email}` (always the same generic answer) → `POST /auth/reset-password {challenge_id, code, new_password}` (204; all sessions revoked).

Error body for code problems: `{"detail":{"code":"invalid_code|expired|locked|resend_wait|too_many_sends|delivery_failed","message":"…","attempts_left":n}}`.

## Endpoints
| Method | Path | Purpose |
|---|---|---|
| PATCH | `/api/account` | Update Account |
| DELETE | `/api/account/chat-history` | Delete Chat History |
| POST | `/api/account/delete` | Delete Account |
| GET | `/api/account/export` | Export Data |
| GET | `/api/account/security` | Overview |
| PUT | `/api/account/security/channel` | Set Channel |
| DELETE | `/api/account/security/passkeys/{pid}` | Delete Passkey |
| POST | `/api/account/security/phone` | Add Phone |
| POST | `/api/account/security/phone/verify` | Verify Phone |
| DELETE | `/api/account/security/sessions/{sid}` | Revoke Session |
| POST | `/api/auth/change-password` | Change Password |
| POST | `/api/auth/forgot-password` | Forgot Password |
| POST | `/api/auth/login` | Login |
| POST | `/api/auth/logout` | Logout |
| POST | `/api/auth/logout-all` | Logout All |
| GET | `/api/auth/me` | Me |
| POST | `/api/auth/mfa/send` | Mfa Send |
| POST | `/api/auth/mfa/verify` | Mfa Verify |
| POST | `/api/auth/register` | Register |
| POST | `/api/auth/register/verify` | Register Verify |
| POST | `/api/auth/reset-password` | Reset Password |
| POST | `/api/auth/webauthn/login/options` | Login Options |
| POST | `/api/auth/webauthn/login/verify` | Login Verify |
| POST | `/api/auth/webauthn/register/options` | Enrol Options |
| POST | `/api/auth/webauthn/register/verify` | Enrol Verify |
| POST | `/api/chat` | Send |
| GET | `/api/chat/sessions` | Sessions |
| DELETE | `/api/chat/sessions/{sid}` | Delete Session |
| GET | `/api/chat/sessions/{sid}/messages` | Messages |
| GET | `/api/consents` | Get Consents |
| PUT | `/api/consents` | Update Consents |
| GET | `/api/contacts` | List Contacts |
| POST | `/api/contacts` | Add Contact |
| PUT | `/api/contacts/{cid}` | Update Contact |
| DELETE | `/api/contacts/{cid}` | Delete Contact |
| GET | `/api/emergency` | Info |
| POST | `/api/emergency/open` | Opened |
| POST | `/api/emergency/share-message` | Share Message |
| POST | `/api/prescriptions` | Upload |
| GET | `/api/prescriptions` | List Prescriptions |
| GET | `/api/prescriptions/{pid}` | Get Prescription |
| DELETE | `/api/prescriptions/{pid}` | Delete Prescription |
| POST | `/api/prescriptions/{pid}/confirm` | Confirm |
| GET | `/api/prescriptions/{pid}/image` | Get Image |
| POST | `/api/prescriptions/{pid}/items` | Add Item |
| PUT | `/api/prescriptions/{pid}/items/{iid}` | Edit Item |
| DELETE | `/api/prescriptions/{pid}/items/{iid}` | Remove Item |
| GET | `/api/prescriptions/{pid}/items/{iid}/explain` | Explain |
| GET | `/api/profile` | Get Profile |
| PUT | `/api/profile` | Put Profile |
| GET | `/api/records` | List Records |
| POST | `/api/records` | Create Record |
| PUT | `/api/records/{rid}` | Update Record |
| DELETE | `/api/records/{rid}` | Delete Record |
| POST | `/api/reminders` | Create |
| GET | `/api/reminders` | List Reminders |
| GET | `/api/reminders/adherence` | Adherence |
| POST | `/api/reminders/doses/{did}` | Mark |
| GET | `/api/reminders/due` | Due |
| GET | `/api/reminders/eligible` | Eligible |
| GET | `/api/reminders/today` | Today |
| PATCH | `/api/reminders/{rid}` | Patch |
| DELETE | `/api/reminders/{rid}` | Delete |
| GET | `/api/system/health` | Health |
| GET | `/api/system/status` | Status |
| GET | `/api/timeline` | Timeline |
| GET | `/api/voice/languages` | Languages |
| POST | `/api/voice/transcribe` | Transcribe |
