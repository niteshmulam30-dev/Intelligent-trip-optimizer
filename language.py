from deep_translator import GoogleTranslator
from langdetect import detect


# ==============================
# 🌐 ALL UI STRINGS IN ALL LANGUAGES
# This dictionary drives the 2-way bilingual interface.
# Every key is a logical UI label; every value maps lang_code → translated string.
# ==============================
UI_STRINGS = {
    # --- prompts shown to user ---
    "prompt_starting_city": {
        "en": "🏠 Enter your starting city: ",
        "hi": "🏠 अपना प्रारंभिक शहर दर्ज करें: ",
        "mr": "🏠 तुमचे सुरुवातीचे शहर टाका: ",
        "ta": "🏠 உங்கள் தொடக்க நகரத்தை உள்ளிடவும்: ",
        "te": "🏠 మీ ప్రారంభ నగరాన్ని నమోదు చేయండి: ",
        "kn": "🏠 ನಿಮ್ಮ ಆರಂಭಿಕ ನಗರವನ್ನು ನಮೂದಿಸಿ: ",
        "ml": "🏠 നിങ്ങളുടെ ആരംഭ നഗരം നൽകുക: ",
        "bn": "🏠 আপনার শুরুর শহর লিখুন: ",
        "gu": "🏠 તમારું પ્રારંભ શહેર દાખલ કરો: ",
        "pa": "🏠 ਆਪਣਾ ਸ਼ੁਰੂਆਤੀ ਸ਼ਹਿਰ ਦਰਜ ਕਰੋ: ",
    },
    "prompt_destination": {
        "en": "📍 Enter destination city: ",
        "hi": "📍 गंतव्य शहर दर्ज करें: ",
        "mr": "📍 गंतव्य शहर टाका: ",
        "ta": "📍 இலக்கு நகரத்தை உள்ளிடவும்: ",
        "te": "📍 గమ్యం నగరాన్ని నమోదు చేయండి: ",
        "kn": "📍 ಗಮ್ಯಸ್ಥಾನ ನಗರ ನಮೂದಿಸಿ: ",
        "ml": "📍 ലക്ഷ്യ നഗരം നൽകുക: ",
        "bn": "📍 গন্তব্য শহর লিখুন: ",
        "gu": "📍 મંઝિલ શહેર દાખલ કરો: ",
        "pa": "📍 ਮੰਜ਼ਿਲ ਸ਼ਹਿਰ ਦਰਜ ਕਰੋ: ",
    },
    "prompt_interest": {
        "en": "🎯 Enter interest (temple / beach / mosque / general): ",
        "hi": "🎯 रुचि दर्ज करें (temple / beach / mosque / general): ",
        "mr": "🎯 आवड टाका (temple / beach / mosque / general): ",
        "ta": "🎯 ஆர்வம் உள்ளிடவும் (temple / beach / mosque / general): ",
        "te": "🎯 ఆసక్తి నమోదు చేయండి (temple / beach / mosque / general): ",
        "kn": "🎯 ಆಸಕ್ತಿ ನಮೂದಿಸಿ (temple / beach / mosque / general): ",
        "ml": "🎯 താൽപ്പര്യം നൽകുക (temple / beach / mosque / general): ",
        "bn": "🎯 আগ্রহ লিখুন (temple / beach / mosque / general): ",
        "gu": "🎯 રસ દાખલ કરો (temple / beach / mosque / general): ",
        "pa": "🎯 ਦਿਲਚਸਪੀ ਦਰਜ ਕਰੋ (temple / beach / mosque / general): ",
    },
    "prompt_days": {
        "en": "📅 Number of days: ",
        "hi": "📅 दिनों की संख्या: ",
        "mr": "📅 दिवसांची संख्या: ",
        "ta": "📅 நாட்களின் எண்ணிக்கை: ",
        "te": "📅 రోజుల సంఖ్య: ",
        "kn": "📅 ದಿನಗಳ ಸಂಖ್ಯೆ: ",
        "ml": "📅 ദിവസങ്ങളുടെ എണ്ണം: ",
        "bn": "📅 দিনের সংখ্যা: ",
        "gu": "📅 દિવસોની સંખ્યા: ",
        "pa": "📅 ਦਿਨਾਂ ਦੀ ਗਿਣਤੀ: ",
    },
    "prompt_budget": {
        "en": "💰 Total trip budget (INR): ",
        "hi": "💰 कुल यात्रा बजट (INR): ",
        "mr": "💰 एकूण प्रवास बजेट (INR): ",
        "ta": "💰 மொத்த பயண பட்ஜெட் (INR): ",
        "te": "💰 మొత్తం యాత్ర బడ్జెట్ (INR): ",
        "kn": "💰 ಒಟ್ಟು ಪ್ರಯಾಣ ಬಜೆಟ್ (INR): ",
        "ml": "💰 ആകെ യാത്ര ബഡ്ജറ്റ് (INR): ",
        "bn": "💰 মোট ভ্রমণ বাজেট (INR): ",
        "gu": "💰 કુલ પ્રવાસ બજેટ (INR): ",
        "pa": "💰 ਕੁੱਲ ਯਾਤਰਾ ਬਜਟ (INR): ",
    },
    "prompt_rooms": {
        "en": "🏨 Number of rooms: ",
        "hi": "🏨 कमरों की संख्या: ",
        "mr": "🏨 खोल्यांची संख्या: ",
        "ta": "🏨 அறைகளின் எண்ணிக்கை: ",
        "te": "🏨 గదుల సంఖ్య: ",
        "kn": "🏨 ಕೊಠಡಿಗಳ ಸಂಖ್ಯೆ: ",
        "ml": "🏨 മുറികളുടെ എണ്ണം: ",
        "bn": "🏨 ঘরের সংখ্যা: ",
        "gu": "🏨 ઓરડાઓની સંખ્યા: ",
        "pa": "🏨 ਕਮਰਿਆਂ ਦੀ ਗਿਣਤੀ: ",
    },
    "prompt_view_history": {
        "en": "📜 View past trips first? (y/n): ",
        "hi": "📜 पहले पिछली यात्राएँ देखें? (y/n): ",
        "mr": "📜 आधी जुने प्रवास पाहायचे? (y/n): ",
        "ta": "📜 முதலில் பழைய பயணங்களை பார்க்கவா? (y/n): ",
        "te": "📜 ముందుగా పాత యాత్రలు చూడాలా? (y/n): ",
        "kn": "📜 ಮೊದಲು ಹಿಂದಿನ ಪ್ರಯಾಣ ನೋಡುವುದೇ? (y/n): ",
        "ml": "📜 ആദ്യം പഴയ യാത്രകൾ കാണണോ? (y/n): ",
        "bn": "📜 প্রথমে পুরানো ভ্রমণ দেখুন? (y/n): ",
        "gu": "📜 પહેલા જૂના પ્રવાસ જોવા? (y/n): ",
        "pa": "📜 ਪਹਿਲਾਂ ਪੁਰਾਣੀਆਂ ਯਾਤਰਾਵਾਂ ਦੇਖੋ? (y/n): ",
    },
    "prompt_weather_proceed": {
        "en": "⚠️ High weather risk. Still plan the trip? (y/n): ",
        "hi": "⚠️ उच्च मौसम जोखिम। फिर भी यात्रा की योजना बनाएं? (y/n): ",
        "mr": "⚠️ उच्च हवामान धोका. तरीही प्रवास योजना करायची? (y/n): ",
        "ta": "⚠️ அதிக வானிலை அபாயம். இன்னும் பயணத்தை திட்டமிட வேண்டுமா? (y/n): ",
        "te": "⚠️ అధిక వాతావరణ ప్రమాదం. అయినా యాత్ర ప్లాన్ చేయాలా? (y/n): ",
        "kn": "⚠️ ಹೆಚ್ಚಿನ ಹವಾಮಾನ ಅಪಾಯ. ಇನ್ನೂ ಪ್ರಯಾಣ ಯೋಜಿಸಬೇಕೇ? (y/n): ",
        "ml": "⚠️ ഉയർന്ന കാലാവസ്ഥ അപകടം. ഇപ്പോഴും യാത്ര ആസൂത്രണം ചെയ്യണോ? (y/n): ",
        "bn": "⚠️ উচ্চ আবহাওয়া ঝুঁকি। তবুও যাত্রা পরিকল্পনা করবেন? (y/n): ",
        "gu": "⚠️ ઊંચો હવામાન જોખમ. છતાં પ્રવાસ આયોજન કરવું? (y/n): ",
        "pa": "⚠️ ਉੱਚ ਮੌਸਮ ਜੋਖਮ। ਫਿਰ ਵੀ ਯਾਤਰਾ ਯੋਜਨਾ ਬਣਾਓ? (y/n): ",
    },
    "prompt_another_trip": {
        "en": "🔄 Plan another trip? (y/n): ",
        "hi": "🔄 एक और यात्रा की योजना बनाएं? (y/n): ",
        "mr": "🔄 आणखी एक प्रवास योजना करायची? (y/n): ",
        "ta": "🔄 மற்றொரு பயணத்தை திட்டமிட வேண்டுமா? (y/n): ",
        "te": "🔄 మరొక యాత్ర ప్లాన్ చేయాలా? (y/n): ",
        "kn": "🔄 ಮತ್ತೊಂದು ಪ್ರಯಾಣ ಯೋಜಿಸಬೇಕೇ? (y/n): ",
        "ml": "🔄 മറ്റൊരു യാത്ര ആസൂത്രണം ചെയ്യണോ? (y/n): ",
        "bn": "🔄 আরেকটি ভ্রমণ পরিকল্পনা করবেন? (y/n): ",
        "gu": "🔄 બીજો પ્રવાસ આયોજન કરવો? (y/n): ",
        "pa": "🔄 ਇੱਕ ਹੋਰ ਯਾਤਰਾ ਯੋਜਨਾ ਬਣਾਓ? (y/n): ",
    },
    # --- status / info messages ---
    "msg_header": {
        "en": "🤖 SMART TRAVEL CHAT AGENT v2",
        "hi": "🤖 स्मार्ट ट्रैवल चैट एजेंट v2",
        "mr": "🤖 स्मार्ट ट्रॅव्हल चॅट एजंट v2",
        "ta": "🤖 ஸ்மார்ட் டிராவல் சாட் ஏஜென்ட் v2",
        "te": "🤖 స్మార్ట్ ట్రావెల్ చాట్ ఏజెంట్ v2",
        "kn": "🤖 ಸ್ಮಾರ್ಟ್ ಟ್ರಾವೆಲ್ ಚಾಟ್ ಏಜೆಂಟ್ v2",
        "ml": "🤖 സ്മാർട്ട് ട്രാവൽ ചാറ്റ് ഏജന്റ് v2",
        "bn": "🤖 স্মার্ট ট্রাভেল চ্যাট এজেন্ট v2",
        "gu": "🤖 સ્માર્ટ ટ્રાવેલ ચેટ એજન્ટ v2",
        "pa": "🤖 ਸਮਾਰਟ ਟ੍ਰੈਵਲ ਚੈਟ ਏਜੰਟ v2",
    },
    "msg_invalid_days": {
        "en": "❌ Invalid number of days.",
        "hi": "❌ दिनों की संख्या अमान्य है।",
        "mr": "❌ दिवसांची संख्या अवैध आहे.",
        "ta": "❌ நாட்களின் எண்ணிக்கை தவறானது.",
        "te": "❌ రోజుల సంఖ్య చెల్లదు.",
        "kn": "❌ ದಿನಗಳ ಸಂಖ್ಯೆ ಅಮಾನ್ಯ.",
        "ml": "❌ ദിവസങ്ങളുടെ എണ്ണം അസാധുവാണ്.",
        "bn": "❌ দিনের সংখ্যা অবৈধ।",
        "gu": "❌ દિવસોની સંખ્યા અમાન્ય છે.",
        "pa": "❌ ਦਿਨਾਂ ਦੀ ਗਿਣਤੀ ਅਵੈਧ ਹੈ।",
    },
    "msg_invalid_budget": {
        "en": "❌ Invalid budget or rooms.",
        "hi": "❌ अमान्य बजट या कमरे।",
        "mr": "❌ अवैध बजेट किंवा खोल्या.",
        "ta": "❌ தவறான பட்ஜெட் அல்லது அறைகள்.",
        "te": "❌ చెల్లని బడ్జెట్ లేదా గదులు.",
        "kn": "❌ ಅಮಾನ್ಯ ಬಜೆಟ್ ಅಥವಾ ಕೊಠಡಿಗಳು.",
        "ml": "❌ അസാധുവായ ബഡ്ജറ്റ് അല്ലെങ്കിൽ മുറികൾ.",
        "bn": "❌ অবৈধ বাজেট বা ঘর।",
        "gu": "❌ અમાન્ય બજેટ અથવા ઓરડા.",
        "pa": "❌ ਅਵੈਧ ਬਜਟ ਜਾਂ ਕਮਰੇ।",
    },
    "msg_no_places": {
        "en": "❌ No places found.",
        "hi": "❌ कोई स्थान नहीं मिला।",
        "mr": "❌ कोणतीही जागा सापडली नाही.",
        "ta": "❌ இடங்கள் எதுவும் கிடைக்கவில்லை.",
        "te": "❌ స్థలాలు ఏవీ కనుగొనబడలేదు.",
        "kn": "❌ ಯಾವುದೇ ಸ್ಥಳ ಸಿಗಲಿಲ್ಲ.",
        "ml": "❌ ഒരു സ്ഥലവും കണ്ടെത്തിയില്ല.",
        "bn": "❌ কোনো স্থান পাওয়া যায়নি।",
        "gu": "❌ કોઈ સ્થળ મળ્યું નહીં.",
        "pa": "❌ ਕੋਈ ਥਾਂ ਨਹੀਂ ਮਿਲੀ।",
    },
    "msg_trip_cancelled": {
        "en": "🔙 Trip planning cancelled due to weather conditions.",
        "hi": "🔙 मौसम की स्थिति के कारण यात्रा योजना रद्द।",
        "mr": "🔙 हवामानामुळे प्रवास योजना रद्द.",
        "ta": "🔙 வானிலை காரணமாக பயண திட்டம் ரத்து செய்யப்பட்டது.",
        "te": "🔙 వాతావరణ పరిస్థితుల కారణంగా యాత్ర ప్లాన్ రద్దు.",
        "kn": "🔙 ಹವಾಮಾನ ಕಾರಣದಿಂದ ಪ್ರಯಾಣ ಯೋಜನೆ ರದ್ದು.",
        "ml": "🔙 കാലാവസ്ഥ കാരണം യാത്ര ആസൂത്രണം റദ്ദ് ചെയ്തു.",
        "bn": "🔙 আবহাওয়ার কারণে যাত্রা পরিকল্পনা বাতিল।",
        "gu": "🔙 હવામાન કારણે પ્રવાસ આયોજન રદ.",
        "pa": "🔙 ਮੌਸਮ ਕਾਰਨ ਯਾਤਰਾ ਯੋਜਨਾ ਰੱਦ।",
    },
    "msg_trip_done": {
        "en": "🎉 Trip Plan Generated Successfully!",
        "hi": "🎉 यात्रा योजना सफलतापूर्वक तैयार!",
        "mr": "🎉 प्रवास योजना यशस्वीरित्या तयार!",
        "ta": "🎉 பயண திட்டம் வெற்றிகரமாக உருவாக்கப்பட்டது!",
        "te": "🎉 యాత్ర ప్లాన్ విజయవంతంగా రూపొందించబడింది!",
        "kn": "🎉 ಪ್ರಯಾಣ ಯೋಜನೆ ಯಶಸ್ವಿಯಾಗಿ ರಚಿಸಲಾಗಿದೆ!",
        "ml": "🎉 യാത്ര പദ്ധതി വിജയകരമായി തയ്യാറാക്കി!",
        "bn": "🎉 ভ্রমণ পরিকল্পনা সফলভাবে তৈরি!",
        "gu": "🎉 પ્રવાસ યોજના સફળતાપૂર્વક તૈયાર!",
        "pa": "🎉 ਯਾਤਰਾ ਯੋਜਨਾ ਸਫਲਤਾਪੂਰਵਕ ਤਿਆਰ!",
    },
    "msg_goodbye": {
        "en": "👋 Goodbye! Happy Journey! 🌍",
        "hi": "👋 अलविदा! शुभ यात्रा! 🌍",
        "mr": "👋 निरोप! शुभ प्रवास! 🌍",
        "ta": "👋 விடை! இனிய பயணம்! 🌍",
        "te": "👋 వీడ్కోలు! శుభ యాత్ర! 🌍",
        "kn": "👋 ವಿದಾಯ! ಶುಭ ಪ್ರಯಾಣ! 🌍",
        "ml": "👋 വിടവാങ്ങൽ! ശുഭ യാത്ര! 🌍",
        "bn": "👋 বিদায়! শুভ যাত্রা! 🌍",
        "gu": "👋 ગુડબાય! શુભ પ્રવાસ! 🌍",
        "pa": "👋 ਅਲਵਿਦਾ! ਸ਼ੁਭ ਯਾਤਰਾ! 🌍",
    },
    "msg_budget_exceeded": {
        "en": "⚠️ Budget exceeded! Try a cheaper hotel or reduce travel days.",
        "hi": "⚠️ बजट पार! सस्ता होटल चुनें या दिन घटाएं।",
        "mr": "⚠️ बजेट ओलांडले! स्वस्त हॉटेल निवडा किंवा दिवस कमी करा.",
        "ta": "⚠️ பட்ஜெட் மீறியது! மலிவான ஹோட்டல் தேர்ந்தெடுக்கவும்.",
        "te": "⚠️ బడ్జెట్ మించిపోయింది! చౌక హోటల్ ఎంచుకోండి.",
        "kn": "⚠️ ಬಜೆಟ್ ಮೀರಿದೆ! ಅಗ್ಗದ ಹೋಟೆಲ್ ಆರಿಸಿ.",
        "ml": "⚠️ ബഡ്ജറ്റ് കവിഞ്ഞു! വിലകുറഞ്ഞ ഹോട്ടൽ തിരഞ്ഞെടുക്കൂ.",
        "bn": "⚠️ বাজেট ছাড়িয়ে গেছে! সস্তা হোটেল বেছে নিন।",
        "gu": "⚠️ બજેટ ઓળંગ્યું! સસ્તી હોટેલ પસંદ કરો.",
        "pa": "⚠️ ਬਜਟ ਵੱਧ ਗਿਆ! ਸਸਤਾ ਹੋਟਲ ਚੁਣੋ।",
    },
}


