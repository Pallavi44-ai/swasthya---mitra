import { redirect } from "next/navigation";
/** Reset happens on the same page as "forgot password" (code + new password in one flow). */
export default function ResetRedirect() { redirect("/forgot-password"); }
