import { Router } from "express";
import { db } from "@workspace/db";
import {
  storeProductsTable, storeOrdersTable, storeCategoriesTable,
} from "@workspace/db";
import { eq, count } from "drizzle-orm";
import { logger } from "../../lib/logger";

const router = Router();

router.get("/store/stats", async (_req, res) => {
  try {
    const [[{ value: totalProducts }], [{ value: totalCategories }],
      [{ value: totalOrders }], [{ value: totalDelivered }]] = await Promise.all([
      db.select({ value: count() }).from(storeProductsTable).where(eq(storeProductsTable.isActive, true)),
      db.select({ value: count() }).from(storeCategoriesTable),
      db.select({ value: count() }).from(storeOrdersTable),
      db.select({ value: count() }).from(storeOrdersTable).where(eq(storeOrdersTable.status, "delivered")),
    ]);
    return res.json({ totalProducts, totalCategories, totalOrders, totalDelivered });
  } catch (err) {
    logger.error({ err }, "store stats error");
    return res.status(500).json({ error: "Internal server error" });
  }
});

router.post("/payments/webhook", async (req, res) => {
  logger.info({ body: req.body }, "payment webhook received");
  return res.json({ ok: true });
});

export default router;
