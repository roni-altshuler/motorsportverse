import type { ComponentPropsWithoutRef, ReactNode } from "react";

import { cn } from "@/components/ui/cn";

interface BentoGridProps extends ComponentPropsWithoutRef<"div"> {
  children: ReactNode;
  className?: string;
}

interface BentoCardProps extends ComponentPropsWithoutRef<"div"> {
  name?: string;
  className?: string;
  background?: ReactNode;
  Icon?: React.ComponentType<{ className?: string }>;
  description?: string;
  href?: string;
  cta?: string;
  children?: ReactNode;
}

export function BentoGrid({ children, className, ...props }: BentoGridProps) {
  return (
    <div
      className={cn(
        "grid w-full auto-rows-[16rem] grid-cols-3 gap-3",
        className,
      )}
      {...props}
    >
      {children}
    </div>
  );
}

export function BentoCard({
  name,
  className,
  background,
  Icon,
  description,
  href,
  cta,
  children,
  ...props
}: BentoCardProps) {
  return (
    <div
      key={name}
      className={cn(
        "group relative col-span-3 flex flex-col justify-between overflow-hidden",
        "border border-[var(--hairline)] bg-[var(--surface-card)] rounded-[var(--radius-card,4px)]",
        "hover-lift-premium",
        className,
      )}
      {...props}
    >
      {background ? <div className="absolute inset-0">{background}</div> : null}
      {children ? (
        <div className="relative z-10 h-full w-full">{children}</div>
      ) : (
        <>
          <div className="relative z-10 pointer-events-none flex transform-gpu flex-col gap-1 p-6">
            {Icon ? (
              <Icon className="h-10 w-10 origin-left transform-gpu text-[var(--muted)] transition-all duration-300 ease-in-out group-hover:scale-90 group-hover:text-[var(--ink)]" />
            ) : null}
            {name ? (
              <h3 className="title-md mt-2 text-[var(--ink)]">{name}</h3>
            ) : null}
            {description ? (
              <p className="body-sm max-w-lg text-[var(--body)]">{description}</p>
            ) : null}
          </div>
          {href && cta ? (
            <div className="pointer-events-none absolute bottom-0 flex w-full translate-y-10 transform-gpu flex-row items-center p-4 opacity-0 transition-all duration-300 group-hover:translate-y-0 group-hover:opacity-100">
              <a
                href={href}
                className="pointer-events-auto text-xs font-mono uppercase tracking-[0.18em] text-[var(--ink)] underline-offset-4 hover:underline"
              >
                {cta} →
              </a>
            </div>
          ) : null}
        </>
      )}
      <div className="pointer-events-none absolute inset-0 transform-gpu transition-all duration-300 group-hover:bg-[var(--surface-elevated)]/30" />
    </div>
  );
}
