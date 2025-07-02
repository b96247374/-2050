from flask import Flask, render_template, request, redirect, url_for, session, jsonify, g, flash
from ummalqura.hijri_date import HijriDate
from datetime import datetime
import sqlite3
import os
import base64
import shutil
from io import BytesIO
from PIL import Image

app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.config['PORT'] = 11000

# بيانات مستخدم تجريبية
users = {
    "admin": "password123"
}

commander_info = {
    "name": "العقيد/ محمد بن عبدالله",
    "rank": "قائد قوة الواجب",
    "signature": "signature.png",  # ضع صورة التوقيع في static أو اجعلها None إذا لم توجد
    "visa": "visa.png"  # صورة تأشيرة القائد (إن وجدت)
}

# قائمة رتب الضباط
OFFICER_RANKS = [
    "ملازم", "ملازم أول", "نقيب", "رائد", "مقدم", "عقيد", "عميد", "لواء", "فريق"
]
# قائمة رتب الأفراد
ENLISTED_RANKS = [
    "جندي", "جندي أول", "عريف", "وكيل رقيب", "رقيب", "رقيب أول", "رئيس رقباء"
]

HIJRI_MONTHS = [
    '', 'محرم', 'صفر', 'ربيع الأول', 'ربيع الآخر', 'جمادى الأولى', 'جمادى الآخرة',
    'رجب', 'شعبان', 'رمضان', 'شوال', 'ذو القعدة', 'ذو الحجة'
]

# Backup utility functions
BACKUP_FILES = [
    'database.db',
    'logo.png',
    'signature.png',
    'visa.png',
]
BACKUP_DIR = 'backup'

def create_backup():
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_subdir = os.path.join(BACKUP_DIR, f'backup_{timestamp}')
    os.makedirs(backup_subdir)
    for file_path in BACKUP_FILES:
        if os.path.exists(file_path):
            shutil.copy(file_path, backup_subdir)
    return backup_subdir

def list_backups():
    if not os.path.exists(BACKUP_DIR):
        return []
    return sorted([
        d for d in os.listdir(BACKUP_DIR)
        if os.path.isdir(os.path.join(BACKUP_DIR, d))
    ], reverse=True)

def restore_backup(backup_name):
    backup_subdir = os.path.join(BACKUP_DIR, backup_name)
    restored = []
    for file_name in BACKUP_FILES:
        backup_file = os.path.join(backup_subdir, file_name)
        if os.path.exists(backup_file):
            shutil.copy(backup_file, file_name)
            restored.append(file_name)
    return restored

def init_daily_reports_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''
    CREATE TABLE IF NOT EXISTS daily_reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        name TEXT,
        rank TEXT,
        hijri_date TEXT,
        time TEXT,
        subject TEXT,
        accepted INTEGER,
        rejected INTEGER,
        total INTEGER,
        proof_image TEXT,
        status TEXT DEFAULT 'pending',
        rejection_reason TEXT
    )
    ''')
    # إضافة الحقول إذا لم تكن موجودة (للتوافق مع قواعد بيانات قديمة)
    try:
        c.execute("ALTER TABLE daily_reports ADD COLUMN status TEXT DEFAULT 'pending'")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE daily_reports ADD COLUMN rejection_reason TEXT")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()

def init_users_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        name TEXT,
        rank_type TEXT,
        rank TEXT,
        role TEXT,
        can_view_reports INTEGER DEFAULT 1,
        can_create_report INTEGER DEFAULT 1,
        can_manage_users INTEGER DEFAULT 0,
        can_manage_settings INTEGER DEFAULT 0
    )
    ''')
    # إضافة الحقول إذا لم تكن موجودة (للتوافق مع قواعد بيانات قديمة)
    try:
        c.execute("ALTER TABLE users ADD COLUMN can_view_reports INTEGER DEFAULT 1")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE users ADD COLUMN can_create_report INTEGER DEFAULT 1")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE users ADD COLUMN can_manage_users INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE users ADD COLUMN can_manage_settings INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    # إضافة مستخدم admin افتراضي إذا لم يوجد
    c.execute('SELECT * FROM users WHERE username=?', ('admin',))
    if not c.fetchone():
        c.execute('INSERT INTO users (username, password, name, rank_type, rank, role, can_view_reports, can_create_report, can_manage_users, can_manage_settings) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                  ('admin', 'password123', 'العقيد/ محمد بن عبدالله', 'officer', 'عقيد', 'admin', 1, 1, 1, 1))
    conn.commit()
    conn.close()

def init_settings_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    ''')
    # إعداد القيم الافتراضية إذا لم تكن موجودة
    c.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', ('signature', 'signature.png'))
    c.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', ('visa', 'visa.png'))
    c.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', ('logo', 'logo.png'))
    c.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', ('ministry_name', 'وزارة الداخلية'))
    c.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', ('header_text', 'المملكة العربية السعودية'))
    c.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', ('footer_text', 'اسم القائد والرتبة والتوقيع'))
    conn.commit()
    conn.close()

def get_setting(key):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT value FROM settings WHERE key=?', (key,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def set_setting(key, value):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('REPLACE INTO settings (key, value) VALUES (?, ?)', (key, value))
    conn.commit()
    conn.close()

def get_global_settings():
    if not hasattr(g, 'global_settings'):
        g.global_settings = {
            'logo': get_setting('logo'),
            'ministry_name': get_setting('ministry_name'),
            'header_text': get_setting('header_text'),
            'footer_text': get_setting('footer_text'),
        }
    return g.global_settings

@app.context_processor
def inject_global_settings():
    return get_global_settings()

def init_handover_table_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS handover_table (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        receiver_name TEXT,
        start_time TEXT,
        end_time TEXT,
        violations_count INTEGER,
        notes TEXT
    )''')
    # إضافة الأعمدة الجديدة إذا لم تكن موجودة (للتوافق مع قواعد بيانات قديمة)
    try:
        c.execute("ALTER TABLE handover_table ADD COLUMN start_time TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE handover_table ADD COLUMN end_time TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE handover_table ADD COLUMN violations_count INTEGER")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()

def init_violations_table_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS violations_table (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        military_name TEXT,
        violation_type TEXT,
        day_name TEXT,
        date TEXT,
        notes TEXT
    )''')
    # حذف الأعمدة القديمة إذا وجدت (offender_name)
    # لا يمكن حذف عمود في SQLite مباشرة، لكن سنهمل استخدامه في الكود
    conn.commit()
    conn.close()

def init_appreciation_letters_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS appreciation_letters (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        recipient_name TEXT,
        reason TEXT,
        date TEXT,
        notes TEXT
    )''')
    conn.commit()
    conn.close()

def init_permission_requests_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS permission_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        requester_name TEXT,
        permission_type TEXT,
        date TEXT,
        time TEXT,
        reason TEXT,
        notes TEXT
    )''')
    conn.commit()
    conn.close()

def init_leaves_table_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS leaves_table (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        rank TEXT,
        leave_type TEXT,
        start_date TEXT,
        end_date TEXT,
        notes TEXT
    )''')
    conn.commit()
    conn.close()

