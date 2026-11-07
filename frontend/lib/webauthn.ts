/* Browser side of biometric sign-in (WebAuthn / passkeys). The device does the fingerprint/face/PIN check;
   the server only ever receives a public key and signed challenges – never biometric data. */
const b64uToBuf = (s: string): ArrayBuffer => {
  const pad = "=".repeat((4 - (s.length % 4)) % 4);
  const bin = atob((s + pad).replace(/-/g, "+").replace(/_/g, "/"));
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out.buffer;
};
const bufToB64u = (b: ArrayBuffer): string => {
  let s = ""; new Uint8Array(b).forEach((c) => (s += String.fromCharCode(c)));
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
};

export const biometricSupported = () => typeof window !== "undefined" && !!window.PublicKeyCredential && !!navigator.credentials;

type Json = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any

export async function createPasskey(options: Json): Promise<Json> {
  const pk: PublicKeyCredentialCreationOptions = {
    ...options,
    challenge: b64uToBuf(options.challenge),
    user: { ...options.user, id: b64uToBuf(options.user.id) },
    excludeCredentials: (options.excludeCredentials ?? []).map((c: Json) => ({ ...c, id: b64uToBuf(c.id) })),
  } as PublicKeyCredentialCreationOptions;
  const cred = (await navigator.credentials.create({ publicKey: pk })) as PublicKeyCredential | null;
  if (!cred) throw new Error("No credential was created.");
  const r = cred.response as AuthenticatorAttestationResponse;
  return {
    id: cred.id, rawId: bufToB64u(cred.rawId), type: cred.type, clientExtensionResults: cred.getClientExtensionResults(),
    response: { clientDataJSON: bufToB64u(r.clientDataJSON), attestationObject: bufToB64u(r.attestationObject), transports: r.getTransports?.() ?? [] },
  };
}

export async function getPasskey(options: Json): Promise<Json> {
  const pk: PublicKeyCredentialRequestOptions = {
    ...options,
    challenge: b64uToBuf(options.challenge),
    allowCredentials: (options.allowCredentials ?? []).map((c: Json) => ({ ...c, id: b64uToBuf(c.id) })),
  } as PublicKeyCredentialRequestOptions;
  const cred = (await navigator.credentials.get({ publicKey: pk })) as PublicKeyCredential | null;
  if (!cred) throw new Error("No credential was returned.");
  const r = cred.response as AuthenticatorAssertionResponse;
  return {
    id: cred.id, rawId: bufToB64u(cred.rawId), type: cred.type, clientExtensionResults: cred.getClientExtensionResults(),
    response: {
      clientDataJSON: bufToB64u(r.clientDataJSON), authenticatorData: bufToB64u(r.authenticatorData),
      signature: bufToB64u(r.signature), userHandle: r.userHandle ? bufToB64u(r.userHandle) : null,
    },
  };
}

export function passkeyErrorText(e: unknown): string {
  const n = (e as { name?: string })?.name;
  if (n === "NotAllowedError") return "The fingerprint/face check was cancelled or timed out. You can try again, or use a code instead.";
  if (n === "InvalidStateError") return "This device is already registered.";
  if (n === "SecurityError") return "Biometric sign-in only works on a secure address (https or localhost).";
  return e instanceof Error ? e.message : "Biometric sign-in did not work. Please use a code instead.";
}
