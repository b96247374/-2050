#!/bin/bash
# ملف تشغيل نظام التقارير الإدارية

echo "بدء تشغيل نظام التقارير الإدارية..."

# التأكد من وجود البيئة الافتراضية
if [ ! -d "venv" ]; then
    echo "إنشاء البيئة الافتراضية..."
    python3 -m venv venv
fi

# تفعيل البيئة الافتراضية
source venv/bin/activate

# تثبيت التبعيات إذا لم تكن مثبتة
echo "فحص وتثبيت التبعيات..."
pip install -q Flask ummalqura Pillow Werkzeug

# تشغيل التطبيق
echo "تشغيل التطبيق على http://localhost:11000"
echo "للدخول للنظام استخدم:"
echo "اسم المستخدم: admin"
echo "كلمة المرور: password123"
echo "لإيقاف النظام اضغط Ctrl+C"

python app.py