init_daily_reports_db()
init_users_db()
init_settings_db()
init_handover_table_db()
init_violations_table_db()
init_appreciation_letters_db()
init_permission_requests_db()
init_leaves_table_db()

# تحديث commander_info من قاعدة البيانات
commander_info['signature'] = get_setting('signature')
commander_info['visa'] = get_setting('visa')

# دالة جلب بيانات المستخدم الحالي
def get_current_user():
    if 'username' not in session:
        return None
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT username, name, rank_type, rank, role, can_view_reports, can_create_report, can_manage_users, can_manage_settings FROM users WHERE username=?', (session['username'],))
    user = c.fetchone()
    conn.close()
    if user:
        return {
            'username': user[0],
            'name': user[1],
            'rank_type': user[2],
            'rank': user[3],
            'role': user[4],
            'can_view_reports': bool(user[5]),
            'can_create_report': bool(user[6]),
            'can_manage_users': bool(user[7]),
            'can_manage_settings': bool(user[8])
        }
    return None

# تحديث تسجيل الدخول ليعتمد على قاعدة بيانات المستخدمين
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute('SELECT * FROM users WHERE username=? AND password=?', (username, password))
        user = c.fetchone()
        conn.close()
        if user:
            session['username'] = username
            session['show_monitoring_notice'] = True
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error="بيانات الدخول غير صحيحة")
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))
    show_monitoring_notice = session.pop('show_monitoring_notice', False)
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users WHERE can_create_report=1")
    active_users_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM handover_table")
    handovers_count = c.fetchone()[0]
    c.execute("SELECT * FROM daily_reports ORDER BY id DESC LIMIT 5")
    last_reports = c.fetchall()
    c.execute("SELECT COUNT(*) FROM daily_reports WHERE status = 'approved'")
    accepted_reports_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM daily_reports WHERE status = 'rejected'")
    rejected_reports_count = c.fetchone()[0]
    conn.close()
    signature = get_setting('signature')
    visa = get_setting('visa')
    commander_name = get_setting('commander_name')
    commander_rank = get_setting('commander_rank')
    my_reports_count = my_accepted_reports_count = my_rejected_reports_count = 0
    my_last_report_time = None
    if user['role'] == 'user':
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM daily_reports WHERE username=?", (user['username'],))
        my_reports_count = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM daily_reports WHERE username=? AND status='approved'", (user['username'],))
        my_accepted_reports_count = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM daily_reports WHERE username=? AND status='rejected'", (user['username'],))
        my_rejected_reports_count = c.fetchone()[0]
        c.execute("SELECT time FROM daily_reports WHERE username=? ORDER BY id DESC LIMIT 1", (user['username'],))
        last = c.fetchone()
        if last:
            my_last_report_time = last[0]
        conn.close()
    return render_template('dashboard.html', 
                         username=session['username'], 
                         user=user,
                         logo=get_setting('logo'),
                         ministry_name=get_setting('ministry_name'),
                         header_text=get_setting('header_text'),
                         commander_name=commander_name,
                         commander_rank=commander_rank,
                         commander_signature=signature,
                         commander_visa=visa,
                         signature=signature,
                         visa=visa,
                         show_monitoring_notice=show_monitoring_notice,
                         accepted_reports_count=accepted_reports_count,
                         rejected_reports_count=rejected_reports_count,
                         active_users_count=active_users_count,
                         handovers_count=handovers_count,
                         last_reports=last_reports,
                         my_reports_count=my_reports_count,
                         my_accepted_reports_count=my_accepted_reports_count,
                         my_rejected_reports_count=my_rejected_reports_count,
                         my_last_report_time=my_last_report_time)

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/create_daily_report', methods=['GET', 'POST'])
def create_daily_report():
    user = get_current_user()
    if not user or not user['can_create_report']:
        return redirect(url_for('login'))
    
    # إذا كان المستخدم قائد، يمكنه إنشاء تقرير نيابة عن مستخدم آخر
    can_create_for_others = user['role'] in ['admin', 'commander']
    selected_user = None
    
    if can_create_for_others and request.method == 'GET':
        # جلب قائمة المستخدمين للقائد لاختيار من يريد إنشاء تقرير له
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute('SELECT id, username, name, rank FROM users WHERE can_create_report = 1')
        users_list = c.fetchall()
        conn.close()
    
    username = user['username']
    name = user['name']
    rank = user['rank']
    
    # إذا كان القائد يريد إنشاء تقرير لشخص آخر
    if can_create_for_others and request.method == 'POST':
        selected_user_id = request.form.get('selected_user')
        if selected_user_id and selected_user_id != 'self':
            conn = sqlite3.connect('database.db')
            c = conn.cursor()
            c.execute('SELECT username, name, rank FROM users WHERE id = ?', (selected_user_id,))
            selected_user = c.fetchone()
            conn.close()
            if selected_user:
                username = selected_user[0]
                name = selected_user[1]
                rank = selected_user[2]
    
    now = datetime.now()
    hijri = HijriDate(now.year, now.month, now.day, gr=True)
    hijri_month_name = HIJRI_MONTHS[hijri.month]
    hijri_str = f"{hijri.day} {hijri_month_name} {hijri.year} هـ"
    time_str = now.strftime("%I:%M %p")
    
    if request.method == 'POST':
        # التحقق من الحقول المطلوبة
        subject = request.form.get('subject', '').strip()
        accepted_str = request.form.get('accepted', '')
        rejected_str = request.form.get('rejected', '')
        
        # التحقق من وجود الحقول المطلوبة
        if not subject:
            return render_template('create_daily_report.html', 
                                 name=name, 
                                 rank=rank, 
                                 hijri_date=hijri_str, 
                                 current_time=time_str, 
                                 username=username,
                                 user=user,
                                 can_create_for_others=can_create_for_others,
                                 users_list=users_list if can_create_for_others else None,
                                 commander_name=get_setting('commander_name'),
                                 commander_rank=get_setting('commander_rank'),
                                 commander_signature=get_setting('signature'),
                                 commander_visa=get_setting('visa'),
                                 logo=get_setting('logo'),
                                 ministry_name=get_setting('ministry_name'),
                                 header_text=get_setting('header_text'),
                                 error="يرجى إدخال موضوع التقرير")
        
        if not accepted_str or not rejected_str:
            return render_template('create_daily_report.html', 
                                 name=name, 
                                 rank=rank, 
                                 hijri_date=hijri_str, 
                                 current_time=time_str, 
                                 username=username,
                                 user=user,
                                 can_create_for_others=can_create_for_others,
                                 users_list=users_list if can_create_for_others else None,
                                 commander_name=get_setting('commander_name'),
                                 commander_rank=get_setting('commander_rank'),
                                 commander_signature=get_setting('signature'),
                                 commander_visa=get_setting('visa'),
                                 logo=get_setting('logo'),
                                 ministry_name=get_setting('ministry_name'),
                                 header_text=get_setting('header_text'),
                                 error="يرجى إدخال عدد المخالفات المقبولة والمرفوضة")
        
        try:
            accepted = int(accepted_str)
            rejected = int(rejected_str)
            if accepted < 0 or rejected < 0:
                raise ValueError("القيم يجب أن تكون موجبة")
        except ValueError:
            return render_template('create_daily_report.html', 
                                 name=name, 
                                 rank=rank, 
                                 hijri_date=hijri_str, 
                                 current_time=time_str, 
                                 username=username,
                                 user=user,
                                 can_create_for_others=can_create_for_others,
                                 users_list=users_list if can_create_for_others else None,
                                 commander_name=get_setting('commander_name'),
                                 commander_rank=get_setting('commander_rank'),
                                 commander_signature=get_setting('signature'),
                                 commander_visa=get_setting('visa'),
                                 logo=get_setting('logo'),
                                 ministry_name=get_setting('ministry_name'),
                                 header_text=get_setting('header_text'),
                                 error="يرجى إدخال أرقام صحيحة موجبة للمخالفات المقبولة والمرفوضة")
        
        total = accepted + rejected
        proof_image = None
        
        # التحقق من وجود صورة الإثبات
        if 'proof_image' not in request.files or not request.files['proof_image'].filename:
            return render_template('create_daily_report.html', 
                                 name=name, 
                                 rank=rank, 
                                 hijri_date=hijri_str, 
                                 current_time=time_str, 
                                 username=username,
                                 user=user,
                                 can_create_for_others=can_create_for_others,
                                 users_list=users_list if can_create_for_others else None,
                                 commander_name=get_setting('commander_name'),
                                 commander_rank=get_setting('commander_rank'),
                                 commander_signature=get_setting('signature'),
                                 commander_visa=get_setting('visa'),
                                 logo=get_setting('logo'),
                                 ministry_name=get_setting('ministry_name'),
                                 header_text=get_setting('header_text'),
                                 error="يرجى اختيار صورة الإثبات")
        
        file = request.files['proof_image']
        if file and file.filename:
            # التحقق من نوع الملف
            allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'bmp'}
            if '.' not in file.filename or file.filename.rsplit('.', 1)[1].lower() not in allowed_extensions:
                return render_template('create_daily_report.html', 
                                     name=name, 
                                     rank=rank, 
                                     hijri_date=hijri_str, 
                                     current_time=time_str, 
                                     username=username,
                                     user=user,
                                     can_create_for_others=can_create_for_others,
                                     users_list=users_list if can_create_for_others else None,
                                     commander_name=get_setting('commander_name'),
                                     commander_rank=get_setting('commander_rank'),
                                     commander_signature=get_setting('signature'),
                                     commander_visa=get_setting('visa'),
                                     logo=get_setting('logo'),
                                     ministry_name=get_setting('ministry_name'),
                                     header_text=get_setting('header_text'),
                                     error="يرجى اختيار ملف صورة صحيح (PNG, JPG, JPEG, GIF, BMP)")
            
            # التحقق من حجم الملف (أقل من 5 ميجابايت)
            file.seek(0, 2)  # الانتقال إلى نهاية الملف
            file_size = file.tell()
            file.seek(0)  # العودة إلى بداية الملف
            
            if file_size > 5 * 1024 * 1024:  # 5 ميجابايت
                return render_template('create_daily_report.html', 
                                     name=name, 
                                     rank=rank, 
                                     hijri_date=hijri_str, 
                                     current_time=time_str, 
                                     username=username,
                                     user=user,
                                     can_create_for_others=can_create_for_others,
                                     users_list=users_list if can_create_for_others else None,
                                     commander_name=get_setting('commander_name'),
                                     commander_rank=get_setting('commander_rank'),
                                     commander_signature=get_setting('signature'),
                                     commander_visa=get_setting('visa'),
                                     logo=get_setting('logo'),
                                     ministry_name=get_setting('ministry_name'),
                                     header_text=get_setting('header_text'),
                                     error="حجم الملف يجب أن يكون أقل من 5 ميجابايت")
            
            filename = f"proof_{int(datetime.timestamp(now))}_{file.filename}"
            filepath = os.path.join('static', filename)
            file.save(filepath)
            proof_image = filename
        
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute('''INSERT INTO daily_reports (username, name, rank, hijri_date, time, subject, accepted, rejected, total, proof_image, status)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                  (username, name, rank, hijri_str, time_str, subject, accepted, rejected, total, proof_image, 'pending'))
        conn.commit()
        conn.close()
        
        # إضافة رسالة نجاح في الجلسة
        if user['role'] not in ['admin', 'commander']:
            session['success_message'] = 'تم إرسال التقرير بنجاح!'
            return redirect(url_for('create_daily_report'))
        
        # توجيه المستخدم إلى صفحة مناسبة حسب دوره
        if user['role'] == 'admin':
            return redirect(url_for('daily_reports'))
        elif user['role'] == 'commander':
            return redirect(url_for('daily_reports'))
        else:
            return redirect(url_for('my_reports'))
    
    return render_template('create_daily_report.html', 
                         name=name, 
                         rank=rank, 
                         hijri_date=hijri_str, 
                         current_time=time_str, 
                         username=username,
                         user=user,
                         can_create_for_others=can_create_for_others,
                         users_list=users_list if can_create_for_others else None,
                         commander_name=get_setting('commander_name'),
                         commander_rank=get_setting('commander_rank'),
                         commander_signature=get_setting('signature'),
                         commander_visa=get_setting('visa'),
                         logo=get_setting('logo'),
                         ministry_name=get_setting('ministry_name'),
                         header_text=get_setting('header_text'))

@app.route('/daily_reports')
def daily_reports():
    user = get_current_user()
    if not user or not user['can_view_reports']:
        return redirect(url_for('login'))
    # السماح للقائد وadmin
    if user['role'] not in ['commander', 'admin']:
        return redirect(url_for('dashboard'))
    status_filter = request.args.get('status', 'all')
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    if status_filter and status_filter != 'all':
        c.execute('SELECT id, username, name, rank, hijri_date, time, subject, accepted, rejected, total, proof_image, status, rejection_reason FROM daily_reports WHERE status=? ORDER BY id DESC', (status_filter,))
    else:
        c.execute('SELECT id, username, name, rank, hijri_date, time, subject, accepted, rejected, total, proof_image, status, rejection_reason FROM daily_reports ORDER BY id DESC')
    reports = c.fetchall()
    conn.close()
    return render_template(
        'daily_reports.html',
        reports=reports,
        username=user['username'],
        commander_name=get_setting('commander_name'),
        commander_rank=get_setting('commander_rank'),
        commander_signature=get_setting('signature'),
        commander_visa=get_setting('visa'),
        logo=get_setting('logo'),
        ministry_name=get_setting('ministry_name'),
        header_text=get_setting('header_text'),
        footer_text=get_setting('footer_text'),
        status_filter=status_filter
    )

@app.route('/signature_pad', methods=['GET', 'POST'])
def signature_pad():
    if 'username' not in session or session['username'] != 'admin':
        return redirect(url_for('login'))
    if request.method == 'POST':
        import base64
        from io import BytesIO
        from PIL import Image
        data_url = request.form['signature_data']
        header, encoded = data_url.split(',', 1)
        data = base64.b64decode(encoded)
        img = Image.open(BytesIO(data))
        filename = f"signature_{session['username']}.png"
        filepath = os.path.join('static', filename)
        img.save(filepath)
        commander_info['signature'] = filename
        set_setting('signature', filename)
        return jsonify({'success': True, 'filename': filename})
    return render_template('signature_pad.html', username=session['username'])

@app.route('/visa_pad', methods=['GET', 'POST'])
def visa_pad():
    if 'username' not in session or session['username'] != 'admin':
        return redirect(url_for('login'))
    if request.method == 'POST':
        import base64
        from io import BytesIO
        from PIL import Image
        data_url = request.form['visa_data']
        header, encoded = data_url.split(',', 1)
        data = base64.b64decode(encoded)
        img = Image.open(BytesIO(data))
        filename = f"visa_{session['username']}.png"
        filepath = os.path.join('static', filename)
        img.save(filepath)
        commander_info['visa'] = filename
        set_setting('visa', filename)
        return jsonify({'success': True, 'filename': filename})
    return render_template('visa_pad.html', username=session['username'])

# صفحة إدارة المستخدمين (للمدير فقط)
@app.route('/users')
def users():
    user = get_current_user()
    if not user or not (user['role'] in ['admin', 'officer', 'commander'] or user['can_manage_users']):
        return redirect(url_for('login'))
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT id, username, name, rank_type, rank, role FROM users')
    users_list = c.fetchall()
    conn.close()
    return render_template('users.html', users=users_list, officer_ranks=OFFICER_RANKS, enlisted_ranks=ENLISTED_RANKS, user=user)

# إضافة مستخدم جديد (للمدير فقط)
@app.route('/add_user', methods=['GET', 'POST'])
def add_user():
    user = get_current_user()
    if not user or user['role'] != 'admin':
        return redirect(url_for('login'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        name = request.form.get('name')
        rank_type = request.form.get('rank_type')
        rank = request.form.get('rank')
        role = request.form.get('role')
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        try:
            c.execute('INSERT INTO users (username, password, name, rank_type, rank, role) VALUES (?, ?, ?, ?, ?, ?)',
                      (username, password, name, rank_type, rank, role))
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            return render_template('add_user.html', error="اسم المستخدم مستخدم مسبقاً!", user=user, officer_ranks=OFFICER_RANKS, enlisted_ranks=ENLISTED_RANKS)
        conn.close()
        return redirect(url_for('users'))
    # في حالة GET أو أي حالة أخرى
    return render_template('add_user.html', user=user, officer_ranks=OFFICER_RANKS, enlisted_ranks=ENLISTED_RANKS)

# حذف مستخدم (للمدير فقط)
@app.route('/delete_user/<int:user_id>')
def delete_user(user_id):
    user = get_current_user()
    if not user or user['role'] != 'admin':
        return redirect(url_for('login'))
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('DELETE FROM users WHERE id=?', (user_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('users'))

@app.route('/approve_report/<int:report_id>')
def approve_report(report_id):
    user = get_current_user()
    if not user or user['role'] != 'admin':
        return redirect(url_for('login'))
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('UPDATE daily_reports SET status=? WHERE id=?', ('approved', report_id))
    conn.commit()
    conn.close()
    return redirect(url_for('daily_reports'))

@app.route('/reject_report/<int:report_id>', methods=['GET', 'POST'])
def reject_report(report_id):
    user = get_current_user()
    if not user or user['role'] != 'admin':
        return redirect(url_for('login'))
    if request.method == 'POST':
        reason = request.form.get('rejection_reason', '')
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute('UPDATE daily_reports SET status=?, rejection_reason=? WHERE id=?', ('rejected', reason, report_id))
        conn.commit()
        conn.close()
        return redirect(url_for('daily_reports'))
    return render_template('reject_report.html', report_id=report_id)

@app.route('/delete_report/<int:report_id>')
def delete_report(report_id):
    user = get_current_user()
    if not user or user['role'] not in ['admin', 'commander']:
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    # الحصول على معلومات التقرير قبل الحذف
    c.execute('SELECT proof_image FROM daily_reports WHERE id=?', (report_id,))
    report = c.fetchone()
    
    if report and report[0]:
        # حذف ملف الصورة من المجلد
        try:
            image_path = os.path.join('static', report[0])
            if os.path.exists(image_path):
                os.remove(image_path)
        except:
            pass  # تجاهل الأخطاء في حذف الملف
    
    # حذف التقرير من قاعدة البيانات
    c.execute('DELETE FROM daily_reports WHERE id=?', (report_id,))
    conn.commit()
    conn.close()
    
    # إضافة رسالة نجاح
    session['success_message'] = "تم حذف التقرير بنجاح!"
    
    return redirect(url_for('daily_reports'))

@app.route('/delete_multiple_reports', methods=['POST'])
def delete_multiple_reports():
    user = get_current_user()
    if not user or user['role'] != 'admin':
        return jsonify({'success': False, 'error': 'غير مصرح لك بهذا الإجراء'})
    
    try:
        report_ids_str = request.form.get('report_ids', '')
        if not report_ids_str:
            return jsonify({'success': False, 'error': 'لم يتم تحديد أي تقارير'})
        
        # تحويل السلسلة إلى قائمة من الأرقام
        report_ids = [int(id.strip()) for id in report_ids_str.split(',') if id.strip().isdigit()]
        
        if not report_ids:
            return jsonify({'success': False, 'error': 'معرفات التقارير غير صحيحة'})
        
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        
        # الحصول على معلومات التقارير قبل الحذف
        c.execute('SELECT id, proof_image FROM daily_reports WHERE id IN ({})'.format(','.join('?' * len(report_ids))), report_ids)
        reports_to_delete = c.fetchall()
        
        deleted_count = 0
        for report_id, proof_image in reports_to_delete:
            # حذف التقرير من قاعدة البيانات
            c.execute('DELETE FROM daily_reports WHERE id = ?', (report_id,))
            
            # حذف ملف الصورة إذا كان موجوداً
            if proof_image:
                try:
                    os.remove(os.path.join('static', proof_image))
                except FileNotFoundError:
                    pass  # الملف غير موجود، لا مشكلة
            
            deleted_count += 1
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True, 
            'message': f'تم حذف {deleted_count} تقرير بنجاح',
            'deleted_count': deleted_count
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'حدث خطأ أثناء حذف التقارير: {str(e)}'})

@app.route('/archive')
def archive():
    user = get_current_user()
    if not user or user['role'] not in ['admin', 'commander']:
        return redirect(url_for('login'))
    
    search_query = request.args.get('search', '')
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    if search_query:
        # البحث في التقارير
        c.execute('''SELECT id, name, rank, hijri_date, time, subject, accepted, rejected, total, proof_image, status, rejection_reason 
                     FROM daily_reports 
                     WHERE name LIKE ? OR subject LIKE ? OR username LIKE ?
                     ORDER BY id DESC''', 
                  (f'%{search_query}%', f'%{search_query}%', f'%{search_query}%'))
    else:
        # عرض جميع التقارير
        c.execute('SELECT id, name, rank, hijri_date, time, subject, accepted, rejected, total, proof_image, status, rejection_reason FROM daily_reports ORDER BY id DESC')
    
    reports = c.fetchall()
    conn.close()
    
    return render_template('archive.html',
                         reports=reports,
                         search_query=search_query,
                         username=user['username'],
                         user=user,
                         commander_name=get_setting('commander_name'),
                         commander_rank=get_setting('commander_rank'),
                         commander_signature=get_setting('signature'),
                         commander_visa=get_setting('visa'),
                         logo=get_setting('logo'),
                         ministry_name=get_setting('ministry_name'),
                         header_text=get_setting('header_text'))

# صفحة إعدادات النظام (للمدير فقط)
@app.route('/settings', methods=['GET', 'POST'])
def settings():
    user = get_current_user()
    if not user or not (user['role'] in ['admin', 'officer', 'commander'] or user['can_manage_settings']):
        return redirect(url_for('login'))
    if request.method == 'POST':
        ministry_name = request.form.get('ministry_name')
        header_text = request.form.get('header_text')
        footer_text = request.form.get('footer_text')
        set_setting('ministry_name', ministry_name)
        set_setting('header_text', header_text)
        set_setting('footer_text', footer_text)
        # رفع شعار جديد إذا تم رفعه
        if 'logo' in request.files:
            file = request.files['logo']
            if file and file.filename:
                filename = f"logo_{int(datetime.timestamp(datetime.now()))}_{file.filename}"
                filepath = os.path.join('static', filename)
                file.save(filepath)
                set_setting('logo', filename)
        return redirect(url_for('settings'))
    # جلب القيم الحالية
    ministry_name = get_setting('ministry_name')
    header_text = get_setting('header_text')
    footer_text = get_setting('footer_text')
    logo = get_setting('logo')
    return render_template('settings.html', ministry_name=ministry_name, header_text=header_text, footer_text=footer_text, logo=logo, user=user)

# صفحة تعديل صلاحيات المستخدم (للمدير فقط)
@app.route('/edit_permissions/<int:user_id>', methods=['GET', 'POST'])
def edit_permissions(user_id):
    user = get_current_user()
    if not user or user['role'] != 'admin':
        return redirect(url_for('login'))
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    if request.method == 'POST':
        print(request.form)  # تشخيص استقبال البيانات من الفورم
        # دعم أخذ user_id من input hidden إذا كان موجودًا
        form_user_id = request.form.get('user_id')
        if form_user_id and str(form_user_id).isdigit():
            user_id = int(form_user_id)
        can_view_reports = 1 if request.form.get('can_view_reports') == 'on' else 0
        can_create_report = 1 if request.form.get('can_create_report') == 'on' else 0
        can_manage_users = 1 if request.form.get('can_manage_users') == 'on' else 0
        can_manage_settings = 1 if request.form.get('can_manage_settings') == 'on' else 0
        c.execute('''UPDATE users SET can_view_reports=?, can_create_report=?, can_manage_users=?, can_manage_settings=? WHERE id=?''',
                  (can_view_reports, can_create_report, can_manage_users, can_manage_settings, user_id))
        conn.commit()
        conn.close()
        return redirect(url_for('users'))
    c.execute('SELECT id, username, name, can_view_reports, can_create_report, can_manage_users, can_manage_settings FROM users WHERE id=?', (user_id,))
    u = c.fetchone()
    conn.close()
    return render_template('edit_permissions.html', u=u, user=user)

@app.route('/backup', methods=['POST'])
def backup():
    backup_path = create_backup()
    flash(f'تم إنشاء نسخة احتياطية في: {backup_path}', 'success')
    return redirect(url_for('settings'))

@app.route('/backups')
def backups():
    backups = list_backups()
    return render_template('backups.html', backups=backups)

@app.route('/restore_backup/<backup_name>', methods=['POST'])
def restore_backup_route(backup_name):
    restored = restore_backup(backup_name)
    flash(f'تمت استعادة النسخة الاحتياطية: {backup_name}', 'success')
    return redirect(url_for('settings'))

@app.route('/my_reports')
def my_reports():
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT id, name, rank, hijri_date, time, subject, accepted, rejected, total, proof_image, status, rejection_reason FROM daily_reports WHERE username=? ORDER BY id DESC', (user['username'],))
    reports = c.fetchall()
    conn.close()
    
    return render_template('my_reports.html', 
                         reports=reports, 
                         username=user['username'],
                         user=user,
                         commander_name=get_setting('commander_name'),
                         commander_rank=get_setting('commander_rank'),
                         commander_signature=get_setting('signature'),
                         commander_visa=get_setting('visa'),
                         logo=get_setting('logo'),
                         ministry_name=get_setting('ministry_name'),
                         header_text=get_setting('header_text'))

@app.route('/clear_success_message', methods=['POST'])
def clear_success_message():
    """حذف رسالة النجاح من الجلسة"""
    session.pop('success_message', None)
    return jsonify({'success': True})

@app.route('/get_user_permissions/<int:user_id>')
def get_user_permissions(user_id):
    user = get_current_user()
    if not user or user['role'] != 'admin':
        return jsonify({'error': 'غير مصرح'}), 403
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT id, username, name, rank, role, can_view_reports, can_create_report, can_manage_users, can_manage_settings FROM users WHERE id=?', (user_id,))
    u = c.fetchone()
    conn.close()
    if not u:
        return jsonify({'error': 'المستخدم غير موجود'}), 404
    return jsonify({
        'id': u[0],
        'username': u[1],
        'name': u[2],
        'rank': u[3],
        'role': u[4],
        'can_view_reports': bool(u[5]),
        'can_create_report': bool(u[6]),
        'can_manage_users': bool(u[7]),
        'can_manage_settings': bool(u[8])
    })

@app.route('/create_report', methods=['GET', 'POST'])
def create_report():
    user = get_current_user()
    if not user or not user['can_create_report']:
        return redirect(url_for('login'))
    if request.method == 'POST':
        subject = request.form.get('subject', '').strip()
        details = request.form.get('details', '').strip()
        accepted = int(request.form.get('accepted', 0))
        rejected = int(request.form.get('rejected', 0))
        total = accepted + rejected
        notes = request.form.get('notes', '').strip()
        attachment = None
        if 'attachment' in request.files and request.files['attachment'].filename:
            file = request.files['attachment']
            filename = f"comprehensive_{user['username']}_{file.filename}"
            filepath = os.path.join('static', filename)
            file.save(filepath)
            attachment = filename
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS comprehensive_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            subject TEXT,
            details TEXT,
            accepted INTEGER,
            rejected INTEGER,
            total INTEGER,
            attachment TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        c.execute('''INSERT INTO comprehensive_reports (username, subject, details, accepted, rejected, total, attachment, notes)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                  (user['username'], subject, details, accepted, rejected, total, attachment, notes))
        conn.commit()
        conn.close()
        return render_template('create_report.html', user=user, success=True)
    return render_template('create_report.html', user=user)

