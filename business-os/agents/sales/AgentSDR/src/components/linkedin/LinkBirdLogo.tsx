import Link from "next/link";
import { cn } from "@/lib/linkedin/utils";

const LOGO_SRC = "/linkbird-light-theme-logo.svg";

export function LinkBirdLogo({
  size = "sm",
  href,
  fullWidth = false,
}: {
  size?: "sm" | "lg";
  href?: string;
  fullWidth?: boolean;
}) {
  const img = (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={LOGO_SRC}
      alt="linkbird"
      className={cn(
        "h-auto object-contain",
        fullWidth
          ? size === "lg"
            ? "w-full max-h-14"
            : "w-full max-h-10"
          : size === "lg"
            ? "w-full max-h-14 max-w-xs"
            : "w-full max-h-10 max-w-[11.5rem]"
      )}
    />
  );

  const wrapperClass = fullWidth
    ? "flex w-full justify-center items-center"
    : "inline-flex items-center shrink-0";

  if (href) {
    return (
      <Link href={href} className={wrapperClass}>
        {img}
      </Link>
    );
  }

  return <span className={wrapperClass}>{img}</span>;
}
