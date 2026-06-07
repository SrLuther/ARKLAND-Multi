declare module "openid" {
  export class RelyingParty {
    constructor(
      returnUrl: string,
      realm: string | null,
      stateless: boolean,
      strict: boolean,
      extensions: unknown[],
    );
    authenticate(
      identifier: string,
      immediate: boolean,
      callback: (error: Error | null, authUrl: string | null) => void,
    ): void;
    verifyAssertion(
      requestOrUrl: import("http").IncomingMessage | string,
      callback: (
        error: Error | null,
        result: { authenticated: boolean; claimedIdentifier?: string },
      ) => void,
    ): void;
  }
}
