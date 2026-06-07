import { Router, type IRouter } from "express";
import healthRouter from "./health";
import authRouter from "./store/auth";
import categoriesRouter from "./store/categories";
import productsRouter from "./store/products";
import ordersRouter from "./store/orders";
import adminRouter from "./store/admin";
import statsRouter from "./store/stats";

const router: IRouter = Router();

router.use(healthRouter);
router.use(authRouter);
router.use(categoriesRouter);
router.use(productsRouter);
router.use(ordersRouter);
router.use(adminRouter);
router.use(statsRouter);

export default router;
