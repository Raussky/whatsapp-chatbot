"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface Chatbot {
  id: string;
  name: string;
}

interface Conversation {
  id: string;
  customer_phone: string;
  status: string;
  last_message_at: string;
}

interface Message {
  id: string;
  content: string;
  direction: "inbound" | "outbound";
  timestamp: string;
}

interface SelectedConversation extends Conversation {
  messages: Message[];
}

const ConversationsPage = () => {
  const [chatbots, setChatbots] = useState<Chatbot[]>([]);
  const [selectedChatbotId, setSelectedChatbotId] = useState<string | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selectedConversation, setSelectedConversation] =
    useState<SelectedConversation | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    const fetchChatbots = async () => {
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
          const chatbotsRes = await fetch(
            `http://localhost:5000/api/chatbots?company_id=${companyId}`,
            { headers: { Authorization: `Bearer ${token}` } }
          );
          if (!chatbotsRes.ok) throw new Error("Failed to fetch chatbots");
          const chatbotsData = await chatbotsRes.json();
          setChatbots(chatbotsData.chatbots);
          if (chatbotsData.chatbots.length > 0) {
            setSelectedChatbotId(chatbotsData.chatbots[0].id);
          }
        }
      } catch (error) {
        console.error(error);
        router.push("/signin");
      } finally {
        setLoading(false);
      }
    };
    fetchChatbots();
  }, [router]);

  useEffect(() => {
    if (!selectedChatbotId) return;

    const fetchConversations = async () => {
      const token = localStorage.getItem("access_token");
      try {
        const res = await fetch(
          `http://localhost:5000/api/chatbots/${selectedChatbotId}/conversations`,
          { headers: { Authorization: `Bearer ${token}` } }
        );
        if (res.ok) {
          const data = await res.json();
          setConversations(data.conversations);
        }
      } catch (error) {
        console.error(error);
      }
    };
    fetchConversations();
  }, [selectedChatbotId]);

  const handleConversationClick = async (conversationId: string) => {
    const token = localStorage.getItem("access_token");
    try {
      const res = await fetch(
        `http://localhost:5000/api/conversations/${conversationId}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (res.ok) {
        const data = await res.json();
        setSelectedConversation(data.conversation);
      }
    } catch (error) {
      console.error(error);
    }
  };

  if (loading) {
    return <div>Loading...</div>;
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      <div className="md:col-span-1">
        <Card>
          <CardHeader>
            <CardTitle>Conversations</CardTitle>
          </CardHeader>
          <CardContent>
            <Select onValueChange={setSelectedChatbotId} value={selectedChatbotId || ""}>
              <SelectTrigger>
                <SelectValue placeholder="Select a chatbot" />
              </SelectTrigger>
              <SelectContent>
                {chatbots.map((bot) => (
                  <SelectItem key={bot.id} value={bot.id}>
                    {bot.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <div className="mt-4 space-y-2">
              {conversations.map((conv) => (
                <div
                  key={conv.id}
                  className="p-2 border rounded-md cursor-pointer hover:bg-muted"
                  onClick={() => handleConversationClick(conv.id)}
                >
                  <p className="font-semibold">{conv.customer_phone}</p>
                  <p className="text-sm text-muted-foreground">
                    Last message: {new Date(conv.last_message_at).toLocaleString()}
                  </p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
      <div className="md:col-span-2">
        <Card>
          <CardHeader>
            <CardTitle>Messages</CardTitle>
          </CardHeader>
          <CardContent>
            {selectedConversation ? (
              <div className="space-y-4">
                {selectedConversation.messages.map((msg) => (
                  <div
                    key={msg.id}
                    className={`flex ${
                      msg.direction === "outbound" ? "justify-end" : "justify-start"
                    }`}
                  >
                    <div
                      className={`p-3 rounded-lg max-w-xs ${
                        msg.direction === "outbound"
                          ? "bg-primary text-primary-foreground"
                          : "bg-muted"
                      }`}
                    >
                      <p>{msg.content}</p>
                      <p className="text-xs text-right mt-1">
                        {new Date(msg.timestamp).toLocaleTimeString()}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p>Select a conversation to view messages.</p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default ConversationsPage;
