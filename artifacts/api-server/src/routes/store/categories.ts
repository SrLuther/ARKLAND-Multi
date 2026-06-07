import { Router } from "express";
import { db } from "@workspace/db";
import { storeCategoriesTable, storeProductsTable } from "@workspace/db";
import { eq, sql } from "drizzle-orm";
import { logger } from "../../lib/logger";

const router = Router();

router.get("/categories", async (_req, res) => {
  try {
    const rows = await db
      .select({
        id: storeCategoriesTable.id,
        slug: storeCategoriesTable.slug,
        name: storeCategoriesTable.name,
        icon: storeCategoriesTable.icon,
        sortOrder: storeCategoriesTable.sortOrder,
        productCount: sql<number>`cast(count(${storeProductsTable.id}) as int)`,
      })
      .from(storeCategoriesTable)
      .leftJoin(
        storeProductsTable,
        eq(storeProductsTable.categoryId, storeCategoriesTable.id),
      )
      .groupBy(storeCategoriesTable.id)
      .orderBy(storeCategoriesTable.sortOrder);
    return res.json(rows);
  } catch (err) {
    logger.error({ err }, "categories error");
    return res.status(500).json({ error: "Internal server error" });
  }
});

export default router;
