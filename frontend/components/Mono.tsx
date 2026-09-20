type MonoProps = { children: React.ReactNode };
export function Mono({ children }: MonoProps) {
  return <span className="mono">{children}</span>;
}
