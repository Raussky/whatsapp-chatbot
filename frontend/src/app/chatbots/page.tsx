"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";
import { PlusCircle, MoreHorizontal } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useRouter } from "next/navigation";

interface Chatbot {
  id: string;
  name: string;
  status: string;
  total_conversations: number;
}

interface Company {
  id: string;
  name: string;
}

interface User {
  companies: { company: Company }[];
}

const ChatbotsPage = () => {
  const [user, setUser] = useState<User | null>(null);
  const [chatbots, setChatbots] = useState<Chatbot[]>([]);
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
        setUser(userData.user);

        if (userData.user.companies.length > 0) {
          const companyId = userData.user.companies[0].company.id;
          const chatbotsRes = await fetch(
            `http://localhost:5000/api/chatbots?company_id=${companyId}`,
            {
              headers: { Authorization: `Bearer ${token}` },
            }
          );

          if (!chatbotsRes.ok) throw new Error("Failed to fetch chatbots");
          const chatbotsData = await chatbotsRes.json();
          setChatbots(chatbotsData.chatbots);
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

  const handleDelete = async (chatbotId: string) => {
    if (!confirm("Are you sure you want to delete this chatbot?")) return;

    const token = localStorage.getItem("access_token");
    try {
      const res = await fetch(`http://localhost:5000/api/chatbots/${chatbotId}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });

      if (res.ok) {
        setChatbots(chatbots.filter((c) => c.id !== chatbotId));
      } else {
        alert("Failed to delete chatbot");
      }
    } catch (error) {
      alert("Failed to delete chatbot");
    }
  };

  if (loading) {
    return <div>Loading...</div>;
  }

  return (
    <div>
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold md:text-2xl">Chatbots</h1>
        <Button onClick={() => router.push("/chatbots/new")}>
          <PlusCircle className="mr-2 h-4 w-4" /> Create new Chatbot
        </Button>
      </div>
      <div className="mt-6">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Conversations</TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {chatbots.map((chatbot) => (
              <TableRow key={chatbot.id}>
                <TableCell>{chatbot.name}</TableCell>
                <TableCell>{chatbot.status}</TableCell>
                <TableCell>{chatbot.total_conversations}</TableCell>
                <TableCell>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" className="h-8 w-8 p-0">
                        <span className="sr-only">Open menu</span>
                        <MoreHorizontal className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem
                        onClick={() => router.push(`/chatbots/${chatbot.id}`)}
                      >
                        Edit
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => handleDelete(chatbot.id)}>
                        Delete
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
};

export default ChatbotsPage;
