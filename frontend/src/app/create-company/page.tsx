"use client";

import { useState } from "react";
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

const CreateCompanyPage = () => {
  const [name, setName] = useState("");
  const [businessType, setBusinessType] = useState("");
  const [description, setDescription] = useState("");
  const [website, setWebsite] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const accessToken = localStorage.getItem("access_token");
      if (!accessToken) {
        setError("You are not logged in");
        router.push("/signin");
        return;
      }

      const res = await fetch("http://localhost:5000/api/companies", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken}`,
        },
        body: JSON.stringify({
          name,
          business_type: businessType,
          description,
          website,
        }),
      });

      if (res.ok) {
        router.push("/");
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
    <div className="flex items-center justify-center min-h-screen bg-gray-100">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Create Company</CardTitle>
          <CardDescription>
            Tell us about your company to get started.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit}>
            <div className="grid w-full items-center gap-4">
              <div className="flex flex-col space-y-1.5">
                <Label htmlFor="name">Company Name</Label>
                <Input
                  id="name"
                  placeholder="Acme Inc."
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                />
              </div>
              <div className="flex flex-col space-y-1.5">
                <Label htmlFor="business-type">Business Type</Label>
                <Input
                  id="business-type"
                  placeholder="e.g., SaaS, E-commerce"
                  value={businessType}
                  onChange={(e) => setBusinessType(e.target.value)}
                  required
                />
              </div>
              <div className="flex flex-col space-y-1.5">
                <Label htmlFor="description">Description</Label>
                <Textarea
                  id="description"
                  placeholder="What does your company do?"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                />
              </div>
              <div className="flex flex-col space-y-1.5">
                <Label htmlFor="website">Website (optional)</Label>
                <Input
                  id="website"
                  placeholder="https://acme.com"
                  value={website}
                  onChange={(e) => setWebsite(e.target.value)}
                />
              </div>
              {error && <p className="text-red-500 text-sm">{error}</p>}
            </div>
            <Button type="submit" className="w-full mt-6" disabled={loading}>
              {loading ? "Creating..." : "Create Company"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
};

export default CreateCompanyPage;
