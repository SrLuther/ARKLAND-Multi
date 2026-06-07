import { useState } from "react";
import { useGetMe, useAdminListProducts, useAdminListOrders, useAdminUpdateOrder, useAdminUpdateProduct } from "@workspace/api-client-react";
import { Redirect } from "wouter";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useToast } from "@/hooks/use-toast";

export default function Admin() {
  const { data: user, isLoading: userLoading } = useGetMe();
  const [productPage, setProductPage] = useState(1);
  const [orderPage, setOrderPage] = useState(1);
  
  const { data: productsData, refetch: refetchProducts } = useAdminListProducts({ page: productPage });
  const { data: ordersData, refetch: refetchOrders } = useAdminListOrders({ page: orderPage });
  
  const updateOrder = useAdminUpdateOrder();
  const updateProduct = useAdminUpdateProduct();
  const { toast } = useToast();

  if (userLoading) return null;
  if (!user?.authenticated || !user?.isAdmin) {
    return <Redirect to="/" />;
  }

  const handleOrderStatusChange = (id: number, status: string) => {
    updateOrder.mutate({ id, data: { status: status as any } }, {
      onSuccess: () => {
        toast({ title: "Status atualizado" });
        refetchOrders();
      }
    });
  };

  const handleToggleProductActive = (id: number, currentStatus: boolean, data: any) => {
     updateProduct.mutate({ id, data: { ...data, isActive: !currentStatus } }, {
      onSuccess: () => {
        toast({ title: "Produto atualizado" });
        refetchProducts();
      }
     });
  };

  return (
    <div className="container mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold mb-8">Painel Admin</h1>

      <Tabs defaultValue="products">
        <TabsList className="mb-8">
          <TabsTrigger value="products">Produtos</TabsTrigger>
          <TabsTrigger value="orders">Pedidos</TabsTrigger>
        </TabsList>

        <TabsContent value="products">
          <Card>
            <CardHeader>
              <CardTitle>Gerenciar Produtos</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>ID</TableHead>
                      <TableHead>Nome</TableHead>
                      <TableHead>Preço</TableHead>
                      <TableHead>Categoria</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Ação</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {productsData?.items.map(p => (
                      <TableRow key={p.id}>
                        <TableCell>#{p.id}</TableCell>
                        <TableCell>{p.name}</TableCell>
                        <TableCell>{p.price}</TableCell>
                        <TableCell>{p.categorySlug || '-'}</TableCell>
                        <TableCell>
                          <Badge variant={p.isActive ? "default" : "secondary"}>
                            {p.isActive ? "Ativo" : "Inativo"}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <Button 
                            variant="outline" 
                            size="sm"
                            onClick={() => handleToggleProductActive(p.id, p.isActive, p)}
                          >
                            {p.isActive ? "Desativar" : "Ativar"}
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="orders">
          <Card>
            <CardHeader>
              <CardTitle>Gerenciar Pedidos</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>ID</TableHead>
                      <TableHead>Usuário</TableHead>
                      <TableHead>Produto</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Ação</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {ordersData?.items.map(o => (
                      <TableRow key={o.id}>
                        <TableCell>#{o.id}</TableCell>
                        <TableCell>{o.displayName || o.steamId}</TableCell>
                        <TableCell>{o.productName} (x{o.quantity})</TableCell>
                        <TableCell>
                          <Badge variant="outline">{o.status}</Badge>
                        </TableCell>
                        <TableCell>
                          <Select 
                            value={o.status} 
                            onValueChange={(val) => handleOrderStatusChange(o.id, val)}
                          >
                            <SelectTrigger className="w-32">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="pending">Pendente</SelectItem>
                              <SelectItem value="paid">Pago</SelectItem>
                              <SelectItem value="delivered">Entregue</SelectItem>
                              <SelectItem value="failed">Falhou</SelectItem>
                              <SelectItem value="refunded">Reembolsado</SelectItem>
                            </SelectContent>
                          </Select>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
