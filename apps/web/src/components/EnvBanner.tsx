import { IS_DEMO, IS_TEST } from "../lib/env";

/** Impossible-to-miss strip on every screen of the test and demo copies. The real app shows nothing. */
export function EnvBanner() {
  if (!IS_TEST && !IS_DEMO) return null;
  return (
    <div className={`env-banner ${IS_TEST ? "env-banner-test" : "env-banner-demo"}`} role="status">
      {IS_TEST
        ? <><strong>TEST ENVIRONMENT</strong> · fake data · nothing here affects the real app</>
        : <><strong>DEMO</strong> · practice data on this laptop</>}
    </div>
  );
}
