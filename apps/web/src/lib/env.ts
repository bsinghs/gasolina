// Which copy of the app this build is. Set at build time with VITE_APP_ENV.
//   production: the real app (no banner)
//   test:       the test copy, with fake data and a reset button
//   demo:       `make demo` on a laptop
export const APP_ENV = (import.meta.env.VITE_APP_ENV ?? "production").toLowerCase();
export const IS_TEST = APP_ENV === "test";
export const IS_DEMO = APP_ENV === "demo";
