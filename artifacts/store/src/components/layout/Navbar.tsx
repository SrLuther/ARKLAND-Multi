import { Link } from "wouter";
import { useGetMe, useLogout } from "@workspace/api-client-react";
import { Button } from "@/components/ui/button";
import { ShoppingCart, LogOut, PackageSearch, ShieldAlert, User, LogIn, LayoutDashboard } from "lucide-react";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";

export default function Navbar() {
  const { data: user } = useGetMe();
  const logout = useLogout();

  return (
    <header className="sticky top-0 z-50 w-full border-b border-border/40 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container mx-auto px-4 h-16 flex items-center justify-between">
        <div className="flex items-center gap-6">
          <Link href="/" className="flex items-center gap-2">
            <img
              src={`${import.meta.env.BASE_URL}logo.png`}
              alt="ARKLAND Brasil"
              className="h-10 w-10 rounded-lg object-cover"
            />
            <span className="font-bold text-xl tracking-tight text-primary">ARKLAND</span>
          </Link>
          <nav className="hidden md:flex items-center gap-6 text-sm font-medium text-muted-foreground">
            <Link href="/shop" className="hover:text-primary transition-colors flex items-center gap-2">
              <PackageSearch className="w-4 h-4" />
              Loja
            </Link>
            {user?.authenticated && (
              <Link href="/orders" className="hover:text-primary transition-colors flex items-center gap-2">
                <ShoppingCart className="w-4 h-4" />
                Meus Pedidos
              </Link>
            )}
            {user?.authenticated && user?.isAdmin && (
              <Link href="/admin" className="hover:text-primary transition-colors flex items-center gap-2">
                <ShieldAlert className="w-4 h-4" />
                Admin
              </Link>
            )}
          </nav>
        </div>

        <div className="flex items-center gap-4">
          {user?.authenticated ? (
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2 text-sm">
                <span className="text-muted-foreground hidden sm:inline-block">Pontos:</span>
                <span className="font-bold text-primary">{user.points}</span>
              </div>
              <div className="h-6 w-px bg-border hidden sm:block" />
              <div className="flex items-center gap-3">
                <Avatar className="w-8 h-8 border border-border">
                  <AvatarImage src={user.avatarUrl || ""} />
                  <AvatarFallback><User className="w-4 h-4" /></AvatarFallback>
                </Avatar>
                <span className="text-sm font-medium hidden sm:inline-block">{user.displayName}</span>
              </div>
              <Button variant="ghost" size="icon" onClick={() => logout.mutate(undefined, { onSuccess: () => window.location.reload() })}>
                <LogOut className="w-4 h-4" />
              </Button>
            </div>
          ) : (
            <Button asChild variant="default" className="gap-2">
              <a href="/api/auth/steam">
                <LogIn className="w-4 h-4" />
                Entrar com Steam
              </a>
            </Button>
          )}
        </div>
      </div>
    </header>
  );
}
