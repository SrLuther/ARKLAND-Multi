import { useParams, Link } from "wouter";
import { useGetProduct, useGetMe, useCreateOrder } from "@workspace/api-client-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Image as ImageIcon, ArrowLeft, ShieldCheck, ShoppingCart, LogIn } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { useState } from "react";

export default function ProductDetail() {
  const { id } = useParams<{ id: string }>();
  const productId = parseInt(id || "0");
  const { toast } = useToast();
  
  const { data: product, isLoading, error } = useGetProduct(productId);
  const { data: user } = useGetMe();
  const createOrder = useCreateOrder();
  
  const [quantity, setQuantity] = useState(1);

  const handleBuy = () => {
    if (!user?.authenticated) return;
    
    createOrder.mutate({ data: { productId, quantity } }, {
      onSuccess: (data) => {
        toast({
          title: "Pedido realizado!",
          description: data.usePoints 
            ? "O produto foi pago com pontos." 
            : "Redirecionando para o pagamento...",
        });
        
        if (data.paymentUrl && !data.usePoints) {
          window.location.href = data.paymentUrl;
        } else {
          // If paid with points, maybe redirect to orders
          window.location.href = "/store/orders";
        }
      },
      onError: (err: any) => {
        toast({
          title: "Erro ao realizar pedido",
          description: err.message || "Tente novamente mais tarde.",
          variant: "destructive"
        });
      }
    });
  };

  if (isLoading) {
    return (
      <div className="container mx-auto px-4 py-8 max-w-5xl">
        <Skeleton className="h-8 w-32 mb-6" />
        <div className="grid md:grid-cols-2 gap-8">
          <Skeleton className="aspect-square w-full rounded-xl" />
          <div className="space-y-6">
            <Skeleton className="h-10 w-3/4" />
            <Skeleton className="h-6 w-1/4" />
            <Skeleton className="h-32 w-full" />
            <Skeleton className="h-12 w-full mt-8" />
          </div>
        </div>
      </div>
    );
  }

  if (error || !product) {
    return (
      <div className="container mx-auto px-4 py-20 text-center">
        <h2 className="text-2xl font-bold text-foreground mb-4">Produto não encontrado</h2>
        <Button asChild><Link href="/shop">Voltar para a Loja</Link></Button>
      </div>
    );
  }

  const canAfford = user?.authenticated && (user.points >= product.price * quantity);

  return (
    <div className="container mx-auto px-4 py-8 max-w-5xl">
      <Button asChild variant="ghost" className="mb-6 text-muted-foreground hover:text-foreground">
        <Link href="/shop"><ArrowLeft className="w-4 h-4 mr-2" /> Voltar para a Loja</Link>
      </Button>

      <div className="grid md:grid-cols-2 gap-8 lg:gap-12">
        {/* Product Image */}
        <div className="bg-card border border-border rounded-xl aspect-square flex items-center justify-center overflow-hidden relative">
          {product.imageUrl ? (
            <img src={product.imageUrl} alt={product.name} className="object-cover w-full h-full" loading="lazy" decoding="async" />
          ) : (
            <ImageIcon className="w-24 h-24 text-muted-foreground/30" />
          )}
          {product.categorySlug && (
             <div className="absolute top-4 left-4 bg-background/80 backdrop-blur px-3 py-1.5 rounded-full border border-border/50 text-sm font-medium">
               {product.categorySlug}
             </div>
          )}
        </div>

        {/* Product Info */}
        <div className="flex flex-col">
          <h1 className="text-3xl md:text-4xl font-bold text-foreground tracking-tight mb-2">{product.name}</h1>
          
          <div className="text-4xl font-extrabold text-primary mb-6 flex items-baseline gap-2">
            {product.price} <span className="text-lg font-medium text-muted-foreground">pontos</span>
          </div>
          
          <div className="prose dark:prose-invert max-w-none text-muted-foreground mb-8">
            <p>{product.description || "Nenhuma descrição disponível."}</p>
          </div>
          
          <div className="grid grid-cols-2 gap-4 mb-8">
            <div className="bg-card border border-border p-4 rounded-lg flex flex-col">
              <span className="text-xs text-muted-foreground uppercase tracking-wider mb-1">Qualidade</span>
              <span className="font-bold text-foreground">{product.quality}%</span>
            </div>
            <div className="bg-card border border-border p-4 rounded-lg flex flex-col">
              <span className="text-xs text-muted-foreground uppercase tracking-wider mb-1">Quantidade In-game</span>
              <span className="font-bold text-foreground">{product.quantity}x</span>
            </div>
          </div>
          
          <div className="mt-auto space-y-4">
            <div className="flex items-center gap-4 bg-card border border-border p-4 rounded-lg">
              <ShieldCheck className="w-8 h-8 text-primary" />
              <div>
                <h4 className="font-bold text-sm">Entrega Automática</h4>
                <p className="text-xs text-muted-foreground">O item será entregue no seu inventário dentro do jogo.</p>
              </div>
            </div>

            {user?.authenticated ? (
              <div className="bg-card border border-border p-4 rounded-lg space-y-4">
                <div className="flex justify-between items-center text-sm">
                  <span className="text-muted-foreground">Seus pontos:</span>
                  <span className="font-bold">{user.points}</span>
                </div>
                
                <div className="flex gap-4">
                  <div className="w-24">
                    <label className="text-xs text-muted-foreground mb-1 block">Qtd.</label>
                    <div className="flex items-center border border-border rounded-md overflow-hidden bg-background">
                      <button 
                        onClick={() => setQuantity(Math.max(1, quantity - 1))}
                        className="px-2 py-1.5 hover:bg-muted text-muted-foreground transition-colors"
                      >-</button>
                      <div className="flex-1 text-center text-sm font-medium">{quantity}</div>
                      <button 
                        onClick={() => setQuantity(quantity + 1)}
                        className="px-2 py-1.5 hover:bg-muted text-muted-foreground transition-colors"
                      >+</button>
                    </div>
                  </div>
                  
                  <div className="flex-1 flex flex-col justify-end">
                    <Button 
                      size="lg" 
                      className="w-full" 
                      onClick={handleBuy}
                      disabled={createOrder.isPending || !product.isActive}
                    >
                      {createOrder.isPending ? "Processando..." : "Comprar Agora"}
                    </Button>
                  </div>
                </div>
                
                {!canAfford && (
                  <p className="text-xs text-destructive text-center mt-2">Você não tem pontos suficientes.</p>
                )}
              </div>
            ) : (
              <Button asChild size="lg" className="w-full h-14 text-lg">
                <a href="/api/auth/steam">
                  <LogIn className="w-5 h-5 mr-2" />
                  Entrar para Comprar
                </a>
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
