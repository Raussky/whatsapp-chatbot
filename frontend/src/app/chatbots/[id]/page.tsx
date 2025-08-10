"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useRouter, useParams } from "next/navigation";

interface Chatbot {
  name: string;
  description: string;
  welcome_message: string;
  fallback_message: string;
}

const EditChatbotPage = () => {
  const [chatbot, setChatbot] = useState<Chatbot | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [welcomeMessage, setWelcomeMessage] = useState("");
  const [fallbackMessage, setFallbackMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();
  const params = useParams();
  const { id: chatbotId } = params;

  useEffect(() => {
    const fetchChatbot = async () => {
      const token = localStorage.getItem("access_token");
      if (!token) {
        router.push("/signin");
        return;
      }

      try {
        const res = await fetch(`http://localhost:5000/api/chatbots/${chatbotId}`, {
          headers: { Authorization: `Bearer ${token}` },
        });

        if (res.ok) {
          const data = await res.json();
          setChatbot(data.chatbot);
          setName(data.chatbot.name);
          setDescription(data.chatbot.description);
          setWelcomeMessage(data.chatbot.welcome_message);
          setFallbackMessage(data.chatbot.fallback_message);
        } else {
          router.push("/chatbots");
        }
      } catch (error) {
        router.push("/chatbots");
      }
    };

    if (chatbotId) {
      fetchChatbot();
    }
  }, [chatbotId, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    const token = localStorage.getItem("access_token");

    try {
      const res = await fetch(`http://localhost:5000/api/chatbots/${chatbotId}`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          name,
          description,
          welcome_message: welcomeMessage,
          fallback_message: fallbackMessage,
        }),
      });

      if (res.ok) {
        router.push("/chatbots");
      } else {
        const data = await res.json();
        setError(data.error || "Something went wrong");
      }
    } catch (error) {
      setError("Something went wrong");
    } finally {
      setLoading(false);
    }
  };

  if (!chatbot) {
    return <div>Loading...</div>;
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Edit Chatbot</CardTitle>
        <CardDescription>
          Update the details of your chatbot.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit}>
          <div className="grid w-full items-center gap-4">
            <div className="flex flex-col space-y-1.5">
              <Label htmlFor="name">Name</Label>
              <Input
                id="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
              />
            </div>
            <div className="flex flex-col space-y-1.5">
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </div>
            <div className="flex flex-col space-y-1.5">
              <Label htmlFor="welcome-message">Welcome Message</Label>
              <Textarea
                id="welcome-message"
                value={welcomeMessage}
                onChange={(e) => setWelcomeMessage(e.target.value)}
              />
            </div>
            <div className="flex flex-col space-y-1.5">
              <Label htmlFor="fallback-message">Fallback Message</Label>
              <Textarea
                id="fallback-message"
                value={fallbackMessage}
                onChange={(e) => setFallbackMessage(e.target.value)}
              />
            </div>
            {error && <p className="text-red-500 text-sm">{error}</p>}
          </div>
          <Button type="submit" className="w-full mt-6" disabled={loading}>
            {loading ? "Saving..." : "Save Changes"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
};

export default EditChatbotPage;
