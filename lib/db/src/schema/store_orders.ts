import {
  pgTable, serial, text, integer, timestamp,
} from "drizzle-orm/pg-core";
import { createInsertSchema } from "drizzle-zod";
import { z } from "zod/v4";

export const orderStatusEnum = ["pending", "paid", "delivered", "failed", "refunded"] as const;
export type OrderStatus = typeof orderStatusEnum[number];

export const storeOrdersTable = pgTable("store_orders", {
  id: serial("id").primaryKey(),
  steamId: text("steam_id").notNull(),
  displayName: text("display_name"),
  productId: integer("product_id").notNull(),
  productName: text("product_name").notNull(),
  quantity: integer("quantity").notNull().default(1),
  pointsPaid: integer("points_paid").notNull(),
  status: text("status").$type<OrderStatus>().notNull().default("pending"),
  paymentId: text("payment_id"),
  paymentUrl: text("payment_url"),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow().$onUpdate(() => new Date()),
});

export const insertStoreOrderSchema = createInsertSchema(storeOrdersTable).omit({
  id: true,
  createdAt: true,
  updatedAt: true,
});
export type InsertStoreOrder = z.infer<typeof insertStoreOrderSchema>;
export type StoreOrder = typeof storeOrdersTable.$inferSelect;
