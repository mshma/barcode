import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))  # DON'T CHANGE THIS !!!

from flask import Flask, render_template, send_from_directory

# استيراد blueprints
from src.routes.upload import upload_bp

# إنشاء تطبيق Flask
app = Flask(__name__)

# تسجيل blueprints
app.register_blueprint(upload_bp)

# تعيين مجلد الملفات الثابتة
app.static_folder = 'static'

# الصفحة الرئيسية
@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')

# تشغيل التطبيق
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
