// Waitlist mode: while false, /register shows the waitlist form instead of a
// signup form, and CTAs across the marketing site point to the waitlist.
// Mirrors the backend's `enable_public_registration` flag — flip both together.
export const REGISTRATION_OPEN = process.env.NEXT_PUBLIC_REGISTRATION_OPEN !== "false";
