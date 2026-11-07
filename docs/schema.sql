-- Generated from the SQLAlchemy models (PostgreSQL dialect). The app creates these tables itself on start-up (create_all).
-- Columns typed EncryptedText/EncryptedJSON hold Fernet ciphertext (TEXT) – never plaintext.

CREATE TABLE audit_logs (
	id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36), 
	action VARCHAR(60) NOT NULL, 
	detail VARCHAR(300), 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);
CREATE INDEX ix_audit_logs_user_id ON audit_logs (user_id);

CREATE TABLE knowledge_chunks (
	id VARCHAR(36) NOT NULL, 
	doc_id VARCHAR(80) NOT NULL, 
	title VARCHAR(200) NOT NULL, 
	section VARCHAR(200) NOT NULL, 
	source_name VARCHAR(200) NOT NULL, 
	source_url VARCHAR(400), 
	review_status VARCHAR(30) NOT NULL, 
	text TEXT NOT NULL, 
	embedding JSON, 
	embedding_model VARCHAR(60), 
	position INTEGER NOT NULL, 
	PRIMARY KEY (id)
);
CREATE INDEX ix_kb_doc ON knowledge_chunks (doc_id);

CREATE TABLE users (
	id VARCHAR(36) NOT NULL, 
	email VARCHAR(254) NOT NULL, 
	password_hash VARCHAR(100) NOT NULL, 
	full_name VARCHAR(120) NOT NULL, 
	preferred_language VARCHAR(5) NOT NULL, 
	timezone VARCHAR(64) NOT NULL, 
	phone VARCHAR(20), 
	email_verified BOOLEAN NOT NULL, 
	phone_verified BOOLEAN NOT NULL, 
	mfa_channel VARCHAR(5) NOT NULL, 
	token_version INTEGER NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);
CREATE UNIQUE INDEX ix_users_email ON users (email);

CREATE TABLE chat_sessions (
	id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	title TEXT NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);
CREATE INDEX ix_chat_sessions_user_id ON chat_sessions (user_id);

CREATE TABLE consent_records (
	id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	purpose VARCHAR(50) NOT NULL, 
	granted BOOLEAN NOT NULL, 
	policy_version VARCHAR(10) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);
CREATE INDEX ix_consent_user_purpose ON consent_records (user_id, purpose, created_at);
CREATE INDEX ix_consent_records_user_id ON consent_records (user_id);

CREATE TABLE emergency_contacts (
	id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	phone VARCHAR(20) NOT NULL, 
	relationship VARCHAR(50), 
	is_primary BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);
CREATE INDEX ix_emergency_contacts_user_id ON emergency_contacts (user_id);

CREATE TABLE emergency_events (
	id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	trigger VARCHAR(20) NOT NULL, 
	severity VARCHAR(12) NOT NULL, 
	flags JSON, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);
CREATE INDEX ix_emergency_events_user_id ON emergency_events (user_id);

CREATE TABLE health_profiles (
	user_id VARCHAR(36) NOT NULL, 
	date_of_birth DATE, 
	sex VARCHAR(20), 
	blood_group VARCHAR(5), 
	height_cm FLOAT, 
	weight_kg FLOAT, 
	allergies TEXT, 
	conditions TEXT, 
	notes TEXT, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (user_id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE health_records (
	id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	record_type VARCHAR(30) NOT NULL, 
	title VARCHAR(200) NOT NULL, 
	record_date DATE NOT NULL, 
	details TEXT, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);
CREATE INDEX ix_records_user_date ON health_records (user_id, record_date);

CREATE TABLE otp_challenges (
	id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	purpose VARCHAR(20) NOT NULL, 
	channel VARCHAR(5) NOT NULL, 
	destination VARCHAR(254) NOT NULL, 
	code_hash VARCHAR(64), 
	expires_at TIMESTAMP WITH TIME ZONE, 
	attempts INTEGER NOT NULL, 
	sends INTEGER NOT NULL, 
	last_sent_at TIMESTAMP WITH TIME ZONE, 
	consumed_at TIMESTAMP WITH TIME ZONE, 
	webauthn_challenge VARCHAR(200), 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);
CREATE INDEX ix_otp_user_purpose ON otp_challenges (user_id, purpose);

CREATE TABLE prescriptions (
	id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	status VARCHAR(15) NOT NULL, 
	image_path VARCHAR(300), 
	image_mime VARCHAR(30), 
	quality JSON, 
	extraction_engine VARCHAR(40) NOT NULL, 
	ocr_text TEXT, 
	warnings JSON, 
	doctor_name TEXT, 
	prescribed_date DATE, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	confirmed_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);
CREATE INDEX ix_prescriptions_user_id ON prescriptions (user_id);

CREATE TABLE user_sessions (
	id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	user_agent VARCHAR(200), 
	method VARCHAR(20) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	last_seen_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	revoked_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);
CREATE INDEX ix_user_sessions_user_id ON user_sessions (user_id);

CREATE TABLE webauthn_credentials (
	id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	credential_id BYTEA NOT NULL, 
	public_key BYTEA NOT NULL, 
	sign_count INTEGER NOT NULL, 
	name VARCHAR(60) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	last_used_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	UNIQUE (credential_id)
);
CREATE INDEX ix_webauthn_credentials_user_id ON webauthn_credentials (user_id);

CREATE TABLE chat_messages (
	id VARCHAR(36) NOT NULL, 
	session_id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	role VARCHAR(10) NOT NULL, 
	content TEXT NOT NULL, 
	language VARCHAR(5) NOT NULL, 
	intent VARCHAR(30), 
	safety_level VARCHAR(12), 
	sources JSON, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(session_id) REFERENCES chat_sessions (id) ON DELETE CASCADE, 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);
CREATE INDEX ix_chat_messages_user_id ON chat_messages (user_id);
CREATE INDEX ix_chat_messages_session_id ON chat_messages (session_id);

CREATE TABLE prescription_items (
	id VARCHAR(36) NOT NULL, 
	prescription_id VARCHAR(36) NOT NULL, 
	position INTEGER NOT NULL, 
	medicine_name TEXT, 
	strength TEXT, 
	form VARCHAR(30), 
	dosage_instruction TEXT, 
	frequency_text TEXT, 
	duration_text TEXT, 
	confidence FLOAT NOT NULL, 
	needs_review BOOLEAN NOT NULL, 
	flags TEXT, 
	edited_by_user BOOLEAN NOT NULL, 
	user_confirmed BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(prescription_id) REFERENCES prescriptions (id) ON DELETE CASCADE
);
CREATE INDEX ix_prescription_items_prescription_id ON prescription_items (prescription_id);

CREATE TABLE reminders (
	id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	prescription_item_id VARCHAR(36) NOT NULL, 
	times JSON NOT NULL, 
	start_date DATE NOT NULL, 
	end_date DATE, 
	active BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(prescription_item_id) REFERENCES prescription_items (id) ON DELETE CASCADE
);
CREATE INDEX ix_reminders_user_id ON reminders (user_id);

CREATE TABLE dose_logs (
	id VARCHAR(36) NOT NULL, 
	reminder_id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	scheduled_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	status VARCHAR(10) NOT NULL, 
	acted_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_dose_slot UNIQUE (reminder_id, scheduled_at), 
	FOREIGN KEY(reminder_id) REFERENCES reminders (id) ON DELETE CASCADE, 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);
CREATE INDEX ix_dose_user_time ON dose_logs (user_id, scheduled_at);

