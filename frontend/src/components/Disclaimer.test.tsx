import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import {
  ANALYTICS_DISCLAIMER,
  FOOTER_DISCLAIMER,
  REGISTRATION_DISCLAIMER,
} from "@/content/disclaimer";

import { Disclaimer } from "./Disclaimer";

describe("Disclaimer (05 §5.6 — the un-retypable copy)", () => {
  it("renders the footer variant byte-for-byte from the constants module", () => {
    render(<Disclaimer variant="footer" />);
    expect(screen.getByTestId("disclaimer-footer").textContent).toBe(FOOTER_DISCLAIMER);
  });

  it("renders the analytics variant byte-for-byte", () => {
    render(<Disclaimer variant="analytics" />);
    expect(screen.getByTestId("disclaimer-analytics").textContent).toBe(ANALYTICS_DISCLAIMER);
  });

  it("renders the registration variant byte-for-byte", () => {
    render(<Disclaimer variant="registration" />);
    expect(screen.getByTestId("disclaimer-registration").textContent).toBe(
      REGISTRATION_DISCLAIMER,
    );
  });

  it("the constants carry 05 §5.6's exact wording (the pinned strings)", () => {
    expect(FOOTER_DISCLAIMER).toBe(
      "TCS Joining Tracker is an independent community platform and is not affiliated with, endorsed by, or operated by Tata Consultancy Services (TCS). Information displayed on the platform is primarily user-submitted and may not represent official TCS information.",
    );
    expect(ANALYTICS_DISCLAIMER).toBe(
      "Notice: All metrics shown below are calculated exclusively from voluntarily submitted candidate data. They do not represent official TCS corporate communications or hiring figures.",
    );
    expect(REGISTRATION_DISCLAIMER).toBe(
      "By creating an account, you acknowledge that this is a peer support community and not an official TCS human resources portal.",
    );
  });

  it("the footer string contains the non-affiliation clause", () => {
    expect(FOOTER_DISCLAIMER).toContain("not affiliated with");
  });
});
