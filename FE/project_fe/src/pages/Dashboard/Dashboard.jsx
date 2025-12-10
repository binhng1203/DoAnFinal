import Card from "../../components/ui/Card";
import Button from "../../components/ui/Button";
import TextInput from "../../components/ui/TextInput";
import { useState } from "react";

export default function HomePage() {
  const [name, setName] = useState("");

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold text-slate-800">
        Dashboard
      </h1>
    </div>
  );
}
