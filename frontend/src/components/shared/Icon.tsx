"use client";

interface IconProps {
  name: string;
  filled?: boolean;
  className?: string;
  style?: React.CSSProperties;
}

/**
 * Material Symbols Outlined icon wrapper.
 * Loads the icon font via globals.css / layout.tsx; we just toggle the class.
 */
export function Icon({ name, filled = false, className = "", style }: IconProps) {
  return (
    <span
      className={["material-symbols-outlined", className].join(" ")}
      style={{
        fontVariationSettings: `'FILL' ${filled ? 1 : 0}, 'wght' 400, 'GRAD' 0, 'opsz' 24`,
        verticalAlign: "middle",
        ...style,
      }}
      aria-hidden
    >
      {name}
    </span>
  );
}
