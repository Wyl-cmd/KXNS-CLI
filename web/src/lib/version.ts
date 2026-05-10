declare const __KXNS_CLI_VERSION__: string | undefined;

export const kxnsCliVersion =
  typeof __KXNS_CLI_VERSION__ !== "undefined" && __KXNS_CLI_VERSION__
    ? __KXNS_CLI_VERSION__
    : "dev";
