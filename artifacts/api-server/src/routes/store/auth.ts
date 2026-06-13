import { Router } from "express";
import { RelyingParty } from "openid";
import { db } from "@workspace/db";
import { storeUsersTable } from "@workspace/db";
import { eq } from "drizzle-orm";
import { logger } from "../../lib/logger";

const router = Router();

const STEAM_OPENID_URL = "https://steamcommunity.com/openid";
const STEAM_API_KEY = process.env.STEAM_API_KEY ?? "";

function getBaseUrl(): string {
  const domains = process.env.REPLIT_DOMAINS;
  if (domains) {
    const first = domains.split(",")[0].trim();
    return `https://${first}`;
  }
  return "http://localhost:80";
}

function makeRelyingParty(): RelyingParty {
  const base = getBaseUrl();
  const returnUrl = `${base}/api/auth/steam/callback`;
  return new RelyingParty(returnUrl, base, true, true, []);
}

async function fetchSteamProfile(
  steamId: string,
): Promise<{ displayName: string; avatarUrl: string } | null> {
  try {
    const url = `https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/?key=${STEAM_API_KEY}&steamids=${steamId}`;
    const res = await fetch(url);
    if (!res.ok) return null;
    const data = (await res.json()) as {
      response: {
        players: Array<{ personaname: string; avatarfull: string }>;
      };
    };
    const player = data.response.players[0];
    if (!player) return null;
    return { displayName: player.personaname, avatarUrl: player.avatarfull };
  } catch (err) {
    logger.error({ err }, "fetchSteamProfile error");
    return null;
  }
}

router.get("/auth/steam", (_req, res) => {
  const rp = makeRelyingParty();
  rp.authenticate(STEAM_OPENID_URL, false, (err, authUrl) => {
    if (err || !authUrl) {
      logger.error({ err }, "Steam OpenID authenticate error");
      return res.status(500).send("Erro ao iniciar login Steam");
    }
    return res.redirect(authUrl);
  });
});

router.get("/auth/steam/callback", (req, res) => {
  const rp = makeRelyingParty();
  rp.verifyAssertion(req, async (err, result) => {
    if (err || !result?.authenticated || !result.claimedIdentifier) {
      logger.error({ err }, "Steam OpenID verify error");
      return res.redirect(`${getBaseUrl()}/store/?auth=fail`);
    }

    const steamId = result.claimedIdentifier.split("/").pop() ?? "";
    if (!steamId || !/^\d+$/.test(steamId)) {
      return res.redirect(`${getBaseUrl()}/store/?auth=fail`);
    }

    const profile = await fetchSteamProfile(steamId);
    const displayName = profile?.displayName ?? steamId;
    const avatarUrl = profile?.avatarUrl ?? "";

    try {
      await db
        .insert(storeUsersTable)
        .values({
          steamId,
          displayName,
          avatarUrl,
          points: 0,
          isAdmin: false,
        })
        .onConflictDoUpdate({
          target: storeUsersTable.steamId,
          set: {
            displayName,
            avatarUrl,
          },
        });

      const [user] = await db
        .select({ isAdmin: storeUsersTable.isAdmin })
        .from(storeUsersTable)
        .where(eq(storeUsersTable.steamId, steamId));
      const isAdmin = user?.isAdmin ?? false;

      const sess = req.session as any;
      sess.steamId = steamId;
      sess.isAdmin = isAdmin;

      req.session.save(() => {
        res.redirect(`${getBaseUrl()}/store/`);
      });
    } catch (dbErr) {
      logger.error({ err: dbErr }, "Steam callback DB error");
      return res.redirect(`${getBaseUrl()}/store/?auth=fail`);
    }
  });
});

router.get("/auth/me", async (req, res) => {
  const sess = req.session as any;
  if (!sess?.steamId) {
    return res.json({
      authenticated: false,
      isAdmin: false,
      points: 0,
      steamId: null,
      displayName: null,
      avatarUrl: null,
    });
  }
  try {
    const [user] = await db
      .select()
      .from(storeUsersTable)
      .where(eq(storeUsersTable.steamId, sess.steamId));
    if (!user) {
      return res.json({
        authenticated: false,
        isAdmin: false,
        points: 0,
        steamId: null,
        displayName: null,
        avatarUrl: null,
      });
    }
    return res.json({
      authenticated: true,
      steamId: user.steamId,
      displayName: user.displayName,
      avatarUrl: user.avatarUrl,
      isAdmin: user.isAdmin,
      points: user.points,
    });
  } catch (err) {
    logger.error({ err }, "auth/me error");
    return res.status(500).json({ error: "Internal server error" });
  }
});

router.post("/auth/logout", (req, res) => {
  req.session?.destroy?.(() => {});
  return res.json({ ok: true });
});

export default router;
