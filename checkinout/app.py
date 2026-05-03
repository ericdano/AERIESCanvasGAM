import os
import smtplib
from email.mime.text import MIMEText
from flask import Flask, request, jsonify
import pymssql
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler

load_dotenv()

app = Flask(__name__, static_folder='public', static_url_path='')

# --- DATABASE HELPER ---
def get_db_connection():
    return pymssql.connect(
        server=os.getenv('DB_SERVER'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME'),
        as_dict=True
    )

# Helper to get the current user's school site
def get_user_site(cursor, email):
    cursor.execute("SELECT SchoolSite FROM UserSettings WHERE UserEmail = %s", (email,))
    row = cursor.fetchone()
    return row['SchoolSite'] if row and row['SchoolSite'] else None

# --- MIDDLEWARE ---
@app.before_request
def get_staff_user():
    request.staff_user = request.headers.get('x-forwarded-email', 'dev_staff@school.edu')

# --- ROUTES ---
@app.route('/')
def index():
    return app.send_static_file('index.html')

@app.route('/api/search-students', methods=['GET'])
def search_students():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify([])
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                search_term = f"%{query}%"
                cursor.execute("""
                    SELECT TOP 10 ID, FN, LN, SEM 
                    FROM STU 
                    WHERE DEL = 0 AND (
                        CAST(ID AS VARCHAR) LIKE %s OR 
                        FN LIKE %s OR 
                        LN LIKE %s OR 
                        ISNULL(FN, '') + ' ' + ISNULL(LN, '') LIKE %s
                    )
                """, (search_term, search_term, search_term, search_term))
                return jsonify(cursor.fetchall())
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/checkout', methods=['POST'])
def checkout():
    data = request.json
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # 1. Grab the site selected on the checkout screen
                checkout_site = data.get('site')
                
                # 2. If it's blank, fallback to their default settings site
                if not checkout_site:
                    checkout_site = get_user_site(cursor, request.staff_user)
                
                # 3. If STILL blank, block the checkout
                if not checkout_site:
                    return jsonify({'error': 'Please select a School Site for this checkout.'}), 400

                cursor.execute("""
                    INSERT INTO ItemTransactions 
                    (StudentID, StudentFirstName, StudentLastName, ItemBarcode, Reason, Status, CheckoutStaffUser, SchoolSite) 
                    VALUES (%s, %s, %s, %s, %s, 'CheckedOut', %s, %s)
                """, (data['studentId'], data['firstName'], data['lastName'], data['barcode'], data.get('reason', ''), request.staff_user, checkout_site))
            conn.commit()
        return jsonify({'success': True, 'message': 'Item checked out successfully.'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/checkin', methods=['POST'])
def checkin():
    barcode = request.json.get('barcode')
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # We do not filter check-in by site, just in case a device is returned to the wrong campus!
                cursor.execute("""
                    UPDATE ItemTransactions 
                    SET Status = 'CheckedIn', CheckinDateTime = GETDATE(), CheckinStaffUser = %s
                    OUTPUT inserted.StudentFirstName, inserted.StudentLastName
                    WHERE ItemBarcode = %s AND Status = 'CheckedOut'
                """, (request.staff_user, barcode))
                student = cursor.fetchone()
            conn.commit()
            if student:
                return jsonify({'success': True, 'student': student})
            return jsonify({'error': 'Item not found or already checked in.'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/active-checkouts', methods=['GET'])
def active_checkouts():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                site = get_user_site(cursor, request.staff_user)
                if not site:
                    return jsonify([])

                cursor.execute("""
                    SELECT StudentID, StudentFirstName, StudentLastName, ItemBarcode, CheckoutDateTime, CheckoutStaffUser
                    FROM ItemTransactions WHERE Status = 'CheckedOut' AND SchoolSite = %s ORDER BY CheckoutDateTime DESC
                """, (site,))
                items = cursor.fetchall()
                for item in items:
                    if item['CheckoutDateTime']:
                        item['CheckoutDateTime'] = item['CheckoutDateTime'].strftime('%Y-%m-%d %I:%M %p')
                return jsonify(items)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
@app.route('/api/dashboard', methods=['GET'])
def dashboard_stats():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                site = get_user_site(cursor, request.staff_user)
                if not site:
                    return jsonify({'requiresSetup': True})

                # 1. Items checked out TODAY
                cursor.execute("""
                    SELECT COUNT(*) as OutToday FROM ItemTransactions 
                    WHERE Status = 'CheckedOut' AND SchoolSite = %s 
                    AND CAST(CheckoutDateTime AS DATE) = CAST(GETDATE() AS DATE)
                """, (site,))
                out_today = cursor.fetchone()['OutToday']

                # 2. Total items currently checked out
                cursor.execute("""
                    SELECT COUNT(*) as TotalOut FROM ItemTransactions 
                    WHERE Status = 'CheckedOut' AND SchoolSite = %s
                """, (site,))
                total_out = cursor.fetchone()['TotalOut']

                # 3. Total overdue items
                cursor.execute("""
                    SELECT COUNT(*) as OverdueCount FROM ItemTransactions 
                    WHERE Status = 'CheckedOut' AND SchoolSite = %s 
                    AND CAST(CheckoutDateTime AS DATE) < CAST(GETDATE() AS DATE)
                """, (site,))
                overdue_count = cursor.fetchone()['OverdueCount']

                # 4. Top 5 oldest overdue items
                cursor.execute("""
                    SELECT TOP 5 StudentFirstName, StudentLastName, ItemBarcode, CheckoutDateTime 
                    FROM ItemTransactions 
                    WHERE Status = 'CheckedOut' AND SchoolSite = %s 
                    AND CAST(CheckoutDateTime AS DATE) < CAST(GETDATE() AS DATE)
                    ORDER BY CheckoutDateTime ASC
                """, (site,))
                top_overdue = cursor.fetchall()
                
                # Format the dates
                for item in top_overdue:
                    if item['CheckoutDateTime']:
                        item['CheckoutDateTime'] = item['CheckoutDateTime'].strftime('%Y-%m-%d')

                return jsonify({
                    'site': site,
                    'outToday': out_today,
                    'totalOut': total_out,
                    'overdueCount': overdue_count,
                    'topOverdue': top_overdue
                })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
@app.route('/api/history', methods=['GET'])
def history():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                site = get_user_site(cursor, request.staff_user)
                if not site:
                    return jsonify([])

                cursor.execute("""
                    SELECT StudentID, StudentFirstName, StudentLastName, ItemBarcode, Status,
                           CheckoutDateTime, CheckoutStaffUser, CheckinDateTime, CheckinStaffUser
                    FROM ItemTransactions WHERE SchoolSite = %s ORDER BY CheckoutDateTime DESC
                """, (site,))
                items = cursor.fetchall()
                for item in items:
                    if item['CheckoutDateTime']:
                        item['CheckoutDateTime'] = item['CheckoutDateTime'].strftime('%Y-%m-%d %I:%M %p')
                    if item['CheckinDateTime']:
                        item['CheckinDateTime'] = item['CheckinDateTime'].strftime('%Y-%m-%d %I:%M %p')
                    else:
                        item['CheckinDateTime'] = 'Pending'
                    if not item['CheckinStaffUser']:
                        item['CheckinStaffUser'] = 'N/A'
                return jsonify(items)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/settings', methods=['GET', 'POST'])
def manage_settings():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                if request.method == 'POST':
                    data = request.json
                    cursor.execute("SELECT UserEmail FROM UserSettings WHERE UserEmail = %s", (request.staff_user,))
                    if cursor.fetchone():
                        cursor.execute("""
                            UPDATE UserSettings 
                            SET SchoolSite = %s, EmailTemplate = %s, ReplyToEmail = %s 
                            WHERE UserEmail = %s
                        """, (data['site'], data['template'], data['replyTo'], request.staff_user))
                    else:
                        cursor.execute("""
                            INSERT INTO UserSettings (UserEmail, SchoolSite, EmailTemplate, ReplyToEmail) 
                            VALUES (%s, %s, %s, %s)
                        """, (request.staff_user, data['site'], data['template'], data['replyTo']))
                    conn.commit()
                    return jsonify({'success': True})
                else:
                    cursor.execute("SELECT SchoolSite, EmailTemplate, ReplyToEmail FROM UserSettings WHERE UserEmail = %s", (request.staff_user,))
                    settings = cursor.fetchone()
                    return jsonify(settings if settings else {})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/overdue', methods=['GET'])
def overdue_items():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                site = get_user_site(cursor, request.staff_user)
                if not site:
                    return jsonify([])

                cursor.execute("""
                    SELECT t.TransactionID, t.StudentID, t.StudentFirstName, t.StudentLastName, 
                           t.ItemBarcode, t.CheckoutDateTime, s.SEM as StudentEmail
                    FROM ItemTransactions t
                    LEFT JOIN STU s ON t.StudentID = s.ID
                    WHERE t.Status = 'CheckedOut' AND t.SchoolSite = %s AND CAST(t.CheckoutDateTime AS DATE) < CAST(GETDATE() AS DATE)
                    ORDER BY t.CheckoutDateTime ASC
                """, (site,))
                items = cursor.fetchall()
                for item in items:
                    if item['CheckoutDateTime']:
                        item['CheckoutDateTime'] = item['CheckoutDateTime'].strftime('%Y-%m-%d %I:%M %p')
                return jsonify(items)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/send-emails', methods=['POST'])
def send_manual_emails():
    transaction_ids = request.json.get('transactionIds', [])
    if not transaction_ids:
        return jsonify({'error': 'No items selected'}), 400

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT EmailTemplate, ReplyToEmail FROM UserSettings WHERE UserEmail = %s", (request.staff_user,))
                settings = cursor.fetchone() or {}
                
                template = settings.get('EmailTemplate') or 'Hi [FirstName],\n\nYou checked out an item (Barcode: [Barcode]) on [Date]. Please return it to the office as soon as possible.\n\nThank you!'
                reply_to = settings.get('ReplyToEmail') or ''

                placeholders = ','.join(['%s'] * len(transaction_ids))
                query = f"""
                    SELECT t.StudentFirstName, t.StudentLastName, t.ItemBarcode, t.CheckoutDateTime, s.SEM as StudentEmail
                    FROM ItemTransactions t
                    LEFT JOIN STU s ON t.StudentID = s.ID
                    WHERE t.TransactionID IN ({placeholders})
                """
                cursor.execute(query, tuple(transaction_ids))
                items_to_email = cursor.fetchall()

        send_emails_via_smtp(items_to_email, template, reply_to)
        return jsonify({'success': True, 'count': len(items_to_email)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def send_emails_via_smtp(items, template, reply_to):
    smtp_server = os.getenv('SMTP_SERVER')
    smtp_port = int(os.getenv('SMTP_PORT', 25))
    smtp_user = os.getenv('SMTP_USER')
    smtp_pass = os.getenv('SMTP_PASSWORD')

    # Since we aren't authenticating with a user, we need a fallback "From" address
    from_address = smtp_user if smtp_user else "noreply@auhsdschools.org"

    with smtplib.SMTP(smtp_server, smtp_port) as server:
        # Only attempt encryption and login if a user/pass is actually provided
        if smtp_user and smtp_pass:
            server.starttls()
            server.login(smtp_user, smtp_pass)

        for item in items:
            if not item['StudentEmail']: continue 
            body = template.replace('[FirstName]', item['StudentFirstName'] or '')
            body = body.replace('[LastName]', item['StudentLastName'] or '')
            body = body.replace('[Barcode]', item['ItemBarcode'] or '')
            date_str = item['CheckoutDateTime'].strftime('%Y-%m-%d') if hasattr(item['CheckoutDateTime'], 'strftime') else str(item['CheckoutDateTime'])
            body = body.replace('[Date]', date_str)

            msg = MIMEText(body)
            msg['Subject'] = "Overdue Device Notice"
            msg['From'] = from_address
            msg['To'] = item['StudentEmail']
            if reply_to: msg.add_header('Reply-To', reply_to)
            server.send_message(msg)

def send_auto_overdue_emails():
    print("Running auto overdue email check...")
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT t.TransactionID, t.StudentFirstName, t.StudentLastName, t.ItemBarcode, 
                           t.CheckoutDateTime, t.CheckoutStaffUser, s.SEM as StudentEmail
                    FROM ItemTransactions t
                    LEFT JOIN STU s ON t.StudentID = s.ID
                    WHERE t.Status = 'CheckedOut' AND CAST(t.CheckoutDateTime AS DATE) < CAST(GETDATE() AS DATE)
                """)
                items = cursor.fetchall()
                if not items: return

                items_by_staff = {}
                for item in items:
                    staff = item['CheckoutStaffUser']
                    if staff not in items_by_staff: items_by_staff[staff] = []
                    items_by_staff[staff].append(item)

                for staff, staff_items in items_by_staff.items():
                    cursor.execute("SELECT EmailTemplate, ReplyToEmail FROM UserSettings WHERE UserEmail = %s", (staff,))
                    settings = cursor.fetchone() or {}
                    template = settings.get('EmailTemplate') or 'Hi [FirstName],\n\nYou checked out an item (Barcode: [Barcode]) on [Date]. Please return it to the office as soon as possible.\n\nThank you!'
                    reply_to = settings.get('ReplyToEmail') or ''
                    send_emails_via_smtp(staff_items, template, reply_to)
                    print(f"Sent {len(staff_items)} auto overdue notices for {staff}.")
    except Exception as e:
        print(f"Error in auto email job: {e}")

scheduler = BackgroundScheduler()
scheduler.add_job(func=send_auto_overdue_emails, trigger="cron", hour=15, minute=0)
scheduler.start()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3005)