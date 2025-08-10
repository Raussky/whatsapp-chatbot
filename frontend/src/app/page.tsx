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
import { PlusCircle } from "lucide-react";
import { useRouter } from "next/navigation";

interface Company {
  id: string;
  name: string;
}

interface User {
  companies: { company: Company }[];
}

interface CompanyStats {
  usage_stats: {
    chatbot_count: number;
    conversation_count: number;
    message_count: number;
  };
  subscription: {
    plan: {
      name: string;
    };
  };
}

const DashboardPage = () => {
  const [user, setUser] = useState<User | null>(null);
  const [stats, setStats] = useState<CompanyStats | null>(null);
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
        // Fetch user data
        const userRes = await fetch("http://localhost:5000/api/auth/me", {
          headers: { Authorization: `Bearer ${token}` },
        });

        if (!userRes.ok) throw new Error("Failed to fetch user");
        const userData = await userRes.json();
        setUser(userData.user);

        // Fetch company stats if there are companies
        if (userData.user.companies.length > 0) {
          const companyId = userData.user.companies[0].company.id;
          const statsRes = await fetch(
            `http://localhost:5000/api/companies/${companyId}/stats`,
            {
              headers: { Authorization: `Bearer ${token}` },
            }
          );

          if (!statsRes.ok) throw new Error("Failed to fetch stats");
          const statsData = await statsRes.json();
          setStats(statsData);
        }
      } catch (error) {
        console.error(error);
        router.push("/signin");
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
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold md:text-2xl">Dashboard</h1>
        <Button onClick={() => router.push("/chatbots/new")}>
          <PlusCircle className="mr-2 h-4 w-4" /> Create new Chatbot
        </Button>
      </div>
      {stats ? (
        <div className="grid gap-4 md:grid-cols-2 md:gap-8 lg:grid-cols-4 mt-6">
          <Card>
            <CardHeader>
              <CardTitle>Total Chatbots</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {stats.usage_stats.chatbot_count}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Total Conversations</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {stats.usage_stats.conversation_count}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Total Messages</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {stats.usage_stats.message_count}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Subscription Plan</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {stats.subscription?.plan.name || "No plan"}
              </div>
            </CardContent>
          </Card>
        </div>
      ) : (
        <div className="text-center py-10">
          <p>No company data available. Create a company to get started.</p>
        </div>
      )}
    </div>
  );
};

export default DashboardPage;
