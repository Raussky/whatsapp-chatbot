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
import { useRouter } from "next/navigation";

interface Company {
  id: string;
  name: string;
}

interface User {
  companies: { company: Company }[];
}

const NewChatbotPage = () => {
  const [user, setUser] = useState<User | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [welcomeMessage, setWelcomeMessage] = useState("");
  const [fallbackMessage, setFallbackMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  useEffect(() => {
    const fetchUser = async () => {
      const token = localStorage.getItem("access_token");
      if (!token) {
        router.push("/signin");
        return;
      }
      try {
        const res = await fetch("http://localhost:5000/api/auth/me", {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok) {
          const data = await res.json();
          setUser(data.user);
        } else {
          router.push("/signin");
        }
      } catch (error) {
        router.push("/signin");
      }
    };
    fetchUser();
  }, [router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    if (!user || user.companies.length === 0) {
      setError("No company found. Please create a company first.");
      setLoading(false);
      return;
    }

    const companyId = user.companies[0].company.id;
    const token = localStorage.getItem("access_token");

    try {
      const res = await fetch("http://localhost:5000/api/chatbots", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          company_id: companyId,
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

  return (
    <Card>
      <CardHeader>
        <CardTitle>Create new Chatbot</CardTitle>
        <CardDescription>
          Fill in the details to create a new chatbot.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit}>
          <div className="grid w-full items-center gap-4">
            <div className="flex flex-col space-y-1.5">
              <Label htmlFor="name">Name</Label>
              <Input
                id="name"
                placeholder="My new chatbot"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
              />
            </div>
            <div className="flex flex-col space-y-1.5">
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                placeholder="What is this chatbot about?"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </div>
            <div className="flex flex-col space-y-1.5">
              <Label htmlFor="welcome-message">Welcome Message</Label>
              <Textarea
                id="welcome-message"
                placeholder="Hello! How can I help you today?"
                value={welcomeMessage}
                onChange={(e) => setWelcomeMessage(e.target.value)}
              />
            </div>
            <div className="flex flex-col space-y-1.5">
              <Label htmlFor="fallback-message">Fallback Message</Label>
              <Textarea
                id="fallback-message"
                placeholder="I'm sorry, I didn't understand that."
                value={fallbackMessage}
                onChange={(e) => setFallbackMessage(e.target.value)}
              />
            </div>
            {error && <p className="text-red-500 text-sm">{error}</p>}
          </div>
          <Button type="submit" className="w-full mt-6" disabled={loading}>
            {loading ? "Creating..." : "Create Chatbot"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
};

export default NewChatbotPage;
