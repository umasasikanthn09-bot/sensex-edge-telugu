"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function LoginPage() {

  const router = useRouter();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const handleLogin = () => {

    if (
      username === "admin" &&
      password === "baba@123"
    ) {

      localStorage.setItem("adminLogin", "true");

      router.push("/admin");

    } else {

      alert("❌ Invalid Username or Password");

    }

  };


  return (
    <main className="min-h-screen bg-black text-white flex items-center justify-center">

      <div className="bg-gray-900 border border-yellow-500 rounded-2xl p-8 w-full max-w-md">

        <h1 className="text-3xl text-yellow-400 font-bold text-center mb-6">
          Admin Login
        </h1>


        <input
          type="text"
          placeholder="Username"
          className="w-full p-3 mb-4 rounded bg-black border border-gray-600"
          value={username}
          onChange={(e)=>setUsername(e.target.value)}
        />


        <input
          type="password"
          placeholder="Password"
          className="w-full p-3 mb-6 rounded bg-black border border-gray-600"
          value={password}
          onChange={(e)=>setPassword(e.target.value)}
        />


        <button
          onClick={handleLogin}
          className="w-full bg-yellow-400 text-black font-bold py-3 rounded-xl"
        >
          Login
        </button>


      </div>

    </main>
  );
}