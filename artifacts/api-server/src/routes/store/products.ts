import { Router } from "express";
import { db } from "@workspace/db";
import { storeProductsTable, storeCategoriesTable } from "@workspace/db";
import { eq, ilike, and, count } from "drizzle-orm";
import { logger } from "../../lib/logger";

const router = Router();

router.get("/products", async (req, res) => {
  try {
    const page = Math.max(1, Number(req.query.page) || 1);
    const limit = Math.min(48, Math.max(1, Number(req.query.limit) || 24));
    const offset = (page - 1) * limit;
    const categorySlug = req.query.category as string | undefined;
    const search = req.query.search as string | undefined;

    const conditions: ReturnType<typeof eq>[] = [
      eq(storeProductsTable.isActive, true),
    ];

    let categoryId: number | undefined;
    if (categorySlug) {
      const [cat] = await db
        .select({ id: storeCategoriesTable.id })
        .from(storeCategoriesTable)
        .where(eq(storeCategoriesTable.slug, categorySlug));
      if (cat) {
        categoryId = cat.id;
        conditions.push(eq(storeProductsTable.categoryId, cat.id) as any);
      }
    }
    if (search) {
      conditions.push(ilike(storeProductsTable.name, `%${search}%`) as any);
    }

    const where = and(...conditions);

    const [{ value: total }] = await db
      .select({ value: count() })
      .from(storeProductsTable)
      .where(where);

    const items = await db
      .select({
        id: storeProductsTable.id,
        slug: storeProductsTable.slug,
        name: storeProductsTable.name,
        description: storeProductsTable.description,
        imageUrl: storeProductsTable.imageUrl,
        price: storeProductsTable.price,
        categoryId: storeProductsTable.categoryId,
        categorySlug: storeCategoriesTable.slug,
        blueprint: storeProductsTable.blueprint,
        quantity: storeProductsTable.quantity,
        quality: storeProductsTable.quality,
        forceBlueprint: storeProductsTable.forceBlueprint,
        isFeatured: storeProductsTable.isFeatured,
        isActive: storeProductsTable.isActive,
        createdAt: storeProductsTable.createdAt,
      })
      .from(storeProductsTable)
      .leftJoin(storeCategoriesTable, eq(storeCategoriesTable.id, storeProductsTable.categoryId))
      .where(where)
      .limit(limit)
      .offset(offset);

    return res.json({
      items: items.map((p) => ({
        ...p,
        createdAt: p.createdAt.toISOString(),
      })),
      total,
      page,
      limit,
      totalPages: Math.ceil(total / limit),
    });
  } catch (err) {
    logger.error({ err }, "products error");
    return res.status(500).json({ error: "Internal server error" });
  }
});

router.get("/products/featured", async (_req, res) => {
  try {
    const items = await db
      .select({
        id: storeProductsTable.id,
        slug: storeProductsTable.slug,
        name: storeProductsTable.name,
        description: storeProductsTable.description,
        imageUrl: storeProductsTable.imageUrl,
        price: storeProductsTable.price,
        categoryId: storeProductsTable.categoryId,
        categorySlug: storeCategoriesTable.slug,
        blueprint: storeProductsTable.blueprint,
        quantity: storeProductsTable.quantity,
        quality: storeProductsTable.quality,
        forceBlueprint: storeProductsTable.forceBlueprint,
        isFeatured: storeProductsTable.isFeatured,
        isActive: storeProductsTable.isActive,
        createdAt: storeProductsTable.createdAt,
      })
      .from(storeProductsTable)
      .leftJoin(storeCategoriesTable, eq(storeCategoriesTable.id, storeProductsTable.categoryId))
      .where(and(eq(storeProductsTable.isFeatured, true), eq(storeProductsTable.isActive, true)))
      .limit(12);
    return res.json(items.map((p) => ({ ...p, createdAt: p.createdAt.toISOString() })));
  } catch (err) {
    logger.error({ err }, "featured products error");
    return res.status(500).json({ error: "Internal server error" });
  }
});

router.get("/products/:id", async (req, res) => {
  try {
    const id = parseInt(req.params.id);
    if (isNaN(id)) return res.status(404).json({ error: "Not found" });
    const [p] = await db
      .select({
        id: storeProductsTable.id,
        slug: storeProductsTable.slug,
        name: storeProductsTable.name,
        description: storeProductsTable.description,
        imageUrl: storeProductsTable.imageUrl,
        price: storeProductsTable.price,
        categoryId: storeProductsTable.categoryId,
        categorySlug: storeCategoriesTable.slug,
        blueprint: storeProductsTable.blueprint,
        quantity: storeProductsTable.quantity,
        quality: storeProductsTable.quality,
        forceBlueprint: storeProductsTable.forceBlueprint,
        isFeatured: storeProductsTable.isFeatured,
        isActive: storeProductsTable.isActive,
        createdAt: storeProductsTable.createdAt,
      })
      .from(storeProductsTable)
      .leftJoin(storeCategoriesTable, eq(storeCategoriesTable.id, storeProductsTable.categoryId))
      .where(and(eq(storeProductsTable.id, id), eq(storeProductsTable.isActive, true)));
    if (!p) return res.status(404).json({ error: "Not found" });
    return res.json({ ...p, createdAt: p.createdAt.toISOString() });
  } catch (err) {
    logger.error({ err }, "get product error");
    return res.status(500).json({ error: "Internal server error" });
  }
});

export default router;
