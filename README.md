# IOA — Institute Outreach Automation

أتمتة التواصل مع المعاهد التدريبية عبر WhatsApp Web، مع موافقات فردية عن بُعد عبر بوت تليجرام.

نظام سطح مكتب يعمل محلياً على نظام Windows، بدون خادم سحابي دائم.

## الميزات الرئيسية

- قراءة بيانات المعاهد من ملفات Excel (.xlsx) مع كشف تلقائي للأعمدة (يدعم العربية والإنجليزية)
- قراءة قالب الرسالة من ملف TXT واستبدال `{{institute_name}}` فقط
- استخدام ملف تعريف كروم الثابت **Profile 40** فقط (لا غيرها)
- موافقات فردية لكل معهد عبر بوت تليجرام (أوامر: /start, /status, /pause, /resume, /next, /skip, /help)
- جدولة الإرسال بتوقيت Asia/Aden
- قاعدة بيانات SQLite محلية للتخزين الأولي (local-first)
- لوحة تحكم سطح مكتب احترافية بلغة العربية والإنجليزية (PySide6)
- سجلات أنشطة وأخطاء تفصيلية

## هيكل المشروع

```
IOA/
├── main.py                      # نقطة دخول التطبيق
├── requirements.txt             # تبعيات بايثون
├── .env.example                 # نموذج إعدادات environment (تُنسخ إلى .env محلياً)
├── .gitignore
├── build_windows.bat            # سكريبت بناء ملف تنفيذي لنظام Windows
├── pyinstaller.spec             # إعدادات PyInstaller
├── config/
│   └── settings.py              # إعدادات التطبيق (بما في ذلك مسار Profile 40 الثابت)
├── core/
│   ├── campaign_manager.py      # إدارة الحملات
│   ├── contact_manager.py       # إدارة جهات الاتصال
│   ├── message_engine.py        # محرك الرسائل
│   ├── approval_manager.py      # إدارة الموافقات عبر تليجرام
│   ├── scheduler.py             # المجدول المحلي
│   └── execution_manager.py     # إدارة التنفيذ والإرسال
├── integrations/
│   ├── whatsapp/
│   │   ├── browser_manager.py   # إدارة متصفح كروم وملف التعريف
│   │   ├── chrome_profile_manager.py  # إدارة ملف تعريف كروم 40
│   │   ├── whatsapp_client.py   # عميل واتساب ويب
│   │   └── message_sender.py    # إرسال الرسائل والتحقق من结果
│   └── telegram/
│       ├── bot.py               # بوت تليجرام
│       ├── notifications.py     # الإشعارات عبر تليجرام
│       └── approval_handlers.py # معالجات الموافقات
├── data/
│   ├── database.py              # طبقة SQLite
│   ├── excel_manager.py         # مدير ملفات Excel
│   ├── backup_manager.py        # مدير النسخ الاحتياطية
│   └── models.py                # نماذج البيانات
├── ui/
│   ├── main_window.py           # النافذة الرئيسية
│   ├── dashboard.py             # لوحة التحكم
│   ├── contacts_view.py         # عرض جهات الاتصال
│   ├── campaign_view.py         # عرض الحملات
│   ├── settings_view.py         # شاشة الإعدادات
│   └── logs_view.py             # عرض السجلات
├── tests/                       # اختبارات تلقائية
├── logs/                        # سجلات التشغيل
├── storage/
│   ├── backups/                 # نسخ احتياطية من Excel
│   └── database/                # قاعدة بيانات SQLite
└── dist/                        # ملفات البناء النهائية
```

## المتطلبات الأولية (Windows)

- نظام تشغيل Windows 10 أو أحدث
- Python 3.11+ (مضمن في ملف التنصيب)
- جوجل كروم مثبت مع ملف تعريف "Profile 40" موجود at:
  `C:\Users\USERW\AppData\Local\Google\Chrome\User Data\Profile 40`
- حساب واتساب موثق في ملف التعريف 40
- اتصال إنترنت لإرسال الرسائل وتشغيل بوت تليجرام

## التثبيت والاستخدام

راجع ملف `INSTALL.md` لتعليمات التثبيت التفصيلية، وملف `USER_MANUAL.md` لدليل المستخدم.

## إعداد تليجرام

1. أنشئ بوت عبر @BotFather واحصل على توكن البوت.
2. احصل على معرف الدردشة (Chat ID) للمستخدم المخول.
3. أنشئ ملف `.env` في مجلد التثبيت وضع فيه:
   - `IOA_TELEGRAM_BOT_TOKEN`
   - `IOA_TELEGRAM_CHAT_ID`

## ملاحظات هامة

- لا تُرسل أي رسالة دون موافقة فردية صريحة من خلال تليجرام.
- يستخدم التطبيق حصراً ملف تعريف كروم "Profile 40" المحدد.
- لا يُستخرج أو يُنسخ أي أسرار authenticate من متصفح المستخدم.
- جميع البيانات تبقى محلية على جهاز المستخدم (لا خادم سحابي).
- ملف `.env` لا يُرفق مع الكود المصدر ويبقى على جهاز المستخدم فقط.

## التطوير والاختبار

```bash
# إنشاء بيئة افتراضية وتثبيت التبعيات
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt

# تشغيل التطبيق
python main.py

# تشغيل الاختبارات
.venv\Scripts\pytest tests/
```

## بناء نسخة Windows (EXE)

```bash
build_windows.bat
```

يُنتج ملف `dist/IOA.exe` مع جميع الموارد اللازمة.

## معايير القبول

يحتوي هذا المشروع على 모든 متطلبات ملف المواصفات `IOA.md`، مع تمييز واضح بين الميزات المختبرة في بيئة التطوير السحابية (via Mocks) والميزات التي تتطلب التحقق على جهاز Windows محلي (واتساب الحقيقي، ملف تعريف 40).
