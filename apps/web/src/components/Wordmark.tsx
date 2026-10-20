/** El nombre del producto: «posiq.», con el punto en el acento. */
export function Wordmark({ className = "" }: { className?: string }) {
  return (
    <span className={`select-none text-[20px] font-semibold leading-none tracking-[-0.02em] ${className}`}>
      posiq<span className="text-accent">.</span>
    </span>
  );
}
