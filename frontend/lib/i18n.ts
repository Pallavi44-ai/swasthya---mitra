import type { Lang } from "./types";

export const LANGS: { code: Lang; label: string; native: string; locale: string }[] = [
  { code: "en", label: "English", native: "English", locale: "en-IN" },
  { code: "hi", label: "Hindi", native: "हिन्दी", locale: "hi-IN" },
  { code: "kn", label: "Kannada", native: "ಕನ್ನಡ", locale: "kn-IN" },
  { code: "te", label: "Telugu", native: "తెలుగు", locale: "te-IN" },
];
export const localeOf = (l: Lang) => LANGS.find((x) => x.code === l)!.locale;

// Core interface strings in 4 languages. Hindi/Kannada/Telugu text should be reviewed by native speakers.
const D = {
  home: { en: "Home", hi: "होम", kn: "ಮುಖಪುಟ", te: "హోమ్" },
  chat: { en: "Ask", hi: "पूछें", kn: "ಕೇಳಿ", te: "అడగండి" },
  medicines: { en: "Prescriptions", hi: "पर्चे", kn: "ಪ್ರಿಸ್ಕ್ರಿಪ್ಷನ್", te: "ప్రిస్క్రిప్షన్" },
  reminders: { en: "Reminders", hi: "रिमाइंडर", kn: "ರಿಮೈಂಡರ್", te: "రిమైండర్లు" },
  profile: { en: "My health", hi: "मेरा स्वास्थ्य", kn: "ನನ್ನ ಆರೋಗ್ಯ", te: "నా ఆరోగ్యం" },
  records: { en: "Records", hi: "रिकॉर्ड", kn: "ದಾಖಲೆಗಳು", te: "రికార్డులు" },
  security: { en: "Sign-in security", hi: "साइन-इन सुरक्षा", kn: "ಸೈನ್-ಇನ್ ಭದ್ರತೆ", te: "సైన్-ఇన్ భద్రత" },
  privacy: { en: "Privacy", hi: "गोपनीयता", kn: "ಗೌಪ್ಯತೆ", te: "గోప్యత" },
  status: { en: "System status", hi: "सिस्टम स्थिति", kn: "ಸಿಸ್ಟಮ್ ಸ್ಥಿತಿ", te: "సిస్టమ్ స్థితి" },
  sos: { en: "Emergency", hi: "आपातकाल", kn: "ತುರ್ತು", te: "అత్యవసరం" },
  namaste: { en: "Namaste", hi: "नमस्ते", kn: "ನಮಸ್ಕಾರ", te: "నమస్తే" },
  tapSpeak: { en: "Tap to speak", hi: "बोलने के लिए दबाएँ", kn: "ಮಾತನಾಡಲು ಒತ್ತಿ", te: "మాట్లాడటానికి నొక్కండి" },
  listening: { en: "Listening… tap to stop", hi: "सुन रहा हूँ… रोकने के लिए दबाएँ", kn: "ಕೇಳುತ್ತಿದ್ದೇನೆ… ನಿಲ್ಲಿಸಲು ಒತ್ತಿ", te: "వింటున్నాను… ఆపడానికి నొక్కండి" },
  typeHere: { en: "Type your question", hi: "अपना सवाल लिखें", kn: "ನಿಮ್ಮ ಪ್ರಶ್ನೆ ಬರೆಯಿರಿ", te: "మీ ప్రశ్న రాయండి" },
  send: { en: "Send", hi: "भेजें", kn: "ಕಳುಹಿಸಿ", te: "పంపండి" },
  heard: { en: "Check what I heard, then press Send.", hi: "देखिए मैंने क्या सुना, फिर भेजें दबाएँ।", kn: "ನಾನು ಕೇಳಿದ್ದನ್ನು ಪರಿಶೀಲಿಸಿ, ನಂತರ ಕಳುಹಿಸಿ ಒತ್ತಿ.", te: "నేను విన్నది సరిచూసి, తర్వాత పంపండి నొక్కండి." },
  readAloud: { en: "Read aloud", hi: "पढ़कर सुनाएँ", kn: "ಓದಿ ಹೇಳಿ", te: "చదివి వినిపించండి" },
  stopReading: { en: "Stop", hi: "रोकें", kn: "ನಿಲ್ಲಿಸಿ", te: "ఆపండి" },
  todayMeds: { en: "Today's medicines", hi: "आज की दवाइयाँ", kn: "ಇಂದಿನ ಔಷಧಿಗಳು", te: "ఈ రోజు మందులు" },
  taken: { en: "Taken", hi: "ले ली", kn: "ತೆಗೆದುಕೊಂಡೆ", te: "తీసుకున్నాను" },
  skip: { en: "Skip", hi: "छोड़ें", kn: "ಬಿಟ್ಟುಬಿಡಿ", te: "వదిలేయండి" },
  timeToTake: { en: "Time to take", hi: "दवा लेने का समय", kn: "ಔಷಧಿ ತೆಗೆದುಕೊಳ್ಳುವ ಸಮಯ", te: "మందు వేసుకునే సమయం" },
  call108: { en: "Call 108 now", hi: "अभी 108 पर कॉल करें", kn: "ಈಗ 108 ಕ್ಕೆ ಕರೆ ಮಾಡಿ", te: "ఇప్పుడే 108 కు కాల్ చేయండి" },
  emergencyHead: { en: "Do you need urgent help?", hi: "क्या आपको तुरंत मदद चाहिए?", kn: "ನಿಮಗೆ ತುರ್ತು ಸಹಾಯ ಬೇಕೇ?", te: "మీకు అత్యవసర సహాయం కావాలా?" },
  notDoctor: { en: "General information only. Not a doctor.", hi: "केवल सामान्य जानकारी। डॉक्टर का विकल्प नहीं।", kn: "ಸಾಮಾನ್ಯ ಮಾಹಿತಿ ಮಾತ್ರ. ವೈದ್ಯರ ಬದಲಿ ಅಲ್ಲ.", te: "సాధారణ సమాచారం మాత్రమే. వైద్యుడికి ప్రత్యామ్నాయం కాదు." },
  logout: { en: "Log out", hi: "लॉग आउट", kn: "ಲಾಗ್ ಔಟ್", te: "లాగ్ అవుట్" },
  textSize: { en: "Text size", hi: "अक्षर का आकार", kn: "ಅಕ್ಷರ ಗಾತ್ರ", te: "అక్షరాల పరిమాణం" },
  contrast: { en: "High contrast", hi: "ज़्यादा कंट्रास्ट", kn: "ಹೆಚ್ಚು ಕಾಂಟ್ರಾಸ್ಟ್", te: "అధిక కాంట్రాస్ట్" },
  newChat: { en: "New chat", hi: "नई बातचीत", kn: "ಹೊಸ ಸಂಭಾಷಣೆ", te: "కొత్త సంభాషణ" },
  earlierChats: { en: "Earlier chats", hi: "पिछली बातचीत", kn: "ಹಿಂದಿನ ಸಂಭಾಷಣೆಗಳು", te: "గత సంభాషణలు" },
  letsPlay: { en: "Let's play a game", hi: "चलो एक खेल खेलें", kn: "ಒಂದು ಆಟ ಆಡೋಣ", te: "ఒక ఆట ఆడుదాం" },
  talkWithMe: { en: "Talk with me", hi: "मुझसे बात करें", kn: "ನನ್ನೊಂದಿಗೆ ಮಾತನಾಡಿ", te: "నాతో మాట్లాడండి" },
  helpRelax: { en: "Help me relax", hi: "मुझे शांत होने में मदद करें", kn: "ನನಗೆ ಶಾಂತವಾಗಲು ಸಹಾಯ ಮಾಡಿ", te: "నేను ప్రశాంతంగా ఉండటానికి సహాయం చేయండి" },
  stopReadingAll: { en: "Stop reading aloud", hi: "पढ़ना बंद करें", kn: "ಓದುವುದನ್ನು ನಿಲ್ಲಿಸಿ", te: "చదవడం ఆపండి" },
  deleteChat: { en: "Delete", hi: "हटाएँ", kn: "ಅಳಿಸಿ", te: "తొలగించండి" },
  sureDelete: { en: "Delete this chat?", hi: "यह बातचीत हटाएँ?", kn: "ಈ ಸಂಭಾಷಣೆಯನ್ನು ಅಳಿಸಬೇಕೇ?", te: "ఈ సంభాషణను తొలగించాలా?" },
  yesDelete: { en: "Yes, delete", hi: "हाँ, हटाएँ", kn: "ಹೌದು, ಅಳಿಸಿ", te: "అవును, తొలగించండి" },
  cancel: { en: "Cancel", hi: "रद्द करें", kn: "ರದ್ದು ಮಾಡಿ", te: "రద్దు చేయండి" },
  language: { en: "Language", hi: "भाषा", kn: "ಭಾಷೆ", te: "భాష" },
} as const;

export type TKey = keyof typeof D;
export const t = (key: TKey, lang: Lang): string => (D[key] as Record<string, string>)[lang] ?? D[key].en;
