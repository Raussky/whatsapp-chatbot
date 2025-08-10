"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";
import { useRouter } from "next/navigation";

interface Subscription {
  id: string;
  plan: {
    name: string;
    price_monthly: number;
  };
  status: string;
  current_period_end: string;
}

interface Invoice {
  id: string;
  created_at: string;
  total: number;
  status: string;
  invoice_pdf: string;
}

const BillingPage = () => {
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    const fetchData = async () => {
      const token = localStorage.getItem("access_token");
      if (!token) {
        router.push("/signin");
        return;
      }

      try {
        const userRes = await fetch("http://localhost:5000/api/auth/me", {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!userRes.ok) throw new Error("Failed to fetch user");
        const userData = await userRes.json();

        if (userData.user.companies.length > 0) {
          const companyId = userData.user.companies[0].company.id;

          const subRes = await fetch(
            `http://localhost:5000/api/billing/current-subscription?company_id=${companyId}`,
            { headers: { Authorization: `Bearer ${token}` } }
          );
          if (subRes.ok) {
            const subData = await subRes.json();
            if (subData.subscriptions.length > 0) {
              setSubscription(subData.subscriptions[0]);
            }
          }

          const invoicesRes = await fetch(
            `http://localhost:5000/api/billing/invoices?company_id=${companyId}`,
            { headers: { Authorization: `Bearer ${token}` } }
          );
          if (invoicesRes.ok) {
            const invoicesData = await invoicesRes.json();
            setInvoices(invoicesData.invoices);
          }
        }
      } catch (error) {
        console.error(error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [router]);

  if (loading) {
    return <div>Loading...</div>;
  }

  return (
    <div>
      <h1 className="text-lg font-semibold md:text-2xl">Billing</h1>
      <div className="grid gap-6 mt-6">
        <Card>
          <CardHeader>
            <CardTitle>Subscription Plan</CardTitle>
            <CardDescription>
              Manage your subscription and billing details.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {subscription ? (
              <div>
                <p>
                  <strong>Current Plan:</strong> {subscription.plan.name}
                </p>
                <p>
                  <strong>Price:</strong> ${subscription.plan.price_monthly}/month
                </p>
                <p>
                  <strong>Status:</strong> {subscription.status}
                </p>
                <p>
                  <strong>Next payment:</strong>{" "}
                  {new Date(subscription.current_period_end).toLocaleDateString()}
                </p>
                <div className="mt-4">
                  <Button>Change Plan</Button>
                  <Button variant="destructive" className="ml-2">
                    Cancel Subscription
                  </Button>
                </div>
              </div>
            ) : (
              <p>No active subscription.</p>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Billing History</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Date</TableHead>
                  <TableHead>Amount</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Invoice</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {invoices.map((invoice) => (
                  <TableRow key={invoice.id}>
                    <TableCell>
                      {new Date(invoice.created_at).toLocaleDateString()}
                    </TableCell>
                    <TableCell>${invoice.total}</TableCell>
                    <TableCell>{invoice.status}</TableCell>
                    <TableCell>
                      <a
                        href={invoice.invoice_pdf}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        Download
                      </a>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default BillingPage;
