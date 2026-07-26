export default function TodayPage() {
  return (
    <main className="min-h-screen bg-black text-white">

      {/* Header */}
      <section className="bg-yellow-400 text-black py-10 text-center">
        <h1 className="text-5xl font-black">
          Today's Sensex Options Levels
        </h1>

        <p className="mt-4 text-xl font-medium">
          Daily Support • Resistance • Market Trend
        </p>
      </section>

      {/* Levels */}
      <section className="max-w-6xl mx-auto px-6 py-16">

        <div className="grid md:grid-cols-2 gap-8">

          {/* Support */}
          <div className="bg-gray-900 border border-green-500 rounded-2xl p-8">
            <h2 className="text-3xl text-green-400 font-bold mb-6">
              🟢 Support Levels
            </h2>

            <ul className="space-y-3 text-lg">
              <li>Support 1 : ________</li>
              <li>Support 2 : ________</li>
              <li>Support 3 : ________</li>
            </ul>
          </div>

          {/* Resistance */}
          <div className="bg-gray-900 border border-red-500 rounded-2xl p-8">
            <h2 className="text-3xl text-red-400 font-bold mb-6">
              🔴 Resistance Levels
            </h2>

            <ul className="space-y-3 text-lg">
              <li>Resistance 1 : ________</li>
              <li>Resistance 2 : ________</li>
              <li>Resistance 3 : ________</li>
            </ul>
          </div>

        </div>

        {/* Trend */}
        <div className="bg-gray-900 border border-yellow-500 rounded-2xl p-8 mt-10">

          <h2 className="text-3xl text-yellow-400 font-bold mb-5">
            📈 Market Trend
          </h2>

          <p className="text-xl">
            Trend : ____________________
          </p>

        </div>

        {/* Notes */}
        <div className="bg-gray-900 border border-blue-500 rounded-2xl p-8 mt-10">

          <h2 className="text-3xl text-blue-400 font-bold mb-5">
            📝 Important Notes
          </h2>

          <ul className="space-y-3">
            <li>• Wait for confirmation before entry.</li>
            <li>• Follow strict Stop Loss.</li>
            <li>• Avoid emotional trading.</li>
            <li>• Capital protection is the first priority.</li>
          </ul>

        </div>

      </section>

    </main>
  );
}