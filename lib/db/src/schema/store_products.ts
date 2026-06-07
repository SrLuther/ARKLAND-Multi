import {
  pgTable, serial, text, integer, boolean, real, timestamp,
} from "drizzle-orm/pg-core";
import { createInsertSchema } from "drizzle-zod";
import { z } from "zod/v4";

export const storeProductsTable = pgTable("store_products", {
  id: serial("id").primaryKey(),
  slug: text("slug").notNull().unique(),
  name: text("name").notNull(),
  description: text("description"),
  imageUrl: text("image_url"),
  price: integer("price").notNull().default(0),
  categoryId: integer("category_id"),
  blueprint: text("blueprint"),
  quantity: integer("quantity").notNull().default(1),
  quality: real("quality").notNull().default(0),
  forceBlueprint: boolean("force_blueprint").notNull().default(false),
  isFeatured: boolean("is_featured").notNull().default(false),
  isActive: boolean("is_active").notNull().default(true),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow().$onUpdate(() => new Date()),
});

export const insertStoreProductSchema = createInsertSchema(storeProductsTable).omit({
  id: true,
  createdAt: true,
  updatedAt: true,
});
export type InsertStoreProduct = z.infer<typeof insertStoreProductSchema>;
export type StoreProduct = typeof storeProductsTable.$inferSelect;
