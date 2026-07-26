"use client";

import { useEffect, useState } from "react";
import { db } from "../admin/lib/firebase";
import { doc, onSnapshot } from "firebase/firestore";

export default function PremiumPage() {
  const [data, setData] = useState({
    date: "",
    updatedTime: "",

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
    result1: "",
result2: "",
result3: "",
  });

useEffect(() => {
  const unsubscribe = onSnapshot(
    doc(db, "premium", "today"),
    (snap) => {
      if (snap.exists()) {
        setData(snap.data() as any);
      }
    }
  );

  return () => unsubscribe();
}, []);

  return (
    <main className="min-h-screen bg-black text-white">

      {/* HEADER */}

      <header className="border-b border-yellow-500">

        <div className="max-w-7xl mx-auto p-6">

          <h1 className="text-4xl font-black text-yellow-400 text-center">
            Today's Premium Levels
          </h1>

          <p className="text-center text-gray-400 mt-2">
            Sensex Edge Telugu Premium Members
          </p>

        </div>

      </header>

      {/* TOP INFO */}

      <section className="max-w-6xl mx-auto mt-10 px-6">

        <div className="bg-gray-900 border border-yellow-500 rounded-2xl p-6">

          <div className="grid md:grid-cols-3 gap-4">

            <div className="bg-black border border-yellow-500 rounded-xl p-5 text-center">

              <p className="text-gray-400">
                Updated Time
              </p>

              <h3 className="text-2xl font-bold text-yellow-400">
               {data.updatedTime
  ? new Date(`2000-01-01T${data.updatedTime}`).toLocaleTimeString("en-IN", {
      hour: "numeric",
      minute: "2-digit",
      hour12: true,
    })
  : ""}
               
                </h3>

            </div>

            <div className="bg-black border border-green-500 rounded-xl p-5 text-center">

              <p className="text-gray-400">
                Time Frame
              </p>

              <h3 className="text-2xl font-bold text-green-400">
                15 Minutes
              </h3>

            </div>

            <div className="bg-black border border-red-500 rounded-xl p-5 text-center">

              <p className="text-gray-400">
                Date
              </p>

              <h3 className="text-2xl font-bold text-red-400">
                {data.date}
              </h3>

            </div>

          </div>

        </div>

      </section>

      {/* SENSEX INDEX LEVELS */}

<section className="max-w-6xl mx-auto mt-10 px-6">

  <div className="bg-gray-900 border-2 border-yellow-500 rounded-2xl p-8">

    <h2 className="text-4xl text-yellow-400 font-black mb-8 text-center">
      SENSEX INDEX LEVELS
    </h2>


    <div className="grid md:grid-cols-2 gap-8">


      {/* SUPPORT SIDE */}

      <div className="bg-black border border-green-500 rounded-xl p-6">

        <h3 className="text-2xl text-green-400 font-bold mb-5">
          Support Side
        </h3>


        <div className="bg-gray-900 rounded-xl p-5 mb-4 border border-gray-700">

          <p className="text-xl font-bold text-white">
  Support Level : 
  <span className="text-yellow-400 ml-2">
    {data.supportLevel}
  </span>
</p>

        </div>


        <div className="bg-gray-900 rounded-xl p-5 mb-4 border border-gray-700">

          <p className="text-xl font-bold text-white">
  Target 1 :
  <span className="text-yellow-400 ml-2">
    {data.supportTarget1}
  </span>
</p>

        </div>


        <div className="bg-gray-900 rounded-xl p-5 border border-gray-700">

          <p className="text-xl font-bold text-white">
  Target 2 :
  <span className="text-yellow-400 ml-2">
    {data.supportTarget2}
  </span>
</p>

        </div>


      </div>




      {/* RESISTANCE SIDE */}

      <div className="bg-black border border-red-500 rounded-xl p-6">

        <h3 className="text-2xl text-red-400 font-bold mb-5">
          Resistance Side
        </h3>


        <div className="bg-gray-900 rounded-xl p-5 mb-4 border border-gray-700">

          <p className="text-xl font-bold text-white">
  Resistance Level :
  <span className="text-yellow-400 ml-2">
    {data.resistanceLevel}
  </span>
</p>

        </div>


        <div className="bg-gray-900 rounded-xl p-5 mb-4 border border-gray-700">

          <p className="text-xl font-bold text-white">
  Target 1 :
  <span className="text-yellow-400 ml-2">
    {data.resistanceTarget1}
  </span>
</p>

        </div>


        <div className="bg-gray-900 rounded-xl p-5 border border-gray-700">

          <p className="text-xl font-bold text-white">
  Target 2 :
  <span className="text-yellow-400 ml-2">
    {data.resistanceTarget2}
  </span>
</p>

        </div>


      </div>


    </div>


  </div>


</section>
{/* CE LEVELS */}

<section className="max-w-6xl mx-auto mt-10 px-6">

  <div className="bg-gray-900 border-2 border-green-500 rounded-2xl p-8">

    <h2 className="text-4xl text-green-400 font-black mb-8 text-center">
      CE LEVELS
    </h2>

    <div className="grid md:grid-cols-2 gap-8">

      {/* CE SUPPORT */}

      <div className="bg-black border border-green-500 rounded-xl p-6">

        <h3 className="text-2xl text-green-400 font-bold mb-5">
          Support Levels
        </h3>

        <div className="bg-gray-900 rounded-xl p-5 mb-4 border border-gray-700">
          <p className="text-xl font-bold text-white">
            Support 1 :
            <span className="text-green-400 ml-2">
              {data.ceSupport1}
            </span>
          </p>
        </div>

        <div className="bg-gray-900 rounded-xl p-5 border border-gray-700">
          <p className="text-xl font-bold text-white">
            Support 2 :
            <span className="text-green-400 ml-2">
              {data.ceSupport2}
            </span>
          </p>
        </div>

      </div>

      {/* CE RESISTANCE */}

      <div className="bg-black border border-red-500 rounded-xl p-6">

        <h3 className="text-2xl text-red-400 font-bold mb-5">
          Resistance Levels
        </h3>

        <div className="bg-gray-900 rounded-xl p-5 mb-4 border border-gray-700">
          <p className="text-xl font-bold text-white">
            Resistance 1 :
            <span className="text-yellow-400 ml-2">
              {data.ceResistance1}
            </span>
          </p>
        </div>

        <div className="bg-gray-900 rounded-xl p-5 border border-gray-700">
          <p className="text-xl font-bold text-white">
            Resistance 2 :
            <span className="text-yellow-400 ml-2">
              {data.ceResistance2}
            </span>
          </p>
        </div>

      </div>

    </div>

  </div>

</section>

     {/* PE LEVELS */}

<section className="max-w-6xl mx-auto mt-10 px-6">

  <div className="bg-gray-900 border-2 border-red-500 rounded-2xl p-8">

    <h2 className="text-4xl text-red-400 font-black mb-8 text-center">
      PE LEVELS
    </h2>


    <div className="grid md:grid-cols-2 gap-8">


      {/* PE SUPPORT */}

      <div className="bg-black border border-green-500 rounded-xl p-6">

        <h3 className="text-2xl text-green-400 font-bold mb-5">
          Support Levels
        </h3>


        <div className="bg-gray-900 rounded-xl p-5 mb-4 border border-gray-700">

          <p className="text-xl font-bold text-white">
            Support 1 :
            <span className="text-yellow-400 ml-2">
              {data.peSupport1}
            </span>
          </p>

        </div>


        <div className="bg-gray-900 rounded-xl p-5 border border-gray-700">

          <p className="text-xl font-bold text-white">
            Support 2 :
            <span className="text-yellow-400 ml-2">
              {data.peSupport2}
            </span>
          </p>

        </div>


      </div>



      {/* PE RESISTANCE */}

      <div className="bg-black border border-red-500 rounded-xl p-6">

        <h3 className="text-2xl text-red-400 font-bold mb-5">
          Resistance Levels
        </h3>


        <div className="bg-gray-900 rounded-xl p-5 mb-4 border border-gray-700">

          <p className="text-xl font-bold text-white">
            Resistance 1 :
            <span className="text-yellow-400 ml-2">
              {data.peResistance1}
            </span>
          </p>

        </div>


        <div className="bg-gray-900 rounded-xl p-5 border border-gray-700">

          <p className="text-xl font-bold text-white">
            Resistance 2 :
            <span className="text-yellow-400 ml-2">
              {data.peResistance2}
            </span>
          </p>

        </div>


      </div>


    </div>


  </div>


</section>
            {/* Trading Note */}

      <section className="max-w-6xl mx-auto mt-10 px-6">

        <div className="bg-yellow-500 text-black rounded-2xl p-8">

          <h2 className="text-3xl font-black">
            Trading Note
          </h2>

          <p className="mt-5 text-lg leading-8">
            ఒక Strike Priceలో Support Break అయి Red Candle Close అయితే,
            పరిస్థితిని బట్టి Opposite Strike Priceలో Entryని పరిశీలించాలి.
            <br /><br />
            Trend Strike Priceలో Support Break అయితే Trend మారే అవకాశాన్ని
            పరిగణించాలి.
          </p>

        </div>

      </section>

    {/* Results Gallery */}

<section className="max-w-6xl mx-auto mt-10 px-6">

  <div className="bg-gray-900 border border-yellow-500 rounded-2xl p-8">

    <h2 className="text-3xl text-yellow-400 font-black mb-6">
      📸 Results Gallery
    </h2>


    <div className="grid md:grid-cols-3 gap-6">


      {/* TODAY RESULT */}

      <div className="bg-black border border-green-500 rounded-xl p-5 text-center">

        <h3 className="text-green-400 font-bold text-xl">
          Today Result
        </h3>

        <img
          src={data.result1}
          alt=""
          className="mt-4 w-full h-40 object-cover rounded-lg"
        />

      </div>



      {/* Previous */}

      <div className="bg-black border border-yellow-500 rounded-xl p-5 text-center">

        <h3 className="text-yellow-400 font-bold text-xl">
          Previous
        </h3>

        <img
          src={data.result2}
          alt=""
          className="mt-4 w-full h-40 object-cover rounded-lg"
        />

      </div>



      {/* History */}

      <div className="bg-black border border-red-500 rounded-xl p-5 text-center">

        <h3 className="text-red-400 font-bold text-xl">
          History
        </h3>

        <img
          src={data.result3}
          alt=""
          className="mt-4 w-full h-40 object-cover rounded-lg"
        />

      </div>


    </div>

  </div>

</section>
{/* Disclaimer */}

      <section className="max-w-6xl mx-auto mt-10 mb-16 px-6">

        <div className="bg-gray-900 border border-yellow-500 rounded-2xl p-8">

          <h2 className="text-2xl text-yellow-400 font-bold mb-4">
            Disclaimer
          </h2>

          <p className="leading-8 text-gray-300">
            మా లక్ష్యం సభ్యులకు ఆర్థిక అవగాహన, క్రమశిక్షణ మరియు సరైన విశ్లేషణను అందించడం.
            <br /><br />
            ట్రేడింగ్ నిర్ణయాలు పూర్తిగా సభ్యుల స్వంత బాధ్యత.
          </p>

        </div>

      </section>

    </main>
  );
}