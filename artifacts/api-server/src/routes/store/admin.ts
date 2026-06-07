import { Router } from "express";
import { db } from "@workspace/db";
import {
  storeProductsTable, storeOrdersTable, storeCategoriesTable,
} from "@workspace/db";
import { eq, count, desc } from "drizzle-orm";
import { logger } from "../../lib/logger";

const router = Router();

function requireAdmin(req: any, res: any, next: any) {
  if (!(req.session as any)?.isAdmin) {
    return res.status(403).json({ error: "Forbidden" });
  }
  return next();
}

router.get("/admin/products", requireAdmin, async (req, res) => {
  try {
    const page = Math.max(1, Number(req.query.page) || 1);
    const limit = 24;
    const offset = (page - 1) * limit;

    const [{ value: total }] = await db.select({ value: count() }).from(storeProductsTable);
    const items = await db
      .select()
      .from(storeProductsTable)
      .limit(limit)
      .offset(offset)
      .orderBy(desc(storeProductsTable.createdAt));

    return res.json({
      items: items.map((p) => ({ ...p, createdAt: p.createdAt.toISOString(), updatedAt: p.updatedAt.toISOString() })),
      total,
      page,
      limit,
      totalPages: Math.ceil(total / limit),
    });
  } catch (err) {
    logger.error({ err }, "admin list products error");
    return res.status(500).json({ error: "Internal server error" });
  }
});

router.post("/admin/products", requireAdmin, async (req, res) => {
  try {
    const [product] = await db.insert(storeProductsTable).values(req.body).returning();
    return res.status(201).json({ ...product, createdAt: product.createdAt.toISOString(), updatedAt: product.updatedAt.toISOString() });
  } catch (err) {
    logger.error({ err }, "admin create product error");
    return res.status(500).json({ error: "Internal server error" });
  }
});

router.patch("/admin/products/:id", requireAdmin, async (req, res) => {
  try {
    const id = parseInt(req.params.id);
    if (isNaN(id)) return res.status(404).json({ error: "Not found" });
    const [product] = await db
      .update(storeProductsTable)
      .set({ ...req.body, updatedAt: new Date() })
      .where(eq(storeProductsTable.id, id))
      .returning();
    if (!product) return res.status(404).json({ error: "Not found" });
    return res.json({ ...product, createdAt: product.createdAt.toISOString(), updatedAt: product.updatedAt.toISOString() });
  } catch (err) {
    logger.error({ err }, "admin update product error");
    return res.status(500).json({ error: "Internal server error" });
  }
});

router.delete("/admin/products/:id", requireAdmin, async (req, res) => {
  try {
    const id = parseInt(req.params.id);
    if (isNaN(id)) return res.status(404).json({ error: "Not found" });
    await db.update(storeProductsTable).set({ isActive: false }).where(eq(storeProductsTable.id, id));
    return res.json({ ok: true });
  } catch (err) {
    logger.error({ err }, "admin delete product error");
    return res.status(500).json({ error: "Internal server error" });
  }
});

router.get("/admin/orders", requireAdmin, async (req, res) => {
  try {
    const page = Math.max(1, Number(req.query.page) || 1);
    const limit = 24;
    const offset = (page - 1) * limit;

    const [{ value: total }] = await db.select({ value: count() }).from(storeOrdersTable);
    const items = await db
      .select()
      .from(storeOrdersTable)
      .limit(limit)
      .offset(offset)
      .orderBy(desc(storeOrdersTable.createdAt));

    return res.json({
      items: items.map((o) => ({ ...o, createdAt: o.createdAt.toISOString(), updatedAt: o.updatedAt.toISOString() })),
      total,
      page,
      limit,
      totalPages: Math.ceil(total / limit),
    });
  } catch (err) {
    logger.error({ err }, "admin list orders error");
    return res.status(500).json({ error: "Internal server error" });
  }
});

router.patch("/admin/orders/:id", requireAdmin, async (req, res) => {
  try {
    const id = parseInt(req.params.id);
    if (isNaN(id)) return res.status(404).json({ error: "Not found" });
    const [order] = await db
      .update(storeOrdersTable)
      .set({ status: req.body.status, updatedAt: new Date() })
      .where(eq(storeOrdersTable.id, id))
      .returning();
    if (!order) return res.status(404).json({ error: "Not found" });
    return res.json({ ...order, createdAt: order.createdAt.toISOString(), updatedAt: order.updatedAt.toISOString() });
  } catch (err) {
    logger.error({ err }, "admin update order error");
    return res.status(500).json({ error: "Internal server error" });
  }
});

export default router;
