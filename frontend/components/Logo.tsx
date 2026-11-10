/**
 * The Parallax mark: three slanted layers of the same shape. The white front layer is
 * the real car; the purple layers behind it are the AI's alternate line. When animated
 * they slide apart at different speeds, the way parallax layers move.
 */
const SHAPE = "14,64 38,8 56,8 32,64";

export function ParallaxMark({
  size = 32,
  motion = "none",
  title = "Parallax",
}: {
  size?: number;
  motion?: "none" | "intro" | "loop";
  title?: string;
}) {
  return (
    <svg
      className={`px-mark px-mark--${motion}`}
      width={size * (86 / 64)}
      height={size}
      viewBox="10 4 86 64"
      role="img"
      aria-label={title}
    >
      <polygon className="px-layer px-layer--far" points={SHAPE} />
      <polygon className="px-layer px-layer--mid" points={SHAPE} />
      <polygon className="px-layer px-layer--front" points={SHAPE} />
    </svg>
  );
}

export function Wordmark({ size = 20 }: { size?: number }) {
  return (
    <span className="px-brand" style={{ fontSize: size }}>
      <ParallaxMark size={size * 1.05} />
      <span className="px-word">PARALLAX</span>
    </span>
  );
}
