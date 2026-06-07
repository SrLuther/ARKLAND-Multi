import { Router } from "express";
import { db } from "@workspace/db";
import {
  storeOrdersTable, storeProductsTable, storeUsersTable,
} from "@workspace/db";
import { eq, and, desc } from "drizzle-orm";
import { logger } from "../../lib/logger";

const router = Router();

function requireAuth(req: any, res: any, next: any) {
  if (!(req.session as any)?.steamId) {
    return res.status(401).json({ error: "Unauthorized" });
  }
  return next();
}

router.get("/orders", requireAuth, async (req, res) => {
  try {
    const steamId = (req.session as any).steamId as string;
    const orders = await db
      .select()
      .from(storeOrdersTable)
      .where(eq(storeOrdersTable.steamId, steamId))
      .orderBy(desc(storeOrdersTable.createdAt));
    return res.json(
      orders.map((o) => ({
        ...o,
        createdAt: o.createdAt.toISOString(),
        updatedAt: o.updatedAt.toISOString(),
      })),
    );
  } catch (err) {
    logger.error({ err }, "list orders error");
    return res.status(500).json({ error: "Internal server error" });
  }
});

router.post("/orders", requireAuth, async (req, res) => {
  try {
    const steamId = (req.session as any).steamId as string;
    const { productId, quantity = 1 } = req.body as { productId: number; quantity?: number };

    const [product] = await db
      .select()
      .from(storeProductsTable)
      .where(and(eq(storeProductsTable.id, productId), eq(storeProductsTable.isActive, true)));
    if (!product) return res.status(404).json({ error: "Product not found" });

    const [user] = await db
      .select()
      .from(storeUsersTable)
      .where(eq(storeUsersTable.steamId, steamId));
    if (!user) return res.status(401).json({ error: "User not found" });

    const totalCost = product.price * quantity;

    if (user.points >= totalCost) {
      const [order] = await db
        .insert(storeOrdersTable)
        .values({
          steamId,
          displayName: user.displayName,
          productId: product.id,
          productName: product.name,
          quantity,
          pointsPaid: totalCost,
          status: "paid",
        })
        .returning();

      await db
        .update(storeUsersTable)
        .set({ points: user.points - totalCost })
        .where(eq(storeUsersTable.steamId, steamId));

      return res.status(201).json({
        order: { ...order, createdAt: order.createdAt.toISOString(), updatedAt: order.updatedAt.toISOString() },
        paymentUrl: null,
        usePoints: true,
      });
    }

    const [order] = await db
      .insert(storeOrdersTable)
      .values({
        steamId,
        displayName: user.displayName,
        productId: product.id,
        productName: product.name,
        quantity,
        pointsPaid: totalCost,
        status: "pending",
      })
      .returning();

    return res.status(201).json({
      order: { ...order, createdAt: order.createdAt.toISOString(), updatedAt: order.updatedAt.toISOString() },
      paymentUrl: `/store/checkout/${order.id}`,
      usePoints: false,
    });
  } catch (err) {
    logger.error({ err }, "create order error");
    return res.status(500).json({ error: "Internal server error" });
  }
});

router.get("/orders/:id", requireAuth, async (req, res) => {
  try {
    const id = parseInt(req.params.id);
    if (isNaN(id)) return res.status(404).json({ error: "Not found" });
    const steamId = (req.session as any).steamId as string;
    const isAdmin = (req.session as any).isAdmin as boolean;
    const cond = isAdmin
      ? eq(storeOrdersTable.id, id)
      : and(eq(storeOrdersTable.id, id), eq(storeOrdersTable.steamId, steamId));
    const [order] = await db.select().from(storeOrdersTable).where(cond);
    if (!order) return res.status(404).json({ error: "Not found" });
    return res.json({ ...order, createdAt: order.createdAt.toISOString(), updatedAt: order.updatedAt.toISOString() });
  } catch (err) {
    logger.error({ err }, "get order error");
    return res.status(500).json({ error: "Internal server error" });
  }
});

export default router;
