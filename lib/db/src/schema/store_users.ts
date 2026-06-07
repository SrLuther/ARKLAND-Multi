import { pgTable, text, integer, boolean, timestamp } from "drizzle-orm/pg-core";
import { createInsertSchema } from "drizzle-zod";
import { z } from "zod/v4";

export const storeUsersTable = pgTable("store_users", {
  steamId: text("steam_id").primaryKey(),
  displayName: text("display_name"),
  avatarUrl: text("avatar_url"),
  isAdmin: boolean("is_admin").notNull().default(false),
  points: integer("points").notNull().default(0),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow().$onUpdate(() => new Date()),
});

export const insertStoreUserSchema = createInsertSchema(storeUsersTable).omit({
  createdAt: true,
  updatedAt: true,
});
export type InsertStoreUser = z.infer<typeof insertStoreUserSchema>;
export type StoreUser = typeof storeUsersTable.$inferSelect;
