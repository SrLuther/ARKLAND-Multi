import { useEffect, useState } from "react";
import { useListCategories, useListProducts } from "@workspace/api-client-react";
import { Link, useSearch } from "wouter";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { PackageSearch, Image as ImageIcon, Search } from "lucide-react";

export default function Shop() {
  const searchString = useSearch();
  const searchParams = new URLSearchParams(searchString);
  const initialCategory = searchParams.get("category") || undefined;
  
  const [category, setCategory] = useState<string | undefined>(initialCategory);
  const [search, setSearch] = useState(searchParams.get("search") || "");
  const [debouncedSearch, setDebouncedSearch] = useState(searchParams.get("search") || "");
  const [page, setPage] = useState(1);

  const { data: categories, isLoading: categoriesLoading } = useListCategories();
  const { data: productsData, isLoading: productsLoading } = useListProducts({
    category,
    search: debouncedSearch || undefined,
    page,
    limit: 12
  });

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebouncedSearch(search.trim());
      setPage(1);
    }, 250);
    return () => {
      window.clearTimeout(timer);
    };
  }, [search]);

  const handleCategoryClick = (slug?: string) => {
    setCategory(slug);
    setPage(1);
  };

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="flex flex-col md:flex-row gap-8">
        {/* Sidebar */}
        <aside className="w-full md:w-64 flex-shrink-0 space-y-6">
          <div className="bg-card border border-border rounded-lg p-4">
            <h3 className="font-bold text-lg mb-4 flex items-center gap-2">
              <PackageSearch className="w-5 h-5 text-primary" />
              Categorias
            </h3>
            {categoriesLoading ? (
              <div className="space-y-2">
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
              </div>
            ) : (
              <div className="space-y-1">
                <button
                  onClick={() => handleCategoryClick(undefined)}
                  className={`w-full text-left px-3 py-2 rounded-md text-sm transition-colors ${!category ? 'bg-primary text-primary-foreground font-medium' : 'hover:bg-muted text-muted-foreground hover:text-foreground'}`}
                >
                  Todas as Categorias
                </button>
                {categories?.map((cat) => (
                  <button
                    key={cat.id}
                    onClick={() => handleCategoryClick(cat.slug)}
                    className={`w-full text-left px-3 py-2 rounded-md text-sm flex justify-between items-center transition-colors ${category === cat.slug ? 'bg-primary text-primary-foreground font-medium' : 'hover:bg-muted text-muted-foreground hover:text-foreground'}`}
                  >
                    <span>{cat.name}</span>
                    <span className={`text-xs ${category === cat.slug ? 'text-primary-foreground/80' : 'text-muted-foreground/50'}`}>{cat.productCount}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </aside>

        {/* Main Content */}
        <div className="flex-1">
          {/* Search Bar */}
          <div className="mb-6 bg-card border border-border rounded-lg p-4 flex items-center justify-between gap-4">
            <h2 className="text-xl font-bold hidden sm:block">
              {category ? categories?.find(c => c.slug === category)?.name || "Categoria" : "Todos os Produtos"}
            </h2>
            <form onSubmit={(e) => e.preventDefault()} className="flex-1 max-w-md relative">
              <Input
                type="search"
                placeholder="Buscar produtos..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full pr-10"
              />
              <Button type="button" variant="ghost" size="icon" className="absolute right-0 top-0 h-full" onClick={() => { setDebouncedSearch(search.trim()); setPage(1); }}>
                <Search className="w-4 h-4 text-muted-foreground" />
              </Button>
            </form>
          </div>

          {/* Product Grid */}
          {productsLoading ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
              {[...Array(8)].map((_, i) => (
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
          ) : productsData?.items.length === 0 ? (
            <div className="text-center py-20 bg-card border border-border rounded-lg">
              <PackageSearch className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
              <h3 className="text-xl font-bold text-foreground mb-2">Nenhum produto encontrado</h3>
              <p className="text-muted-foreground mb-6">Tente ajustar seus filtros ou termo de busca.</p>
              <Button onClick={() => { setCategory(undefined); setSearch(""); setDebouncedSearch(""); }}>
                Limpar Filtros
              </Button>
            </div>
          ) : (
            <>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6 mb-8">
                {productsData?.items.map((product) => (
                  <Card key={product.id} className="flex flex-col overflow-hidden group hover:border-primary/50 transition-colors">
                    <div className="relative h-48 bg-muted flex items-center justify-center overflow-hidden">
                      {product.imageUrl ? (
                        <img src={product.imageUrl} alt={product.name} className="object-cover w-full h-full group-hover:scale-105 transition-transform duration-500" loading="lazy" decoding="async" />
                      ) : (
                        <ImageIcon className="w-12 h-12 text-muted-foreground/30" />
                      )}
                      {product.isFeatured && (
                         <div className="absolute top-2 right-2 bg-primary text-primary-foreground text-xs font-bold px-2 py-1 rounded">
                           Destaque
                         </div>
                      )}
                      {product.categorySlug && (
                        <div className="absolute bottom-2 left-2 bg-background/80 backdrop-blur text-foreground text-xs px-2 py-1 rounded border border-border/50">
                          {product.categorySlug}
                        </div>
                      )}
                    </div>
                    <CardHeader className="flex-1 pb-4">
                      <CardTitle className="line-clamp-1">{product.name}</CardTitle>
                      <div className="text-2xl font-bold text-primary mt-2">
                        {product.price} <span className="text-sm font-normal text-muted-foreground">pts</span>
                      </div>
                    </CardHeader>
                    <CardFooter className="pt-0">
                      <Button asChild className="w-full">
                        <Link href={`/product/${product.id}`}>Ver Detalhes</Link>
                      </Button>
                    </CardFooter>
                  </Card>
                ))}
              </div>

              {/* Pagination */}
              {productsData && productsData.totalPages > 1 && (
                <div className="flex justify-center gap-2">
                  <Button 
                    variant="outline" 
                    disabled={page === 1}
                    onClick={() => setPage(p => Math.max(1, p - 1))}
                  >
                    Anterior
                  </Button>
                  <div className="flex items-center px-4 font-medium text-sm">
                    Página {page} de {productsData.totalPages}
                  </div>
                  <Button 
                    variant="outline" 
                    disabled={page === productsData.totalPages}
                    onClick={() => setPage(p => Math.min(productsData.totalPages, p + 1))}
                  >
                    Próxima
                  </Button>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
