"use client";

import { useState } from "react";
import { db } from "@/lib/firebase";
import { doc, setDoc } from "firebase/firestore";
export default function AdminPage() {
const [date, setDate] = useState("");
const [updatedTime, setUpdatedTime] = useState("");
const [sensexSpot, setSensexSpot] = useState("");
const clearForm = () => {
 const [formData, setFormData] = useState({
  date: "",
  updatedTime: "",
  sensexSpot: "",
  const saveLevels = async () => {
  try {
    await setDoc(doc(db, "premium", "today"), {
      date,
      updatedTime,
      sensexSpot,
    });

    alert("✅ Today's Levels Saved Successfully!");
  } catch (error) {
    console.error(error);
    alert("❌ Error Saving Data");
  }
};

  supportLevel: "",
  supportTarget1: "",
  supportTarget2: "",

  resistanceLevel: "",
  resistanceTarget1: "",
  resistanceTarget2: "",
});
const handleChange = (
  e: React.ChangeEvent<HTMLInputElement>
) => {
  setFormData({
    ...formData,
    [e.target.name]: e.target.value,
  });
};
  setDate("");
  setUpdatedTime("");
  setSensexSpot("");
}; 
return (
    <main className="min-h-screen bg-black text-white p-8">

      <h1 className="text-4xl font-black text-yellow-400 text-center mb-10">
        Sensex Edge Telugu - Admin Dashboard
      </h1>

      <div className="max-w-6xl mx-auto bg-gray-900 border border-yellow-500 rounded-2xl p-8">

        <h2 className="text-3xl font-bold text-yellow-400 mb-8">
          Today's Market Details
        </h2>

        <div className="grid md:grid-cols-3 gap-6">

          <div>
            <label className="block text-yellow-400 mb-2">
              Date
            </label>

            <input
  type="date"
  value={date}
  onChange={(e) => setDate(e.target.value)}
  className="w-full p-3 rounded-lg bg-black border border-gray-600"
/>
          </div>

          <div>
            <label className="block text-yellow-400 mb-2">
              Updated Time
            </label>

            <input
  type="time"
  value={updatedTime}
  onChange={(e) => setUpdatedTime(e.target.value)}
  className="w-full p-3 rounded-lg bg-black border border-gray-600"
/>
          </div>

          <div>
            <label className="block text-yellow-400 mb-2">
              Sensex Spot
            </label>

            <input
  type="text"
  placeholder="Enter Sensex Spot"
  value={sensexSpot}
  onChange={(e) => setSensexSpot(e.target.value)}
  className="w-full p-3 rounded-lg bg-black border border-gray-600"
/>
          </div>

        </div>

        <hr className="my-10 border-gray-700" />
                {/* Sensex Index Levels */}

        <h2 className="text-3xl font-bold text-yellow-400 mb-8">
          Sensex Index Levels
        </h2>

        <div className="grid md:grid-cols-2 gap-8">

          <div className="bg-black border border-green-500 rounded-xl p-6">

            <h3 className="text-2xl text-green-400 font-bold mb-5">
              Support Side
            </h3>

            <input
              type="text"
              placeholder="Support Level"
              className="w-full p-3 mb-4 rounded-lg bg-gray-900 border border-gray-600"
            />

            <input
              type="text"
              placeholder="Target 1"
              className="w-full p-3 mb-4 rounded-lg bg-gray-900 border border-gray-600"
            />

            <input
              type="text"
              placeholder="Target 2"
              className="w-full p-3 rounded-lg bg-gray-900 border border-gray-600"
            />

          </div>

          <div className="bg-black border border-red-500 rounded-xl p-6">

            <h3 className="text-2xl text-red-400 font-bold mb-5">
              Resistance Side
            </h3>

            <input
              type="text"
              placeholder="Resistance Level"
              className="w-full p-3 mb-4 rounded-lg bg-gray-900 border border-gray-600"
            />

            <input
              type="text"
              placeholder="Target 1"
              className="w-full p-3 mb-4 rounded-lg bg-gray-900 border border-gray-600"
            />

            <input
              type="text"
              placeholder="Target 2"
              className="w-full p-3 rounded-lg bg-gray-900 border border-gray-600"
            />

          </div>

        </div>

        <hr className="my-10 border-gray-700" />

        {/* CE Levels */}

        <h2 className="text-3xl font-bold text-green-400 mb-8">
          CE Levels
        </h2>
                <div className="grid md:grid-cols-2 gap-8">

          <div className="bg-black border border-green-500 rounded-xl p-6">

            <h3 className="text-yellow-400 text-xl font-bold mb-5">
              Support Levels
            </h3>

            <input
              type="text"
              placeholder="Support 1"
              className="w-full p-3 mb-4 rounded-lg bg-gray-900 border border-gray-600"
            />

            <input
              type="text"
              placeholder="Support 2"
              className="w-full p-3 rounded-lg bg-gray-900 border border-gray-600"
            />

          </div>

          <div className="bg-black border border-red-500 rounded-xl p-6">

            <h3 className="text-yellow-400 text-xl font-bold mb-5">
              Resistance Levels
            </h3>

            <input
              type="text"
              placeholder="Resistance 1"
              className="w-full p-3 mb-4 rounded-lg bg-gray-900 border border-gray-600"
            />

            <input
              type="text"
              placeholder="Resistance 2"
              className="w-full p-3 rounded-lg bg-gray-900 border border-gray-600"
            />

          </div>

        </div>

        <hr className="my-10 border-gray-700" />

        <h2 className="text-3xl font-bold text-red-400 mb-8">
          PE Levels
        </h2>

        <div className="grid md:grid-cols-2 gap-8">

          <div className="bg-black border border-green-500 rounded-xl p-6">

            <h3 className="text-yellow-400 text-xl font-bold mb-5">
              Support Levels
            </h3>

            <input
              type="text"
              placeholder="Support 1"
              className="w-full p-3 mb-4 rounded-lg bg-gray-900 border border-gray-600"
            />

            <input
              type="text"
              placeholder="Support 2"
              className="w-full p-3 rounded-lg bg-gray-900 border border-gray-600"
            />

          </div>

          <div className="bg-black border border-red-500 rounded-xl p-6">

            <h3 className="text-yellow-400 text-xl font-bold mb-5">
              Resistance Levels
            </h3>

            <input
              type="text"
              placeholder="Resistance 1"
              className="w-full p-3 mb-4 rounded-lg bg-gray-900 border border-gray-600"
            />

            <input
              type="text"
              placeholder="Resistance 2"
              className="w-full p-3 rounded-lg bg-gray-900 border border-gray-600"
            />

          </div>

        </div>

        <hr className="my-10 border-gray-700" />

        <h2 className="text-3xl font-bold text-yellow-400 mb-6">
          Upload Results Screenshot
        </h2>

        <input
          type="file"
          className="w-full p-3 rounded-lg bg-black border border-gray-600"
        />

        <hr className="my-10 border-gray-700" />
                <div className="mt-10 flex flex-col md:flex-row justify-center gap-5">

          <button
  onClick={clearForm}
  className="bg-gray-700 hover:bg-gray-600 text-white text-xl font-bold px-8 py-4 rounded-xl transition"
>
  🗑 Clear Form
</button>

          <a
            href="/premium"
            target="_blank"
            className="bg-blue-600 hover:bg-blue-500 text-white text-xl font-bold px-8 py-4 rounded-xl transition text-center"
          >
            👁 Preview Premium Page
          </a>

          <button
 alert("Save Button Clicked");
 onClick={saveLevels}
  className="bg-yellow-400 hover:bg-yellow-300 text-black text-xl font-black px-8 py-4 rounded-xl transition"
>
  💾 Save Today's Levels
</button>

        </div>

      </div>

    </main>
  );
}