@app.route('/comprehensive_reports', methods=['GET', 'POST'])
def comprehensive_reports():
    user = get_current_user()
    if not user or (user['role'] != 'commander' and user['role'] != 'admin'):
        return redirect(url_for('login'))
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT id, username, name, rank, hijri_date, time, subject, accepted, rejected, total, proof_image, status, rejection_reason FROM daily_reports ORDER BY id DESC')
    reports = c.fetchall()
    conn.close()
    return render_template(
        'comprehensive_reports.html',
        reports=reports,
        user=user,
        username=user['username'],
        commander_name=get_setting('commander_name'),
        commander_rank=get_setting('commander_rank'),
        commander_signature=get_setting('signature'),
        commander_visa=get_setting('visa'),
        logo=get_setting('logo'),
        ministry_name=get_setting('ministry_name'),
        header_text=get_setting('header_text'),
        footer_text=get_setting('footer_text')
    )

@app.route('/my_comprehensive_reports')
def my_comprehensive_reports():
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''SELECT id, subject, details, accepted, rejected, total, attachment, notes, status, rejection_reason, created_at FROM comprehensive_reports WHERE username=? ORDER BY id DESC''', (user['username'],))
    reports = c.fetchall()
    conn.close()
    return render_template('my_comprehensive_reports.html', user=user, reports=reports)

@app.route('/manage_signature_visa', methods=['GET', 'POST'])
def manage_signature_visa():
    user = get_current_user()
    if not user or (user['role'] != 'commander' and user['role'] != 'admin'):
        return redirect(url_for('login'))
    signature = get_setting('signature')
    visa = get_setting('visa')
    commander_name = get_setting('commander_name') or ''
    commander_rank = get_setting('commander_rank') or ''
    msg = None
    if request.method == 'POST':
        import base64
        from io import BytesIO
        from PIL import Image
        if 'delete_signature' in request.form:
            if signature and os.path.exists(os.path.join('static', signature)):
                os.remove(os.path.join('static', signature))
            set_setting('signature', '')
            signature = ''
            msg = 'تم حذف التوقيع بنجاح.'
        elif 'delete_visa' in request.form:
            if visa and os.path.exists(os.path.join('static', visa)):
                os.remove(os.path.join('static', visa))
            set_setting('visa', '')
            visa = ''
            msg = 'تم حذف التأشيرة بنجاح.'
        else:
            # حفظ التوقيع المرسوم إذا وجد
            signature_drawn = request.form.get('signature_drawn', '')
            if signature_drawn and signature_drawn.startswith('data:image/png;base64,'):
                img_data = base64.b64decode(signature_drawn.split(',')[1])
                img = Image.open(BytesIO(img_data))
                img.save(os.path.join('static', 'signature_admin.png'))
                set_setting('signature', 'signature_admin.png')
                signature = 'signature_admin.png'
                msg = 'تم تحديث التوقيع بنجاح.'
            # حفظ التأشيرة المرسومة إذا وجدت
            visa_drawn = request.form.get('visa_drawn', '')
            if visa_drawn and visa_drawn.startswith('data:image/png;base64,'):
                img_data = base64.b64decode(visa_drawn.split(',')[1])
                img = Image.open(BytesIO(img_data))
                img.save(os.path.join('static', 'visa_admin.png'))
                set_setting('visa', 'visa_admin.png')
                visa = 'visa_admin.png'
                msg = 'تم تحديث التأشيرة بنجاح.'
            # رفع الملفات التقليدي
            if 'signature' in request.files and request.files['signature'].filename:
                file = request.files['signature']
                filename = f'signature_admin.png'
                filepath = os.path.join('static', filename)
                file.save(filepath)
                set_setting('signature', filename)
                signature = filename
                msg = 'تم تحديث التوقيع بنجاح.'
            if 'visa' in request.files and request.files['visa'].filename:
                file = request.files['visa']
                filename = f'visa_admin.png'
                filepath = os.path.join('static', filename)
                file.save(filepath)
                set_setting('visa', filename)
                visa = filename
                msg = 'تم تحديث التأشيرة بنجاح.'
            # إعدادات اسم القائد والرتبة
            commander_name = request.form.get('commander_name', '').strip()
            commander_rank = request.form.get('commander_rank', '').strip()
            set_setting('commander_name', commander_name)
            set_setting('commander_rank', commander_rank)
            msg = 'تم تحديث إعدادات القائد بنجاح.'
    return render_template('manage_signature_visa.html', user=user, signature=signature, visa=visa, msg=msg, commander_name=commander_name, commander_rank=commander_rank)

@app.route('/delete_comprehensive_report/<int:report_id>')
def delete_comprehensive_report(report_id):
    user = get_current_user()
    if not user or (user['role'] != 'commander' and user['role'] != 'admin'):
        return redirect(url_for('login'))
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('DELETE FROM comprehensive_reports WHERE id=?', (report_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('comprehensive_reports'))

@app.route('/comprehensive_report_print/<int:report_id>')
def comprehensive_report_print(report_id):
    user = get_current_user()
    if not user or (user['role'] != 'commander' and user['role'] != 'admin'):
        return redirect(url_for('login'))
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''SELECT id, username, subject, details, accepted, rejected, total, attachment, notes, status, rejection_reason, created_at FROM comprehensive_reports WHERE id=?''', (report_id,))
    report = c.fetchone()
    conn.close()
    if not report:
        return 'التقرير غير موجود', 404
    signature = get_setting('signature')
    visa = get_setting('visa')
    commander_name = get_setting('commander_name')
    commander_rank = get_setting('commander_rank')
    logo = get_setting('logo')
    ministry_name = get_setting('ministry_name')
    header_text = get_setting('header_text')
    datetime_now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return render_template('comprehensive_report_print.html', user=user, report=report, signature=signature, visa=visa, commander_name=commander_name, commander_rank=commander_rank, logo=logo, ministry_name=ministry_name, header_text=header_text, datetime_now=datetime_now)

