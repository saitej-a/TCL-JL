/**
 * 05 §5.6's three sanctioned disclaimer strings — stored ONCE so no later
 * view re-types them (UI-04 cannot drift if the string exists here). The
 * Disclaimer test compares rendered text against these constants, and these
 * constants against the spec, byte-for-byte.
 */

export const FOOTER_DISCLAIMER =
  "TCS Joining Tracker is an independent community platform and is not affiliated with, endorsed by, or operated by Tata Consultancy Services (TCS). Information displayed on the platform is primarily user-submitted and may not represent official TCS information.";

export const ANALYTICS_DISCLAIMER =
  "Notice: All metrics shown below are calculated exclusively from voluntarily submitted candidate data. They do not represent official TCS corporate communications or hiring figures.";

export const REGISTRATION_DISCLAIMER =
  "By creating an account, you acknowledge that this is a peer support community and not an official TCS human resources portal.";
