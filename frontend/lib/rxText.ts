export function flagText(f: string): string {
  if (f.startsWith("unclear:")) {
    const names: Record<string, string> = { name: "the medicine name", strength: "the strength", dosage_instruction: "the instructions", duration: "how long to take it", frequency: "how often", form: "the form (tablet, syrup…)" };
    return `The reader was unsure about ${names[f.slice(8)] ?? f.slice(8).replace(/_/g, " ")}.`;
  }
  const m: Record<string, string> = {
    strength_not_found: "Strength (for example 500mg) was not found. Check your strip or label.",
    dosage_instruction_not_found: "Instructions were not found. Type them exactly as written on the prescription.",
    duration_not_found: "Number of days was not found.",
    low_ocr_confidence: "The print was hard to read. Check every letter.",
    name_not_found_in_ocr_text: "The name could not be matched to the printed text. Check it carefully.",
    dosage_not_verified_in_ocr_text: "The instructions could not be cross-checked with the printed text.",
    unverified_no_ocr_text: "Nothing could be cross-checked (handwriting?). Check everything.",
    instruction_not_recognised: "I could not recognise this instruction. It is shown exactly as written; ask your doctor or pharmacist what it means.",
    model_uncertainty_note: "The reader was not sure about part of this line (see the note below).",
    added_by_user: "Added by you",
  };
  return m[f] ?? f.replace(/_/g, " ");
}
export function warningText(w: string): string {
  const m: Record<string, string> = {
    image_low_resolution: "The photo is small. A closer photo reads better.",
    image_blurry: "The photo looks blurry. Hold the phone steady and tap to focus.",
    image_too_dark: "The photo is dark. Use more light.",
    image_overexposed: "The photo is too bright. Avoid glare.",
    image_low_contrast: "The writing does not stand out. Try a flat, well-lit surface.",
    local_ocr_unavailable: "The text reader is not installed on this server, so nothing could be read automatically.",
    ai_consent_off_local_only: "AI reading is off (Privacy page). Only the local text reader was used.",
    ai_not_configured_local_only: "AI reading is not configured on this server. Only the local text reader was used.",
    ai_extraction_failed_used_local_parser: "AI reading failed, so the local text reader was used.",
    model_reports_poor_legibility: "The AI found the writing hard to read.",
    image_rotated_automatically: "The photo was sideways or upside down, so I turned it upright.",
    ai_lines_discarded_as_invalid: "Some lines the AI returned were unusable and were left out. Compare with your paper to make sure nothing is missing.",
  };
  return m[w] ?? w.replace(/_/g, " ");
}
export type RxStatus = "clear" | "check" | "unclear";
/** Status is always shown as an icon AND words, never by colour alone. "Clear" still needs the user's confirmation. */
export const STATUS_INFO: Record<RxStatus, { label: string; help: string; cls: string; icon: "check" | "alert" | "x" }> = {
  clear: { label: "Clear", help: "Looks readable. Still compare it with your paper before confirming.", cls: "bg-ok-tint text-ok", icon: "check" },
  check: { label: "Check", help: "Some details need your attention. Please check them carefully.", cls: "bg-saffron-tint text-saffron-ink", icon: "alert" },
  unclear: { label: "Unclear", help: "I could not read this reliably. Type it yourself from the paper, or remove it.", cls: "bg-sos-tint text-sos", icon: "x" },
};
export const confidenceTone = (l: string) => (l === "high" ? "bg-ok-tint text-ok" : l === "medium" ? "bg-saffron-tint text-saffron-ink" : "bg-sos-tint text-sos");

/** Downscale big phone photos before upload (saves data on slow 2G/3G connections). */
export async function shrinkImage(file: File, maxSide = 1800): Promise<File> {
  if (!file.type.startsWith("image/") || file.size < 400_000) return file;
  try {
    const bmp = await createImageBitmap(file);
    const k = Math.min(1, maxSide / Math.max(bmp.width, bmp.height));
    const c = document.createElement("canvas"); c.width = Math.round(bmp.width * k); c.height = Math.round(bmp.height * k);
    c.getContext("2d")!.drawImage(bmp, 0, 0, c.width, c.height);
    const blob: Blob | null = await new Promise((r) => c.toBlob(r, "image/jpeg", 0.88));
    return blob ? new File([blob], "prescription.jpg", { type: "image/jpeg" }) : file;
  } catch { return file; }
}