@app.route('/handover_table', methods=['GET', 'POST'])
def handover_table():
    user = get_current_user()
    if not user or (user['role'] != 'commander' and user['role'] != 'admin'):
        return redirect(url_for('login'))
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    if request.method == 'POST':
        edit_id = request.form.get('edit_id', '').strip()
        receiver_name = request.form.get('receiver_name', '').strip()
        start_time = request.form.get('start_time', '').strip()
        end_time = request.form.get('end_time', '').strip()
        violations_count = request.form.get('violations_count', '').strip()
        notes = request.form.get('notes', '').strip()
        if edit_id:
            c.execute('UPDATE handover_table SET receiver_name=?, start_time=?, end_time=?, violations_count=?, notes=? WHERE id=?',
                      (receiver_name, start_time, end_time, violations_count, notes, edit_id))
            conn.commit()
        elif receiver_name and start_time and end_time and violations_count:
            c.execute('INSERT INTO handover_table (receiver_name, start_time, end_time, violations_count, notes) VALUES (?, ?, ?, ?, ?)',
                      (receiver_name, start_time, end_time, violations_count, notes))
            conn.commit()
    c.execute('SELECT id, receiver_name, start_time, end_time, violations_count, notes FROM handover_table ORDER BY id DESC')
    handovers = c.fetchall()
    conn.close()
    return render_template('handover_table.html', user=user, handovers=handovers)

