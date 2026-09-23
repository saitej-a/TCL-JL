import {
  ANALYTICS_DISCLAIMER,
  FOOTER_DISCLAIMER,
  REGISTRATION_DISCLAIMER,
} from "@/content/disclaimer";

export type DisclaimerVariant = "footer" | "analytics" | "registration";

const VARIANT_TEXT: Record<DisclaimerVariant, string> = {
  footer: FOOTER_DISCLAIMER,
  analytics: ANALYTICS_DISCLAIMER,
  registration: REGISTRATION_DISCLAIMER,
};

interface DisclaimerProps {
  variant: DisclaimerVariant;
  className?: string;
}

/**
 * §5.6's disclaimer in §4.3's legal type (text-[11px] leading-normal), muted.
 * The text comes from `src/content/disclaimer.ts` — the single source every
 * placement (9.2's footer, 9.4's analytics header) renders.
 */
export function Disclaimer({ variant, className = "" }: DisclaimerProps) {
  return (
    <p
      data-testid={`disclaimer-${variant}`}
      className={`text-[11px] leading-normal text-slate-500 dark:text-slate-400 ${className}`.trim()}
    >
      {VARIANT_TEXT[variant]}
    </p>
  );
}
