export type Lang = "en" | "hi" | "kn" | "te";

export interface User { id: string; email_verified: boolean; phone_verified: boolean; mfa_channel: "email" | "sms"; email: string; full_name: string; preferred_language: Lang; timezone: string; created_at: string }
export type ConsentKey = "ai_processing" | "store_chat_history" | "health_data_personalisation" | "store_prescription_images" | "emergency_sharing";
export type Consents = Record<ConsentKey, boolean>;

export interface Contact { id: string; name: string; phone: string; relationship: string | null; is_primary: boolean }
export interface Profile {
  date_of_birth: string | null; sex: "female" | "male" | "other" | null; blood_group: string | null;
  height_cm: number | null; weight_kg: number | null; allergies: string[]; conditions: string[]; notes: string | null; age: number | null;
}
export interface HealthRecord { id: string; record_type: string; title: string; record_date: string; details: string | null; created_at: string }
export interface TimelineEvent { id: string; kind: "record" | "prescription" | "emergency" | "profile"; title: string; subtitle: string | null; at: string }

export interface Source { n: number; title: string; section: string; source_name: string; source_url: string | null; review_status: string }
export interface ChatReply {
  session_id: string | null; reply: string; language: Lang; mode: "emergency" | "llm_rag" | "general_chat" | "companion" | "retrieval_only" | "navigation" | "unavailable";
  unavailable_reason: "no_consent" | "not_configured" | "error" | null;
  safety: { level: "none" | "urgent" | "emergency"; flags: string[]; labels: string[]; banner: string | null; numbers: { label: string; number: string; kind: string }[]; contacts: Contact[] };
  sources: Source[]; actions: { label: string; href: string }[]; disclaimer: string; stored: boolean; guard_removed: string[];
  topic?: "health" | "general" | "emotional" | "activity" | null;
}
export interface ChatSessionItem { id: string; title: string; created_at: string }
export interface StoredMessage { id: string; role: "user" | "assistant"; content: string; language: Lang; created_at: string }
export interface ChatMessage { id: string; role: "user" | "assistant"; text: string; reply?: ChatReply }

export interface RxItem {
  id: string; medicine_name: string | null; strength: string | null; form: string | null; dosage_instruction: string | null;
  frequency_text: string | null; duration_text: string | null; confidence: number; confidence_label: "high" | "medium" | "low";
  needs_review: boolean; flags: string[]; edited_by_user: boolean; user_confirmed: boolean;
  verification_status?: "clear" | "check" | "unclear"; raw_text?: string | null; uncertainty_note?: string | null; additional_instructions?: string | null;
}
export interface Prescription {
  id: string; status: "extracted" | "confirmed" | "failed" | "discarded"; extraction_engine: string; quality: Record<string, unknown> | null;
  warnings: string[]; doctor_name: string | null; prescribed_date: string | null; created_at: string; confirmed_at: string | null;
  has_image: boolean; items: RxItem[]; message: string | null;
  patient?: Record<string, string> | null; prescriber?: Record<string, string> | null; diagnosis?: string | null; full_transcription?: string | null; ai_warnings?: string[];
}
export interface RxImpact { status: string; medicines: number; reminders: number; active_reminders: number; doses_logged: number; doses_taken: number; in_timeline: boolean; has_photo: boolean }
export interface Explain { original: string | null; parsed: boolean; lines: string[]; suggested_times: string[]; as_needed: boolean }
export interface Eligible { prescription_item_id: string; prescription_id: string; medicine_name: string; strength: string | null; dosage_instruction: string; duration_text: string | null }
export interface Reminder { id: string; prescription_item_id: string; medicine_name: string; strength: string | null; dosage_instruction: string; times: string[]; start_date: string; end_date: string | null; active: boolean }
export interface Dose { id: string; reminder_id: string; scheduled_at: string; local_time: string; status: "pending" | "taken" | "skipped" | "missed"; medicine_name: string; strength: string | null; dosage_instruction: string }
export interface Adherence { days: { date: string; taken: number; skipped: number; missed: number }[]; taken: number; skipped: number; missed: number; percent: number | null }
export interface EmergencyInfo { numbers: { label: string; number: string; kind: string }[]; contacts: Contact[]; location_sharing_allowed: boolean }
export interface SystemStatus {
  environment: string; database: string; gemini_configured: boolean; limitations: string[];
  components: { id: string; name: string; state: "implemented" | "configured" | "needs_configuration"; note?: string }[];
}

/** State of a pending one-time-code step, as returned by the server. */
export interface Challenge {
  challenge_id: string; channel: "email" | "sms"; destination_masked: string; otp_sent: boolean;
  expires_in: number; resend_in: number; sends_left: number; max_attempts: number; methods?: ("otp" | "biometric")[]; message?: string;
}
export interface SecurityOverview {
  email: string; email_verified: boolean; phone_masked: string | null; phone_verified: boolean; mfa_channel: "email" | "sms"; sms_available: boolean;
  passkeys: { id: string; name: string; created_at: string; last_used_at: string | null }[];
  sessions: { id: string; created_at: string; last_seen_at: string; device: string | null; current: boolean; method: string }[];
  recent_activity: { action: string; at: string }[]; session_idle_minutes: number;
}
