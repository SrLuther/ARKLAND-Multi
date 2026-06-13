import { useGetStoreStats, useListFeaturedProducts } from "@workspace/api-client-react";
import { Link } from "wouter";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { ShoppingCart, Package, CheckCircle, TrendingUp, Image as ImageIcon } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";

export default function Home() {
  const { data: stats, isLoading: statsLoading } = useGetStoreStats();
  const { data: featured, isLoading: featuredLoading } = useListFeaturedProducts();

  return (
    <div className="flex flex-col w-full">
      {/* Hero Section */}
      <section className="relative w-full h-[500px] flex items-center justify-center overflow-hidden border-b border-border bg-card">
        <div className="absolute inset-0 bg-gradient-to-r from-background to-background/50 z-10" />
        <div className="container relative z-20 px-4 flex flex-col md:flex-row items-center gap-10 max-w-5xl mx-auto">
          <img
            src={`${import.meta.env.BASE_URL}logo.png`}
            alt="ARKLAND Brasil"
            className="hidden md:block w-56 h-56 rounded-2xl object-cover shadow-2xl flex-shrink-0"
          />
          <div className="flex flex-col items-start text-center md:text-left">
          <h1 className="text-4xl md:text-6xl font-extrabold tracking-tight mb-4 text-foreground">
            Sobreviva. Domine. <span className="text-primary">Conquiste.</span>
          </h1>
          <p className="text-lg md:text-xl text-muted-foreground mb-8 max-w-2xl">
            A loja definitiva para itens, dinos, kits e ranks no ARKLAND. 
            Eleve sua gameplay para o próximo nível.
          </p>
          <div className="flex items-center gap-4">
            <Button asChild size="lg" className="h-12 px-8 text-base">
              <Link href="/shop">Explorar Loja</Link>
            </Button>
            <Button asChild variant="outline" size="lg" className="h-12 px-8 text-base">
              <Link href="/orders">Meus Pedidos</Link>
            </Button>
          </div>
          </div>
        </div>
      </section>

      {/* Stats Bar */}
      <section className="border-b border-border bg-card/50">
        <div className="container mx-auto px-4 py-8">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6 text-center">
            <div className="flex flex-col items-center justify-center space-y-2">
              <Package className="w-8 h-8 text-primary mb-2" />
              {statsLoading ? <Skeleton className="h-8 w-20" /> : <span className="text-3xl font-bold">{stats?.totalProducts}</span>}
              <span className="text-sm text-muted-foreground uppercase tracking-wider">Produtos</span>
            </div>
            <div className="flex flex-col items-center justify-center space-y-2">
              <ShoppingCart className="w-8 h-8 text-primary mb-2" />
              {statsLoading ? <Skeleton className="h-8 w-20" /> : <span className="text-3xl font-bold">{stats?.totalOrders}</span>}
              <span className="text-sm text-muted-foreground uppercase tracking-wider">Pedidos</span>
            </div>
            <div className="flex flex-col items-center justify-center space-y-2">
              <CheckCircle className="w-8 h-8 text-primary mb-2" />
              {statsLoading ? <Skeleton className="h-8 w-20" /> : <span className="text-3xl font-bold">{stats?.totalDelivered}</span>}
              <span className="text-sm text-muted-foreground uppercase tracking-wider">Entregas</span>
            </div>
            <div className="flex flex-col items-center justify-center space-y-2">
              <TrendingUp className="w-8 h-8 text-primary mb-2" />
              {statsLoading ? <Skeleton className="h-8 w-20" /> : <span className="text-3xl font-bold">{stats?.totalCategories}</span>}
              <span className="text-sm text-muted-foreground uppercase tracking-wider">Categorias</span>
            </div>
          </div>
        </div>
      </section>

      {/* Featured Products */}
      <section className="container mx-auto px-4 py-16">
        <h2 className="text-3xl font-bold mb-8 flex items-center gap-3">
          <span className="w-8 h-1 bg-primary inline-block rounded"></span>
          Destaques
        </h2>
        
        {featuredLoading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
            {[...Array(4)].map((_, i) => (
              <Card key={i} className="flex flex-col overflow-hidden">
                <Skeleton className="h-48 w-full rounded-none" />
                <CardHeader>
                  <Skeleton className="h-6 w-3/4 mb-2" />
                  <Skeleton className="h-4 w-1/2" />
                </CardHeader>
                <CardFooter className="mt-auto pt-6">
                  <Skeleton className="h-10 w-full" />
                </CardFooter>
              </Card>
            ))}
          </div>
        ) : featured?.length === 0 ? (
          <div className="text-center py-12 text-muted-foreground bg-card rounded-lg border border-border">
            Nenhum produto em destaque no momento.
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
            {featured?.map((product) => (
              <Card key={product.id} className="flex flex-col overflow-hidden group hover:border-primary/50 transition-colors">
                <div className="relative h-48 bg-muted flex items-center justify-center overflow-hidden">
                  {product.imageUrl ? (
                    <img src={product.imageUrl} alt={product.name} className="object-cover w-full h-full group-hover:scale-105 transition-transform duration-500" loading="lazy" decoding="async" />
                  ) : (
                    <ImageIcon className="w-12 h-12 text-muted-foreground/30" />
                  )}
                  <div className="absolute top-2 right-2 bg-primary text-primary-foreground text-xs font-bold px-2 py-1 rounded">
                    Destaque
                  </div>
                </div>
                <CardHeader>
                  <CardTitle className="line-clamp-1">{product.name}</CardTitle>
                  <div className="text-2xl font-bold text-primary mt-2">
                    {product.price} <span className="text-sm font-normal text-muted-foreground">pts</span>
                  </div>
                </CardHeader>
                <CardFooter className="mt-auto pt-4">
                  <Button asChild className="w-full">
                    <Link href={`/product/${product.id}`}>Ver Detalhes</Link>
                  </Button>
                </CardFooter>
              </Card>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
