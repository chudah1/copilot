import { renderSocialCard, socialImageSize } from "./social-card";

export const alt = "penKeep — your investment decisions, remembered";
export const size = socialImageSize;
export const contentType = "image/png";

export default function TwitterImage() {
  return renderSocialCard();
}
