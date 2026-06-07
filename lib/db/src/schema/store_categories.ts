import { pgTable, serial, text, integer, timestamp } from "drizzle-orm/pg-core";
import { createInsertSchema } from "drizzle-zod";
import { z } from "zod/v4";

export const storeCategoriesTable = pgTable("store_categories", {
  id: serial("id").primaryKey(),
  slug: text("slug").notNull().unique(),
  name: text("name").notNull(),
  icon: text("icon"),
  sortOrder: integer("sort_order").notNull().default(0),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
});

export const insertStoreCategorySchema = createInsertSchema(storeCategoriesTable).omit({
  id: true,
  createdAt: true,
});
export type InsertStoreCategory = z.infer<typeof insertStoreCategorySchema>;
export type StoreCategory = typeof storeCategoriesTable.$inferSelect;
