import { useListMyOrders } from "@workspace/api-client-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { format } from "date-fns";
import { ptBR } from "date-fns/locale";

export default function Orders() {
  const { data: orders, isLoading } = useListMyOrders();

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'delivered': return "bg-emerald-500/10 text-emerald-500 border-emerald-500/20";
      case 'paid': return "bg-blue-500/10 text-blue-500 border-blue-500/20";
      case 'pending': return "bg-yellow-500/10 text-yellow-500 border-yellow-500/20";
      case 'failed': return "bg-red-500/10 text-red-500 border-red-500/20";
      case 'refunded': return "bg-gray-500/10 text-gray-500 border-gray-500/20";
      default: return "bg-secondary text-secondary-foreground";
    }
  };

  const getStatusLabel = (status: string) => {
    switch (status) {
      case 'delivered': return "Entregue";
      case 'paid': return "Pago (Aguardando Entrega)";
      case 'pending': return "Pendente";
      case 'failed': return "Falhou";
      case 'refunded': return "Reembolsado";
      default: return status;
    }
  };

  return (
    <div className="container mx-auto px-4 py-8 max-w-5xl">
      <h1 className="text-3xl font-bold mb-8">Meus Pedidos</h1>

      <Card>
        <CardHeader>
          <CardTitle>Histórico de Compras</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-4">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : !orders || orders.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              Você ainda não realizou nenhum pedido.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>ID</TableHead>
                    <TableHead>Produto</TableHead>
                    <TableHead>Data</TableHead>
                    <TableHead className="text-right">Valor</TableHead>
                    <TableHead className="text-center">Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {orders.map((order) => (
                    <TableRow key={order.id}>
                      <TableCell className="font-medium">#{order.id}</TableCell>
                      <TableCell>{order.productName} (x{order.quantity})</TableCell>
                      <TableCell>{format(new Date(order.createdAt), "dd/MM/yyyy HH:mm", { locale: ptBR })}</TableCell>
                      <TableCell className="text-right font-bold text-primary">{order.pointsPaid} pts</TableCell>
                      <TableCell className="text-center">
                        <Badge variant="outline" className={getStatusColor(order.status)}>
                          {getStatusLabel(order.status)}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
