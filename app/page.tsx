import Image from "next/image";
import Link from "next/link";

export default function Home() {
  return (
    <main className="min-h-screen bg-black text-white">

      {/* Header */}
      <header className="border-b border-yellow-500">
        <div className="max-w-7xl mx-auto flex justify-between items-center p-5">

          <div className="flex items-center gap-4">
  <Image
    src="/logo.png"
    alt="Sensex Edge Telugu"
    width={70}
    height={70}
    priority
  />

  <div>
    <h1 className="text-3xl font-extrabold text-yellow-400">
      Sensex Edge Telugu
    </h1>

    <p className="text-sm text-gray-300">
      తెలుగు వారి ఆర్థిక స్వేచ్ఛకు విశ్వసనీయ మార్గదర్శి
    </p>
  </div>
</div>

          <nav className="flex gap-6 text-sm">
     <a href="/" className="hover:text-yellow-400">
  Home
</a>

<a href="/premium" className="hover:text-yellow-400">
  Today's Levels
</a>

<a href="#about" className="hover:text-yellow-400">
  About
</a>

<a href="#contact" className="hover:text-yellow-400">
  Contact
</a>
          </nav>

        </div>
      </header>

      {/* Hero */}
<section className="text-center py-24 px-6">

  <h2 className="text-6xl font-black text-yellow-400">
    SENSEX EDGE TELUGU
  </h2>

  <p className="text-xl text-gray-300 mt-6 max-w-3xl mx-auto">
    Professional Telugu Platform for Sensex Options Intraday Traders.
    Daily Market Analysis, Support & Resistance Levels,
    Risk Management and Trading Education.
  </p>

  <div className="mt-10 flex justify-center gap-5 flex-wrap">

          <a
            href="https://www.youtube.com/@SensexEdgeTelugu-w5d"
            target="_blank"
            className="bg-yellow-400 text-black px-8 py-4 rounded-xl font-bold hover:bg-yellow-300 transition"
          >
            📺 Visit YouTube
          </a>

         <Link
  href="/premium"
  className="border border-yellow-400 px-8 py-4 rounded-xl hover:bg-yellow-400 hover:text-black transition inline-block"
>
  📈 Today's Levels
</Link>

        </div>

      </section>

      {/* Features */}
      <section className="max-w-6xl mx-auto px-6 pb-20">

        <h3 className="text-4xl text-center text-yellow-400 font-bold mb-12">
          Why Choose Sensex Edge Telugu?
        </h3>

        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">

          <div className="bg-gray-900 rounded-2xl p-6 border border-yellow-500">
            <h4 className="text-yellow-400 font-bold text-xl">Daily Levels</h4>
            <p className="text-gray-400 mt-3">
              Accurate Intraday Support & Resistance Levels.
            </p>
          </div>

          <div className="bg-gray-900 rounded-2xl p-6 border border-yellow-500">
            <h4 className="text-yellow-400 font-bold text-xl">Market Analysis</h4>
            <p className="text-gray-400 mt-3">
              Easy Telugu explanations with market direction.
            </p>
          </div>

          <div className="bg-gray-900 rounded-2xl p-6 border border-yellow-500">
            <h4 className="text-yellow-400 font-bold text-xl">Risk Management</h4>
            <p className="text-gray-400 mt-3">
              Protect your capital with disciplined trading.
            </p>
          </div>

          <div className="bg-gray-900 rounded-2xl p-6 border border-yellow-500">
            <h4 className="text-yellow-400 font-bold text-xl">Learn Trading</h4>
            <p className="text-gray-400 mt-3">
              Step-by-step learning for beginners and professionals.
            </p>
          </div>

        </div>

      </section>
{/* Telugu Welcome Section */}

<section className="max-w-5xl mx-auto px-6 pb-20">

  <div className="bg-gray-900 border border-yellow-500 rounded-2xl p-10 text-center">

    <h3 className="text-4xl font-bold text-yellow-400 mb-6">
      ఆర్థిక స్వేచ్ఛను పొందాలనుకునే వారికి స్వాగతం
    </h3>

    <p className="text-lg text-gray-300 leading-9">
      <strong className="text-yellow-400">Sensex Edge Telugu</strong> అనేది
      స్వయం ఉపాధి కోరుకునే వారికి, ఆర్థిక విజ్ఞానాన్ని పెంపొందించుకోవాలనుకునే వారికి,
      క్రమశిక్షణతో ట్రేడింగ్ నేర్చుకుని తమ భవిష్యత్తును మెరుగుపరచుకోవాలనుకునే
      ప్రతి తెలుగు వ్యక్తికి అంకితమైన వేదిక.
    </p>

    <div className="grid md:grid-cols-2 gap-4 mt-8 text-left">

      <div>✅ స్వయం ఉపాధి సాధించాలని కోరుకునే వారు</div>
      <div>✅ ఆర్థిక స్వేచ్ఛ దిశగా ప్రయాణించాలనుకునే వారు</div>
      <div>✅ ఉద్యోగంతో పాటు అదనపు నైపుణ్యాన్ని అభివృద్ధి చేసుకోవాలనుకునే వారు</div>
      <div>✅ క్రమశిక్షణతో ట్రేడింగ్ నేర్చుకోవాలనుకునే వారు</div>
      <div>✅ రిస్క్ మేనేజ్‌మెంట్ నేర్చుకోవాలనుకునే వారు</div>
      <div>✅ తెలుగులో సులభంగా నేర్చుకోవాలనుకునే ప్రతి ఒక్కరూ</div>

    </div>

  </div>

</section>{/* Mission Section */}

<section className="max-w-5xl mx-auto px-6 pb-16">

  <div className="bg-yellow-400 text-black rounded-2xl p-10 text-center shadow-xl">

    <h3 className="text-4xl font-extrabold mb-6">
      🎯 మా లక్ష్యం
    </h3>

    <p className="text-xl leading-9">
      తెలుగు ప్రజలకు ఆర్థిక విజ్ఞానం,
      క్రమశిక్షణతో కూడిన ట్రేడింగ్ అవగాహన,
      రిస్క్ మేనేజ్‌మెంట్ మరియు బాధ్యతాయుతమైన
      ఆర్థిక నిర్ణయాల కోసం
      <strong> విశ్వసనీయ వేదికగా </strong>
      నిలవడం మా లక్ష్యం.
    </p>

  </div>

</section>

{/* About Us */}

<section id="about" className="max-w-5xl mx-auto px-6 pb-16">

  <div className="bg-gray-900 border border-yellow-500 rounded-2xl p-10">

    <h3 className="text-4xl font-extrabold text-yellow-400 text-center mb-8">
      👨‍💼 About Sensex Edge Telugu
    </h3>

    <div className="space-y-8">

      <div>
        <h4 className="text-2xl font-bold text-yellow-400 mb-3">
          English
        </h4>

        <p className="text-gray-300 leading-8">
          <strong className="text-yellow-400">Sensex Edge Telugu</strong> is dedicated
          to helping traders build market discipline, improve price action
          understanding, and develop strong risk management skills through
          educational market analysis.

          <br /><br />

          Our Premium Levels are designed to support better decision-making
          with clearly defined Support, Resistance, CE and PE levels.

          <br /><br />

          <strong className="text-white">
            Trade Smart. Stay Disciplined. Grow Consistently.
          </strong>
        </p>
      </div>

      <hr className="border-gray-700" />

      <div>
        <h4 className="text-2xl font-bold text-yellow-400 mb-3">
          తెలుగు
        </h4>

        <p className="text-gray-300 leading-8">
          <strong className="text-yellow-400">Sensex Edge Telugu</strong>
          యొక్క ముఖ్య ఉద్దేశ్యం ట్రేడర్లకు మార్కెట్‌పై సరైన అవగాహన,
          క్రమశిక్షణ మరియు రిస్క్ మేనేజ్‌మెంట్ నేర్పించడం.

          <br /><br />

          మా Premium Levels ద్వారా Support, Resistance,
          CE మరియు PE Levelsను స్పష్టంగా అందిస్తూ,
          ట్రేడింగ్‌లో సరైన నిర్ణయాలు తీసుకునేలా సహాయం చేస్తాము.

          <br /><br />

          <strong className="text-white">
            విజయవంతమైన ట్రేడింగ్‌కు షార్ట్‌కట్స్ కాదు...
            అవగాహన, సహనం మరియు క్రమశిక్షణే నిజమైన మార్గం.
          </strong>
        </p>
      </div>

    </div>

  </div>

</section>

{/* Contact */}

<section id="contact" className="max-w-5xl mx-auto px-6 pb-20">

  <div className="bg-yellow-400 text-black rounded-2xl p-10 text-center">

    <h3 className="text-4xl font-extrabold mb-8">
      📞 Contact Us
    </h3>

    <div className="space-y-5 text-xl">

      <p>
        📺 <strong>YouTube:</strong> Sensex Edge Telugu
      </p>

      <p>
  💬 <strong>WhatsApp:</strong>{" "}
  <a
    href="https://wa.me/91XXXXXXXXXX"
    target="_blank"
    rel="noopener noreferrer"
    className="text-blue-800 font-bold hover:underline"
  >
    +91 8639047069
  </a>
</p>

<p>
  📧 <strong>Email:</strong>{" "}
  <a
    href="mailto:your-email@example.com"
    className="text-blue-800 font-bold hover:underline"
  >
    sensexedgetelugu@gmail.com
  </a>
</p>

    </div>

    <div className="mt-8 text-lg font-bold">
      ⭐ Knowledge Builds Confidence.<br />
      Discipline Creates Success.
    </div>

  </div>

</section>

{/* Disclaimer */}

<section className="max-w-5xl mx-auto px-6 pb-20">

  <div className="bg-gray-900 border border-yellow-500 rounded-2xl p-8">

    <h3 className="text-3xl font-bold text-yellow-400 mb-5">
      ⚠️ Disclaimer
    </h3>

    <p className="text-gray-300 leading-8">
      ఈ Website మరియు YouTube Channelలో అందించే సమాచారం
      విద్యాపరమైన (Educational) ప్రయోజనాల కోసం మాత్రమే.
      షేర్ మార్కెట్ మరియు Options Tradingలో పెట్టుబడులు రిస్క్‌కు లోబడి ఉంటాయి.
      ప్రతి ట్రేడ్ లేదా పెట్టుబడి నిర్ణయం తీసుకునే ముందు
      మీ స్వంత పరిశీలన చేయండి.
    </p>

  </div>

</section>
      {/* Footer */}
     <footer className="border-t border-yellow-500 mt-16 py-10 text-center text-gray-400">

  <h3 className="text-2xl font-bold text-yellow-400">
    Sensex Edge Telugu
  </h3>

  <p className="mt-3">
    తెలుగు వారి ఆర్థిక స్వేచ్ఛకు విశ్వసనీయ మార్గదర్శి
  </p>

  <div className="mt-5 flex justify-center gap-6">

    <a
      href="https://www.youtube.com/@SensexEdgeTelugu-w5d"
      target="_blank"
      className="hover:text-yellow-400"
    >
      YouTube
    </a>

    <a
      href="https://wa.me/918639047069"
      target="_blank"
      className="hover:text-yellow-400"
    >
      WhatsApp
    </a>

    <a
      href="mailto:sensexedgetelugu@gmail.com"
      className="hover:text-yellow-400"
    >
      Email
    </a>

  </div>

  <p className="mt-6 text-sm">
    © 2026 Sensex Edge Telugu. All Rights Reserved.
  </p>

</footer>

    </main>
  );
}