@app.route('/delete_handover/<int:handover_id>')
def delete_handover(handover_id):
    user = get_current_user()
    if not user or (user['role'] != 'commander' and user['role'] != 'admin'):
        return redirect(url_for('login'))
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('DELETE FROM handover_table WHERE id=?', (handover_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('handover_table'))

@app.route('/violations_table', methods=['GET', 'POST'])
def violations_table():
    user = get_current_user()
    if not user or (user['role'] != 'commander' and user['role'] != 'admin'):
        return redirect(url_for('login'))
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    if request.method == 'POST':
        military_name = request.form.get('military_name', '').strip()
        violation_type = request.form.get('violation_type', '').strip()
        day_name = request.form.get('day_name', '').strip()
        date = request.form.get('date', '').strip()
        notes = request.form.get('notes', '').strip()
        if military_name and violation_type and day_name and date:
            c.execute('INSERT INTO violations_table (military_name, violation_type, day_name, date, notes) VALUES (?, ?, ?, ?, ?)',
                      (military_name, violation_type, day_name, date, notes))
            conn.commit()
    c.execute('SELECT id, military_name, violation_type, day_name, date, notes FROM violations_table ORDER BY id DESC')
    violations = c.fetchall()
    conn.close()
    return render_template('violations_table.html', user=user, violations=violations)

@app.route('/delete_violation/<int:violation_id>')
def delete_violation(violation_id):
    user = get_current_user()
    if not user or (user['role'] != 'commander' and user['role'] != 'admin'):
        return redirect(url_for('login'))
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('DELETE FROM violations_table WHERE id=?', (violation_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('violations_table'))

@app.route('/violation_report_print/<int:violation_id>')
def violation_report_print(violation_id):
    user = get_current_user()
    if not user or (user['role'] != 'commander' and user['role'] != 'admin'):
        return redirect(url_for('login'))
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT id, military_name, violation_type, day_name, date, notes FROM violations_table WHERE id=?', (violation_id,))
    violation = c.fetchone()
    conn.close()
    if not violation:
        return 'المخالفة غير موجودة', 404
    signature = get_setting('signature')
    visa = get_setting('visa')
    commander_name = get_setting('commander_name')
    commander_rank = get_setting('commander_rank')
    logo = get_setting('logo')
    ministry_name = get_setting('ministry_name')
    header_text = get_setting('header_text')
    datetime_now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return render_template('violation_report_print.html', user=user, violation=violation, signature=signature, visa=visa, commander_name=commander_name, commander_rank=commander_rank, logo=logo, ministry_name=ministry_name, header_text=header_text, datetime_now=datetime_now)

@app.route('/appreciation_letters', methods=['GET', 'POST'])
def appreciation_letters():
    user = get_current_user()
    if not user or (user['role'] != 'commander' and user['role'] != 'admin'):
        return redirect(url_for('login'))
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    if request.method == 'POST':
        recipient_name = request.form.get('recipient_name', '').strip()
        reason = request.form.get('reason', '').strip()
        date = request.form.get('date', '').strip()
        notes = request.form.get('notes', '').strip()
        if recipient_name and reason and date:
            c.execute('INSERT INTO appreciation_letters (recipient_name, reason, date, notes) VALUES (?, ?, ?, ?)',
                      (recipient_name, reason, date, notes))
            conn.commit()
    c.execute('SELECT id, recipient_name, reason, date, notes FROM appreciation_letters ORDER BY id DESC')
    letters = c.fetchall()
    conn.close()
    return render_template('appreciation_letters.html', user=user, letters=letters)

@app.route('/delete_appreciation_letter/<int:letter_id>')
def delete_appreciation_letter(letter_id):
    user = get_current_user()
    if not user or (user['role'] != 'commander' and user['role'] != 'admin'):
        return redirect(url_for('login'))
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('DELETE FROM appreciation_letters WHERE id=?', (letter_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('appreciation_letters'))

@app.route('/permission_requests', methods=['GET', 'POST'])
def permission_requests():
    user = get_current_user()
    if not user or (user['role'] != 'commander' and user['role'] != 'admin'):
        return redirect(url_for('login'))
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    if request.method == 'POST':
        requester_name = request.form.get('requester_name', '').strip()
        permission_type = request.form.get('permission_type', '').strip()
        date = request.form.get('date', '').strip()
        time_ = request.form.get('time', '').strip()
        reason = request.form.get('reason', '').strip()
        notes = request.form.get('notes', '').strip()
        if requester_name and permission_type and date and time_:
            c.execute('INSERT INTO permission_requests (requester_name, permission_type, date, time, reason, notes) VALUES (?, ?, ?, ?, ?, ?)',
                      (requester_name, permission_type, date, time_, reason, notes))
            conn.commit()
    c.execute('SELECT id, requester_name, permission_type, date, time, reason, notes FROM permission_requests ORDER BY id DESC')
    requests = c.fetchall()
    conn.close()
    return render_template('permission_requests.html', user=user, requests=requests)

@app.route('/delete_permission_request/<int:request_id>')
def delete_permission_request(request_id):
    user = get_current_user()
    if not user or (user['role'] != 'commander' and user['role'] != 'admin'):
        return redirect(url_for('login'))
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('DELETE FROM permission_requests WHERE id=?', (request_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('permission_requests'))

@app.route('/permission_request_view/<int:request_id>')
def permission_request_view(request_id):
    user = get_current_user()
    if not user or (user['role'] != 'commander' and user['role'] != 'admin'):
        return redirect(url_for('login'))
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT id, requester_name, permission_type, date, time, reason, notes FROM permission_requests WHERE id=?', (request_id,))
    req = c.fetchone()
    conn.close()
    if not req:
        return 'الطلب غير موجود', 404
    signature = get_setting('signature')
    visa = get_setting('visa')
    commander_name = get_setting('commander_name')
    commander_rank = get_setting('commander_rank')
    logo = get_setting('logo')
    ministry_name = get_setting('ministry_name')
    header_text = get_setting('header_text')
    datetime_now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return render_template('permission_request_view.html', user=user, req=req, signature=signature, visa=visa, commander_name=commander_name, commander_rank=commander_rank, logo=logo, ministry_name=ministry_name, header_text=header_text, datetime_now=datetime_now)

@app.route('/appreciation_letter_print/<int:letter_id>')
def appreciation_letter_print(letter_id):
    user = get_current_user()
    if not user or (user['role'] != 'commander' and user['role'] != 'admin'):
        return redirect(url_for('login'))
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT id, recipient_name, reason, date, notes FROM appreciation_letters WHERE id=?', (letter_id,))
    letter = c.fetchone()
    conn.close()
    if not letter:
        return 'الخطاب غير موجود', 404
    signature = get_setting('signature')
    visa = get_setting('visa')
    commander_name = get_setting('commander_name')
    commander_rank = get_setting('commander_rank')
    logo = get_setting('logo')
    ministry_name = get_setting('ministry_name')
    header_text = get_setting('header_text')
    from datetime import datetime
    datetime_now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return render_template('appreciation_letter_print.html', user=user, letter=letter, signature=signature, visa=visa, commander_name=commander_name, commander_rank=commander_rank, logo=logo, ministry_name=ministry_name, header_text=header_text, datetime_now=datetime_now)

@app.route('/appreciation_letter_view/<int:letter_id>')
def appreciation_letter_view(letter_id):
    user = get_current_user()
    if not user or (user['role'] != 'commander' and user['role'] != 'admin'):
        return redirect(url_for('login'))
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT id, recipient_name, reason, date, notes FROM appreciation_letters WHERE id=?', (letter_id,))
    letter = c.fetchone()
    conn.close()
    if not letter:
        return 'الخطاب غير موجود', 404
    signature = get_setting('signature')
    visa = get_setting('visa')
    commander_name = get_setting('commander_name')
    commander_rank = get_setting('commander_rank')
    logo = get_setting('logo')
    ministry_name = get_setting('ministry_name')
    header_text = get_setting('header_text')
    from datetime import datetime
    datetime_now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return render_template('appreciation_letter_view.html', user=user, letter=letter, signature=signature, visa=visa, commander_name=commander_name, commander_rank=commander_rank, logo=logo, ministry_name=ministry_name, header_text=header_text, datetime_now=datetime_now)

@app.route('/permission_request_print/<int:request_id>')
def permission_request_print(request_id):
    user = get_current_user()
    if not user or (user['role'] != 'commander' and user['role'] != 'admin'):
        return redirect(url_for('login'))
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT id, requester_name, permission_type, date, time, reason, notes FROM permission_requests WHERE id=?', (request_id,))
    req = c.fetchone()
    conn.close()
    if not req:
        return 'الطلب غير موجود', 404
    signature = get_setting('signature')
    visa = get_setting('visa')
    commander_name = get_setting('commander_name')
    commander_rank = get_setting('commander_rank')
    logo = get_setting('logo')
    ministry_name = get_setting('ministry_name')
    header_text = get_setting('header_text')
    from datetime import datetime
    datetime_now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return render_template('permission_request_print.html', user=user, req=req, signature=signature, visa=visa, commander_name=commander_name, commander_rank=commander_rank, logo=logo, ministry_name=ministry_name, header_text=header_text, datetime_now=datetime_now)

@app.route('/delete_all_handovers')
def delete_all_handovers():
    user = get_current_user()
    if not user or (user['role'] != 'commander' and user['role'] != 'admin'):
        return redirect(url_for('login'))
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('DELETE FROM handover_table')
    conn.commit()
    conn.close()
    return redirect(url_for('handover_table'))

@app.route('/leaves_table', methods=['GET', 'POST'])
def leaves_table():
    user = get_current_user()
    if not user or (user['role'] != 'commander' and user['role'] != 'admin'):
        return redirect(url_for('login'))
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        rank = request.form.get('rank', '').strip()
        leave_type = request.form.get('leave_type', '').strip()
        start_date = request.form.get('start_date', '').strip()
        end_date = request.form.get('end_date', '').strip()
        notes = request.form.get('notes', '').strip()
        if name and rank and leave_type and start_date and end_date:
            c.execute('INSERT INTO leaves_table (name, rank, leave_type, start_date, end_date, notes) VALUES (?, ?, ?, ?, ?, ?)',
                      (name, rank, leave_type, start_date, end_date, notes))
            conn.commit()
    c.execute('SELECT id, name, rank, leave_type, start_date, end_date, notes FROM leaves_table ORDER BY id DESC')
    leaves = c.fetchall()
    conn.close()
    return render_template('leaves_table.html', user=user, leaves=leaves)

@app.route('/delete_leave/<int:leave_id>')
def delete_leave(leave_id):
    user = get_current_user()
    if not user or (user['role'] != 'commander' and user['role'] != 'admin'):
        return redirect(url_for('login'))
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('DELETE FROM leaves_table WHERE id=?', (leave_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('leaves_table'))

@app.route('/leave_view/<int:leave_id>')
def leave_view(leave_id):
    user = get_current_user()
    if not user or (user['role'] != 'commander' and user['role'] != 'admin'):
        return redirect(url_for('login'))
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT id, name, rank, leave_type, start_date, end_date, notes FROM leaves_table WHERE id=?', (leave_id,))
    leave = c.fetchone()
    conn.close()
    if not leave:
        return 'الإجازة غير موجودة', 404
    signature = get_setting('signature')
    visa = get_setting('visa')
    commander_name = get_setting('commander_name')
    commander_rank = get_setting('commander_rank')
    logo = get_setting('logo')
    ministry_name = get_setting('ministry_name')
    header_text = get_setting('header_text')
    from datetime import datetime
    datetime_now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return render_template('leave_view.html', user=user, leave=leave, signature=signature, visa=visa, commander_name=commander_name, commander_rank=commander_rank, logo=logo, ministry_name=ministry_name, header_text=header_text, datetime_now=datetime_now)

@app.route('/leave_print/<int:leave_id>')
def leave_print(leave_id):
    user = get_current_user()
    if not user or (user['role'] != 'commander' and user['role'] != 'admin'):
        return redirect(url_for('login'))
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT id, name, rank, leave_type, start_date, end_date, notes FROM leaves_table WHERE id=?', (leave_id,))
    leave = c.fetchone()
    conn.close()
    if not leave:
        return 'الإجازة غير موجودة', 404
    signature = get_setting('signature')
    visa = get_setting('visa')
    commander_name = get_setting('commander_name')
    commander_rank = get_setting('commander_rank')
    logo = get_setting('logo')
    ministry_name = get_setting('ministry_name')
    header_text = get_setting('header_text')
    from datetime import datetime
    datetime_now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return render_template('leave_print.html', user=user, leave=leave, signature=signature, visa=visa, commander_name=commander_name, commander_rank=commander_rank, logo=logo, ministry_name=ministry_name, header_text=header_text, datetime_now=datetime_now)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=11000, debug=True) 