def ui(key, lang):
    """Return the UI string for a given key in the given language (fallback: English)."""
    return UI_STRINGS.get(key, {}).get(lang) or UI_STRINGS.get(key, {}).get("en", key)


class IndianLanguageTranslator:
    def __init__(self):
        self.languages = {
            "en": "English",
            "hi": "Hindi",
            "mr": "Marathi",
            "ta": "Tamil",
            "te": "Telugu",
            "kn": "Kannada",
            "ml": "Malayalam",
            "bn": "Bengali",
            "gu": "Gujarati",
            "pa": "Punjabi",
        }

    # 🌍 Detect language
    def detect_language(self, text):
        try:
            return detect(text)
        except:
            return "en"

    # 🔄 Translate text
    def translate(self, text, source="auto", target="en"):
        try:
            return GoogleTranslator(source=source, target=target).translate(text)
        except Exception as e:
            return f"Error: {str(e)}"

    # 🔁 Auto 2-way translation
    def auto_translate(self, text):
        detected_lang = self.detect_language(text)
        if detected_lang == "en":
            return {
                "direction": "English → Indian Language",
                "message": "Please choose a target language",
            }
        translated = self.translate(text, source="auto", target="en")
        return {
            "detected_language": detected_lang,
            "translated_to_english": translated,
        }

    # 🔁 Manual translation
    def manual_translate(self, text, target_lang):
        return self.translate(text, source="auto", target=target_lang)

    # 🖨️ Bilingual input helper
    def bilingual_input(self, key, lang):
        """
        Show the prompt in the chosen language AND English (if different),
        read user input, auto-detect & translate to English if needed.
        Returns (raw_input, english_value).
        """
        prompt_native  = ui(key, lang)
        prompt_english = ui(key, "en")

        if lang != "en":
            full_prompt = f"{prompt_native}\n   ({prompt_english})"
        else:
            full_prompt = prompt_native

        raw = input(full_prompt).strip()
        if not raw:
            return raw, raw

        detected = self.detect_language(raw)
        if detected != "en":
            english = self.translate(raw, source="auto", target="en")
            print(f"  ✅ [{detected.upper()} → EN] {english}")
            return raw, english.strip().title()
        return raw, raw.strip().title()

    # 🖨️ Print a UI message in chosen language
    def say(self, key, lang, **kwargs):
        """Print a UI message in the chosen language."""
        msg = ui(key, lang)
        if kwargs:
            try:
                msg = msg.format(**kwargs)
            except Exception:
                pass
        print(msg)


