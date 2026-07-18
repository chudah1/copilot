import { ImageResponse } from "next/og";

export const size = {
  width: 180,
  height: 180,
};

export const contentType = "image/png";

export default function AppleIcon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#ECE7DB",
          borderRadius: 36,
        }}
      >
        <svg viewBox="0 0 32 36" width="104" height="117" fill="none">
          <path
            d="M3 36V14Q3 3 16 3t13 11v22Z"
            stroke="#1E5C3A"
            strokeWidth="2"
            strokeLinejoin="round"
          />
          <path d="m16 9 3.5 11-3.5 4-3.5-4Z" fill="#1E5C3A" />
          <line x1="16" y1="15" x2="16" y2="24" stroke="#ECE7DB" strokeWidth="1" />
          <circle cx="16" cy="24" r="1" fill="#1E5C3A" />
        </svg>
      </div>
    ),
    size,
  );
}
