/** El nombre del producto: «posiq.», con el punto en el acento. */
export function Wordmark({ className = "" }: { className?: string }) {
  return (
    <span className={`select-none font-display text-[22px] font-bold leading-none tracking-[-0.03em] ${className}`}>
      posiq<span className="text-accent">.</span>
    </span>
  );
}
