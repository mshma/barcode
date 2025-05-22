import os
import uuid
import pandas as pd
import barcode
from barcode.writer import ImageWriter
from barcode import Code128
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Image as ReportLabImage, Table, TableStyle
from reportlab.lib.units import cm
from flask import Blueprint, request, jsonify, current_app, send_from_directory

# إنشاء blueprint للتعامل مع طلبات الرفع
upload_bp = Blueprint('upload', __name__)

# مسار حفظ الملفات المؤقتة
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads')
BARCODES_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'barcodes')
PDF_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'pdfs')

# التأكد من وجود المجلدات
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(BARCODES_FOLDER, exist_ok=True)
os.makedirs(PDF_FOLDER, exist_ok=True)

@upload_bp.route('/upload', methods=['POST'])
def upload_file():
    """
    نقطة نهاية API لرفع ملف إكسل ومعالجته وتوليد الباركودات وملف PDF
    """
    try:
        # التحقق من وجود ملف في الطلب
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'لم يتم تحديد ملف'}), 400
        
        file = request.files['file']
        
        # التحقق من أن الملف له اسم
        if file.filename == '':
            return jsonify({'success': False, 'error': 'لم يتم تحديد ملف'}), 400
        
        # التحقق من امتداد الملف
        if not file.filename.endswith(('.xlsx', '.xls')):
            return jsonify({'success': False, 'error': 'يرجى رفع ملف إكسل صالح (.xlsx أو .xls)'}), 400
        
        # إنشاء اسم فريد للملف
        unique_id = str(uuid.uuid4())
        excel_filename = f"{unique_id}_{file.filename}"
        excel_path = os.path.join(UPLOAD_FOLDER, excel_filename)
        
        # حفظ الملف
        file.save(excel_path)
        
        # معالجة ملف الإكسل
        try:
            df = pd.read_excel(excel_path)
            
            # التحقق من وجود بيانات في الملف
            if df.empty:
                return jsonify({'success': False, 'error': 'ملف الإكسل فارغ'}), 400
            
            # التحقق من وجود عمودين على الأقل
            if df.shape[1] < 2:
                return jsonify({'success': False, 'error': 'يجب أن يحتوي ملف الإكسل على عمودين على الأقل (الرقم والعنوان)'}), 400
            
            # استخراج البيانات
            data = []
            for _, row in df.iterrows():
                # استخدام العمودين الأول والثاني بغض النظر عن أسمائهما
                item_number = str(row.iloc[0])
                item_name = str(row.iloc[1])
                data.append((item_number, item_name))
            
            # توليد الباركودات
            barcode_paths = generate_barcodes(data, unique_id)
            
            # إنشاء ملف PDF
            pdf_filename = f"barcodes_{unique_id}.pdf"
            pdf_path = os.path.join(PDF_FOLDER, pdf_filename)
            create_pdf(barcode_paths, pdf_path)
            
            # إرجاع رابط التنزيل
            return jsonify({
                'success': True, 
                'pdf_url': f'/download/{pdf_filename}',
                'filename': f'barcodes.pdf'
            })
            
        except Exception as e:
            return jsonify({'success': False, 'error': f'خطأ في معالجة ملف الإكسل: {str(e)}'}), 500
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'حدث خطأ: {str(e)}'}), 500

@upload_bp.route('/download/<filename>', methods=['GET'])
def download_file(filename):
    """
    نقطة نهاية API لتنزيل ملف PDF
    """
    return send_from_directory(PDF_FOLDER, filename, as_attachment=True)

def generate_barcodes(data, unique_id):
    """
    توليد الباركودات لكل مدخل وحفظها كصور
    """
    barcode_paths = []
    
    for i, (item_number, item_name) in enumerate(data):
        # إنشاء صورة فارغة
        img_width = 400
        img_height = 200
        img = Image.new('RGB', (img_width, img_height), color='white')
        draw = ImageDraw.Draw(img)
        
        # إضافة النص (العنوان والرقم)
        try:
            # محاولة استخدام خط عربي إذا كان متوفراً
            font = ImageFont.truetype("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", 14)
        except:
            # استخدام الخط الافتراضي إذا لم يكن الخط العربي متوفراً
            font = ImageFont.load_default()
        
        # كتابة العنوان والرقم
        draw.text((10, 10), item_name, fill='black', font=font)
        draw.text((10, 30), item_number, fill='black', font=font)
        
        # إنشاء الباركود
        barcode_class = Code128(item_number, writer=ImageWriter())
        barcode_filename = f'{BARCODES_FOLDER}/barcode_{unique_id}_{i}'
        barcode_path = barcode_class.save(barcode_filename)
        
        # فتح صورة الباركود ودمجها مع الصورة الرئيسية
        barcode_img = Image.open(barcode_path)
        barcode_img = barcode_img.resize((350, 100))  # تغيير حجم الباركود
        
        # لصق الباركود في الصورة
        img.paste(barcode_img, (25, 70))
        
        # حفظ الصورة النهائية
        label_path = f'{BARCODES_FOLDER}/label_{unique_id}_{i}.png'
        img.save(label_path)
        barcode_paths.append(label_path)
    
    return barcode_paths

def create_pdf(barcode_paths, pdf_path):
    """
    إنشاء ملف PDF يحتوي على الباركودات بتنسيق مشابه للملف المرجعي
    """
    # إنشاء ملف PDF
    doc = SimpleDocTemplate(pdf_path, pagesize=A4)
    elements = []
    
    # تحديد عدد الأعمدة والصفوف في الصفحة (4 أعمدة كما في المرجع)
    cols = 4
    
    # تجهيز مصفوفة الصور للجدول
    table_data = []
    row_data = []
    
    # إضافة الصور إلى الجدول
    for i, img_path in enumerate(barcode_paths):
        # التأكد من وجود الصورة
        if os.path.exists(img_path):
            # تحميل الصورة وتغيير حجمها
            img = ReportLabImage(img_path, width=4*cm, height=2*cm)
            row_data.append(img)
            
            # إذا اكتمل الصف، أضفه إلى الجدول وابدأ صفًا جديدًا
            if len(row_data) == cols:
                table_data.append(row_data)
                row_data = []
        
        # إذا وصلنا إلى نهاية البيانات ولم يكتمل الصف، أضف خلايا فارغة
        if i == len(barcode_paths) - 1 and row_data:
            while len(row_data) < cols:
                row_data.append('')
            table_data.append(row_data)
    
    # إنشاء الجدول
    if table_data:
        table = Table(table_data, colWidths=[4.5*cm]*cols, rowHeights=[2.2*cm]*len(table_data))
        
        # تطبيق نمط الجدول
        table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ]))
        
        elements.append(table)
    
    # إنشاء ملف PDF
    doc.build(elements)
    
    return pdf_path
