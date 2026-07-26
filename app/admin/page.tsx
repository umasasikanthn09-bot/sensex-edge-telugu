"use client";

import { useState } from "react";
import { db } from "./lib/firebase";
import { doc, setDoc } from "firebase/firestore";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
export default function AdminPage() {
  const router = useRouter();

useEffect(() => {

  const login = localStorage.getItem("adminLogin");

  if (login !== "true") {
    router.push("/login");
  }

}, []);
  const [date, setDate] = useState("");
  const [updatedTime, setUpdatedTime] = useState("");
  const [sensexSpot, setSensexSpot] = useState("");

  const [supportLevel, setSupportLevel] = useState("");
  const [supportTarget1, setSupportTarget1] = useState("");
  const [supportTarget2, setSupportTarget2] = useState("");

  const [resistanceLevel, setResistanceLevel] = useState("");
  const [resistanceTarget1, setResistanceTarget1] = useState("");
  const [resistanceTarget2, setResistanceTarget2] = useState("");
  const [ceSupport1, setCeSupport1] = useState("");
const [ceSupport2, setCeSupport2] = useState("");

const [ceResistance1, setCeResistance1] = useState("");
const [ceResistance2, setCeResistance2] = useState("");
  const [peSupport1, setPeSupport1] = useState("");
const [peSupport2, setPeSupport2] = useState("");

const [peResistance1, setPeResistance1] = useState("");
const [peResistance2, setPeResistance2] = useState("");
const [result1, setResult1] = useState("");
const [result2, setResult2] = useState("");
const [result3, setResult3] = useState("");
const uploadImage = async (file: File, imageNumber: number) => {

  const formData = new FormData();

  formData.append("file", file);
  formData.append(
    "upload_preset",
    "sensex-results"
  );

  try {

    const response = await fetch(
      "https://api.cloudinary.com/v1_1/k0174nam/image/upload",
      {
        method: "POST",
        body: formData,
      }
    );

    const data = await response.json();

    if (imageNumber === 1) {
  setResult1(data.secure_url);
  localStorage.setItem("result1", data.secure_url);
}

if (imageNumber === 2) {
  setResult2(data.secure_url);
  localStorage.setItem("result2", data.secure_url);
}

if (imageNumber === 3) {
  setResult3(data.secure_url);
  localStorage.setItem("result3", data.secure_url);
}

    alert("✅ Image Uploaded Successfully");

  } catch (error) {

    console.error(error);
    alert("❌ Image Upload Failed");

  }

};
  const clearForm = async () => {
  setDate("");
  setUpdatedTime("");
  setSensexSpot("");

  setSupportLevel("");
  setSupportTarget1("");
  setSupportTarget2("");

  setResistanceLevel("");
  setResistanceTarget1("");
  setResistanceTarget2("");

  setCeSupport1("");
  setCeSupport2("");
  setCeResistance1("");
  setCeResistance2("");

  setPeSupport1("");
  setPeSupport2("");
  setPeResistance1("");
  setPeResistance2("");

 const img1 = localStorage.getItem("result1") || "";
const img2 = localStorage.getItem("result2") || "";
const img3 = localStorage.getItem("result3") || "";
  await setDoc(doc(db, "premium", "today"), {
    date: "",
    updatedTime: "",
    sensexSpot: "",

    supportLevel: "",
    supportTarget1: "",
    supportTarget2: "",

    resistanceLevel: "",
    resistanceTarget1: "",
    resistanceTarget2: "",

    ceSupport1: "",
    ceSupport2: "",
    ceResistance1: "",
    ceResistance2: "",

    peSupport1: "",
    peSupport2: "",
    peResistance1: "",
    peResistance2: "",
    result1: img1,
result2: img2,
result3: img3,
  });

  alert("✅ All Levels Cleared");
};

  const saveLevels = async () => {
  alert("Save Button Clicked");

  try {
    
  await setDoc(doc(db, "premium", "today"), {
  date,
  updatedTime,
  sensexSpot,

  supportLevel,
  supportTarget1,
  supportTarget2,

  resistanceLevel,
  resistanceTarget1,
  resistanceTarget2,

  ceSupport1,
  ceSupport2,
  ceResistance1,
  ceResistance2,

  peSupport1,
peSupport2,
peResistance1,
peResistance2,

result1: localStorage.getItem("result1") || "",
result2: localStorage.getItem("result2") || "",
result3: localStorage.getItem("result3") || "",

});

alert("✅ Today's Levels Saved Successfully!");
  } catch (error: any) {
    console.error(error);
    alert(error.message);
  }
};

return (

    <main className="min-h-screen bg-black text-white p-8">


      {/* Admin Navigation */}

      <div className="max-w-6xl mx-auto flex justify-between items-center mb-8">

        <nav className="flex gap-6">

          <a
            href="/"
            className="text-white hover:text-yellow-400"
          >
            🏠 Home
          </a>

          <a
            href="/admin"
            className="text-white hover:text-yellow-400"
          >
            🔐 Admin
          </a>

          <a
            href="/premium"
            className="text-white hover:text-yellow-400"
          >
            ⭐ Premium
          </a>

          <button
  onClick={() => {
    localStorage.removeItem("adminLogin");
    window.location.href = "/login";
  }}
  className="text-red-400 hover:text-red-600"
>
  🚪 Logout
</button>

        </nav>

      </div>


      <h1 className="text-4xl font-black text-yellow-400 text-center mb-10">
        Sensex Edge Telugu - Admin Dashboard
      </h1>

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
        {/* Results Screenshot Upload */}

<h2 className="text-3xl font-bold text-yellow-400 mb-8">
  Results Screenshots
</h2>

<div className="grid md:grid-cols-3 gap-6 mb-10">


  <div className="bg-black border border-green-500 rounded-xl p-6">

    <h3 className="text-xl text-green-400 font-bold mb-4">
      Screenshot 1
    </h3>

    <input
      type="file"
      accept="image/*"
      onChange={(e) =>
        e.target.files &&
        uploadImage(e.target.files[0], 1)
      }
      className="w-full"
    />

  </div>



  <div className="bg-black border border-yellow-500 rounded-xl p-6">

    <h3 className="text-xl text-yellow-400 font-bold mb-4">
      Screenshot 2
    </h3>

    <input
      type="file"
      accept="image/*"
      onChange={(e) =>
        e.target.files &&
        uploadImage(e.target.files[0], 2)
      }
      className="w-full"
    />

  </div>



  <div className="bg-black border border-red-500 rounded-xl p-6">

    <h3 className="text-xl text-red-400 font-bold mb-4">
      Screenshot 3
    </h3>

    <input
      type="file"
      accept="image/*"
      onChange={(e) =>
        e.target.files &&
        uploadImage(e.target.files[0], 3)
      }
      className="w-full"
    />

  </div>


</div>
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
  value={supportLevel}
  onChange={(e) => setSupportLevel(e.target.value)}
  className="w-full p-3 mb-4 rounded-lg bg-gray-900 border border-gray-600"
/>

            <input
  type="text"
  placeholder="Target 1"
  value={supportTarget1}
  onChange={(e) => setSupportTarget1(e.target.value)}
  className="w-full p-3 mb-4 rounded-lg bg-gray-900 border border-gray-600"
/>
            <input
  type="text"
  placeholder="Target 2"
  value={supportTarget2}
  onChange={(e) => setSupportTarget2(e.target.value)}
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
  value={resistanceLevel}
  onChange={(e) => setResistanceLevel(e.target.value)}
  className="w-full p-3 mb-4 rounded-lg bg-gray-900 border border-gray-600"
/>

            <input
  type="text"
  placeholder="Target 1"
  value={resistanceTarget1}
  onChange={(e) => setResistanceTarget1(e.target.value)}
  className="w-full p-3 mb-4 rounded-lg bg-gray-900 border border-gray-600"
/>

           <input
  type="text"
  placeholder="Target 2"
  value={resistanceTarget2}
  onChange={(e) => setResistanceTarget2(e.target.value)}
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
  value={ceSupport1}
  onChange={(e) => setCeSupport1(e.target.value)}
  className="w-full p-3 mb-4 rounded-lg bg-gray-900 border border-gray-600"
/>

            <input
  type="text"
  placeholder="Support 2"
  value={ceSupport2}
  onChange={(e) => setCeSupport2(e.target.value)}
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
  value={ceResistance1}
  onChange={(e) => setCeResistance1(e.target.value)}
  className="w-full p-3 mb-4 rounded-lg bg-gray-900 border border-gray-600"
/>

            <input
  type="text"
  placeholder="Resistance 2"
  value={ceResistance2}
  onChange={(e) => setCeResistance2(e.target.value)}
  className="w-full p-3 rounded-lg bg-gray-900 border border-gray-600"
/>

        </div>
        
        </div>

        <hr className="my-10 border-gray-700" />

       
{/* PE Levels */}

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
      value={peSupport1}
      onChange={(e) => setPeSupport1(e.target.value)}
      className="w-full p-3 mb-4 rounded-lg bg-gray-900 border border-gray-600"
    />

    <input
      type="text"
      placeholder="Support 2"
      value={peSupport2}
      onChange={(e) => setPeSupport2(e.target.value)}
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
      value={peResistance1}
      onChange={(e) => setPeResistance1(e.target.value)}
      className="w-full p-3 mb-4 rounded-lg bg-gray-900 border border-gray-600"
    />

    <input
      type="text"
      placeholder="Resistance 2"
      value={peResistance2}
      onChange={(e) => setPeResistance2(e.target.value)}
      className="w-full p-3 rounded-lg bg-gray-900 border border-gray-600"
    />

  </div>

</div>

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