# ==============================
# 🎯 STANDALONE CLI
# ==============================

def run_translator():
    translator = IndianLanguageTranslator()

    print("\n===================================")
    print("  INDIAN LANGUAGE TRANSLATOR 🇮🇳")
    print("===================================\n")

    while True:
        print("\n1. Auto Detect → Translate to English")
        print("2. English → Indian Language")
        print("3. Indian Language → Another Language")
        print("4. Exit")

        choice = input("\nChoose option: ")

        if choice == "1":
            text   = input("\nEnter text: ")
            result = translator.auto_translate(text)
            print("\n--- Result ---")
            print("Detected Language:", result.get("detected_language"))
            print("English:", result.get("translated_to_english"))

        elif choice == "2":
            text = input("\nEnter English text: ")
            print("\nAvailable Languages:")
            for code, name in translator.languages.items():
                if code != "en":
                    print(f"  {code} → {name}")
            target = input("\nEnter language code: ")
            result = translator.manual_translate(text, target)
            print("\n--- Result ---")
            print("Translated:", result)

        elif choice == "3":
            text = input("\nEnter text: ")
            print("\nAvailable Languages:")
            for code, name in translator.languages.items():
                print(f"  {code} → {name}")
            target = input("\nEnter target language code: ")
            result = translator.manual_translate(text, target)
            print("\n--- Result ---")
            print("Translated:", result)

        elif choice == "4":
            print("\n👋 Exiting Translator")
            break

        else:
            print("❌ Invalid choice")


if __name__ == "__main__":
    run_translator()