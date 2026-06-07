export default function Footer() {
  return (
    <footer className="border-t border-border py-8 mt-12 bg-card">
      <div className="container mx-auto px-4 text-center">
        <img
          src={`${import.meta.env.BASE_URL}logo.png`}
          alt="ARKLAND Brasil"
          className="h-20 w-20 rounded-xl object-cover mx-auto mb-3"
        />
        <h3 className="font-bold text-lg text-foreground mb-2">ARKLAND Store</h3>
        <p className="text-sm text-muted-foreground">
          Sua loja definitiva de itens, dinos e kits para ARK: Survival Evolved.
        </p>
        <p className="text-xs text-muted-foreground mt-6">
          &copy; {new Date().getFullYear()} ARKLAND. Todos os direitos reservados.
        </p>
      </div>
    </footer>
  );
}
